"""Acceptance tests for the generated web-host surface.

A firm workspace that lists ``web-host`` gets an HTML tool host for pyRevit inside its
extension (``lib/<namespace>_web``: WebView2 in a WPF window) and a read-only ``Web Tool
Demo`` button. The window itself needs Revit, WPF and WebView2, so these tests cover what
can be proven without them: the pure modules run under CPython, the generated files obey
the offline, no-inline-script and neutral-identity rules, and the host code carries the
design (assemblies from the running Revit folder, navigation limits). Nothing here is
live-verified in Revit.
"""

from __future__ import annotations

import ast
import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from formwork_engine.adapters import layout, render_all  # noqa: E402
from formwork_engine.checks import check_outputs  # noqa: E402
from formwork_engine.diagnostics import Diagnostics  # noqa: E402
from formwork_engine.outputs import text_file  # noqa: E402
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
FORBIDDEN = re.compile(r"rgdt|rockwell|robmintzes", re.IGNORECASE)
PACKAGE_FILES = ("__init__.py", "bridge.py", "session.py", "log.py", "compat.py", "webview2_support.py", "host.py", "ShellWindow.xaml")
ASSET_FILES = ("assets/bridge.js", "assets/tool-ui.js", "assets/tool.css", "assets/symbol-light.svg")
DEMO_FILES = ("bundle.yaml", "script.py", "tool.html", "tool.js", "icon.png", "icon.dark.png")
URL = re.compile(r"https?://[^\s\"'<>)\\;,]+", re.IGNORECASE)


def edit_json(path: Path, mutate) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def import_from(lib: Path, package: str, *modules: str):
    """Import generated pure modules under CPython with the generated lib folder on sys.path."""
    saved = list(sys.path)
    try:
        sys.path.insert(0, str(lib))
        return [importlib.import_module("{}.{}".format(package, name)) for name in modules]
    finally:
        sys.path[:] = saved


def forget(package: str) -> None:
    for name in [n for n in sys.modules if n == package or n.startswith(package + ".")]:
        del sys.modules[name]


class WebHostCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="web host ")
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
    def lib(root: Path, extension: str) -> Path:
        return root / "extensions" / (extension + ".extension") / "lib"

    @staticmethod
    def package(root: Path, extension: str, namespace: str) -> Path:
        return root / "extensions" / (extension + ".extension") / "lib" / (namespace + "_web")

    @staticmethod
    def demo(root: Path, extension: str, panel: str) -> Path:
        return root / "extensions" / (extension + ".extension") / (extension + ".tab") / (panel + ".panel") / "WebToolDemo.pushbutton"

    @staticmethod
    def host_paths(root: Path) -> list[str]:
        manifest = json.loads((root / ".formwork" / "manifest.json").read_text(encoding="utf-8"))
        return sorted(rel for rel, entry in manifest["files"].items() if entry["adapter"] == "web-host")


class GeneratedFilesTests(WebHostCase):
    def test_files_exist_and_are_managed_for_both_profiles(self) -> None:
        for extension, namespace, profile, panel in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, namespace)
                package = self.package(root, extension, namespace)
                for name in PACKAGE_FILES + ASSET_FILES:
                    self.assertTrue((package / name).is_file(), name)
                demo = self.demo(root, extension, panel)
                for name in DEMO_FILES:
                    self.assertTrue((demo / name).is_file(), name)
                self.assertTrue((root / "docs" / "toolbar" / "tools" / "web-tool-demo.md").is_file())
                manifest = json.loads((root / ".formwork" / "manifest.json").read_text(encoding="utf-8"))
                paths = self.host_paths(root)
                self.assertGreaterEqual(len(paths), 19)
                for rel in paths:
                    self.assertEqual(manifest["files"][rel]["ownership"], "managed", rel)
                self.assertIn("web-host.not-live-verified", [d["code"] for d in self.report["diagnostics"]])

    def test_no_webview2_binaries_are_shipped(self) -> None:
        for _, namespace, profile, _ in PROFILES:
            with self.subTest(profile=namespace):
                diags = Diagnostics()
                rendered = render_all(load_profile(profile, diags))
                names = [f.path.rsplit("/", 1)[-1].lower() for f in rendered.files if f.adapter == "web-host"]
                self.assertEqual([n for n in names if n.endswith((".dll", ".exe", ".nupkg", ".winmd"))], [])
                self.assertEqual([n for n in names if "webview2" in n and not n.endswith(".py")], [])

    def test_packaged_fonts_resolve_from_the_assets_folder(self) -> None:
        root = self.workspace(BIMXBERT, "fonts")
        assets = self.package(root, "BIMxBert", "bimxbert") / "assets"
        css = (assets / "tool.css").read_text(encoding="utf-8")
        urls = re.findall(r'url\("([^"]+)"\)', css)
        self.assertGreaterEqual(len(urls), 6)
        for url in urls:
            self.assertTrue(url.startswith("fonts/"), url)
            self.assertTrue((assets / url).is_file(), url)
        for family in ("barlow-condensed", "geist", "geist-mono"):
            self.assertTrue((assets / "fonts" / family / "OFL.txt").is_file(), family)
        quill = self.workspace(QUILLMOOR, "system fonts")
        self.assertFalse((self.package(quill, "Quillmoor", "quillmoor") / "assets" / "fonts").exists())

    def test_stylesheet_is_built_from_the_firm_tokens(self) -> None:
        for _, namespace, profile, _ in PROFILES:
            with self.subTest(profile=namespace):
                diags = Diagnostics()
                rendered = render_all(load_profile(profile, diags))
                css = next(f for f in rendered.files if f.path.endswith("web_host/tool.css") or f.path.endswith("_web/assets/tool.css")).content.decode("utf-8")
                self.assertIn("--{}-color-surface-default:".format(namespace), css)
                self.assertIn(".btn--primary", css)
                for component in (".tool-header", ".step", ".metrics", ".tbl", ".progress", ".log", ".tool__actions", ".badge--success"):
                    self.assertIn(component, css)
                other = "bimxbert" if namespace == "quillmoor" else "quillmoor"
                self.assertNotIn(other, css.lower())

    def test_no_foreign_identity_in_generated_files(self) -> None:
        for extension, namespace, profile, _ in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, "leak " + namespace)
                text_paths = [rel for rel in self.host_paths(root) if not rel.endswith((".png", ".ttf", ".otf"))]
                self.assertGreater(len(text_paths), 12)
                config = json.loads((profile / "firm.json").read_text(encoding="utf-8"))
                own = config["identity"]["links"]["support"]  # the firm's own data, not host content
                other = "bimxbert" if namespace == "quillmoor" else "quillmoor"
                for rel in text_paths:
                    text = (root / rel).read_text(encoding="utf-8").replace(own, "")
                    self.assertIsNone(FORBIDDEN.search(text), rel)
                    if not rel.endswith(".svg"):
                        self.assertNotIn(other, text.lower(), rel)


