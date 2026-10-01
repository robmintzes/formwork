"""Acceptance tests for the generated ui-kit surface.

A firm workspace that lists ``ui-kit`` gets a themed WPF dialog kit inside its
extension (``lib/<namespace>_ui``) and a read-only ``UI Kit Demo`` button. WPF
reports a missing resource key only when a window is shown, so these tests
resolve every key statically. Nothing here is live-verified in Revit.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
import xml.etree.ElementTree as ElementTree

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from formwork_engine.adapters import render_all  # noqa: E402
from formwork_engine.checks import check_outputs  # noqa: E402
from formwork_engine.diagnostics import Diagnostics  # noqa: E402
from formwork_engine.profile import load_profile  # noqa: E402
from formwork_engine.workspace import init_workspace, render_workspace, validate_firm  # noqa: E402
from validators.check_bundle_structure import validate_bundle_structure  # noqa: E402
from validators.check_safety_rules import find_violations  # noqa: E402
from validators.validate_toolbar_spec import validate_toolbar_spec  # noqa: E402

QUILLMOOR = REPO / "profiles" / "quillmoor"
BIMXBERT = REPO / "profiles" / "bimxbert"
PROFILES = (
    ("Quillmoor", "quillmoor", QUILLMOOR, "Starter"),
    ("BIMxBert", "bimxbert", BIMXBERT, "Foundation"),
)
XAML_KEY = "{http://schemas.microsoft.com/winfx/2006/xaml}Key"
REFERENCE = re.compile(r"\{(?:Dynamic|Static)Resource\s+([^}\s]+)\}")
DICTIONARIES = ("Theme.xaml", "Controls.xaml", "Icons.xaml")
DIALOGS = ("ResultDialog.xaml", "ChooserDialog.xaml", "SelectionDialog.xaml")
FORBIDDEN = re.compile(r"rgdt|rockwell|robmintzes", re.IGNORECASE)
PYTHON_MODULES = ("__init__", "bootstrap", "result_model", "result_dialog", "chooser_dialog", "selection_dialog")


def edit_json(path: Path, mutate) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def xaml_keys(root: ElementTree.Element) -> list[str]:
    return [node.attrib[XAML_KEY] for node in root.iter() if XAML_KEY in node.attrib]


def xaml_references(root: ElementTree.Element) -> list[str]:
    found: list[str] = []
    for node in root.iter():
        for value in list(node.attrib.values()) + [node.text or ""]:
            found.extend(REFERENCE.findall(value))
    return found


def unresolved_keys(package: Path) -> list[tuple[str, str]]:
    """(file, key) for every Dynamic/StaticResource reference no dictionary defines."""
    defined: set[str] = set()
    for name in DICTIONARIES:
        defined.update(xaml_keys(ElementTree.parse(package / name).getroot()))
    problems = []
    for name in DICTIONARIES + DIALOGS:
        for key in xaml_references(ElementTree.parse(package / name).getroot()):
            if key not in defined:
                problems.append((name, key))
    return problems


class UiKitCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ui kit ")
        self.base = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def workspace(self, profile: Path, name: str, mutate=None) -> Path:
        firm = self.base / ("profile " + name)
        shutil.copytree(profile, firm)
        if mutate:
            edit_json(firm / "firm.json", mutate)
        root = self.base / ("Workspace " + name)
        init_workspace(firm, root)
        report = render_workspace(root)
        self.assertEqual(report["summary"]["outcome"], "pass", report["diagnostics"])
        self.report = report
        return root

    @staticmethod
    def package(root: Path, extension: str, namespace: str) -> Path:
        return root / "extensions" / (extension + ".extension") / "lib" / (namespace + "_ui")

    @staticmethod
    def kit_paths(root: Path) -> list[str]:
        manifest = json.loads((root / ".formwork" / "manifest.json").read_text(encoding="utf-8"))
        return sorted(rel for rel, entry in manifest["files"].items() if entry["adapter"] == "ui-kit")


class GeneratedFilesTests(UiKitCase):
    def test_files_exist_and_are_managed_for_both_profiles(self) -> None:
        for extension, namespace, profile, panel in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, namespace)
                package = self.package(root, extension, namespace)
                for name in tuple(m + ".py" for m in PYTHON_MODULES) + DICTIONARIES + DIALOGS + ("assets/symbol-inverse.png",):
                    self.assertTrue((package / name).is_file(), name)
                demo = root / "extensions" / (extension + ".extension") / (extension + ".tab") / (panel + ".panel") / "UIKitDemo.pushbutton"
                for name in ("bundle.yaml", "script.py", "icon.png", "icon.dark.png"):
                    self.assertTrue((demo / name).is_file(), name)
                self.assertTrue((root / "extensions" / (extension + ".extension") / "tests" / "test_ui_kit_contract.py").is_file())
                self.assertTrue((root / "docs" / "toolbar" / "tools" / "ui-kit-demo.md").is_file())
                manifest = json.loads((root / ".formwork" / "manifest.json").read_text(encoding="utf-8"))
                paths = self.kit_paths(root)
                self.assertGreaterEqual(len(paths), 19)
                for rel in paths:
                    self.assertEqual(manifest["files"][rel]["ownership"], "managed", rel)
                self.assertIn("ui-kit.not-live-verified", [d["code"] for d in self.report["diagnostics"]])

    def test_packaged_fonts_and_licences_are_copied_inside_the_extension(self) -> None:
        root = self.workspace(BIMXBERT, "fonts")
        package = self.package(root, "BIMxBert", "bimxbert")
        for family in ("barlow-condensed", "geist", "geist-mono"):
            files = sorted(p.name for p in (package / "fonts" / family).iterdir())
            self.assertIn("OFL.txt", files)
            self.assertTrue(any(name.endswith(".ttf") for name in files), family)
        theme = (package / "Theme.xaml").read_text(encoding="utf-8")
        self.assertIn("fonts/geist/#Geist", theme)
        self.assertNotIn("assets/fonts", theme)  # extension code never reaches into workspace assets/
        self.assertNotIn("..", re.sub(r"<!--.*?-->", "", theme, flags=re.DOTALL))
        # The system-font profile packages nothing and still resolves.
        quill = self.workspace(QUILLMOOR, "system fonts")
        self.assertFalse((self.package(quill, "Quillmoor", "quillmoor") / "fonts").exists())

    def test_lucide_licence_reaches_the_third_party_notices(self) -> None:
        root = self.workspace(QUILLMOOR, "notices")
        notices = (root / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("Lucide", notices)
        self.assertIn("ISC License", notices)
        self.assertIn("The MIT License (MIT) (for portions derived from Feather)", notices)
        self.assertIn("Icons.xaml", notices)
        icons = (self.package(root, "Quillmoor", "quillmoor") / "Icons.xaml").read_text(encoding="utf-8")
        self.assertIn("Lucide", icons)
        self.assertIn("ISC", icons)
        # Not enabled: notices say nothing is packaged.
        plain = self.workspace(QUILLMOOR, "plain", lambda c: c["surfaces"].remove("ui-kit"))
        self.assertIn("_No icon sets are packaged._", (plain / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8"))

    def test_no_foreign_identity_in_generated_kit_files(self) -> None:
        for extension, namespace, profile, _ in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, "leak " + namespace)
                paths = self.kit_paths(root)
                text_paths = [rel for rel in paths if not rel.endswith((".png", ".ttf", ".otf"))]
                self.assertGreater(len(text_paths), 15)
                config = json.loads((profile / "firm.json").read_text(encoding="utf-8"))
                # Profile-supplied identity (the support URL) is the firm's own data, not kit content.
                own = config["identity"]["links"]["support"]
                for rel in text_paths:
                    text = (root / rel).read_text(encoding="utf-8").replace(own, "")
                    self.assertIsNone(FORBIDDEN.search(text), rel)
                self.assertIsNone(FORBIDDEN.search((root / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")), "notices")
                # The other firm's identity never leaks either.
                other = "bimxbert" if namespace == "quillmoor" else "quillmoor"
                for rel in text_paths:
                    self.assertNotIn(other, (root / rel).read_text(encoding="utf-8").lower(), rel)


class XamlResolutionTests(UiKitCase):
    def test_every_xaml_file_parses_and_every_key_resolves(self) -> None:
        for extension, namespace, profile, _ in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, "xaml " + namespace)
                package = self.package(root, extension, namespace)
                for name in DICTIONARIES + DIALOGS:
                    ElementTree.parse(package / name)
                self.assertEqual(unresolved_keys(package), [])
                keys = xaml_keys(ElementTree.parse(package / "Controls.xaml").getroot())
                self.assertEqual(len(keys), len(set(keys)))
                prefix = extension if extension == "Quillmoor" else "Bimxbert"
                self.assertTrue(all(key.startswith(prefix + ".") for key in keys), [k for k in keys if not k.startswith(prefix + ".")])

    def test_the_resolution_check_catches_a_typo(self) -> None:
        root = self.workspace(QUILLMOOR, "typo")
        package = self.package(root, "Quillmoor", "quillmoor")
        broken = self.base / "broken"
        shutil.copytree(package, broken)
        dialog = broken / "ResultDialog.xaml"
        dialog.write_text(dialog.read_text(encoding="utf-8").replace("Quillmoor.Titlebar.Label", "Quillmoor.Titlebar.Lable"), encoding="utf-8")
        self.assertEqual(unresolved_keys(broken), [("ResultDialog.xaml", "Quillmoor.Titlebar.Lable")])

    def test_kit_covers_the_ported_control_families(self) -> None:
        root = self.workspace(QUILLMOOR, "families")
        keys = set(xaml_keys(ElementTree.parse(self.package(root, "Quillmoor", "quillmoor") / "Controls.xaml").getroot()))
        for suffix in (
            "Button.Primary", "Button.Secondary", "Chip", "ListItem", "Card", "Badge.Info", "Badge.Danger",
            "Field", "Field.Mono", "Check", "Radio", "Callout.Info", "Callout.Warn", "Callout.Danger", "Callout.Success",
            "Progress", "Output.Log", "Titlebar", "Titlebar.CloseButton", "Step.Number", "Step.Title", "Caption",
            "Hairline", "Section", "Stat.Tile", "Stat.Key", "Stat.Value", "ListBox",
        ):
            self.assertIn("Quillmoor." + suffix, keys)
        icons = set(xaml_keys(ElementTree.parse(self.package(root, "Quillmoor", "quillmoor") / "Icons.xaml").getroot()))
        for name in ("UsageReusable", "UsageSetup", "UsageOneTime", "AlertTriangle", "CheckCircle", "X"):
            self.assertIn("Quillmoor.Icon." + name, icons)

    def test_dialog_chrome_contract(self) -> None:
        root = self.workspace(QUILLMOOR, "chrome")
        package = self.package(root, "Quillmoor", "quillmoor")
        presentation = "{http://schemas.microsoft.com/winfx/2006/xaml/presentation}"
        for name in ("ResultDialog.xaml", "ChooserDialog.xaml"):
            window = ElementTree.parse(package / name).getroot()
            self.assertEqual(window.attrib["Width"], "560", name)  # compact size class
            self.assertEqual(window.attrib["SizeToContent"], "Height", name)
            self.assertEqual(window.attrib["WindowStyle"], "None", name)
            self.assertNotIn("MinHeight", window.attrib)
            self.assertEqual(window.attrib["TextOptions.TextRenderingMode"], "Grayscale", name)
        selector = ElementTree.parse(package / "SelectionDialog.xaml").getroot()
        self.assertEqual((selector.attrib["Width"], selector.attrib["Height"]), ("640", "560"))
        # Every kit window uses the same WPF-drawn frame: a resizable WindowStyle=None
        # window showed a system resize strip over the titlebar in Revit 2026.
        for name in ("ResultDialog.xaml", "ChooserDialog.xaml", "SelectionDialog.xaml"):
            window = ElementTree.parse(package / name).getroot()
            self.assertEqual(window.attrib["ResizeMode"], "NoResize", name)
            self.assertEqual(window.attrib["AllowsTransparency"], "True", name)
            self.assertEqual(window.attrib["Background"], "Transparent", name)
        result = ElementTree.parse(package / "ResultDialog.xaml").getroot()
        buttons = {b.attrib.get("{http://schemas.microsoft.com/winfx/2006/xaml}Name"): b for b in result.iter(presentation + "Button")}
        self.assertNotIn("MinimizeBtn", buttons)  # a modal dialog gets no minimize
        self.assertEqual(buttons["ActionBtn"].attrib["Grid.Column"], "3")  # primary rightmost
        chooser = ElementTree.parse(package / "ChooserDialog.xaml").getroot()
        confirm = next(b for b in chooser.iter(presentation + "Button") if b.attrib.get("{http://schemas.microsoft.com/winfx/2006/xaml}Name") == "ConfirmBtn")
        self.assertEqual(confirm.attrib["IsDefault"], "True")

    def test_appearance_change_changes_controls_and_labels(self) -> None:
        base = self.workspace(QUILLMOOR, "shape-base")
        package = self.package(base, "Quillmoor", "quillmoor")
        before = (package / "Controls.xaml").read_text(encoding="utf-8")

        def square_uppercase(config) -> None:
            config["appearance"]["button"]["shape"] = "square"
            config["appearance"]["button"]["label_case"] = "uppercase"
            config["appearance"]["badge"]["label_case"] = "uppercase"

        changed = self.workspace(QUILLMOOR, "shape-changed", square_uppercase)
        package_changed = self.package(changed, "Quillmoor", "quillmoor")
        after = (package_changed / "Controls.xaml").read_text(encoding="utf-8")
        self.assertNotEqual(before, after)
        self.assertIn('CornerRadius="18"', before)  # pill, 36 DIP control
        self.assertNotIn('CornerRadius="18"', after)
        self.assertIn("COPY LOG", (package_changed / "ResultDialog.xaml").read_text(encoding="utf-8"))
        self.assertIn("Copy log", (package / "ResultDialog.xaml").read_text(encoding="utf-8"))
        self.assertIn("BUTTON_UPPERCASE = True", (package_changed / "bootstrap.py").read_text(encoding="utf-8"))
        self.assertIn("BUTTON_UPPERCASE = False", (package / "bootstrap.py").read_text(encoding="utf-8"))
        self.assertEqual(unresolved_keys(package_changed), [])

    def test_specimen_controls_are_the_base_of_the_kit_controls(self) -> None:
        # Shared token logic: every style the specimen defines is defined, unchanged, in the kit.
        root = self.workspace(BIMXBERT, "shared")
        specimen = (root / "specimens" / "wpf" / "Controls.xaml").read_text(encoding="utf-8")
        kit = (self.package(root, "BIMxBert", "bimxbert") / "Controls.xaml").read_text(encoding="utf-8")
        body = specimen[specimen.index("<Style"): specimen.rindex("</ResourceDictionary>")].strip()
        self.assertIn(body, kit)
        # Theme differs only in where packaged fonts resolve from.
        theme_specimen = (root / "specimens" / "wpf" / "Theme.xaml").read_text(encoding="utf-8")
        theme_kit = (self.package(root, "BIMxBert", "bimxbert") / "Theme.xaml").read_text(encoding="utf-8")
        self.assertEqual(
            theme_specimen.replace("../../assets/fonts/", "fonts/"),
            theme_kit,
        )


class PythonModuleTests(UiKitCase):
    def test_generated_python_passes_the_ironpython_guard(self) -> None:
        for _, namespace, profile, _ in PROFILES:
            with self.subTest(profile=namespace):
                diags = Diagnostics()
                loaded = load_profile(profile, diags)
                self.assertIsNotNone(loaded, diags.items)
                rendered = render_all(loaded)
                checked = Diagnostics()
                check_outputs(rendered.files, checked)
                self.assertEqual([d for d in checked.items if d.severity == "error"], [])
                kit_python = [f for f in rendered.files if f.adapter == "ui-kit" and f.path.endswith(".py")]
                self.assertGreaterEqual(len(kit_python), 8)
                for item in kit_python:
                    text = item.content.decode("utf-8")
                    self.assertTrue(text.isascii(), item.path)
                    self.assertNotIn("ModuleNotFoundError", text, item.path)
                    self.assertNotRegex(text, r"(?m)^\s*except\s+\w+\s*,", item.path)
                    if not item.path.endswith(("test_ui_kit_contract.py", "script.py", "__init__.py", "result_model.py")):
                        self.assertIn("from __future__ import absolute_import", text, item.path)

    def test_demo_is_read_only_and_validates_context_first(self) -> None:
        root = self.workspace(QUILLMOOR, "demo")
        script = (root / "extensions/Quillmoor.extension/Quillmoor.tab/Starter.panel/UIKitDemo.pushbutton/script.py").read_text(encoding="utf-8")
        for needle in ("Transaction", "StartTransaction", "SubTransaction", ".Commit(", "doc.Delete", ".Create"):
            self.assertNotIn(needle, script)
        body = script[script.index("def main"):]
        self.assertLess(body.index("doc is None"), body.index("chooser_dialog.ask"))
        self.assertLess(body.index("chooser_dialog.ask"), body.index("selection_dialog.show"))
        self.assertLess(body.index("selection_dialog.show"), body.rindex("_show("))
        self.assertIn("MAX_VIEWS = 50", script)
        self.assertIn("from quillmoor_ui import chooser_dialog, result_dialog, selection_dialog", script)
        self.assertEqual(find_violations(root), [])

    def test_pure_logic_and_stubbed_import_of_every_module(self) -> None:
        root = self.workspace(BIMXBERT, "import")
        lib = root / "extensions" / "BIMxBert.extension" / "lib"
        # A WPF-free host: the kit's modules import clr/System/pyrevit at module scope.
        stubs = {
            name: mock.MagicMock()
            for name in (
                "clr", "System", "System.Windows", "System.Windows.Controls", "System.Windows.Input",
                "System.Windows.Markup", "System.Windows.Media", "System.Windows.Media.Imaging",
                "System.Windows.Shapes", "System.Windows.Threading", "pyrevit",
            )
        }
        forms = types.ModuleType("pyrevit.forms")
        forms.WPFWindow = type("WPFWindow", (), {})
        stubs["pyrevit.forms"] = forms
        stubs["pyrevit"].forms = forms
        saved_path = list(sys.path)
        try:
            with mock.patch.dict(sys.modules, stubs):
                sys.path.insert(0, str(lib))
                package = importlib.import_module("bimxbert_ui")
                self.assertTrue(Path(package.__file__).is_relative_to(lib))
                bootstrap = importlib.import_module("bimxbert_ui.bootstrap")
                chooser = importlib.import_module("bimxbert_ui.chooser_dialog")
                selection = importlib.import_module("bimxbert_ui.selection_dialog")
                importlib.import_module("bimxbert_ui.result_dialog")
                model = importlib.import_module("bimxbert_ui.result_model")

                self.assertEqual(chooser.normalize_options(["a"]), [("a", "a", "")])
                self.assertEqual(chooser.normalize_options([("k", "Label")]), [("k", "Label", "")])
                self.assertEqual(chooser.normalize_options([("k", "Label", "More")]), [("k", "Label", "More")])
                self.assertEqual(chooser.normalize_options([{"key": "k", "label": "L", "detail": "D"}]), [("k", "L", "D")])
                self.assertEqual(chooser.normalize_options([{"label": "no key"}, None]), [])
                self.assertEqual(chooser.normalize_options(None), [])
                self.assertEqual(selection.filter_labels(["Level 01", "Roof"], " LEVEL "), [0])
                self.assertEqual(selection.filter_labels(["a", "b"], ""), [0, 1])

                self.assertEqual(bootstrap.button_text("Close"), "Close")  # as-written profile
                self.assertEqual(sorted(bootstrap.USAGE), ["one-time", "reusable", "setup"])
                self.assertEqual(bootstrap.USAGE["setup"][1], "Bimxbert.Icon.UsageSetup")
                with self.assertRaises(ValueError):
                    bootstrap.apply_theme(None)

                result = model.ToolResult.from_dict({"status": "success", "summary": "ok", "log": ["x", "y"], "counts": {"ok": 2}})
                self.assertEqual((result.heading, result.log_text, result.counts["fail"]), ("Success", "x\ny", 0))
                self.assertEqual(model.ToolResult.from_dict({"status": "bogus"}).status, "failed")
                self.assertEqual(model.ToolResult("canceled", "", {}, [], []).heading, "Canceled")
        finally:
            sys.path[:] = saved_path
            for name in [n for n in sys.modules if n == "bimxbert_ui" or n.startswith("bimxbert_ui.")]:
                del sys.modules[name]

    def test_importing_the_package_needs_no_wpf(self) -> None:
        root = self.workspace(QUILLMOOR, "bare import")
        lib = root / "extensions" / "Quillmoor.extension" / "lib"
        code = "import sys; sys.path.insert(0, sys.argv[1]); import quillmoor_ui; from quillmoor_ui.result_model import ToolResult; print(ToolResult.from_dict({'status':'success'}).heading)"
        completed = subprocess.run([sys.executable, "-c", code, str(lib)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "Success")

    def test_the_generated_contract_test_passes_in_the_workspace(self) -> None:
        for extension, namespace, profile, _ in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, "contract " + namespace)
                completed = subprocess.run(
                    [sys.executable, "-m", "unittest", "discover", "-s", "extensions/{}.extension/tests".format(extension), "-p", "test_ui_kit_contract.py"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                self.assertIn("Ran 9 tests", completed.stderr)


class FoundationValidatorTests(UiKitCase):
    def test_foundation_validators_pass_on_the_workspace(self) -> None:
        for _, namespace, profile, _ in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, "validators " + namespace)
                errors, _warnings = validate_bundle_structure(root)
                self.assertEqual(errors, [])
                _stats, spec_errors = validate_toolbar_spec(root)
                self.assertEqual(spec_errors, [])
                self.assertEqual(find_violations(root), [])
                fragment = (root / "docs" / "toolbar" / "spec.d" / "foundation-sample.md").read_text(encoding="utf-8")
                self.assertIn("id: ui-kit-demo", fragment)
                self.assertIn("id: hello-button", fragment)
                bundle = next(root.rglob("UIKitDemo.pushbutton/bundle.yaml")).read_text(encoding="utf-8")
                self.assertIn("title: UI Kit Demo", bundle)
                self.assertIn("help_url:", bundle)
                self.assertIn("author:", bundle)

    def test_without_the_surface_the_sample_is_unchanged(self) -> None:
        # web-host appends its own entry to the fragment, so it is off here too.
        root = self.workspace(QUILLMOOR, "no kit", lambda c: [c["surfaces"].remove("ui-kit"), c["surfaces"].remove("web-host")])
        fragment = (root / "docs" / "toolbar" / "spec.d" / "foundation-sample.md").read_text(encoding="utf-8")
        self.assertNotIn("ui-kit-demo", fragment)
        self.assertTrue(fragment.endswith("HelloButton.pushbutton\n```\n"), fragment[-120:])
        self.assertFalse((root / "docs" / "toolbar" / "tools" / "ui-kit-demo.md").exists())
        self.assertFalse(list(root.rglob("UIKitDemo.pushbutton")))
        self.assertFalse((root / "extensions" / "Quillmoor.extension" / "lib" / "quillmoor_ui").exists())

    def test_the_surface_requires_the_sample(self) -> None:
        firm = self.base / "needs sample"
        shutil.copytree(QUILLMOOR, firm)
        edit_json(firm / "firm.json", lambda c: c.update(surfaces=["ui-kit", "wpf-specimen"]))
        report = validate_firm(firm)
        self.assertEqual(report["summary"]["outcome"], "fail")
        self.assertIn("config.surface-requires", [d["code"] for d in report["diagnostics"]])

    def test_second_render_is_a_no_op(self) -> None:
        root = self.workspace(QUILLMOOR, "repeat")
        again = render_workspace(root)
        self.assertEqual(again["summary"]["outcome"], "pass")
        self.assertEqual(again["summary"]["changes"], 0)
        self.assertEqual(again["summary"]["conflicts"], 0)
        self.assertEqual(set(again["summary"]["actions"]) - {"unchanged", "skip"}, set())

    def test_schema_and_config_list_the_surface(self) -> None:
        schema = json.loads((REPO / "schemas" / "firm-config.v1.schema.json").read_text(encoding="utf-8"))
        self.assertIn("ui-kit", schema["properties"]["surfaces"]["items"]["enum"])
        for profile in (QUILLMOOR, BIMXBERT):
            self.assertIn("ui-kit", json.loads((profile / "firm.json").read_text(encoding="utf-8"))["surfaces"])


if __name__ == "__main__":
    unittest.main()
