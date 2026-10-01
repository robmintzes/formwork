"""Firm overrides of generated files: deliberate customization without conflicts."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from toolkit_engine.workspace import init_workspace, render_workspace, validate_firm  # noqa: E402

THEME = "specimens/wpf/Theme.xaml"
OVERRIDE = "firm/overrides/" + THEME


class OverrideTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="overrides ")
        self.root = Path(self._tmp.name) / "Quillmoor DT"
        init_workspace(REPO / "profiles" / "quillmoor", self.root)
        self.assertEqual(render_workspace(self.root)["summary"]["outcome"], "pass")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write_override(self, rel: str, text: str) -> Path:
        path = self.root / "firm" / "overrides" / Path(*rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def codes(self, report) -> list[str]:
        return [d["code"] for d in report["diagnostics"]]

    def custom_theme(self) -> str:
        return (self.root / THEME).read_text(encoding="utf-8").replace("</ResourceDictionary>", "  <!-- firm tweak -->\n</ResourceDictionary>")

    def test_override_replaces_generated_content_without_conflict(self) -> None:
        text = self.custom_theme()
        self.write_override(THEME, text)
        report = render_workspace(self.root)
        self.assertEqual(report["summary"]["outcome"], "pass", report["diagnostics"])
        self.assertIn("override.applied", self.codes(report))
        self.assertEqual((self.root / THEME).read_text(encoding="utf-8"), text)
        manifest = json.loads((self.root / ".toolkit" / "manifest.json").read_text(encoding="utf-8"))
        entry = manifest["files"][THEME]
        self.assertTrue(entry["override"])
        self.assertNotEqual(entry["generated_sha256"], entry["sha256"])
        again = render_workspace(self.root)
        self.assertEqual(again["summary"]["changes"], 0)

    def test_upstream_change_is_reported_and_override_kept(self) -> None:
        text = self.custom_theme()
        self.write_override(THEME, text)
        render_workspace(self.root)
        tokens = self.root / "firm" / "tokens.tokens.json"
        data = json.loads(tokens.read_text(encoding="utf-8"))
        data["palette"]["moss"]["700"]["$value"] = {"colorSpace": "srgb", "components": [0.1, 0.3, 0.6], "hex": "#1A4D99"}
        tokens.write_text(json.dumps(data), encoding="utf-8")
        report = render_workspace(self.root)
        self.assertEqual(report["summary"]["outcome"], "pass", report["diagnostics"])
        self.assertIn("override.upstream-changed", self.codes(report))
        self.assertEqual((self.root / THEME).read_text(encoding="utf-8"), text)
        self.assertIn("#1A4D99", (self.root / "docs" / "guides" / "hello-button.html").read_text(encoding="utf-8"))

    def test_removing_the_override_restores_generated_content(self) -> None:
        generated = (self.root / THEME).read_bytes()
        override = self.write_override(THEME, self.custom_theme())
        render_workspace(self.root)
        override.unlink()
        report = render_workspace(self.root)
        self.assertEqual(report["summary"]["outcome"], "pass", report["diagnostics"])
        self.assertEqual((self.root / THEME).read_bytes(), generated)

    def test_orphan_and_seed_overrides_are_errors(self) -> None:
        self.write_override("docs/not-generated.md", "x\n")
        self.write_override("README.md", "# ours\n")
        report = render_workspace(self.root)
        self.assertEqual(report["summary"]["outcome"], "fail")
        self.assertIn("override.orphan", self.codes(report))
        self.assertIn("override.not-managed", self.codes(report))
        self.assertFalse((self.root / "docs" / "not-generated.md").exists())

    def test_overrides_still_pass_output_checks(self) -> None:
        self.write_override(THEME, "<ResourceDictionary><unclosed></ResourceDictionary>\n")
        report = render_workspace(self.root)
        self.assertIn("output.xaml-invalid", self.codes(report))
        self.assertNotIn("unclosed", (self.root / THEME).read_text(encoding="utf-8"))

    def test_config_validate_sees_overrides(self) -> None:
        self.write_override("docs/not-generated.md", "x\n")
        report = validate_firm(self.root / "firm")
        self.assertIn("override.orphan", self.codes(report))


if __name__ == "__main__":
    unittest.main()