class PythonModuleTests(WebHostCase):
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
                python = [f for f in rendered.files if f.adapter == "web-host" and f.path.endswith(".py")]
                self.assertEqual(len(python), 8)
                for item in python:
                    text = item.content.decode("utf-8")
                    self.assertTrue(text.isascii(), item.path)
                    self.assertNotIn("ModuleNotFoundError", text, item.path)
                    self.assertNotRegex(text, r"(?m)^\s*except\s+\w+\s*,", item.path)
                    self.assertNotIn("nonlocal", text, item.path)
                    if "/lib/" in item.path and not item.path.endswith("__init__.py"):
                        self.assertIn("from __future__ import absolute_import", text, item.path)
                    # Warnings become errors, so an invalid escape sequence in a docstring fails here.
                    with warnings.catch_warnings():
                        warnings.simplefilter("error")
                        compile(text, item.path, "exec")

    def test_bridge_dispatch_and_error_envelopes(self) -> None:
        root = self.workspace(QUILLMOOR, "bridge")
        lib = self.lib(root, "Quillmoor")
        try:
            (bridge,) = import_from(lib, "quillmoor_web", "bridge")
            reports: list[tuple[str, str]] = []

            class Tool:
                @bridge.expose
                def add(self, a, b=0):
                    return a + b

                @bridge.expose
                def echo(self, **kwargs):
                    return kwargs

                @bridge.expose
                def boom(self):
                    raise ValueError("secret path C:\\Users\\someone\\model.rvt is unreadable")

                @bridge.expose
                def make_set(self):
                    return {1, 2}

                def not_exposed(self):
                    return "hidden"

                @bridge.expose
                def _private(self):
                    return "hidden"

            tool = Tool()
            hub = bridge.Bridge(tool, on_error=lambda name, trace: reports.append((name, trace)))
            self.assertEqual(sorted(hub.methods), ["add", "boom", "echo", "make_set"])

            def call(payload):
                return json.loads(hub.dispatch_json(payload if isinstance(payload, str) else json.dumps(payload)))

            self.assertEqual(call({"id": "r1", "method": "add", "args": [3, 4]}), {"id": "r1", "ok": True, "result": 7})
            self.assertEqual(call({"id": "r2", "method": "add", "kwargs": {"a": 10, "b": 32}})["result"], 42)
            self.assertEqual(call({"id": "r3", "method": "add", "args": [1]})["result"], 1)

            unknown = call({"id": "r4", "method": "nope"})
            self.assertEqual((unknown["id"], unknown["ok"]), ("r4", False))
            self.assertIn("Method not exposed", unknown["error"])
            for name in ("not_exposed", "_private", "__class__", "dispatch_json"):
                self.assertFalse(call({"id": "x", "method": name})["ok"], name)
            self.assertFalse(call({"id": "x", "method": ["add"]})["ok"])
            self.assertFalse(call({"id": "x"})["ok"])

            failed = call({"id": "r5", "method": "boom"})
            self.assertEqual(failed["ok"], False)
            self.assertIn("unreadable", failed["error"])
            self.assertEqual(sorted(failed), ["error", "id", "ok"])  # a message, never a traceback
            self.assertNotIn("Traceback", hub.dispatch_json(json.dumps({"id": "r5", "method": "boom"})))
            self.assertEqual(reports[0][0], "boom")
            self.assertIn("Traceback", reports[0][1])  # the log callback does get it

            bad_args = call({"id": "r6", "method": "add", "args": [1, 2, 3]})
            self.assertFalse(bad_args["ok"])
            self.assertNotIn("Traceback", json.dumps(bad_args))
            self.assertFalse(call({"id": "r7", "method": "add", "args": "12"})["ok"])
            self.assertFalse(call({"id": "r8", "method": "add", "kwargs": [1]})["ok"])

            unserializable = call({"id": "r9", "method": "make_set"})
            self.assertFalse(unserializable["ok"])
            self.assertIn("not JSON-serializable", unserializable["error"])

            self.assertFalse(call("{not json")["ok"])
            self.assertIsNone(call("{not json")["id"])
            self.assertFalse(call("[1, 2]")["ok"])
            self.assertFalse(call("42")["ok"])
        finally:
            forget("quillmoor_web")

    def test_json_round_trip_of_non_ascii_text(self) -> None:
        root = self.workspace(BIMXBERT, "unicode")
        lib = self.lib(root, "BIMxBert")
        try:
            (bridge,) = import_from(lib, "bimxbert_web", "bridge")

            class Tool:
                @bridge.expose
                def name(self):
                    return {"level": "Level 8\u00ba", "tower": "Br\u00fcckenstra\u00dfe \u2014 \u30bf\u30ef\u30fc", "bytes": "caf\u00e9".encode("utf-8"), "ids": [1, 2]}

                @bridge.expose
                def echo(self, text):
                    return text

            hub = bridge.Bridge(Tool())
            reply = json.loads(hub.dispatch_json(json.dumps({"id": "u1", "method": "name"})))
            self.assertEqual(reply["result"]["level"], "Level 8\u00ba")
            self.assertEqual(reply["result"]["tower"], "Br\u00fcckenstra\u00dfe \u2014 \u30bf\u30ef\u30fc")
            self.assertEqual(reply["result"]["bytes"], "caf\u00e9")
            text = "\u00e9\u00e8 \u4e2d\u6587 \U0001f3d7"
            echoed = json.loads(hub.dispatch_json(json.dumps({"id": "u2", "method": "echo", "args": [text]}, ensure_ascii=False)))
            self.assertEqual(echoed["result"], text)
            self.assertEqual(bridge.dumps({"k": "\u00e9"}), json.dumps({"k": "\u00e9"}))
        finally:
            forget("bimxbert_web")

    def test_session_chunking_progress_and_cancel(self) -> None:
        root = self.workspace(QUILLMOOR, "session")
        lib = self.lib(root, "Quillmoor")
        try:
            (session,) = import_from(lib, "quillmoor_web", "session")

            class Fake(session.ToolSession):
                def __init__(self):
                    session.ToolSession.__init__(self)
                    self.events = []

                def post_event(self, name, data=None):
                    self.events.append((name, data))

            tool = Fake()
            result = tool.run_chunked([1, 2, 3], lambda item: {"id": item, "status": "ok"}, label="Reading")
            self.assertEqual((result["status"], result["counts"]), ("success", {"ok": 3, "warn": 0, "fail": 0}))
            self.assertEqual([e[0] for e in tool.events], ["progress"] * 3)
            self.assertEqual(tool.events[-1][1], {"done": 3, "total": 3, "label": "Reading 3 / 3"})

            def flaky(item):
                if item == 2:
                    raise RuntimeError("item two failed")
                return {"id": item, "status": "ok"}

            partial = tool.run_chunked([1, 2, 3], flaky)
            self.assertEqual(partial["status"], "partial")
            self.assertEqual(partial["counts"]["fail"], 1)
            self.assertIn("item two failed", partial["log"][0])
            self.assertEqual(tool.run_chunked([1], lambda item: 1 / 0)["status"], "failed")

            def canceling(item):
                tool.cancel()
                return {"id": item, "status": "ok"}

            canceled = tool.run_chunked([1, 2, 3], canceling)
            self.assertEqual(canceled["status"], "canceled")
            self.assertEqual(len(canceled["items"]), 1)
            self.assertEqual(tool.run_chunked([], lambda item: item)["status"], "success")
        finally:
            forget("quillmoor_web")

    def test_log_writes_under_a_namespaced_folder_and_never_raises(self) -> None:
        root = self.workspace(QUILLMOOR, "log")
        lib = self.lib(root, "Quillmoor")
        appdata = self.base / "local app data"
        appdata.mkdir()
        try:
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(appdata)}), contextlib.redirect_stdout(io.StringIO()) as printed:
                (log,) = import_from(lib, "quillmoor_web", "log")
                self.assertEqual(Path(log.LOG_FILE), appdata / "quillmoor" / "logs" / "web.log")
                log.log("hello {0} \u00e9", "world")
                log.log("plain")
                log.log("bad {0", 1)  # malformed format string must not raise
            self.assertIn("[quillmoor_web", printed.getvalue())
            text = (appdata / "quillmoor" / "logs" / "web.log").read_text(encoding="utf-8")
            self.assertIn("hello world \u00e9", text)
            self.assertIn("[quillmoor_web", text)
        finally:
            forget("quillmoor_web")

    def test_support_module_finds_host_assemblies_and_polices_navigation(self) -> None:
        root = self.workspace(BIMXBERT, "support")
        lib = self.lib(root, "BIMxBert")
        try:
            (support,) = import_from(lib, "bimxbert_web", "webview2_support")
            self.assertEqual(support.TOOL_HOST, "bimxbert-tool.test")
            self.assertEqual(support.ASSETS_HOST, "bimxbert-assets.test")
            self.assertEqual(support.OVERRIDE_ENV, "BIMXBERT_WEBVIEW2_DIR")

            allowed = (
                "https://bimxbert-tool.test/tool.html",
                "https://BIMXBERT-TOOL.test/tool.html?x=1#top",
                "https://bimxbert-assets.test/bridge.js",
                "https://bimxbert-assets.test",
            )
            refused = (
                "", None, "about:blank", "file:///C:/Windows/win.ini", "data:text/html,hi",
                "http://bimxbert-tool.test/tool.html",
                "https://bimxbert-tool.test:8443/tool.html",
                "https://bimxbert-tool.test.evil.example/x",
                "https://evil.example/https://bimxbert-tool.test/",
                "https://bimxbert-tool.test@evil.example/x",
                "https://evil.example\\@bimxbert-tool.test/x",
                "https://bimxbert-tool.test\\@evil.example/x",
                "https://bimxbert-tool.test/a b",
                "https://quillmoor-tool.test/tool.html",
                "javascript:alert(1)",
                "https://example.com/",
            )
            for uri in allowed:
                self.assertTrue(support.is_allowed_uri(uri), uri)
            for uri in refused:
                self.assertFalse(support.is_allowed_uri(uri), uri)

            revit = self.base / "Fake Revit 2030"
            revit.mkdir()
            for name in support.WEBVIEW2_ASSEMBLIES:
                (revit / (name + ".dll")).write_bytes(b"MZ")
            override = self.base / "firm supplied"
            override.mkdir()
            (override / "Microsoft.Web.WebView2.Core.dll").write_bytes(b"MZ")

            process_path = str(revit / "Revit.exe")
            dirs = support.search_directories(process_path, {})
            self.assertEqual([folder for _, folder in dirs], [str(revit)])
            self.assertEqual(support.find_assembly("Microsoft.Web.WebView2.Wpf", dirs), str(revit / "Microsoft.Web.WebView2.Wpf.dll"))
            self.assertIsNone(support.find_assembly("Microsoft.Web.WebView2.WinForms", dirs))
            self.assertEqual(support.search_directories(None, {}), [])

            # Without a loader anywhere, none is reported; then both documented layouts are found.
            self.assertIsNone(support.find_native_loader(str(revit)))
            nested = revit / "runtimes" / "win-x64" / "native"
            nested.mkdir(parents=True)
            (nested / "WebView2Loader.dll").write_bytes(b"MZ")
            self.assertEqual(support.find_native_loader(str(revit)), str(nested / "WebView2Loader.dll"))
            (revit / "WebView2Loader.dll").write_bytes(b"MZ")
            self.assertEqual(support.find_native_loader(str(revit)), str(revit / "WebView2Loader.dll"))

            # A Revit that ships none falls back to the firm-supplied folder, in order.
            bare = self.base / "Fake Revit 2022"
            bare.mkdir()
            dirs = support.search_directories(str(bare / "Revit.exe"), {"BIMXBERT_WEBVIEW2_DIR": str(override)})
            self.assertEqual([folder for _, folder in dirs], [str(bare), str(override)])
            self.assertEqual(support.find_assembly("Microsoft.Web.WebView2.Core", dirs), str(override / "Microsoft.Web.WebView2.Core.dll"))
            self.assertIsNone(support.find_assembly("Microsoft.Web.WebView2.Wpf", dirs))

            message = support.missing_message("Web Tool Demo", ["Microsoft.Web.WebView2.Wpf.dll"], dirs)
            for needle in ("Web Tool Demo", "Microsoft.Web.WebView2.Wpf.dll", str(bare), "BIMXBERT_WEBVIEW2_DIR", "2022"):
                self.assertIn(needle, message)
            self.assertTrue(message.isascii())
            self.assertIn("WebView2 Runtime", support.runtime_hint())
        finally:
            forget("bimxbert_web")

    def test_compat_imports_without_revit(self) -> None:
        root = self.workspace(QUILLMOOR, "compat")
        lib = self.lib(root, "Quillmoor")
        try:
            (compat,) = import_from(lib, "quillmoor_web", "compat")

            class Modern:
                Value = 7

            class Legacy:
                IntegerValue = 9

            self.assertEqual(compat.eid_int(Modern()), 7)
            self.assertEqual(compat.eid_int(Legacy()), 9)
        finally:
            forget("quillmoor_web")

    def test_importing_the_package_loads_nothing(self) -> None:
        root = self.workspace(QUILLMOOR, "bare import")
        lib = self.lib(root, "Quillmoor")
        code = (
            "import sys; sys.path.insert(0, sys.argv[1]); import quillmoor_web; "
            "from quillmoor_web.bridge import expose, Bridge; "
            "print('clr' in sys.modules, 'quillmoor_web.host' in sys.modules)"
        )
        completed = subprocess.run([sys.executable, "-c", code, str(lib)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "False False")


class HostDesignTests(WebHostCase):
    """host.py needs Revit, so its design is asserted on the source."""

    def host_source(self, root: Path, extension: str, namespace: str) -> str:
        return (self.package(root, extension, namespace) / "host.py").read_text(encoding="utf-8")

    def test_assemblies_come_from_the_running_revit_not_a_fixed_path(self) -> None:
        for extension, namespace, profile, _ in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, "paths " + namespace)
                package = self.package(root, extension, namespace)
                for name in ("host.py", "webview2_support.py"):
                    text = (package / name).read_text(encoding="utf-8")
                    self.assertNotRegex(text, r"(?i)program\s*files", name)
                    self.assertNotRegex(text, r"(?i)\b[a-z]:\\\\", name)  # no drive-letter paths
                    self.assertNotIn("Autodesk", text, name)
                host = (package / "host.py").read_text(encoding="utf-8")
                self.assertIn("MainModule.FileName", host)
                self.assertIn("support.search_directories(_process_path(), os.environ)", host)
                self.assertIn("class WebView2HostError", host)
                self.assertNotIn("DLL_DIR", host)
                self.assertFalse(list(package.rglob("*.dll")))

    def test_environment_is_created_by_the_host_never_through_creation_properties(self) -> None:
        root = self.workspace(QUILLMOOR, "environment")
        host = self.host_source(root, "Quillmoor", "quillmoor")
        code_only = "\n".join(line for line in host.splitlines() if not line.lstrip().startswith("#"))
        executable = [node for node in ast.walk(ast.parse(host)) if isinstance(node, ast.Attribute) and node.attr == "CreationProperties"]
        self.assertEqual(executable, [])  # named only in the explanatory docstring
        self.assertIn("CoreWebView2Environment.CreateAsync(None, folder, None)", code_only)
        self.assertIn("EnsureCoreWebView2Async(environment, None)", code_only)
        self.assertIn("self._core_version", code_only)  # user data folder is per Core version

    def test_security_posture_is_in_the_host_code(self) -> None:
        for extension, namespace, profile, _ in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, "posture " + namespace)
                host = self.host_source(root, extension, namespace)
                for needle in (
                    '_subscribe(core, "NavigationStarting"',
                    '_subscribe(core, "FrameNavigationStarting"',
                    '_subscribe(core, "NewWindowRequested"',
                    '"DownloadStarting"',
                    '"PermissionRequested"',
                    "SetVirtualHostNameToFolderMapping(support.TOOL_HOST",
                    "SetVirtualHostNameToFolderMapping(support.ASSETS_HOST",
                    "args.Cancel = True",
                    "args.Handled = True",
                    '"Deny"',
                    "support.is_allowed_uri(source)",
                    "INIT_TIMEOUT_SECONDS",
                    "DispatcherFrame",
                    "AreDevToolsEnabled",
                    "USER_DATA_ROOT",
                ):
                    self.assertIn(needle, host)
                self.assertIn('"{}", "WebView2"'.format(namespace), host)
                # Fail closed: a failed policy attach closes the window instead of loading the page.
                self.assertLess(host.index("self._configure_core(core)"), host.index("self.WebView.Source = Uri(url)"))
                self.assertIn("Fail closed", host)
                self.assertNotIn("NavigateToString", host)
                self.assertNotIn("file:///", host)

    def test_host_module_parses_and_uses_only_the_firm_namespace(self) -> None:
        root = self.workspace(BIMXBERT, "namespace")
        host = self.host_source(root, "BIMxBert", "bimxbert")
        ast.parse(host)
        self.assertIn("from bimxbert_web import webview2_support as support", host)
        self.assertIn("window.bimxbert.call", host)
        self.assertNotRegex(host, r"\{\{\s*[a-z_]+\s*\}\}")


