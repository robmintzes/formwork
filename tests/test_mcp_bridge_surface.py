"""Acceptance tests for the generated mcp-bridge surface.

A firm workspace that lists ``mcp-bridge`` gets a read-only copy of the
foundation's Revit MCP bridge, re-identified for the firm: the pyRevit Routes
API name and the server's default Routes URL come from ``technical.namespace``,
``__author__`` from ``identity.author``, and nothing names the template.
Nothing here is live-verified in Revit.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from toolkit_engine.adapters import mcp_bridge, render_all  # noqa: E402
from toolkit_engine.checks import check_outputs  # noqa: E402
from toolkit_engine.diagnostics import Diagnostics  # noqa: E402
from toolkit_engine.profile import load_profile  # noqa: E402
from toolkit_engine.vendoring import VendoringError  # noqa: E402
from toolkit_engine.workspace import init_workspace, render_workspace, validate_firm  # noqa: E402
from validators.check_bundle_structure import validate_bundle_structure  # noqa: E402
from validators.check_safety_rules import find_violations  # noqa: E402
from validators.validate_toolbar_spec import validate_toolbar_spec  # noqa: E402

QUILLMOOR = REPO / "profiles" / "quillmoor"
BIMXBERT = REPO / "profiles" / "bimxbert"
EXTENSION = "extensions/Quillmoor.extension"
AUTHOR = "Quillmoor Studio Design Technology"
ROUTES_URL = "http://127.0.0.1:48884/quillmoor"
FORBIDDEN = re.compile(r"placeholder|template author|robmintzes", re.IGNORECASE)


def edit_json(path: Path, mutate) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class BridgeCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="mcp bridge ")
        self.base = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def workspace(self, name: str = "Quillmoor Bridge WS") -> Path:
        root = self.base / name
        init_workspace(QUILLMOOR, root)
        report = render_workspace(root)
        self.assertEqual(report["summary"]["outcome"], "pass", report["diagnostics"])
        self.report = report
        return root

    @staticmethod
    def bridge_paths(root: Path) -> list:
        manifest = json.loads((root / ".toolkit" / "manifest.json").read_text(encoding="utf-8"))
        return sorted(rel for rel, entry in manifest["files"].items() if entry["adapter"] == "mcp-bridge")


class GeneratedBridgeTests(BridgeCase):
    def test_bridge_files_exist_and_are_managed(self) -> None:
        root = self.workspace()
        bridge = EXTENSION + "/lib/revit_mcp_bridge/"
        for rel in [EXTENSION + "/startup.py", EXTENSION + "/tests/test_mcp_bridge_runtime.py", "docs/onboarding/MCP_GUIDE.md"] + [
            bridge + name for name in mcp_bridge.BRIDGE_MODULES
        ] + ["servers/revit-mcp/" + rel for rel in mcp_bridge.SERVER_FILES]:
            self.assertTrue((root / rel).is_file(), rel)
        manifest = json.loads((root / ".toolkit" / "manifest.json").read_text(encoding="utf-8"))
        for rel in self.bridge_paths(root):
            self.assertEqual(manifest["files"][rel]["ownership"], "managed", rel)
        # The live probe depends on the foundation's toolkit_cli and is not vendored.
        self.assertFalse((root / "servers" / "revit-mcp" / "mcp-server" / "live_probe.py").exists())
        self.assertIn("mcp-bridge.not-live-verified", [d["code"] for d in self.report["diagnostics"]])

    def test_routes_prefix_is_the_firm_namespace_everywhere(self) -> None:
        root = self.workspace()
        bridge = root / EXTENSION / "lib" / "revit_mcp_bridge"
        for name in mcp_bridge.ROUTE_MODULES:
            text = (bridge / name).read_text(encoding="utf-8")
            self.assertIn('routes.API("quillmoor")', text, name)
            self.assertNotIn('routes.API("placeholder")', text, name)
        settings = (root / "servers/revit-mcp/mcp-server/settings.py").read_text(encoding="utf-8")
        self.assertIn('"{}",'.format(ROUTES_URL), settings)
        self.assertIn("(/quillmoor)", settings)
        server_tests = (root / "servers/revit-mcp/mcp-server/tests/test_settings.py").read_text(encoding="utf-8")
        self.assertEqual(server_tests.count("/quillmoor"), 7)
        guide = (root / "docs/onboarding/MCP_GUIDE.md").read_text(encoding="utf-8")
        self.assertIn(ROUTES_URL + "/health/", guide)
        startup = (root / EXTENSION / "startup.py").read_text(encoding="utf-8")
        self.assertIn("Quillmoor extension loaded and MCP routes registered.", startup)

    def test_no_template_identity_or_foundation_maintainer_leaks(self) -> None:
        root = self.workspace()
        paths = self.bridge_paths(root)
        self.assertGreater(len(paths), 30)
        for rel in paths:
            text = (root / rel).read_text(encoding="utf-8")
            self.assertIsNone(FORBIDDEN.search(text), rel)

    def test_author_metadata_is_the_firm_identity(self) -> None:
        root = self.workspace()
        runtime = [root / EXTENSION / "startup.py"] + sorted((root / EXTENSION / "lib" / "revit_mcp_bridge").glob("*.py"))
        self.assertEqual(len(runtime), 1 + len(mcp_bridge.BRIDGE_MODULES))
        for path in runtime:
            self.assertIn('__author__ = "{}"'.format(AUTHOR), path.read_text(encoding="utf-8"), path.name)

    def test_loopback_only_defaults_are_preserved(self) -> None:
        root = self.workspace()
        settings = (root / "servers/revit-mcp/mcp-server/settings.py").read_text(encoding="utf-8")
        self.assertIn('MCP_HOST: str = os.environ.get("MCP_HOST", "127.0.0.1")', settings)
        self.assertIn("This unauthenticated foundation supports explicit loopback URLs only.", settings)
        self.assertIn('ENABLE_WRITE_TOOLS: bool = _env_bool("ENABLE_WRITE_TOOLS")', settings)
        for rel in ("setup-mcp-server.ps1", "start-local-http.ps1", "start-stdio.ps1"):
            self.assertTrue((root / "servers/revit-mcp/scripts" / rel).read_text(encoding="utf-8").isascii(), rel)

    def test_outputs_pass_the_engine_checks_including_ironpython_guard(self) -> None:
        for firm in (QUILLMOOR, BIMXBERT):
            diags = Diagnostics()
            profile = load_profile(firm, diags)
            self.assertIn("mcp-bridge", profile.config.surfaces)
            rendered = render_all(profile)
            check_outputs(rendered.files, diags)
            self.assertFalse(diags.has_errors, [d for d in diags.items if d.severity == "error"])
            embedded = [f for f in rendered.files if f.path.startswith("extensions/") and f.path.endswith(".py")]
            self.assertTrue([f for f in embedded if "revit_mcp_bridge" in f.path])
            self.assertEqual(validate_firm(firm)["summary"]["outcome"], "pass")

    def test_foundation_validators_pass_on_the_workspace(self) -> None:
        root = self.workspace()
        errors, _ = validate_bundle_structure(root)
        self.assertEqual(errors, [])
        _, spec_errors = validate_toolbar_spec(root)
        self.assertEqual(spec_errors, [])
        self.assertEqual(find_violations(root), [])

    def test_second_render_is_a_no_op(self) -> None:
        root = self.workspace()
        before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
        report = render_workspace(root)
        self.assertEqual(report["summary"]["outcome"], "pass")
        self.assertEqual(report["summary"]["changes"], 0)
        self.assertEqual({p: p.read_bytes() for p in root.rglob("*") if p.is_file()}, before)

    def test_vendored_extension_runtime_tests_pass_in_the_workspace(self) -> None:
        root = self.workspace()
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(root / EXTENSION / "tests")],
            cwd=root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK", result.stderr)

    def test_generated_guide_keeps_the_mandatory_reset_rule(self) -> None:
        root = self.workspace()
        guide = " ".join((root / "docs/onboarding/MCP_GUIDE.md").read_text(encoding="utf-8").split())
        self.assertIn("After clicking **pyRevit Reload**, do **not** call a route.", guide)
        self.assertIn("either fully restart Revit or toggle pyRevit Routes off and back on", guide)
        self.assertIn("`--routes-reset-confirmed` is a human assertion", guide)

    def test_edited_bridge_file_blocks_the_next_render(self) -> None:
        root = self.workspace()
        target = root / EXTENSION / "lib" / "revit_mcp_bridge" / "response.py"
        target.write_text(target.read_text(encoding="utf-8") + "# local edit\n", encoding="utf-8")
        report = render_workspace(root)
        self.assertEqual(report["summary"]["outcome"], "fail")
        self.assertIn("managed-modified", json.dumps(report))


class SurfaceDependencyTests(BridgeCase):
    def test_bridge_requires_the_pyrevit_sample_surface(self) -> None:
        firm = self.base / "firm"
        shutil.copytree(QUILLMOOR, firm)
        edit_json(firm / "firm.json", lambda c: c["surfaces"].remove("pyrevit-sample"))
        report = validate_firm(firm)
        self.assertEqual(report["summary"]["outcome"], "fail")
        self.assertIn("config.surface-requires", [d["code"] for d in report["diagnostics"]])

    def test_other_surfaces_still_work_without_the_bridge(self) -> None:
        firm = self.base / "firm"
        shutil.copytree(QUILLMOOR, firm)
        edit_json(firm / "firm.json", lambda c: c["surfaces"].remove("mcp-bridge"))
        root = self.base / "No Bridge WS"
        init_workspace(firm, root)
        self.assertEqual(render_workspace(root)["summary"]["outcome"], "pass")
        self.assertFalse((root / "servers").exists())
        self.assertFalse((root / EXTENSION / "startup.py").exists())


class VendoringDriftTests(unittest.TestCase):
    """A changed foundation source must fail generation, never render half-rebranded."""

    def fake_foundation(self, root: Path) -> None:
        source = mcp_bridge.SOURCE_EXTENSION
        names = ["startup.py"] + ["{}/{}".format(mcp_bridge.BRIDGE_PACKAGE, n) for n in mcp_bridge.BRIDGE_MODULES]
        for rel in names:
            self.copy(REPO / source / rel, root / source / rel)
        for rel in mcp_bridge.SERVER_FILES + mcp_bridge.SERVER_EXCLUDED:
            self.copy(REPO / mcp_bridge.SERVER_SOURCE / rel, root / mcp_bridge.SERVER_SOURCE / rel)

    @staticmethod
    def copy(source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source, target)

    def render_against(self, fake: Path) -> None:
        profile = load_profile(QUILLMOOR, Diagnostics())
        original = mcp_bridge.FOUNDATION
        mcp_bridge.FOUNDATION = fake
        try:
            mcp_bridge.render(profile)
        finally:
            mcp_bridge.FOUNDATION = original

    def edit(self, fake: Path, rel: str, old: str, new: str) -> None:
        path = fake / rel
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text, rel)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def test_unaltered_copy_of_the_foundation_renders(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bridge drift ") as tmp:
            fake = Path(tmp)
            self.fake_foundation(fake)
            self.render_against(fake)

    def test_changed_substitution_targets_fail_loudly(self) -> None:
        source = mcp_bridge.SOURCE_EXTENSION
        bridge = source + "/" + mcp_bridge.BRIDGE_PACKAGE
        server = mcp_bridge.SERVER_SOURCE + "/mcp-server"
        cases = {
            "routes API name": (bridge + "/routes_health.py", 'routes.API("placeholder")', 'routes.API("renamed")'),
            "bridge author": (bridge + "/compat.py", '__author__ = "Template Author"', '__author__ = "Someone"'),
            "startup author": (source + "/startup.py", '__author__ = "Template Author"', '__author__ = "Someone"'),
            "startup log line": (source + "/startup.py", "Placeholder extension loaded", "Template extension loaded"),
            "settings default URL": (server + "/settings.py", '48884/placeholder"', '48884/renamed"'),
            "settings comment": (server + "/settings.py", "(/placeholder)", "(/renamed)"),
            "settings tests": (server + "/tests/test_settings.py", "http://127.0.0.1/placeholder", "http://127.0.0.1/renamed"),
        }
        for label, (rel, old, new) in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory(prefix="bridge drift ") as tmp:
                fake = Path(tmp)
                self.fake_foundation(fake)
                self.edit(fake, rel, old, new)
                with self.assertRaises(VendoringError):
                    self.render_against(fake)

    def test_extra_substitution_target_fails_loudly(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bridge drift ") as tmp:
            fake = Path(tmp)
            self.fake_foundation(fake)
            rel = mcp_bridge.SOURCE_EXTENSION + "/" + mcp_bridge.BRIDGE_PACKAGE + "/routes_project.py"
            path = fake / rel
            path.write_text(path.read_text(encoding="utf-8") + '\n_OTHER = routes.API("placeholder")\n', encoding="utf-8")
            with self.assertRaises(VendoringError):
                self.render_against(fake)

    def test_new_or_missing_foundation_files_fail_loudly(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bridge drift ") as tmp:
            fake = Path(tmp)
            self.fake_foundation(fake)
            (fake / mcp_bridge.SOURCE_EXTENSION / mcp_bridge.BRIDGE_PACKAGE / "handlers_write.py").write_text("x = 1\n", encoding="utf-8")
            with self.assertRaises(VendoringError):
                self.render_against(fake)
        with tempfile.TemporaryDirectory(prefix="bridge drift ") as tmp:
            fake = Path(tmp)
            self.fake_foundation(fake)
            (fake / mcp_bridge.SERVER_SOURCE / "mcp-server" / "tools" / "project.py").unlink()
            with self.assertRaises(VendoringError):
                self.render_against(fake)


if __name__ == "__main__":
    unittest.main()
