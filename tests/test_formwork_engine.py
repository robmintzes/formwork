"""Acceptance tests for workspace generation (FOUNDATION_SPEC section 10).

These exercise the promises in docs/product/FIRST_MILESTONE.md against real
temporary workspaces whose paths contain spaces. They test behavior (what is
on disk, what is reported), not the generator's internal structure.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from formwork_cli.cli import main as cli_main  # noqa: E402
from formwork_engine.checks import check_outputs  # noqa: E402
from formwork_engine.diagnostics import Diagnostics  # noqa: E402
from formwork_engine.outputs import text_file  # noqa: E402
from formwork_engine.profile import load_profile  # noqa: E402
from formwork_engine.workspace import EngineError, init_workspace, render_workspace, validate_firm  # noqa: E402
from validators.check_bundle_structure import validate_bundle_structure  # noqa: E402
from validators.validate_toolbar_spec import validate_toolbar_spec  # noqa: E402

BIMXBERT = REPO / "profiles" / "bimxbert"
QUILLMOOR = REPO / "profiles" / "quillmoor"
GUIDE = "docs/guides/hello-button.html"
THEME = "specimens/wpf/Theme.xaml"


def tree(root: Path) -> dict[str, str]:
    """Relative path -> sha256 for every file under *root*."""
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def edit_json(path: Path, mutate) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class WorkspaceCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="formwork engine ")
        self.base = Path(self._tmp.name) / "Firm Workspaces"
        self.base.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def make(self, profile: Path = BIMXBERT, name: str = "Design Tech") -> Path:
        workspace = self.base / name
        report = init_workspace(profile, workspace)
        self.assertEqual(report["summary"]["outcome"], "pass", report["diagnostics"])
        rendered = render_workspace(workspace)
        self.assertEqual(rendered["summary"]["outcome"], "pass", rendered["diagnostics"])
        return workspace


class ProfileValidationTests(unittest.TestCase):
    def test_shipped_profiles_validate_without_errors(self) -> None:
        for profile in (BIMXBERT, QUILLMOOR):
            report = validate_firm(profile)
            self.assertEqual(report["summary"]["outcome"], "pass", report["diagnostics"])
            self.assertFalse([d for d in report["diagnostics"] if d["code"] == "a11y.contrast"])

    def test_published_json_schema_matches_engine_vocabulary(self) -> None:
        from formwork_engine import config

        schema = json.loads((REPO / "schemas" / "firm-config.v1.schema.json").read_text(encoding="utf-8"))
        props = schema["properties"]
        self.assertEqual(props["surfaces"]["items"]["enum"], list(config.SURFACES))
        appearance = props["appearance"]["properties"]
        for group, choices in config.APPEARANCE_CHOICES.items():
            for key, options in choices.items():
                self.assertEqual(appearance[group]["properties"][key]["enum"], list(options), group + "." + key)
        self.assertEqual(sorted(props["brand"]["properties"]["assets"]["required"]), sorted(config.ASSET_SLOTS))
        for profile in (BIMXBERT, QUILLMOOR):
            firm = json.loads((profile / "firm.json").read_text(encoding="utf-8"))
            self.assertEqual(set(schema["required"]), set(firm) - {"$schema"})

    def test_unsupported_choice_is_reported_not_hidden(self) -> None:
        codes = {d["code"] for d in validate_firm(BIMXBERT)["diagnostics"]}
        self.assertIn("adapter.unsupported-choice", codes)  # WPF cannot draw registration marks


class InvalidConfigurationTests(unittest.TestCase):
    """Each broken input yields a coded, located diagnostic instead of a traceback."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="formwork config ")
        self.firm = Path(self._tmp.name) / "firm"
        shutil.copytree(QUILLMOOR, self.firm)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def codes(self) -> list[str]:
        diags = Diagnostics()
        self.assertIsNone(load_profile(self.firm, diags))
        self.assertTrue(all(d.location for d in diags.items))
        return diags.codes()

    def tokens(self, mutate) -> None:
        edit_json(self.firm / "tokens.tokens.json", mutate)

    def config(self, mutate) -> None:
        edit_json(self.firm / "firm.json", mutate)

    def test_alias_cycle(self) -> None:
        def cycle(doc):
            doc["palette"]["moss"]["700"] = {"$value": "{color.action.primary.bg}"}
        self.tokens(cycle)
        self.assertIn("token.alias-cycle", self.codes())

    def test_missing_alias_target(self) -> None:
        self.tokens(lambda doc: doc["color"]["text"].__setitem__("primary", {"$value": "{palette.ink.950}"}))
        self.assertIn("token.alias-missing", self.codes())

    def test_missing_required_role(self) -> None:
        self.tokens(lambda doc: doc["color"]["focus"].pop("ring"))
        self.assertIn("token.role-missing", self.codes())

    def test_rem_and_unknown_types_are_rejected(self) -> None:
        def bad(doc):
            doc["space"]["md"] = {"$value": {"value": 1, "unit": "rem"}}
            doc["shadow"] = {"$type": "shadow", "card": {"$value": {}}}
        self.tokens(bad)
        codes = self.codes()
        self.assertIn("token.unit-unsupported", codes)
        self.assertIn("token.type-unsupported", codes)

    def test_hex_disagreeing_with_components(self) -> None:
        self.tokens(lambda doc: doc["palette"]["ink"]["900"]["$value"].__setitem__("hex", "#FF0000"))
        self.assertIn("token.color-hex-mismatch", self.codes())

    def test_unknown_field_gets_a_suggestion(self) -> None:
        self.config(lambda c: c["identity"].__setitem__("dispaly_name", "x"))
        diags = Diagnostics()
        load_profile(self.firm, diags)
        unknown = [d for d in diags.items if d.code == "config.unknown-field"]
        self.assertTrue(unknown and "display_name" in unknown[0].hint)

    def test_newer_schema_names_the_problem(self) -> None:
        self.config(lambda c: c.__setitem__("schema_version", 2))
        self.assertEqual(self.codes(), ["config.schema-too-new"])

    def test_unsafe_and_reserved_names(self) -> None:
        def bad(c):
            c["brand"]["tokens"] = "../outside.tokens.json"
            c["technical"]["pyrevit"]["tab"] = "CON"
            c["maintainers"][0]["branch_prefix"] = "claude"
        self.config(bad)
        codes = self.codes()
        self.assertIn("config.path-invalid", codes)
        self.assertIn("config.name-reserved", codes)
        self.assertIn("config.branch-prefix-agent", codes)

    def test_svg_with_script_is_rejected(self) -> None:
        svg = self.firm / "assets" / "symbol-light.svg"
        svg.write_text(svg.read_text(encoding="utf-8").replace("</svg>", "<script>alert(1)</script></svg>"), encoding="utf-8")
        self.assertIn("brand.svg-unsafe", self.codes())

    def test_external_resource_in_output_is_caught(self) -> None:
        diags = Diagnostics()
        page = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist">'
        check_outputs([text_file("docs/guides/x.html", page, "test")], diags)
        self.assertIn("output.external-resource", diags.codes())


