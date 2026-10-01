"""Acceptance tests for the generated revit-addin surface.

A firm workspace that lists ``revit-addin`` gets a C# add-in starter under
``addins/<Extension>.Addin/``. These tests check the files statically, check the
identity rules (stable AddInId, assembly name and namespace), and, when ``dotnet``
and a Revit install are present, really build the project offline. A successful
build proves only that the code compiles against the installed Revit API; nothing
here loads the add-in in Revit.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import xml.etree.ElementTree as ElementTree

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from toolkit_engine.adapters import render_all, revit_addin  # noqa: E402
from toolkit_engine.checks import check_outputs  # noqa: E402
from toolkit_engine.diagnostics import Diagnostics  # noqa: E402
from toolkit_engine.outputs import text_file  # noqa: E402
from toolkit_engine.profile import load_profile  # noqa: E402
from toolkit_engine.textutil import cs_string, msbuild_text  # noqa: E402
from toolkit_engine.workspace import init_workspace, render_workspace, validate_firm  # noqa: E402
from validators.check_bundle_structure import validate_bundle_structure  # noqa: E402
from validators.check_safety_rules import find_violations  # noqa: E402
from validators.validate_toolbar_spec import validate_toolbar_spec  # noqa: E402

QUILLMOOR = REPO / "profiles" / "quillmoor"
BIMXBERT = REPO / "profiles" / "bimxbert"
# (extension, namespace, profile, sample panel)
PROFILES = (
    ("Quillmoor", "quillmoor", QUILLMOOR, "Starter"),
    ("BIMxBert", "bimxbert", BIMXBERT, "Foundation"),
)
FORBIDDEN = re.compile(r"robmintzes|placeholder|rgdt|rockwell", re.IGNORECASE)
TEXT_SUFFIXES = (".cs", ".csproj", ".addin", ".xaml", ".md", ".gitignore")
REVIT_ROOT = Path(r"C:\Program Files\Autodesk")
BUILD_ENV = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1", DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1")


def edit_json(path: Path, mutate) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def addin_dir(root: Path, extension: str) -> Path:
    return root / "addins" / (extension + ".Addin")


def manifest_id(root: Path, extension: str) -> str:
    tree = ElementTree.parse(addin_dir(root, extension) / (extension + ".Addin.addin"))
    return tree.getroot().find("AddIn/AddInId").text  # type: ignore[union-attr]


def addin_text_files(root: Path, extension: str) -> list[Path]:
    base = addin_dir(root, extension)
    return sorted(p for p in base.rglob("*") if p.is_file() and (p.suffix in TEXT_SUFFIXES or p.name == ".gitignore"))


class AddinCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="revit addin ")
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


class GeneratedFilesTests(AddinCase):
    def test_files_exist_and_are_managed_for_both_profiles(self) -> None:
        for extension, namespace, profile, _panel in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, namespace)
                base = addin_dir(root, extension)
                names = (
                    extension + ".Addin.csproj",
                    extension + ".Addin.addin",
                    "App.cs",
                    "HelloCommand.cs",
                    "SummaryWindow.cs",
                    "ThemeResources.cs",
                    "README.md",
                    ".gitignore",
                    "Resources/Theme.xaml",
                    "Resources/Controls.xaml",
                    "Resources/SummaryWindow.xaml",
                    "Resources/symbol-light.png",
                    "Resources/symbol-inverse.png",
                    "Resources/icon-32.png",
                    "Resources/icon-16.png",
                )
                for name in names:
                    self.assertTrue((base / name).is_file(), name)
                manifest = json.loads((root / ".toolkit" / "manifest.json").read_text(encoding="utf-8"))
                owned = [rel for rel, entry in manifest["files"].items() if entry["adapter"] == "revit-addin"]
                self.assertGreaterEqual(len(owned), len(names))
                for rel in owned:
                    self.assertEqual(manifest["files"][rel]["ownership"], "managed", rel)
                    self.assertTrue(rel.startswith("addins/"), rel)
                ignore = (base / ".gitignore").read_text(encoding="utf-8").split()
                self.assertIn("bin/", ignore)
                self.assertIn("obj/", ignore)
                self.assertIn("revit-addin.not-live-verified", [d["code"] for d in self.report["diagnostics"]])

    def test_packaged_fonts_ship_beside_the_project_and_the_theme_names_them(self) -> None:
        root = self.workspace(BIMXBERT, "fonts")
        base = addin_dir(root, "BIMxBert")
        for family in ("barlow-condensed", "geist", "geist-mono"):
            files = sorted(p.name for p in (base / "fonts" / family).iterdir())
            self.assertIn("OFL.txt", files)
            self.assertTrue(any(name.endswith(".ttf") for name in files), family)
        self.assertIn("fonts/geist/#Geist", (base / "Resources" / "Theme.xaml").read_text(encoding="utf-8"))
        quill = self.workspace(QUILLMOOR, "no-fonts")
        self.assertFalse((addin_dir(quill, "Quillmoor") / "fonts").exists())

    def test_csproj_is_offline_wpf_with_the_documented_properties(self) -> None:
        for extension, _namespace, profile, _panel in PROFILES:
            with self.subTest(extension=extension):
                root = self.workspace(profile, extension)
                path = addin_dir(root, extension) / (extension + ".Addin.csproj")
                text = path.read_text(encoding="utf-8")
                project = ElementTree.fromstring(text)
                self.assertEqual(project.attrib["Sdk"], "Microsoft.NET.Sdk")
                self.assertEqual(project.findall(".//PackageReference"), [])
                self.assertNotIn("PackageDownload", text)
                values = {}
                for prop in project.findall("PropertyGroup/*"):
                    values.setdefault(prop.tag, (prop.text or "").strip())
                self.assertEqual(values["UseWPF"], "true")
                self.assertEqual(values["Nullable"], "enable")
                self.assertEqual(values["LangVersion"], "latest")
                self.assertEqual(values["AssemblyName"], extension + ".Addin")
                self.assertEqual(values["AssemblyVersion"], "1.0.0.0")
                self.assertEqual(values["OutputPath"], "bin\\$(Configuration)\\$(RevitVersion)\\")
                self.assertIn("2026", text)
                self.assertIn("C:\\Program Files\\Autodesk\\Revit $(RevitVersion)\\", text)
                references = {r.attrib["Include"]: r for r in project.findall("ItemGroup/Reference")}
                self.assertEqual(sorted(references), ["RevitAPI", "RevitAPIUI"])
                for reference in references.values():
                    self.assertEqual(reference.find("Private").text, "false")
                embedded = sorted(e.attrib["LogicalName"] for e in project.findall("ItemGroup/EmbeddedResource"))
                self.assertEqual(
                    embedded,
                    sorted(
                        "Resources." + name
                        for name in (
                            "Theme.xaml",
                            "Controls.xaml",
                            "SummaryWindow.xaml",
                            "symbol-light.png",
                            "symbol-inverse.png",
                            "icon-32.png",
                            "icon-16.png",
                        )
                    ),
                )
                for logical in embedded:
                    name = logical.split(".", 1)[1]
                    self.assertTrue((path.parent / "Resources" / name).is_file(), name)
                for unsupported in ("2024", "TKADDIN001"):
                    self.assertIn(unsupported, text)

    def test_xaml_and_manifest_are_well_formed_and_every_style_key_resolves(self) -> None:
        for extension, _namespace, profile, _panel in PROFILES:
            with self.subTest(extension=extension):
                root = self.workspace(profile, extension)
                base = addin_dir(root, extension)
                xaml_key = "{http://schemas.microsoft.com/winfx/2006/xaml}Key"
                defined = set()
                for name in ("Theme.xaml", "Controls.xaml"):
                    tree = ElementTree.parse(base / "Resources" / name).getroot()
                    defined.update(node.attrib[xaml_key] for node in tree.iter() if xaml_key in node.attrib)
                window = ElementTree.parse(base / "Resources" / "SummaryWindow.xaml").getroot()
                reference = re.compile(r"\{(?:Dynamic|Static)Resource\s+([^}\s]+)\}")
                used = set()
                for node in window.iter():
                    for value in node.attrib.values():
                        used.update(reference.findall(value))
                self.assertTrue(used)
                self.assertEqual(sorted(used - defined), [])
                # Names the C# code looks up must exist.
                names = {node.attrib.get("{http://schemas.microsoft.com/winfx/2006/xaml}Name") for node in window.iter()}
                code = (base / "SummaryWindow.cs").read_text(encoding="utf-8")
                for name in re.findall(r'Find<\w+>\(window, "(\w+)"\)', code):
                    self.assertIn(name, names)
                ElementTree.parse(base / (extension + ".Addin.addin"))

    def test_command_is_read_only_and_the_manifest_points_at_the_app(self) -> None:
        root = self.workspace(QUILLMOOR, "command")
        base = addin_dir(root, "Quillmoor")
        command = (base / "HelloCommand.cs").read_text(encoding="utf-8")
        self.assertIn("[Transaction(TransactionMode.ReadOnly)]", command)
        self.assertIn("IsFamilyDocument", command)
        self.assertIn("IsTemplate", command)
        self.assertIn("FilteredElementCollector", command)
        for text in addin_text_files(root, "Quillmoor"):
            if text.suffix == ".cs":
                self.assertNotRegex(text.read_text(encoding="utf-8"), r"new\s+Transaction|SubTransaction|TransactionGroup", text.name)
        addin = ElementTree.parse(base / "Quillmoor.Addin.addin").getroot().find("AddIn")
        self.assertEqual(addin.attrib["Type"], "Application")
        self.assertEqual(addin.find("FullClassName").text, "Quillmoor.Addin.App")
        self.assertEqual(addin.find("Assembly").text, "Quillmoor.Addin\\Quillmoor.Addin.dll")
        self.assertEqual(addin.find("VendorId").text, "quillmoor")
        self.assertIn("class App : IExternalApplication", (base / "App.cs").read_text(encoding="utf-8"))

    def test_ribbon_uses_the_firm_tab_and_a_distinct_panel_name(self) -> None:
        for extension, _namespace, profile, panel in PROFILES:
            with self.subTest(extension=extension):
                root = self.workspace(profile, extension)
                app = (addin_dir(root, extension) / "App.cs").read_text(encoding="utf-8")
                self.assertIn('TabName = "{}"'.format(extension), app)
                self.assertIn('PanelName = "{} Add-in"'.format(panel), app)
                self.assertIn("Autodesk.Revit.Exceptions.ArgumentException", app)
                self.assertIn('"Hello Add-in"', app)

    def test_readme_documents_build_install_and_what_is_unverified(self) -> None:
        root = self.workspace(QUILLMOOR, "readme")
        readme = " ".join((addin_dir(root, "Quillmoor") / "README.md").read_text(encoding="utf-8").split())
        self.assertIn(
            "dotnet build addins\\Quillmoor.Addin\\Quillmoor.Addin.csproj -c Release -p:RevitVersion=2026",
            readme,
        )
        for expected in (
            "%APPDATA%\\Autodesk\\Revit\\Addins\\<year>\\",
            "C:\\Program Files\\Autodesk\\Revit\\Addins\\2027\\",
            "not covered",
            "TKADDIN001",
            "does **not** prove Revit loads the add-in",
            revit_addin.addin_id("quillmoor-design-technology"),
        ):
            self.assertIn(expected, readme)

    def test_icons_are_deterministic_and_the_right_size(self) -> None:
        from toolkit_engine.png import read_png_size

        profile = load_profile(QUILLMOOR, Diagnostics())
        for size in (16, 32):
            first = revit_addin.draw_ribbon_icon(profile, size)
            self.assertEqual(first, revit_addin.draw_ribbon_icon(profile, size))
            self.assertEqual(read_png_size(first), (size, size))
        root = self.workspace(QUILLMOOR, "icons")
        icon = (addin_dir(root, "Quillmoor") / "Resources" / "icon-32.png").read_bytes()
        self.assertEqual(icon, revit_addin.draw_ribbon_icon(profile, 32))


class IdentityTests(AddinCase):
    def test_addin_id_is_stable_across_rebrand_and_repeated_renders(self) -> None:
        first = self.workspace(QUILLMOOR, "plain")
        # A second, separate render of the same profile in a different folder.
        second = self.base / "Workspace again"
        init_workspace(self.base / "profile plain", second)
        self.assertEqual(render_workspace(second)["summary"]["outcome"], "pass")

        def rebrand(config) -> None:
            config["identity"]["display_name"] = "Renamed Quill Atelier"
            config["identity"]["short_name"] = "RQA"
            config["identity"]["author"] = "Renamed Quill Atelier Digital Practice"
            config["identity"]["logo_alt"] = "Renamed Quill Atelier"

        rebranded = self.workspace(QUILLMOOR, "rebrand", rebrand)
        ids = {manifest_id(root, "Quillmoor") for root in (first, second, rebranded)}
        self.assertEqual(len(ids), 1, ids)
        self.assertEqual(ids.pop(), revit_addin.addin_id("quillmoor-design-technology"))
        self.assertRegex(manifest_id(first, "Quillmoor"), r"^[0-9A-F]{8}(-[0-9A-F]{4}){3}-[0-9A-F]{12}$")
        # Display strings follow the brand; technical names do not.
        base_a, base_b = addin_dir(first, "Quillmoor"), addin_dir(rebranded, "Quillmoor")
        self.assertIn("Renamed Quill Atelier", (base_b / "Quillmoor.Addin.addin").read_text(encoding="utf-8"))
        self.assertNotIn("Renamed", (base_a / "Quillmoor.Addin.addin").read_text(encoding="utf-8"))
        for name in ("App.cs", "HelloCommand.cs", "ThemeResources.cs", "SummaryWindow.cs"):
            namespace = re.search(r"^namespace (\S+);", (base_b / name).read_text(encoding="utf-8"), re.MULTILINE)
            self.assertEqual(namespace.group(1), "Quillmoor.Addin", name)
        csproj_b = (base_b / "Quillmoor.Addin.csproj").read_text(encoding="utf-8")
        self.assertIn("<AssemblyName>Quillmoor.Addin</AssemblyName>", csproj_b)
        self.assertIn("<RootNamespace>Quillmoor.Addin</RootNamespace>", csproj_b)

    def test_addin_id_differs_between_profiles_and_follows_only_the_workspace_id(self) -> None:
        quill = self.workspace(QUILLMOOR, "quill")
        bimx = self.workspace(BIMXBERT, "bimx")
        self.assertNotEqual(manifest_id(quill, "Quillmoor"), manifest_id(bimx, "BIMxBert"))
        moved = self.workspace(QUILLMOOR, "moved", lambda c: c["technical"].__setitem__("workspace_id", "quillmoor-other"))
        self.assertNotEqual(manifest_id(moved, "Quillmoor"), manifest_id(quill, "Quillmoor"))
        self.assertEqual(manifest_id(moved, "Quillmoor"), revit_addin.addin_id("quillmoor-other"))

    def test_no_template_or_foundation_maintainer_identity_leaks(self) -> None:
        for extension, namespace, profile, _panel in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, namespace)
                config = json.loads((profile / "firm.json").read_text(encoding="utf-8"))
                support = config["identity"]["links"]["support"]  # a profile's own URL may name its owner
                files = addin_text_files(root, extension)
                self.assertGreaterEqual(len(files), 8)
                for path in files:
                    text = path.read_text(encoding="utf-8").replace(support, "")
                    self.assertIsNone(FORBIDDEN.search(text), path.name)

    def test_surface_needs_no_other_surface(self) -> None:
        root = self.workspace(QUILLMOOR, "alone", lambda c: c.__setitem__("surfaces", ["revit-addin"]))
        self.assertTrue((addin_dir(root, "Quillmoor") / "Quillmoor.Addin.csproj").is_file())
        self.assertFalse((root / "extensions").exists())

    def test_reserved_word_extension_warns_without_failing(self) -> None:
        firm = self.base / "firm"
        shutil.copytree(QUILLMOOR, firm)
        edit_json(firm / "firm.json", lambda c: c["technical"]["pyrevit"].__setitem__("extension", "event"))
        diags = Diagnostics()
        profile = load_profile(firm, diags)
        self.assertIsNotNone(profile)
        result = revit_addin.render(profile)
        warnings = [d for d in result.diagnostics if d.code == "revit-addin.invalid-identifier"]
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].severity, "warning")
        self.assertIn("event", warnings[0].message)
        clean = revit_addin.render(load_profile(QUILLMOOR, Diagnostics()))
        self.assertNotIn("revit-addin.invalid-identifier", [d.code for d in clean.diagnostics])


class EngineIntegrationTests(AddinCase):
    def test_outputs_pass_the_engine_checks_for_both_profiles(self) -> None:
        for _extension, namespace, profile, _panel in PROFILES:
            with self.subTest(profile=namespace):
                diags = Diagnostics()
                loaded = load_profile(profile, diags)
                self.assertIn("revit-addin", loaded.config.surfaces)
                rendered = render_all(loaded)
                check_outputs(rendered.files, diags)
                self.assertFalse(diags.has_errors, [d for d in diags.items if d.severity == "error"])
                self.assertEqual(validate_firm(profile)["summary"]["outcome"], "pass")

    def test_checks_reject_malformed_project_and_manifest_xml_and_non_utf8_csharp(self) -> None:
        for path in ("addins/X.Addin/X.Addin.csproj", "addins/X.Addin/X.Addin.addin"):
            diags = Diagnostics()
            check_outputs([text_file(path, "<Project><Unclosed></Project>", "revit-addin")], diags)
            self.assertIn("output.xml-invalid", diags.codes(), path)
        diags = Diagnostics()
        from toolkit_engine.outputs import OutputFile

        check_outputs([OutputFile("addins/X.Addin/App.cs", b"class A { // \xff\xfe }", "revit-addin")], diags)
        self.assertIn("output.encoding", diags.codes())
        diags = Diagnostics()
        check_outputs([text_file("addins/X.Addin/App.cs", "class A { string s = \"\u00e9\"; }", "revit-addin")], diags)
        self.assertFalse(diags.has_errors)

    def test_foundation_validators_pass_on_the_workspace(self) -> None:
        root = self.workspace(QUILLMOOR, "validators")
        errors, _ = validate_bundle_structure(root)
        self.assertEqual(errors, [])
        _, spec_errors = validate_toolbar_spec(root)
        self.assertEqual(spec_errors, [])
        self.assertEqual(find_violations(root), [])

    def test_second_render_is_a_no_op(self) -> None:
        root = self.workspace(QUILLMOOR, "noop")
        before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
        report = render_workspace(root)
        self.assertEqual(report["summary"]["outcome"], "pass")
        self.assertEqual(report["summary"]["changes"], 0)
        self.assertEqual({p: p.read_bytes() for p in root.rglob("*") if p.is_file()}, before)

    def test_edited_managed_file_blocks_the_next_render(self) -> None:
        root = self.workspace(QUILLMOOR, "edited")
        target = addin_dir(root, "Quillmoor") / "App.cs"
        target.write_text(target.read_text(encoding="utf-8") + "// local edit\n", encoding="utf-8")
        report = render_workspace(root)
        self.assertEqual(report["summary"]["outcome"], "fail")
        self.assertIn("managed-modified", json.dumps(report))


class TextHelperTests(unittest.TestCase):
    def test_cs_string_escapes_for_a_valid_csharp_literal(self) -> None:
        cases = {
            'say "hi"': r'"say \"hi\""',
            "back\\slash": r'"back\\slash"',
            "line1\nline2": r'"line1\nline2"',
            "tab\there": r'"tab\there"',
            "cr\rhere": r'"cr\rhere"',
            "caf\u00e9": r'"caf\u00E9"',
            "smile \U0001F600": r'"smile \uD83D\uDE00"',
            "plain": '"plain"',
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(cs_string(value), expected)
        # Escaped output is single-line ASCII, so it can never end a C# literal early.
        tricky = cs_string('a"b\\c\nd\te\rf\u00e9\U0001F600')
        self.assertTrue(tricky.isascii())
        self.assertNotRegex(tricky, r"[\n\r\t]")

    def test_msbuild_text_escapes_property_metacharacters_then_xml(self) -> None:
        self.assertEqual(msbuild_text("A $(X); 50% <b>"), "A %24(X)%3B 50%25 &lt;b&gt;")


def _dotnet() -> str | None:
    return shutil.which("dotnet")


def _sdk_major() -> int:
    try:
        output = subprocess.run(["dotnet", "--list-sdks"], capture_output=True, text=True, env=BUILD_ENV, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    majors = [int(m.group(1)) for m in re.finditer(r"^(\d+)\.", output, re.MULTILINE)]
    return max(majors) if majors else 0


def _expected_framework(year: int) -> str:
    """Mirror of the csproj rule: .NET 10 for 2027 and for 2025/2026 hosts that moved to it."""
    if year == 2027:
        return "net10.0"
    config = REVIT_ROOT / "Revit {}".format(year) / "AdApplicationFrame.runtimeconfig.json"
    return "net10.0" if config.is_file() and "net10.0" in config.read_text(encoding="utf-8") else "net8.0"


@unittest.skipUnless(_dotnet(), "dotnet is not on PATH")
@unittest.skipUnless(os.name == "nt", "Windows-targeting projects only build on Windows (NETSDK1100 elsewhere)")
class BuildErrorTests(AddinCase):
    """Property errors need dotnet but not a Revit install.

    Revit add-ins target net*-windows, which the .NET SDK refuses to restore on
    other operating systems before the project's own guard targets run.
    """

    def build(self, csproj: Path, *props: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["dotnet", "build", str(csproj), "-c", "Release", "-nologo"] + list(props),
            capture_output=True,
            text=True,
            env=BUILD_ENV,
            timeout=300,
        )

    def test_unsupported_revit_version_names_the_supported_ones(self) -> None:
        root = self.workspace(QUILLMOOR, "unsupported")
        csproj = addin_dir(root, "Quillmoor") / "Quillmoor.Addin.csproj"
        result = self.build(csproj, "-p:RevitVersion=2024")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TKADDIN001", result.stdout)
        self.assertIn("Supported: 2025, 2026 and 2027", result.stdout)
        result = self.build(csproj, "-p:RevitVersion=2026", "-p:RevitTargetFramework=net9.0-windows")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TKADDIN003", result.stdout)

    def test_missing_revit_install_is_a_clear_error_not_a_compiler_cascade(self) -> None:
        root = self.workspace(QUILLMOOR, "missing-api")
        csproj = addin_dir(root, "Quillmoor") / "Quillmoor.Addin.csproj"
        result = self.build(csproj, "-p:RevitVersion=2026", "-p:RevitInstallDir=" + str(self.base / "no revit here") + "\\")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TKADDIN002", result.stdout)
        self.assertNotIn("CS0246", result.stdout)


class DotnetBuildTests(unittest.TestCase):
    """Really compile the generated add-in, offline, against the installed Revit API.

    Compiling proves the code and project are valid for that API; it is not proof
    that Revit loads the add-in.
    """

    durations: list[str] = []

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="revit addin build ")
        cls.base = Path(cls._tmp.name)
        cls.roots: dict[str, Path] = {}
        for extension, namespace, profile, _panel in PROFILES:
            firm = cls.base / ("profile " + namespace)
            shutil.copytree(profile, firm)
            if namespace == "quillmoor":
                # Hostile display text must survive into C# literals and MSBuild properties.
                def accents(config) -> None:
                    config["identity"]["display_name"] = 'Caf\u00e9 "Quill" \\ $(X);50% Studio \U0001F600'
                    config["identity"]["author"] = "Caf\u00e9 Quill Atelier"

                edit_json(firm / "firm.json", accents)
            root = cls.base / ("Workspace " + namespace)
            init_workspace(firm, root)
            report = render_workspace(root)
            assert report["summary"]["outcome"] == "pass", report["diagnostics"]
            cls.roots[namespace] = root

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()
        if cls.durations:
            sys.stderr.write("\nrevit-addin build durations: " + "; ".join(cls.durations) + "\n")

    def build(self, namespace: str, extension: str, year: int) -> Path:
        csproj = addin_dir(self.roots[namespace], extension) / (extension + ".Addin.csproj")
        started = time.monotonic()
        result = subprocess.run(
            ["dotnet", "build", str(csproj), "-c", "Release", "-p:RevitVersion={}".format(year), "-nologo"],
            capture_output=True,
            text=True,
            env=BUILD_ENV,
            timeout=300,
        )
        elapsed = time.monotonic() - started
        self.durations.append("{} {} {:.1f}s".format(extension, year, elapsed))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 Warning(s)", result.stdout, result.stdout)
        output = csproj.parent / "bin" / "Release" / str(year) / (extension + ".Addin.dll")
        self.assertTrue(output.is_file(), output)
        framework = _expected_framework(year)
        deps = (output.with_suffix(".deps.json")).read_text(encoding="utf-8")
        self.assertIn(".NETCoreApp,Version=v" + framework[3:], deps)
        return output

    def require(self, year: int) -> None:
        if not _dotnet():
            self.skipTest("dotnet is not on PATH")
        api = REVIT_ROOT / "Revit {}".format(year) / "RevitAPI.dll"
        if not api.is_file():
            self.skipTest("{} not found".format(api))
        needed = int(_expected_framework(year)[3:].split(".")[0])
        if _sdk_major() < needed:
            self.skipTest("no .NET SDK {} or newer for {}".format(needed, _expected_framework(year)))

    def check_dll_text(self, dll: Path, namespace: str) -> None:
        data = dll.read_bytes()
        if namespace == "quillmoor":
            name = 'Caf\u00e9 "Quill" \\ $(X);50% Studio \U0001F600'
            # The C# literal sits in the #US heap as UTF-16; the Product attribute is UTF-8 metadata.
            self.assertIn(name.encode("utf-16-le"), data)
            self.assertIn(name.encode("utf-8"), data)

    def test_quillmoor_builds_for_revit_2026(self) -> None:
        self.require(2026)
        dll = self.build("quillmoor", "Quillmoor", 2026)
        self.check_dll_text(dll, "quillmoor")

    def test_bimxbert_builds_for_revit_2026_and_ships_fonts(self) -> None:
        self.require(2026)
        dll = self.build("bimxbert", "BIMxBert", 2026)
        self.assertTrue((dll.parent / "fonts" / "geist" / "Geist-Regular.ttf").is_file())
        self.assertTrue((dll.parent / "fonts" / "geist" / "OFL.txt").is_file())

    def test_quillmoor_builds_for_revit_2027(self) -> None:
        self.require(2027)
        self.build("quillmoor", "Quillmoor", 2027)

    def test_build_leaves_nothing_in_the_repository(self) -> None:
        self.assertFalse((REPO / "addins").exists())


if __name__ == "__main__":
    unittest.main()