class PageTests(WebHostCase):
    def web_files(self, root: Path, extension: str, namespace: str, panel: str) -> dict[str, str]:
        package = self.package(root, extension, namespace)
        demo = self.demo(root, extension, panel)
        files = {
            "tool.html": demo / "tool.html",
            "tool.js": demo / "tool.js",
            "bridge.js": package / "assets" / "bridge.js",
            "tool-ui.js": package / "assets" / "tool-ui.js",
            "tool.css": package / "assets" / "tool.css",
            "symbol-light.svg": package / "assets" / "symbol-light.svg",
            "ShellWindow.xaml": package / "ShellWindow.xaml",
        }
        return {name: path.read_text(encoding="utf-8") for name, path in files.items()}

    def test_page_uses_only_the_virtual_hosts_and_has_no_inline_code(self) -> None:
        for extension, namespace, profile, panel in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, "page " + namespace)
                files = self.web_files(root, extension, namespace, panel)
                hosts = {"{}-tool.test".format(namespace), "{}-assets.test".format(namespace)}
                namespace_uris = {"www.w3.org", "schemas.microsoft.com"}  # XML namespace identifiers, not loads
                for name, text in files.items():
                    found = set(re.sub(r"^https?://", "", u).split("/")[0] for u in URL.findall(text))
                    self.assertEqual(found - hosts - namespace_uris, set(), name)
                html = files["tool.html"]
                self.assertIn("Content-Security-Policy", html)
                csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', html).group(1)
                self.assertEqual(
                    csp,
                    "default-src 'self' https://{0}-assets.test https://{0}-tool.test; base-uri 'none'; object-src 'none'; form-action 'none'".format(namespace),
                )
                self.assertNotIn("unsafe-inline", csp)
                self.assertNotIn("unsafe-eval", csp)
                for script in re.findall(r"<script\b([^>]*)>", html):
                    self.assertIn("src=", script)
                self.assertEqual(re.findall(r"<script\b[^>]*>([^<]*\S[^<]*)</script>", html), [])
                self.assertNotRegex(html, r"(?i)\son[a-z]+\s*=")  # no inline event handlers
                self.assertNotRegex(html, r"(?i)\sstyle\s*=")
                self.assertNotRegex(html, r"(?i)<style\b")
                self.assertNotIn("javascript:", html.lower())
                for name in ("tool.js", "bridge.js", "tool-ui.js"):
                    self.assertNotRegex(files[name], r"\beval\s*\(|new Function|innerHTML|document\.write|\.cssText|setAttribute\(\s*[\"']style")
                    self.assertNotRegex(files[name], r"\b(fetch|XMLHttpRequest|WebSocket|importScripts)\b", name)
                self.assertIn("https://{}-assets.test/tool.css".format(namespace), html)
                self.assertIn('src="tool.js"', html)

    def test_page_scripts_define_the_firm_namespaced_api(self) -> None:
        root = self.workspace(QUILLMOOR, "api")
        files = self.web_files(root, "Quillmoor", "quillmoor", "Starter")
        self.assertIn("window.quillmoor = {", files["bridge.js"])
        self.assertIn("window.quillmoorui = {", files["tool-ui.js"])
        for verb in ("call:", "on:", "off:", "close:"):
            self.assertIn(verb, files["bridge.js"])
        self.assertIn('call("close_window")', files["bridge.js"])
        self.assertIn('bridge.call("init_data")', files["tool.js"])
        self.assertNotIn('"export"', files["tool.js"])
        self.assertIn("ui.copyText(summaryText())", files["tool.js"])
        self.assertIn("navigator.clipboard.writeText", files["tool-ui.js"])
        for state in ("idle", "waiting", "partial", "failure", "done"):
            self.assertIn('"{}"'.format(state), files["tool-ui.js"])
        # The action row reads dismiss, secondary, primary.
        html = files["tool.html"]
        self.assertLess(html.index('id="btn-close"'), html.index('id="btn-copy"'))
        self.assertLess(html.index('id="btn-copy"'), html.index('id="btn-refresh"'))
        self.assertLess(html.index('class="spacer"'), html.index('id="btn-refresh"'))

    def test_every_generated_script_compiles_in_node(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is not on PATH")
        root = self.workspace(QUILLMOOR, "node check")
        files = self.web_files(root, "Quillmoor", "quillmoor", "Starter")
        for name in ("tool.js", "bridge.js", "tool-ui.js"):
            target = self.base / name
            target.write_text(files[name], encoding="utf-8")
            completed = subprocess.run([node, "--check", str(target)], capture_output=True, text=True, timeout=60)
            self.assertEqual(completed.returncode, 0, name + completed.stderr)

    def test_bridge_script_round_trips_against_a_stub_host(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is not on PATH")
        root = self.workspace(QUILLMOOR, "node bridge")
        files = self.web_files(root, "Quillmoor", "quillmoor", "Starter")
        bridge_path = self.base / "bridge.js"
        bridge_path.write_text(files["bridge.js"], encoding="utf-8")
        script = self.base / "drive.js"
        script.write_text(
            "const fs = require('fs'); const vm = require('vm');\n"
            "const posted = []; let listener = null;\n"
            "const win = { chrome: { webview: { postMessage: (m) => posted.push(m), addEventListener: (n, f) => { listener = f; } } } };\n"
            "win.window = win;\n"
            "vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), win);\n"
            "const api = win.quillmoor;\n"
            "const out = [];\n"
            "(async () => {\n"
            "  out.push(api.hosted);\n"
            "  const a = api.call('add', { a: 1, b: 2 });\n"
            "  const b = api.call('sum', [1, 2, 3]);\n"
            "  const c = api.call('boom');\n"
            "  out.push(posted.map(JSON.parse));\n"
            "  let seen = null; api.on('progress', (d) => { seen = d; });\n"
            "  listener({ data: JSON.stringify({ event: 'progress', data: { done: 1 } }) });\n"
            "  listener({ data: JSON.stringify({ id: 'req-1', ok: true, result: 3 }) });\n"
            "  listener({ data: { id: 'req-2', ok: true, result: 6 } });\n"
            "  listener({ data: JSON.stringify({ id: 'req-3', ok: false, error: 'nope' }) });\n"
            "  listener({ data: JSON.stringify({ id: 'req-99', ok: true }) });\n"
            "  listener({ data: 'not json' });\n"
            "  out.push(seen, await a, await b);\n"
            "  try { await c; out.push('resolved'); } catch (e) { out.push(e.message); }\n"
            "  api.close(); out.push(JSON.parse(posted[3]).method);\n"
            "  const lone = { }; lone.window = lone; vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), lone);\n"
            "  out.push(lone.quillmoor.hosted);\n"
            "  try { await lone.quillmoor.call('x'); } catch (e) { out.push(e.message); }\n"
            "  console.log(JSON.stringify(out));\n"
            "})();\n",
            encoding="utf-8",
        )
        completed = subprocess.run([node, str(script), str(bridge_path)], capture_output=True, text=True, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        out = json.loads(completed.stdout)
        self.assertIs(out[0], True)
        self.assertEqual(out[1][0], {"id": "req-1", "method": "add", "args": [], "kwargs": {"a": 1, "b": 2}})
        self.assertEqual(out[1][1]["args"], [1, 2, 3])
        self.assertEqual(out[2], {"done": 1})
        self.assertEqual(out[3:5], [3, 6])
        self.assertEqual(out[5], "nope")
        self.assertEqual(out[6], "close_window")
        self.assertIs(out[7], False)
        self.assertIn("Not running inside", out[8])

    def test_tool_ui_helpers_against_a_minimal_dom(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is not on PATH")
        root = self.workspace(QUILLMOOR, "node ui")
        files = self.web_files(root, "Quillmoor", "quillmoor", "Starter")
        ui_path = self.base / "tool-ui.js"
        ui_path.write_text(files["tool-ui.js"], encoding="utf-8")
        script = self.base / "drive-ui.js"
        script.write_text(
            "const fs = require('fs'); const vm = require('vm');\n"
            "const attrs = {};\n"
            "const badge = { _a: { 'data-usage': 'reusable' }, getAttribute(k) { return this._a[k]; }, set title(v) { this._t = v; }, textContent: '' };\n"
            "const button = { textContent: 'Run', _a: {}, getAttribute(k) { return this._a[k] === undefined ? null : this._a[k]; }, setAttribute(k, v) { this._a[k] = v; }, classList: { remove() {}, add() {} }, addEventListener() {} };\n"
            "const body = { setAttribute: (k, v) => { attrs[k] = v; }, appendChild() {} };\n"
            "const document = { readyState: 'complete', body,\n"
            "  querySelectorAll: (s) => s === '.usage[data-usage]' ? [badge] : [],\n"
            "  querySelector: (s) => s === '.tool-header .usage[data-usage]' ? badge : null,\n"
            "  createElement: () => ({ setAttribute() {}, className: '', textContent: '' }), addEventListener() {} };\n"
            "const win = { document, navigator: {}, console, setTimeout, clearTimeout, Promise };\n"
            "win.window = win;\n"
            "vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), Object.assign(win, { document }));\n"
            "const ui = win.quillmoorui;\n"
            "ui.setState('waiting', 'x'); const a = attrs['data-state'];\n"
            "ui.setState('bogus'); const b = attrs['data-state'];\n"
            "const action = ui.primaryAction(button, { verb: 'Run audit', object: 'audit' });\n"
            "const first = button.textContent; action.markRun({ status: 'failed' }); const second = button.textContent;\n"
            "action.markRun({ status: 'success' });\n"
            "console.log(JSON.stringify([a, b, badge.textContent, first, second, button.textContent, action.hasRun(), ui.STATES]));\n",
            encoding="utf-8",
        )
        completed = subprocess.run([node, str(script), str(ui_path)], capture_output=True, text=True, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        out = json.loads(completed.stdout)
        self.assertEqual(out[:7], ["waiting", "waiting", "Reusable", "Run audit", "Run audit", "Update audit", True])
        self.assertEqual(out[7], ["idle", "waiting", "partial", "failure", "canceled", "done"])

    def test_the_offline_check_exempts_only_the_virtual_hosts(self) -> None:
        def errors(path: str, text: str) -> list[str]:
            diags = Diagnostics()
            check_outputs([text_file(path, text, "test")], diags)
            return [d.code for d in diags.items if d.severity == "error"]

        page = '<link rel="stylesheet" href="https://quillmoor-assets.test/tool.css"><img src="https://quillmoor-assets.test/s.svg">'
        self.assertEqual(errors("docs/a.html", page), [])
        self.assertEqual(errors("docs/a.html", "<meta content=\"default-src 'self' https://quillmoor-assets.test https://quillmoor-tool.test; base-uri 'none'\">"), [])
        for bad in (
            '<img src="https://example.com/a.png">',
            '<img src="https://quillmoor-assets.test.example.com/a.png">',
            '<script src="https://cdn.example.com/x.js"></script>',
            '<img src="//quillmoor-tool.test.evil.com/a.png">',
            '<link rel="stylesheet" href="http://quillmoor-assets.test/tool.css">',
        ):
            self.assertEqual(errors("docs/a.html", bad), ["output.external-resource"], bad)
        self.assertEqual(errors("docs/a.css", '@font-face { src: url("https://quillmoor-assets.test/f.ttf"); }'), [])
        self.assertEqual(errors("docs/a.css", '@font-face { src: url("https://fonts.example.com/f.ttf"); }'), ["output.external-resource"])


class DemoTests(WebHostCase):
    def test_demo_is_read_only_and_validates_context_first(self) -> None:
        for extension, namespace, profile, panel in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, "demo " + namespace)
                script = (self.demo(root, extension, panel) / "script.py").read_text(encoding="utf-8")
                for needle in ("Transaction", "StartTransaction", "SubTransaction", ".Commit(", "doc.Delete", ".Create", "Rollback", ".Set("):
                    self.assertNotIn(needle, script)
                body = script[script.index("def main"):]
                self.assertLess(body.index("doc is None"), body.index("IsFamilyDocument"))
                self.assertLess(body.index("IsFamilyDocument"), body.index("WebToolDemoWindow(doc)"))
                self.assertLess(body.index("WebToolDemoWindow(doc)"), body.index("window.show()"))
                self.assertIn("script.exit()", body)
                self.assertIn("except WebView2HostError", body)
                self.assertIn("from {}_web.host import WebToolWindow, WebView2HostError".format(namespace), script)
                self.assertIn("FilteredElementCollector(doc).OfClass(DB.View)", script)
                self.assertEqual(find_violations(root), [])

    def test_demo_counting_logic_with_a_stubbed_revit(self) -> None:
        """Run the demo's pure counting function against fake views (no Revit, no WPF)."""
        root = self.workspace(QUILLMOOR, "counting")
        script = (self.demo(root, "Quillmoor", "Starter") / "script.py").read_text(encoding="utf-8")
        tree = ast.parse(script)
        body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in {"_label", "count_views_by_type"}]
        body[:0] = [node for node in tree.body if isinstance(node, ast.Assign) and node.targets[0].id in {"HIDDEN_VIEW_TYPES", "FRIENDLY_LABELS"}]
        namespace: dict = {}

        class View:
            def __init__(self, view_type, template=False, broken=False):
                self._type, self._template, self._broken = view_type, template, broken

            @property
            def ViewType(self):
                if self._broken:
                    raise RuntimeError("unreadable")
                return self._type

            @property
            def IsTemplate(self):
                return self._template

        views = [View("FloorPlan"), View("FloorPlan"), View("FloorPlan", True), View("CeilingPlan", True),
                 View("ThreeD"), View("ProjectBrowser"), View("Internal"), View("Legend", broken=True)]

        class Collector:
            def __init__(self, doc):
                pass

            def OfClass(self, _cls):
                return views

        namespace["DB"] = mock.MagicMock(FilteredElementCollector=Collector, View=object)
        exec(compile(ast.Module(body=body, type_ignores=[]), "script.py", "exec"), namespace)
        rows, skipped = namespace["count_views_by_type"](object())
        self.assertEqual(skipped, 1)
        self.assertEqual(
            rows,
            [
                {"type": "FloorPlan", "label": "Floor Plan", "views": 2, "templates": 1},
                {"type": "ThreeD", "label": "3D View", "views": 1, "templates": 0},
                {"type": "CeilingPlan", "label": "Ceiling Plan", "views": 0, "templates": 1},
            ],
        )
        self.assertEqual(namespace["_label"]("RevitLinks"), "Revit Links")
        json.dumps(rows)

    def test_icons_are_96_px_pairs_and_differ(self) -> None:
        from formwork_engine.png import read_png_size

        for extension, namespace, profile, panel in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, "icons " + namespace)
                demo = self.demo(root, extension, panel)
                light = (demo / "icon.png").read_bytes()
                dark = (demo / "icon.dark.png").read_bytes()
                self.assertEqual(read_png_size(light), (96, 96))
                self.assertEqual(read_png_size(dark), (96, 96))
                self.assertNotEqual(light, dark)
                sample = (demo.parent / "HelloButton.pushbutton" / "icon.png").read_bytes()
                kit = (demo.parent / "UIKitDemo.pushbutton" / "icon.png").read_bytes()
                self.assertNotIn(light, (sample, kit))

    def test_doc_names_the_tool_and_its_limits(self) -> None:
        root = self.workspace(QUILLMOOR, "doc")
        doc = (root / "docs" / "toolbar" / "tools" / "web-tool-demo.md").read_text(encoding="utf-8")
        for needle in ("Web Tool Demo", "Starter", "Quillmoor", "Modifies the Revit database:** No", "quillmoor-tool.test", "QUILLMOOR".lower()):
            self.assertIn(needle, doc)


class FoundationValidatorTests(WebHostCase):
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
                for tool_id in ("hello-button", "ui-kit-demo", "web-tool-demo"):
                    self.assertIn("id: " + tool_id, fragment)
                bundle = next(root.rglob("WebToolDemo.pushbutton/bundle.yaml")).read_text(encoding="utf-8")
                self.assertIn("title: Web Tool Demo", bundle)
                self.assertIn("help_url:", bundle)
                self.assertIn("author:", bundle)

    def test_without_the_surface_the_spec_fragment_is_unchanged(self) -> None:
        both = self.workspace(QUILLMOOR, "fragment both")
        full = (both / "docs" / "toolbar" / "spec.d" / "foundation-sample.md").read_text(encoding="utf-8")
        kit_only = self.workspace(QUILLMOOR, "fragment kit", lambda c: c["surfaces"].remove("web-host"))
        fragment = (kit_only / "docs" / "toolbar" / "spec.d" / "foundation-sample.md").read_text(encoding="utf-8")
        self.assertNotIn("web-tool-demo", fragment)
        self.assertTrue(fragment.endswith("UIKitDemo.pushbutton\n```\n"), fragment[-120:])
        # The managed fragment with the surface is the same text plus one appended tool entry.
        self.assertTrue(full.startswith(fragment[: -len("\n```\n")]))
        self.assertTrue(full.endswith("WebToolDemo.pushbutton\n```\n"), full[-120:])
        self.assertEqual(full.count("id: web-tool-demo"), 1)
        neither = self.workspace(QUILLMOOR, "fragment neither", lambda c: [c["surfaces"].remove("web-host"), c["surfaces"].remove("ui-kit")])
        plain = (neither / "docs" / "toolbar" / "spec.d" / "foundation-sample.md").read_text(encoding="utf-8")
        self.assertTrue(plain.endswith("HelloButton.pushbutton\n```\n"), plain[-120:])
        self.assertFalse((neither / "docs" / "toolbar" / "tools" / "web-tool-demo.md").exists())
        self.assertFalse(list(neither.rglob("WebToolDemo.pushbutton")))
        self.assertFalse((neither / "extensions" / "Quillmoor.extension" / "lib" / "quillmoor_web").exists())
        # The surface stands alone from the UI kit: web-host without ui-kit still lists only its own tool.
        only_web = self.workspace(QUILLMOOR, "fragment web", lambda c: c["surfaces"].remove("ui-kit"))
        text = (only_web / "docs" / "toolbar" / "spec.d" / "foundation-sample.md").read_text(encoding="utf-8")
        self.assertIn("id: web-tool-demo", text)
        self.assertNotIn("ui-kit-demo", text)
        self.assertTrue((only_web / "extensions" / "Quillmoor.extension" / "lib" / "quillmoor_web" / "host.py").is_file())
        self.assertFalse((only_web / "extensions" / "Quillmoor.extension" / "lib" / "quillmoor_ui").exists())

    def test_the_surface_requires_the_sample(self) -> None:
        firm = self.base / "needs sample"
        shutil.copytree(QUILLMOOR, firm)
        edit_json(firm / "firm.json", lambda c: c.update(surfaces=["web-host", "wpf-specimen"]))
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

    def test_schema_config_and_profiles_list_the_surface(self) -> None:
        schema = json.loads((REPO / "schemas" / "firm-config.v1.schema.json").read_text(encoding="utf-8"))
        self.assertIn("web-host", schema["properties"]["surfaces"]["items"]["enum"])
        for profile in (QUILLMOOR, BIMXBERT):
            self.assertIn("web-host", json.loads((profile / "firm.json").read_text(encoding="utf-8"))["surfaces"])
        self.assertIn("'web-host'", (REPO / "formwork_wizard" / "static" / "app.js").read_text(encoding="utf-8"))

    def test_names_are_derived_from_the_namespace(self) -> None:
        for _, namespace, profile, _ in PROFILES:
            diags = Diagnostics()
            technical = load_profile(profile, diags).config.technical
            self.assertEqual(layout.web_host_names(technical), (namespace + "-tool.test", namespace + "-assets.test"))
            self.assertEqual(layout.web_host_package(technical), namespace + "_web")


@unittest.skipUnless(os.name == "nt", "reads installed Revit folders (Windows only)")
class InstalledRevitTests(WebHostCase):
    """Evidence against real installs when present: the host-folder design finds the files Revit ships."""

    def installs(self) -> list[Path]:
        roots = [Path(p) for p in (os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432")) if p]
        found: list[Path] = []
        for root in roots:
            if (root / "Autodesk").is_dir():
                found.extend(sorted((root / "Autodesk").glob("Revit 20*")))
        return [p for p in dict.fromkeys(found) if (p / "Revit.exe").is_file()]

    def test_support_finds_core_wpf_and_a_native_loader_in_every_installed_revit(self) -> None:
        installs = self.installs()
        if not installs:
            self.skipTest("no Autodesk Revit installation found")
        root = self.workspace(QUILLMOOR, "installed")
        try:
            (support,) = import_from(self.lib(root, "Quillmoor"), "quillmoor_web", "webview2_support")
            checked = 0
            for revit in installs:
                if int(revit.name.rsplit(" ", 1)[-1]) < 2024:
                    continue
                with self.subTest(revit=revit.name):
                    dirs = support.search_directories(str(revit / "Revit.exe"), {})
                    for name in support.WEBVIEW2_ASSEMBLIES:
                        self.assertIsNotNone(support.find_assembly(name, dirs), name)
                    self.assertIsNotNone(support.find_native_loader(str(revit)))
                    checked += 1
            if not checked:
                self.skipTest("no Revit 2024 or later installation found")
        finally:
            forget("quillmoor_web")


if __name__ == "__main__":
    unittest.main()
