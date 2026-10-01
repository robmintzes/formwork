"""Regression tests for the 2026-10-01 adversarial review findings.

Each test reproduces a confirmed bypass from the review and asserts it is
now refused. See docs/reviews/security-review-2026-10-01.md.
"""

from __future__ import annotations

import http.client
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from toolkit_engine.checks import references_remote  # noqa: E402
from toolkit_engine.diagnostics import Diagnostics  # noqa: E402
from toolkit_engine.paths import UnsafePathError, check_relative_path, check_workspace_root  # noqa: E402
from toolkit_engine.profile import _check_svg, load_profile  # noqa: E402
from toolkit_engine.workspace import EngineError, init_workspace, render_workspace  # noqa: E402
from toolkit_wizard.server import WizardHandler, WizardServer  # noqa: E402

QUILLMOOR = REPO / "profiles" / "quillmoor"


def _svg_codes(svg: bytes) -> list[str]:
    diags = Diagnostics()
    _check_svg("assets/x.svg", svg, diags)
    return diags.codes()


class WorkspaceCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="hardening ")
        self.base = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def workspace(self) -> Path:
        root = self.base / "Quillmoor DT"
        init_workspace(QUILLMOOR, root)
        self.assertEqual(render_workspace(root)["summary"]["outcome"], "pass")
        return root

    def tamper_manifest(self, root: Path, rel: str, adapter: str = "common", target: Path | None = None) -> None:
        import hashlib

        manifest_path = root / ".toolkit" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source = target or (root / Path(*rel.split("/")))
        manifest["files"][rel] = {
            "adapter": adapter,
            "ownership": "managed",
            "sha256": hashlib.sha256(source.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


class ManifestTamperingTests(WorkspaceCase):
    def test_case_variant_input_paths_cannot_be_retired(self) -> None:
        root = self.workspace()
        for rel, real in (("FIRM/firm.json", root / "firm" / "firm.json"), (".TOOLKIT/workspace.json", root / ".toolkit" / "workspace.json")):
            with self.subTest(rel=rel):
                self.tamper_manifest(root, rel, target=real)
                with self.assertRaises(EngineError) as caught:
                    render_workspace(root)
                self.assertEqual(caught.exception.code, "manifest.invalid")
                self.assertTrue(real.is_file())
                render_workspace  # keep linters quiet about the loop
                manifest_path = root / ".toolkit" / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["files"].pop(rel)
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def test_unknown_adapter_entries_are_refused(self) -> None:
        root = self.workspace()
        firm_tool = root / "notes.md"
        firm_tool.write_text("firm notes\n", encoding="utf-8")
        self.tamper_manifest(root, "notes.md", adapter="evil-adapter")
        with self.assertRaises(EngineError):
            render_workspace(root)
        self.assertTrue(firm_tool.is_file())


class PathRuleTests(unittest.TestCase):
    def test_extra_windows_device_names(self) -> None:
        for name in ("COM¹.json", "LPT²", "CONIN$.json", "CONOUT$.json", "CON .json", "NUL .txt", "CLOCK$.txt", "docs/aux.md"):
            with self.subTest(name=name):
                self.assertIn("reserved", check_relative_path(name))
        self.assertEqual(check_relative_path("docs/console.md"), "")

    @unittest.skipUnless(os.name == "nt", "system folders are a Windows concept here")
    def test_system_folders_are_not_workspaces(self) -> None:
        windows = Path(os.environ["SystemRoot"]) / "Temp" / "toolkit-ws-test"
        with self.assertRaises(UnsafePathError):
            check_workspace_root(windows, REPO)

    @unittest.skipUnless(os.name == "nt", "junctions are a Windows feature")
    def test_firm_folder_junction_is_refused(self) -> None:
        import _winapi

        with tempfile.TemporaryDirectory(prefix="firm link ") as tmp:
            real = Path(tmp) / "real firm"
            shutil.copytree(QUILLMOOR, real)
            linked = Path(tmp) / "linked firm"
            _winapi.CreateJunction(str(real), str(linked))
            try:
                diags = Diagnostics()
                self.assertIsNone(load_profile(linked, diags))
                self.assertIn("input.reparse-point", diags.codes())
            finally:
                os.rmdir(linked)


class SvgTests(unittest.TestCase):
    BASE = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">{}</svg>'

    def wrap(self, inner: str) -> bytes:
        return self.BASE.replace(b"{}", inner.encode("utf-8"))

    def test_review_bypasses_are_refused(self) -> None:
        cases = {
            "style import": '<style>@import url(http://e.x/a.css);</style><path d="M0 0"/>',
            "fill url": '<path fill="url(http://e.x/p.svg#g)" d="M0 0"/>',
            "set href": '<a href="#x"><set attributeName="href" to="javascript:alert(1)"/></a>',
            "animate href": '<animate attributeName="href" values="http://e.x"/>',
            "javascript attr": '<path d="M0 0" filter="javascript:alert(1)"/>',
            "use external": '<use href="https://e.x/sprite.svg#i"/>',
        }
        for label, inner in cases.items():
            with self.subTest(label=label):
                codes = _svg_codes(self.wrap(inner))
                self.assertTrue({"brand.svg-unsafe", "brand.svg-external"} & set(codes), codes)

    def test_utf16_doctype_is_refused(self) -> None:
        doc = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE svg [<!ENTITY x "y">]><svg xmlns="http://www.w3.org/2000/svg"/>'
        self.assertIn("brand.svg-unsafe", _svg_codes(doc.encode("utf-16")))

    def test_ordinary_marks_still_pass(self) -> None:
        good = self.wrap('<defs><linearGradient id="g"/></defs><path fill="url(#g)" d="M0 0"/><use href="#g"/>')
        self.assertEqual(_svg_codes(good), [])


class RemoteReferenceTests(unittest.TestCase):
    def test_markup_bypasses(self) -> None:
        for text in (
            '<img srcset="a.png 1x, https://e.x/b.png 2x">',
            'a{b:image-set("https://e.x/a.png" 1x)}',
            '<img src="https:evil.com">',
            '<img src="/\\evil.com">',
            '<base href="/">',
            '<object data="http://e.x">',
            '<video poster="//e.x/p.png">',
            '<Image Source="\\\\host\\share\\a.png"/>',
            '<ImageBrush ImageSource="https://e.x/a.png"/>',
            '<BitmapImage UriSource="http://e.x/a.png"/>',
            '<link rel="preload" href="https://e.x/f.woff2">',
        ):
            with self.subTest(text=text):
                self.assertTrue(references_remote(text, "markup"))

    def test_script_bypasses(self) -> None:
        for text in ('new WebSocket("wss://e.x")', 'navigator.sendBeacon("https://e.x")', 'fetch(new URL("https://e.x"))', 'fetch("https:evil")'):
            with self.subTest(text=text):
                self.assertTrue(references_remote(text, "script"))

    def test_legitimate_content_is_not_flagged(self) -> None:
        for text in (
            '<a href="https://support.example/x">https://support.example/x</a>',
            '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>',
            'url("../fonts/a.ttf")',
            "url(#grad)",
            '<ResourceDictionary xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"/>',
        ):
            with self.subTest(text=text):
                self.assertFalse(references_remote(text, "markup"))
        for text in ('fetch("http://127.0.0.1:" + port)', "if (p.includes('//')) {}"):
            with self.subTest(text=text):
                self.assertFalse(references_remote(text, "script"))


class WizardHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = WizardServer(0, token="api-token-abc")
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.host = "127.0.0.1:{}".format(self.server.port)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=20)
        final = {"Host": self.host, "Content-Type": "application/json"}
        final.update(headers or {})
        connection.request(method, path, body=body, headers=final)
        response = connection.getresponse()
        payload = response.read()
        connection.close()
        return response, payload

    def test_preview_cookie_is_not_the_api_token(self) -> None:
        response, _ = self.request("POST", "/api/session", b"{}", {"X-Toolkit-Token": "api-token-abc"})
        cookie_value = response.getheader("Set-Cookie").split(";")[0].split("=", 1)[1]
        self.assertNotEqual(cookie_value, "api-token-abc")
        response, _ = self.request("GET", "/api/starters", headers={"X-Toolkit-Token": cookie_value})
        self.assertEqual(response.status, 403)

    def test_deeply_nested_json_is_a_clean_400(self) -> None:
        body = ("[" * 100000 + "]" * 100000).encode("ascii")
        response, payload = self.request("POST", "/api/start", body, {"X-Toolkit-Token": "api-token-abc"})
        self.assertEqual(response.status, 400)
        self.assertEqual(json.loads(payload)["error"]["code"], "request.json")

    def test_stalled_clients_time_out(self) -> None:
        self.assertGreater(WizardHandler.timeout or 0, 0)


@unittest.skipUnless(os.name == "nt", "8.3 short names are a Windows filesystem feature")
class WebAppShortNameTests(WorkspaceCase):
    def test_short_name_cannot_reach_a_dot_file(self) -> None:
        import ctypes

        node = shutil.which("node")
        if node is None:
            self.skipTest("node is not on PATH")
        root = self.workspace()
        app = root / "apps" / "quillmoor-web"
        secret = app / "public" / ".env-secret"
        secret.write_text("SECRET\n", encoding="utf-8")
        buffer = ctypes.create_unicode_buffer(1024)
        ctypes.windll.kernel32.GetShortPathNameW(str(secret), buffer, 1024)
        short = Path(buffer.value).name
        if not short or short.lower() == secret.name.lower():
            self.skipTest("8.3 short names are disabled on this volume")
        env = dict(os.environ, PORT="0", NODE_NO_WARNINGS="1")
        process = subprocess.Popen([node, "server.ts"], cwd=app, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        try:
            line = process.stdout.readline()
            match = re.search(r":(\d+)/", line)
            self.assertIsNotNone(match, line)
            port = int(match.group(1))
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            connection.request("GET", "/" + short)
            response = connection.getresponse()
            body = response.read()
            connection.close()
            self.assertEqual(response.status, 404, body)
            self.assertNotIn(b"SECRET", body)
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
            process.stdout.close()
            time.sleep(0.2)


if __name__ == "__main__":
    unittest.main()
