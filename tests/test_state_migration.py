"""Pre-0.3 workspaces (state in .toolkit/) keep working and move to .formwork/ (ADR 0010)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from formwork_engine.jsonio import dumps_canonical  # noqa: E402
from formwork_engine.outputs import is_reserved_path  # noqa: E402
from formwork_engine.workspace import EngineError, init_workspace, is_workspace, render_workspace  # noqa: E402

BIMXBERT = REPO / "profiles" / "bimxbert"
GUIDE = "docs/guides/hello-button.html"


def tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def rewrite(path: Path, **changes: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(changes)
    path.write_bytes(dumps_canonical(data).encode("utf-8"))


class LegacyStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="formwork migration ")
        self.workspace = Path(self._tmp.name) / "Legacy Workspace"
        self.assertEqual(init_workspace(BIMXBERT, self.workspace)["summary"]["outcome"], "pass")
        self.assertEqual(render_workspace(self.workspace)["summary"]["outcome"], "pass")
        # Recreate what a 0.2 engine left on disk.
        os.rename(self.workspace / ".formwork", self.workspace / ".toolkit")
        rewrite(self.workspace / ".toolkit" / "workspace.json", kind="toolkit-workspace")
        rewrite(
            self.workspace / ".toolkit" / "manifest.json",
            kind="toolkit-generation-manifest",
            foundation_version="0.2.0-alpha.1",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_dry_run_reports_the_move_and_writes_nothing(self) -> None:
        before = tree(self.workspace)
        report = render_workspace(self.workspace, dry_run=True)
        self.assertEqual(report["summary"]["outcome"], "pass", report["diagnostics"])
        self.assertEqual(report["plan"]["state_migration"], {"from": ".toolkit/", "to": ".formwork/"})
        self.assertIn("workspace.state-migration", [d["code"] for d in report["diagnostics"]])
        self.assertGreater(report["summary"]["changes"], 0)
        self.assertEqual(tree(self.workspace), before)

    def test_render_moves_state_and_leaves_generated_files_alone(self) -> None:
        before = {k: v for k, v in tree(self.workspace).items() if not k.startswith(".toolkit/")}
        report = render_workspace(self.workspace)
        self.assertEqual(report["summary"]["outcome"], "pass", report["diagnostics"])
        self.assertTrue(report["summary"]["written"])
        self.assertFalse((self.workspace / ".toolkit").exists())
        marker = json.loads((self.workspace / ".formwork" / "workspace.json").read_text(encoding="utf-8"))
        manifest = json.loads((self.workspace / ".formwork" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(marker["kind"], "formwork-workspace")
        self.assertEqual(manifest["kind"], "formwork-generation-manifest")
        after = {k: v for k, v in tree(self.workspace).items() if not k.startswith(".formwork/")}
        self.assertEqual(after, before)

        again = render_workspace(self.workspace)
        self.assertEqual(again["summary"]["changes"], 0, again["plan"])
        self.assertIsNone(again["plan"]["state_migration"])

    def test_conflict_blocks_the_move_too(self) -> None:
        (self.workspace / GUIDE).write_text("firm edit", encoding="utf-8")
        report = render_workspace(self.workspace)
        self.assertEqual(report["summary"]["outcome"], "fail")
        self.assertFalse(report["summary"]["written"])
        self.assertTrue((self.workspace / ".toolkit" / "manifest.json").is_file())
        self.assertFalse((self.workspace / ".formwork").exists())
        self.assertEqual((self.workspace / GUIDE).read_text(encoding="utf-8"), "firm edit")

    def test_both_state_folders_is_refused(self) -> None:
        shutil.copytree(self.workspace / ".toolkit", self.workspace / ".formwork")
        before = tree(self.workspace)
        with self.assertRaises(EngineError) as caught:
            render_workspace(self.workspace)
        self.assertEqual(caught.exception.code, "workspace.state-ambiguous")
        self.assertEqual(tree(self.workspace), before)

    def test_wizard_recognizes_a_legacy_workspace(self) -> None:
        self.assertTrue(is_workspace(self.workspace))


class ReservedLegacyPathTests(unittest.TestCase):
    def test_legacy_state_folder_stays_reserved_in_any_case(self) -> None:
        for path in (".toolkit/manifest.json", ".TOOLKIT/workspace.json", ".formwork/x", "Firm/firm.json"):
            self.assertTrue(is_reserved_path(path), path)
        self.assertFalse(is_reserved_path("docs/toolkit/notes.md"))


class CompatibilityAliasTests(unittest.TestCase):
    def test_old_module_name_forwards_with_a_notice(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "toolkit_cli", "config", "validate", "--firm", str(BIMXBERT)],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("python -m formwork_cli", result.stderr)


if __name__ == "__main__":
    unittest.main()