class GenerationTests(WorkspaceCase):
    def test_generated_workspace_passes_foundation_validators(self) -> None:
        for profile, name in ((BIMXBERT, "BIMxBert"), (QUILLMOOR, "Quillmoor")):
            workspace = self.make(profile, name)
            errors, _ = validate_bundle_structure(workspace)
            _, spec_errors = validate_toolbar_spec(workspace)
            self.assertEqual(errors, [], name)
            self.assertEqual(spec_errors, [], name)

    def test_second_render_is_a_no_op(self) -> None:
        workspace = self.make()
        before = tree(workspace)
        report = render_workspace(workspace)
        self.assertEqual(report["summary"]["changes"], 0)
        self.assertFalse(report["summary"]["written"])
        self.assertEqual(tree(workspace), before)

    def test_output_does_not_depend_on_workspace_location(self) -> None:
        first = self.make(name="One")
        second = self.make(name="Two (copy)")
        self.assertEqual(tree(first), tree(second))

    def test_dry_run_writes_nothing(self) -> None:
        workspace = self.base / "Dry"
        init_workspace(BIMXBERT, workspace)
        before = tree(workspace)
        report = render_workspace(workspace, dry_run=True)
        self.assertEqual(report["summary"]["outcome"], "pass")
        self.assertGreater(report["summary"]["changes"], 10)
        self.assertEqual(tree(workspace), before)
        self.assertFalse((workspace / ".formwork" / "manifest.json").exists())

    def test_two_profiles_are_visibly_distinct(self) -> None:
        bimxbert = self.make(BIMXBERT, "B")
        quillmoor = self.make(QUILLMOOR, "Q")
        b_guide = (bimxbert / GUIDE).read_text(encoding="utf-8")
        q_guide = (quillmoor / GUIDE).read_text(encoding="utf-8")
        self.assertIn("#2F4452", b_guide)  # Pacific Blue
        self.assertNotIn("#2F4452", q_guide)
        self.assertIn('"Barlow Condensed"', b_guide)
        self.assertIn('"Georgia"', q_guide)
        self.assertIn("border-radius: 0;", b_guide)  # square buttons
        self.assertIn("border-radius: 18px;", q_guide)  # pill buttons (36px controls)
        self.assertIn("btn--primary::before", b_guide)  # registration marks
        self.assertNotIn("btn--primary::before", q_guide)
        icon = "extensions/{0}.extension/{0}.tab/{1}.panel/HelloButton.pushbutton/icon.png"
        self.assertNotEqual(
            (bimxbert / icon.format("BIMxBert", "Foundation")).read_bytes(),
            (quillmoor / icon.format("Quillmoor", "Starter")).read_bytes(),
        )

    def test_fictional_firm_output_contains_no_default_identity(self) -> None:
        workspace = self.make(QUILLMOOR, "Q")
        leaks = []
        for path in workspace.rglob("*"):
            if not path.is_file() or path.suffix.lower() in (".png", ".ttf", ".otf"):
                continue
            rel = path.relative_to(workspace).as_posix()
            text = path.read_text(encoding="utf-8").lower()
            for needle in ("bimxbert", "robmintzes", "rob mintzes"):
                # The foundation's MIT copyright line is a required notice.
                if needle in text and not (rel == "THIRD_PARTY_NOTICES.md" and needle == "rob mintzes"):
                    leaks.append((rel, needle))
        self.assertEqual(leaks, [])
        bundle = next(workspace.rglob("bundle.yaml")).read_text(encoding="utf-8")
        self.assertIn("author: Quillmoor Studio Design Technology", bundle)
        self.assertIn('help_url: "https://support.quillmoor.example/design-technology"', bundle)
        self.assertIn('alt="Quillmoor Studio"', (workspace / GUIDE).read_text(encoding="utf-8"))

    def test_generated_sample_matches_the_foundation_reference_tool(self) -> None:
        workspace = self.make()
        generated = next(workspace.rglob("HelloButton.pushbutton/script.py")).read_text(encoding="utf-8")
        reference = next((REPO / "extensions").rglob("HelloButton.pushbutton/script.py")).read_text(encoding="utf-8")
        # Only the author line is firm-specific.
        author = re.compile(r'^__author__ = ".*"$', re.MULTILINE)
        self.assertEqual(
            author.sub("__author__ = X", generated),
            author.sub("__author__ = X", reference.replace("\r\n", "\n")),
        )

    def test_notice_resource_matches_repository_license(self) -> None:
        resource = REPO / "formwork_engine" / "resources" / "FOUNDATION_LICENSE.txt"
        self.assertEqual(
            resource.read_text(encoding="utf-8").replace("\r\n", "\n"),
            (REPO / "LICENSE").read_text(encoding="utf-8").replace("\r\n", "\n"),
        )


