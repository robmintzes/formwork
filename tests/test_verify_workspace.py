"""Tests for live-host evidence recording of generated workspaces."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from formwork_cli.verify_workspace import (  # noqa: E402
    MANUAL_TEMPLATE,
    render_markdown,
    run_workspace_verification,
)
from formwork_engine.workspace import init_workspace, render_workspace  # noqa: E402


class FakePyRevit:
    def __init__(self, registered: list[str], version: str = "pyrevit v6.5.5.26237+2044") -> None:
        self.registered = registered
        self.version = version
        self.calls: list[list[str]] = []

    def __call__(self, command):
        self.calls.append(list(command))
        if command[1:] == ["--version"]:
            return subprocess.CompletedProcess(command, 0, self.version + "\nYou have the latest version.\n", "")
        if command[1:] == ["extensions", "paths"]:
            return subprocess.CompletedProcess(command, 0, "==> Extension Search Paths\n" + "\n".join(self.registered) + "\n", "")
        raise AssertionError("unexpected command {}".format(command))


class WorkspaceVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="live check ")
        self.base = Path(self._tmp.name)
        self.workspace = self.base / "BIMxBert Live"
        init_workspace(REPO / "profiles" / "bimxbert", self.workspace)
        render_workspace(self.workspace)
        self.checklist = self.base / "manual-checks.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def fill(self, status: str = "pass", mutate=None) -> None:
        data = json.loads(MANUAL_TEMPLATE.read_text(encoding="utf-8"))
        for item in data["checks"]:
            if item["required"]:
                item["status"] = status
        if mutate:
            mutate(data)
        self.checklist.write_text(json.dumps(data), encoding="utf-8")

    def run_check(self, registered=True, revit="2026"):
        fake = FakePyRevit([str(self.workspace / "extensions")] if registered else [])
        return run_workspace_verification(
            self.workspace,
            manual_checks_path=self.checklist,
            revit_version=revit,
            timestamp="2026-10-01T12:00:00Z",
            run_command=fake,
            which=lambda name: "C:/pyRevit/bin/pyrevit.exe",
        ), fake

    def statuses(self, report) -> dict[str, str]:
        return {c["check_id"]: c["status"] for c in report["checks"]}

    def test_complete_passing_run(self) -> None:
        self.fill()
        report, fake = self.run_check()
        self.assertEqual(report["summary"]["outcome"], "pass", self.statuses(report))
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["metadata"]["pyrevit_version"], "6.5.5.26237")
        self.assertEqual(report["metadata"]["workspace_id"], "bimxbert-design-technology")
        # The verifier only reads pyRevit state; it never adds or forgets paths.
        self.assertTrue(all("add" not in call and "forget" not in call for call in fake.calls))

    def test_evidence_contains_no_local_paths(self) -> None:
        self.fill()
        report, _ = self.run_check()
        text = json.dumps(report) + render_markdown(report)
        self.assertNotIn(str(self.base), text)
        self.assertNotIn(self.base.as_posix(), text)
        self.assertNotIn("pyrevit.exe", text)

    def test_pending_checklist_is_incomplete(self) -> None:
        shutil.copy(MANUAL_TEMPLATE, self.checklist)
        report, _ = self.run_check()
        self.assertEqual(report["summary"]["outcome"], "incomplete")
        self.assertEqual(report["exit_code"], 2)

    def test_unregistered_workspace_fails(self) -> None:
        self.fill()
        report, _ = self.run_check(registered=False)
        self.assertEqual(self.statuses(report)["host.extension-path-registered"], "fail")
        self.assertEqual(report["exit_code"], 1)

    def test_removed_or_downgraded_checks_fail_coverage(self) -> None:
        def tamper(data):
            data["checks"] = [c for c in data["checks"] if c["id"] != "icon-dark-theme"]
            for c in data["checks"]:
                if c["id"] == "no-model-modification":
                    c["required"] = False
        self.fill(mutate=tamper)
        report, _ = self.run_check()
        coverage = next(c for c in report["checks"] if c["check_id"] == "manual.coverage")
        self.assertEqual(coverage["status"], "fail")
        self.assertEqual(coverage["details"], {"missing": ["icon-dark-theme"], "downgraded": ["no-model-modification"]})

    def test_stale_workspace_fails_before_any_host_claim(self) -> None:
        self.fill()
        tokens = self.workspace / "firm" / "tokens.tokens.json"
        data = json.loads(tokens.read_text(encoding="utf-8"))
        data["palette"]["brand"]["800"]["$value"] = {"colorSpace": "srgb", "components": [0.4, 0.1, 0.2], "hex": "#661A33"}
        tokens.write_text(json.dumps(data), encoding="utf-8")
        report, _ = self.run_check()
        self.assertEqual(self.statuses(report)["workspace.render-current"], "fail")
        self.assertEqual(report["summary"]["outcome"], "fail")

    def test_missing_revit_version_is_incomplete(self) -> None:
        self.fill()
        report, _ = self.run_check(revit=None)
        self.assertEqual(self.statuses(report)["host.revit-version"], "warn")
        self.assertEqual(report["summary"]["outcome"], "incomplete")


class WrapperScriptContractTests(unittest.TestCase):
    """Static checks for scripts/verify-generated-workspace.ps1 (no PowerShell execution)."""

    def setUp(self) -> None:
        self.text = (REPO / "scripts" / "verify-generated-workspace.ps1").read_text(encoding="utf-8")

    def test_ascii_for_windows_powershell_51(self) -> None:
        self.assertTrue(all(ord(ch) < 128 for ch in self.text))

    def test_pyrevit_configuration_change_requires_explicit_switch(self) -> None:
        add_index = self.text.index("extensions paths add")
        self.assertGreater(add_index, self.text.index("if ($RegisterExtension)"))

    def test_never_deletes_files(self) -> None:
        for forbidden in ("Remove-Item", "rmdir", " del ", "Clear-Content"):
            self.assertNotIn(forbidden, self.text)

    def test_checklist_is_never_overwritten(self) -> None:
        keep = self.text.index("Keeping existing checklist")
        copy = self.text.index("Copy-Item -LiteralPath $Template")
        self.assertLess(keep, copy)


if __name__ == "__main__":
    unittest.main()
