"""Tests for ``toolkit validate --workspace``."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from toolkit_cli.cli import main as cli_main  # noqa: E402
from toolkit_cli.validate_workspace import run_workspace_validation  # noqa: E402
from toolkit_engine.workspace import init_workspace, render_workspace  # noqa: E402


class ValidateWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="validate ")
        self.workspace = Path(self._tmp.name) / "Quillmoor DT"
        init_workspace(REPO / "profiles" / "quillmoor", self.workspace)
        render_workspace(self.workspace)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def statuses(self, report) -> dict[str, str]:
        return {c["check_id"]: c["status"] for c in report["checks"]}

    def test_fresh_workspace_passes(self) -> None:
        report = run_workspace_validation(self.workspace)
        self.assertEqual(report["summary"]["outcome"], "pass", self.statuses(report))
        self.assertEqual(self.statuses(report)["firm.tests"], "skip")

    def test_stale_inputs_fail(self) -> None:
        firm = self.workspace / "firm" / "firm.json"
        data = json.loads(firm.read_text(encoding="utf-8"))
        data["identity"]["display_name"] = "Quillmoor Renamed"
        firm.write_text(json.dumps(data), encoding="utf-8")
        report = run_workspace_validation(self.workspace)
        self.assertEqual(self.statuses(report)["workspace.render-current"], "fail")

    def test_unsafe_firm_tool_fails_safety(self) -> None:
        tab = next(self.workspace.glob("extensions/*.extension/*.tab"))
        button = tab / "Studio.panel" / "Cleanup.pushbutton"
        button.mkdir(parents=True)
        (button / "script.py").write_text("import shutil\nshutil.rmtree('C:/temp')\n", encoding="utf-8")
        report = run_workspace_validation(self.workspace)
        statuses = self.statuses(report)
        self.assertEqual(statuses["validators.safety"], "fail")
        # The firm tool is also unregistered and incomplete: the spec and bundle checks say so.
        self.assertEqual(statuses["validators.spec"], "fail")
        self.assertEqual(statuses["validators.bundle"], "fail")

    def test_firm_tests_run_and_report(self) -> None:
        tests = self.workspace / "tests"
        tests.mkdir()
        (tests / "test_firm.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n    def test_fails(self):\n        self.fail('firm rule broken')\n",
            encoding="utf-8",
        )
        report = run_workspace_validation(self.workspace)
        self.assertEqual(self.statuses(report)["firm.tests"], "fail")
        self.assertEqual(self.statuses(run_workspace_validation(self.workspace, run_tests=False)).get("firm.tests"), None)

    def test_cli_exit_codes(self) -> None:
        def run(*args):
            with contextlib.redirect_stdout(io.StringIO()):
                return cli_main(list(args))

        self.assertEqual(run("validate", "--workspace", str(self.workspace)), 0)
        (self.workspace / "specimens" / "wpf" / "Theme.xaml").write_text("<ResourceDictionary/>\n", encoding="utf-8")
        self.assertEqual(run("validate", "--workspace", str(self.workspace), "--skip-tests"), 1)


if __name__ == "__main__":
    unittest.main()
