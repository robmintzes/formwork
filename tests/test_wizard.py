"""Wizard backend: draft operations and the loopback security boundary."""

from __future__ import annotations

import base64
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from toolkit_wizard.server import WizardServer  # noqa: E402
from toolkit_wizard.session import WizardError, WizardSession  # noqa: E402


class SessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="wizard ")
        self.base = Path(self._tmp.name)
        self.session = WizardSession()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def config(self) -> dict:
        return json.loads(self.session.state()["files"]["firm.json"]["text"])

    def put_config(self, data: dict) -> None:
        self.session.put_files({"firm.json": {"text": json.dumps(data, indent=2)}}, [])

    def test_starters_list_shipped_profiles(self) -> None:
        ids = {s["id"]: s for s in self.session.starters()}
        self.assertIn("bimxbert", ids)
        self.assertTrue(ids["quillmoor"]["fictional"])

    def test_edit_validate_and_preview(self) -> None:
        self.session.start_from_profile("quillmoor")
        data = self.config()
        data["identity"]["display_name"] = "Larkspur Works"
        self.put_config(data)
        report = self.session.validate()
        self.assertEqual(report["outcome"], "pass", report["diagnostics"])
        self.assertIn("Larkspur Works", self.session.preview["docs/guides/hello-button.html"].decode("utf-8"))

    def test_invalid_draft_reports_diagnostics_and_no_preview(self) -> None:
        self.session.start_from_profile("quillmoor")
        data = self.config()
        data["appearance"]["button"]["shape"] = "blob"
        self.put_config(data)
        report = self.session.validate()
        self.assertEqual(report["outcome"], "fail")
        self.assertIn("config.choice-invalid", [d["code"] for d in report["diagnostics"]])
        self.assertEqual(report["preview_files"], [])

    def test_unsafe_draft_paths_and_types_are_refused(self) -> None:
        self.session.start_from_profile("quillmoor")
        for path in ("../escape.json", "C:/abs.json", "assets/CON.png", "assets/run.exe", "a\\b.json"):
            with self.subTest(path=path):
                with self.assertRaises(WizardError):
                    self.session.put_files({path: {"text": "{}"}}, [])
        with self.assertRaises(WizardError):
            self.session.put_files({}, ["firm.json"])

    def test_logo_upload_round_trip(self) -> None:
        self.session.start_from_profile("quillmoor")
        png = self.session.files["assets/symbol-light.png"]
        self.session.put_files({"assets/symbol-light.png": {"base64": base64.b64encode(png).decode("ascii")}}, [])
        self.assertEqual(self.session.files["assets/symbol-light.png"], png)
        with self.assertRaises(WizardError):
            self.session.put_files({"assets/x.png": {"base64": "not base64!!"}}, [])

    def test_plan_then_apply_new_workspace_then_update(self) -> None:
        self.session.start_from_profile("quillmoor")
        target = str(self.base / "New Firm Workspace")
        plan = self.session.plan(target)
        self.assertFalse(plan["initialized"])
        self.assertFalse((self.base / "New Firm Workspace").exists())  # plan is read-only
        result = self.session.apply(target)
        self.assertEqual(result["outcome"], "pass", result["diagnostics"])
        self.assertTrue((self.base / "New Firm Workspace" / "docs" / "guides" / "hello-button.html").is_file())

        data = self.config()
        data["identity"]["display_name"] = "Quillmoor Renamed"
        self.put_config(data)
        plan = self.session.plan(target)
        self.assertTrue(plan["initialized"])
        actions = {(a["path"], a["action"]) for a in plan["actions"]}
        self.assertIn(("firm/firm.json", "update"), actions)
        self.assertIn(("docs/guides/hello-button.html", "update"), actions)
        self.assertNotIn("Renamed", (self.base / "New Firm Workspace" / "docs" / "guides" / "hello-button.html").read_text(encoding="utf-8"))
        self.session.apply(target)
        self.assertIn("Quillmoor Renamed", (self.base / "New Firm Workspace" / "docs" / "guides" / "hello-button.html").read_text(encoding="utf-8"))

    def test_apply_refuses_when_plan_has_conflicts_and_writes_nothing(self) -> None:
        self.session.start_from_profile("quillmoor")
        target = self.base / "Conflicted"
        self.session.apply(str(target))
        theme = target / "specimens" / "wpf" / "Theme.xaml"
        theme.write_text("<ResourceDictionary/>\n", encoding="utf-8")
        data = self.config()
        data["identity"]["display_name"] = "Should Not Land"
        self.put_config(data)
        firm_before = (target / "firm" / "firm.json").read_bytes()
        with self.assertRaises(WizardError) as caught:
            self.session.apply(str(target))
        self.assertEqual(caught.exception.code, "plan.blocked")
        self.assertEqual((target / "firm" / "firm.json").read_bytes(), firm_before)

    def test_unsafe_workspace_destinations(self) -> None:
        self.session.start_from_profile("quillmoor")
        for target in ("relative/path", str(REPO / "build" / "inside"), str(Path.home())):
            with self.subTest(target=target):
                with self.assertRaises(WizardError):
                    self.session.plan(target)
        busy = self.base / "Busy"
        busy.mkdir()
        (busy / "keep.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(WizardError) as caught:
            self.session.plan(str(busy))
        self.assertEqual(caught.exception.code, "workspace.not-empty")


class BoundaryTests(unittest.TestCase):
    """Real HTTP against a server on an ephemeral loopback port."""

    def setUp(self) -> None:
        self.server = WizardServer(0, token="test-token-123")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host = "127.0.0.1:{}".format(self.server.port)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def request(self, method: str, path: str, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=30)
        final = {"Host": self.host}
        if body is not None:
            final["Content-Type"] = "application/json"
        final.update(headers or {})
        data = json.dumps(body).encode("utf-8") if body is not None else None
        connection.request(method, path, body=data, headers=final)
        response = connection.getresponse()
        payload = response.read()
        connection.close()
        return response, payload

    def auth(self) -> dict:
        return {"X-Toolkit-Token": "test-token-123"}

    def test_api_requires_token(self) -> None:
        response, _ = self.request("GET", "/api/starters")
        self.assertEqual(response.status, 403)
        response, _ = self.request("GET", "/api/starters", headers={"X-Toolkit-Token": "wrong"})
        self.assertEqual(response.status, 403)
        response, payload = self.request("GET", "/api/starters", headers=self.auth())
        self.assertEqual(response.status, 200)
        self.assertIn("starters", json.loads(payload))

    def test_foreign_host_and_origin_are_rejected(self) -> None:
        response, _ = self.request("GET", "/api/starters", headers=dict(self.auth(), Host="attacker.example:80"))
        self.assertEqual(response.status, 421)
        response, _ = self.request("GET", "/", headers={"Host": "evil.test:{}".format(self.server.port)})
        self.assertEqual(response.status, 421)
        response, _ = self.request("POST", "/api/start", {"profile": "quillmoor"}, dict(self.auth(), Origin="https://evil.example"))
        self.assertEqual(response.status, 403)

    def test_static_allow_list_and_security_headers(self) -> None:
        response, _ = self.request("GET", "/")
        self.assertEqual(response.status, 200)
        self.assertIn("default-src 'none'", response.getheader("Content-Security-Policy"))
        self.assertEqual(response.getheader("X-Frame-Options"), "DENY")
        for path in ("/static/../server.py", "/static/..%2fserver.py", "/server.py", "/static/%2e%2e/session.py"):
            with self.subTest(path=path):
                response, _ = self.request("GET", path)
                self.assertEqual(response.status, 404)

    def test_body_rules(self) -> None:
        response, _ = self.request("POST", "/api/start", None, dict(self.auth(), **{"Content-Type": "text/plain", "Content-Length": "2"}))
        self.assertEqual(response.status, 400)
        connection = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=10)
        connection.putrequest("PUT", "/api/files")
        for key, value in dict(self.auth(), Host=self.host, **{"Content-Type": "application/json", "Content-Length": str(10**9)}).items():
            connection.putheader(key, value)
        connection.endheaders()
        response = connection.getresponse()
        self.assertEqual(response.status, 400)
        self.assertEqual(json.loads(response.read())["error"]["code"], "request.too-large")
        connection.close()

    def test_preview_needs_session_cookie(self) -> None:
        self.request("POST", "/api/start", {"profile": "quillmoor"}, self.auth())
        response, payload = self.request("POST", "/api/validate", {}, self.auth())
        self.assertEqual(json.loads(payload)["outcome"], "pass")
        response, _ = self.request("GET", "/preview/docs/guides/hello-button.html")
        self.assertEqual(response.status, 403)
        response, _ = self.request("POST", "/api/session", {}, self.auth())
        cookie = response.getheader("Set-Cookie")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        response, payload = self.request("GET", "/preview/docs/guides/hello-button.html", headers={"Cookie": cookie.split(";")[0]})
        self.assertEqual(response.status, 200)
        self.assertIn(b"Quillmoor", payload)
        self.assertIn("default-src 'none'", response.getheader("Content-Security-Policy"))
        response, _ = self.request("GET", "/preview/../firm.json", headers={"Cookie": cookie.split(";")[0]})
        self.assertEqual(response.status, 404)


if __name__ == "__main__":
    unittest.main()