class RebrandAndPreservationTests(WorkspaceCase):
    def add_custom_tool(self, workspace: Path) -> dict[str, str]:
        button = next(workspace.glob("extensions/*.extension/*.tab")) / "Studio.panel" / "Sheet Audit.pushbutton"
        button.mkdir(parents=True)
        (button / "script.py").write_text('# -*- coding: utf-8 -*-\n__author__ = "Our Firm"\nprint("custom")\n', encoding="utf-8")
        (button / "bundle.yaml").write_text("title: Sheet Audit\ntooltip: Ours.\nauthor: Our Firm\n", encoding="utf-8")
        shutil.copy(next(workspace.rglob("HelloButton.pushbutton/icon.png")), button / "icon.png")
        return {k: v for k, v in tree(workspace).items() if "Studio.panel" in k}

    def rebrand(self, workspace: Path) -> None:
        firm = workspace / "firm"

        def config(c):
            c["identity"]["display_name"] = "Brandt Atelier"
            c["identity"]["author"] = "Brandt Atelier"
            c["appearance"]["button"]["shape"] = "pill"
            c["appearance"]["badge"]["style"] = "outline"

        edit_json(firm / "firm.json", config)
        edit_json(
            firm / "tokens.tokens.json",
            lambda t: t["palette"]["brand"]["800"].__setitem__(
                "$value", {"colorSpace": "srgb", "components": [0.4, 0.1, 0.2], "hex": "#661A33"}
            ),
        )

    def test_brand_change_propagates_and_preserves_firm_work(self) -> None:
        workspace = self.make()
        custom = self.add_custom_tool(workspace)
        notices_before = (workspace / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        icon = next(workspace.rglob("HelloButton.pushbutton/icon.png"))
        icon_before = icon.read_bytes()
        self.rebrand(workspace)

        report = render_workspace(workspace)
        self.assertEqual(report["summary"]["outcome"], "pass", report["diagnostics"])
        updated = {a["path"] for a in report["plan"]["actions"] if a["action"] == "update"}
        for expected in (GUIDE, THEME, "specimens/wpf/Controls.xaml", "specimens/wpf/Specimen.xaml"):
            self.assertIn(expected, updated)
        self.assertIn("#661A33", (workspace / GUIDE).read_text(encoding="utf-8"))
        self.assertIn("#661A33", (workspace / THEME).read_text(encoding="utf-8"))
        self.assertIn("Brandt Atelier", (workspace / GUIDE).read_text(encoding="utf-8"))
        self.assertIn("author: Brandt Atelier", next(workspace.rglob("HelloButton.pushbutton/bundle.yaml")).read_text(encoding="utf-8"))
        self.assertNotEqual(icon.read_bytes(), icon_before)  # pill corners
        # Firm-owned tool is byte-identical; notices survive the rebrand verbatim.
        self.assertEqual({k: v for k, v in tree(workspace).items() if "Studio.panel" in k}, custom)
        self.assertEqual((workspace / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8"), notices_before)
        # Technical identity did not move.
        self.assertTrue((workspace / "extensions" / "BIMxBert.extension").is_dir())

    def test_edited_managed_file_is_a_conflict_and_blocks_everything(self) -> None:
        workspace = self.make()
        theme = workspace / THEME
        theme.write_text(theme.read_text(encoding="utf-8") + "<!-- local tweak -->\n", encoding="utf-8")
        edited = theme.read_bytes()
        self.rebrand(workspace)
        guide_before = (workspace / GUIDE).read_bytes()

        report = render_workspace(workspace)
        self.assertEqual(report["summary"]["outcome"], "fail")
        conflicts = [d for d in report["diagnostics"] if d["code"] == "conflict.managed-modified"]
        self.assertEqual([d["location"] for d in conflicts], [THEME])
        self.assertTrue(conflicts[0]["hint"])
        self.assertEqual(theme.read_bytes(), edited)
        self.assertEqual((workspace / GUIDE).read_bytes(), guide_before)  # nothing else applied

    def test_deleting_a_managed_file_restores_it(self) -> None:
        workspace = self.make()
        (workspace / THEME).unlink()
        report = render_workspace(workspace)
        self.assertIn({"path": THEME, "action": "restore", "ownership": "managed", "adapter": "wpf-specimen"}, report["plan"]["actions"])
        self.assertTrue((workspace / THEME).is_file())

    def test_user_file_at_a_managed_path_is_never_overwritten(self) -> None:
        workspace = self.base / "Prefilled"
        init_workspace(BIMXBERT, workspace)
        guide = workspace / GUIDE
        guide.parent.mkdir(parents=True)
        guide.write_text("my own guide\n", encoding="utf-8")
        report = render_workspace(workspace)
        self.assertIn("conflict.unmanaged-at-managed-path", [d["code"] for d in report["diagnostics"]])
        self.assertEqual(guide.read_text(encoding="utf-8"), "my own guide\n")

    def test_seed_files_become_firm_owned(self) -> None:
        workspace = self.make()
        readme = workspace / "README.md"
        readme.write_text("# Our workspace\n", encoding="utf-8")
        report = render_workspace(workspace)
        self.assertEqual(report["summary"]["outcome"], "pass")
        self.assertEqual(readme.read_text(encoding="utf-8"), "# Our workspace\n")
        readme.unlink()
        render_workspace(workspace)
        self.assertFalse(readme.exists())  # a deliberately deleted seed is not recreated

    def test_crlf_checkout_is_not_a_modification(self) -> None:
        workspace = self.make()
        theme = workspace / THEME
        theme.write_bytes(theme.read_bytes().replace(b"\n", b"\r\n"))
        report = render_workspace(workspace)
        self.assertEqual(report["summary"]["outcome"], "pass", report["diagnostics"])
        self.assertEqual(report["summary"]["changes"], 0)

    def test_renamed_panel_retires_old_files_only_when_unmodified(self) -> None:
        workspace = self.make()
        edit_json(workspace / "firm" / "firm.json", lambda c: c["technical"]["pyrevit"].__setitem__("sample_panel", "Starter Kit"))
        old_script = next(workspace.rglob("Foundation.panel/HelloButton.pushbutton/script.py"))
        old_script.write_text(old_script.read_text(encoding="utf-8") + "# edited\n", encoding="utf-8")
        blocked = render_workspace(workspace)
        self.assertIn("conflict.retired-modified", [d["code"] for d in blocked["diagnostics"]])
        self.assertTrue(old_script.exists())

        old_script.unlink()  # firm accepts losing its edit
        report = render_workspace(workspace)
        self.assertEqual(report["summary"]["outcome"], "pass", report["diagnostics"])
        self.assertFalse(any(workspace.rglob("Foundation.panel/*/*.*")))
        self.assertTrue(any(workspace.rglob("Starter Kit.panel/HelloButton.pushbutton/script.py")))
        self.assertIn("extensions/BIMxBert.extension/BIMxBert.tab/Foundation.panel/HelloButton.pushbutton", report["summary"]["empty_directories"])

    def test_interrupted_apply_converges_on_the_next_run(self) -> None:
        clean = self.make(name="Clean")
        workspace = self.base / "Interrupted"
        init_workspace(BIMXBERT, workspace)
        calls = {"n": 0}

        def flaky(target: Path, content: bytes) -> None:
            calls["n"] += 1
            if calls["n"] == 12:
                raise OSError("simulated disk failure")
            from formwork_engine.apply import atomic_write
            atomic_write(target, content)

        with self.assertRaises(OSError):
            render_workspace(workspace, write=flaky)
        self.assertFalse((workspace / ".formwork" / "manifest.json").exists())
        report = render_workspace(workspace)
        self.assertEqual(report["summary"]["outcome"], "pass", report["diagnostics"])
        self.assertIn("adopt", report["summary"]["actions"])
        self.assertEqual(tree(workspace), tree(clean))
        self.assertFalse(list(workspace.rglob(".formwork-*.tmp")))


class SafetyTests(WorkspaceCase):
    def test_workspace_inside_foundation_is_refused(self) -> None:
        with self.assertRaises(EngineError) as caught:
            init_workspace(BIMXBERT, REPO / "build" / "nested workspace")
        self.assertEqual(caught.exception.code, "workspace.overlaps-foundation")

    def test_drive_root_and_home_are_refused(self) -> None:
        for target in (Path(Path.cwd().anchor), Path.home()):
            with self.assertRaises(EngineError):
                init_workspace(BIMXBERT, target)

    def test_init_refuses_non_empty_directory(self) -> None:
        target = self.base / "Busy"
        target.mkdir()
        (target / "notes.txt").write_text("keep me", encoding="utf-8")
        with self.assertRaises(EngineError) as caught:
            init_workspace(BIMXBERT, target)
        self.assertEqual(caught.exception.code, "workspace.not-empty")
        self.assertEqual((target / "notes.txt").read_text(encoding="utf-8"), "keep me")

    def test_render_requires_initialized_workspace(self) -> None:
        target = self.base / "Plain"
        target.mkdir()
        with self.assertRaises(EngineError) as caught:
            render_workspace(target)
        self.assertEqual(caught.exception.code, "workspace.not-initialized")

    def test_workspace_id_change_is_not_a_silent_rebrand(self) -> None:
        workspace = self.make()
        edit_json(workspace / "firm" / "firm.json", lambda c: c["technical"].__setitem__("workspace_id", "someone-else"))
        report = render_workspace(workspace)
        self.assertIn("workspace.id-mismatch", [d["code"] for d in report["diagnostics"]])

    @unittest.skipUnless(os.name == "nt", "junctions are a Windows feature")
    def test_junction_inside_workspace_is_refused(self) -> None:
        import _winapi

        workspace = self.make()
        outside = self.base / "Outside Target"
        outside.mkdir()
        specimens = workspace / "specimens"
        shutil.rmtree(specimens)
        _winapi.CreateJunction(str(outside), str(specimens))
        try:
            with self.assertRaises(EngineError) as caught:
                render_workspace(workspace)
            self.assertEqual(caught.exception.code, "path.reparse-point")
            self.assertEqual(list(outside.iterdir()), [])
        finally:
            os.rmdir(specimens)

    def test_newer_manifest_is_refused(self) -> None:
        workspace = self.make()
        edit_json(workspace / ".formwork" / "manifest.json", lambda m: m.__setitem__("foundation_version", "99.0.0"))
        with self.assertRaises(EngineError) as caught:
            render_workspace(workspace)
        self.assertEqual(caught.exception.code, "foundation.downgrade")


class CliTests(WorkspaceCase):
    def run_cli(self, *args: str) -> tuple[int, str]:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(io.StringIO()):
            code = cli_main(list(args))
        return code, stream.getvalue()

    def test_exit_codes(self) -> None:
        self.assertEqual(self.run_cli("config", "validate", "--firm", str(QUILLMOOR))[0], 0)
        workspace = self.base / "Cli Workspace"
        self.assertEqual(self.run_cli("init", "--profile", str(QUILLMOOR), "--workspace", str(workspace))[0], 0)
        code, output = self.run_cli("render", "--workspace", str(workspace), "--dry-run", "--format", "json")
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(output)["dry_run"])
        self.assertEqual(self.run_cli("render", "--workspace", str(workspace))[0], 0)
        theme = workspace / THEME
        theme.write_text("<ResourceDictionary/>\n", encoding="utf-8")
        self.assertEqual(self.run_cli("render", "--workspace", str(workspace))[0], 1)
        self.assertEqual(self.run_cli("render", "--workspace", str(self.base / "missing"))[0], 2)


if __name__ == "__main__":
    unittest.main()
