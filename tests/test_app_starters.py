"""Acceptance tests for the generated ``python-app`` and ``web-app`` surfaces.

A firm workspace that lists ``python-app`` gets ``apps/<namespace>-report/`` (a stdlib-only CLI that
renders a CSV or JSON table as a branded offline HTML report); ``web-app`` gets ``apps/<namespace>-web/``
(a dependency-free TypeScript static server and app shell that Node runs by stripping types). These
tests check the files statically and then really run the generated code: the Python app's own unittest
suite and CLI always, and the web app's ``node --test`` when a suitable Node is on PATH. Neither app
involves Revit, so there is nothing here to live-verify.
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
import unittest

try:  # CPython 3.11+
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from toolkit_engine.adapters import render_all, web_theme  # noqa: E402
from toolkit_engine.checks import check_outputs  # noqa: E402
from toolkit_engine.diagnostics import Diagnostics  # noqa: E402
from toolkit_engine.outputs import text_file  # noqa: E402
from toolkit_engine.profile import load_profile  # noqa: E402
from toolkit_engine.workspace import init_workspace, render_workspace  # noqa: E402
from validators.check_bundle_structure import validate_bundle_structure  # noqa: E402
from validators.check_safety_rules import find_violations  # noqa: E402
from validators.validate_toolbar_spec import validate_toolbar_spec  # noqa: E402

QUILLMOOR = REPO / "profiles" / "quillmoor"
BIMXBERT = REPO / "profiles" / "bimxbert"
# (namespace, profile directory)
PROFILES = (("quillmoor", QUILLMOOR), ("bimxbert", BIMXBERT))
FORBIDDEN = re.compile(r"robmintzes|placeholder|rgdt|rockwell", re.IGNORECASE)
TEXT_SUFFIXES = (".py", ".toml", ".csv", ".md", ".css", ".html", ".js", ".ts", ".json", ".svg", ".txt")
EXTERNAL_LOAD = re.compile(
    r"""<(?:img|script|link|iframe|source|video|audio|embed|object)\b[^>]*\b(?:src|href|data)\s*=\s*["']?\s*(?:https?:)?//"""
    r"""|url\(\s*["']?\s*(?:https?:)?//|@import\b""",
    re.IGNORECASE,
)
MINIMUM_NODE = (22, 18)  # type stripping is on by default from here (22.6 to 22.17 need a flag)
RUN_ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", NODE_NO_WARNINGS="1")


def edit_json(path: Path, mutate) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def report_dir(root: Path, namespace: str) -> Path:
    return root / "apps" / (namespace + "-report")


def web_dir(root: Path, namespace: str) -> Path:
    return root / "apps" / (namespace + "-web")


def app_text_files(root: Path, namespace: str) -> list[Path]:
    found = []
    for base in (report_dir(root, namespace), web_dir(root, namespace)):
        found.extend(p for p in base.rglob("*") if p.is_file() and (p.suffix in TEXT_SUFFIXES or p.name == ".gitignore"))
    return sorted(found)


def node_version() -> tuple[int, int] | None:
    node = shutil.which("node")
    if node is None:
        return None
    try:
        out = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=30, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.match(r"v(\d+)\.(\d+)", out.strip())
    return (int(match.group(1)), int(match.group(2))) if match else None


class AppCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="app starters ")
        self.base = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def workspace(self, profile: Path, name: str, mutate=None) -> Path:
        firm = self.base / ("profile " + name)
        shutil.copytree(profile, firm)
        if mutate:
            edit_json(firm / "firm.json", mutate)
        root = self.base / ("Work space " + name)
        init_workspace(firm, root)
        report = render_workspace(root)
        self.assertEqual(report["summary"]["outcome"], "pass", report["diagnostics"])
        self.report = report
        return root


class GeneratedFilesTests(AppCase):
    def test_files_exist_and_are_managed_for_both_profiles(self) -> None:
        for namespace, profile in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, namespace)
                py = report_dir(root, namespace)
                package = py / "src" / (namespace + "_report")
                for rel in (
                    "pyproject.toml",
                    "README.md",
                    "sample.csv",
                    ".gitignore",
                    "tests/test_report.py",
                    "src/{0}_report/__init__.py".format(namespace),
                    "src/{0}_report/__main__.py".format(namespace),
                    "src/{0}_report/branding.py".format(namespace),
                    "src/{0}_report/cli.py".format(namespace),
                    "src/{0}_report/render.py".format(namespace),
                    "src/{0}_report/theme.css".format(namespace),
                    "src/{0}_report/assets/wordmark-inverse.svg".format(namespace),
                    "src/{0}_report/assets/symbol-light.svg".format(namespace),
                ):
                    self.assertTrue((py / rel).is_file(), rel)
                self.assertTrue(package.is_dir())
                web = web_dir(root, namespace)
                for rel in (
                    "package.json",
                    "server.ts",
                    "tsconfig.json",
                    "README.md",
                    ".gitignore",
                    "test/server.test.ts",
                    "public/index.html",
                    "public/theme.css",
                    "public/app.js",
                    "public/assets/wordmark-inverse.svg",
                    "public/assets/symbol-light.svg",
                ):
                    self.assertTrue((web / rel).is_file(), rel)
                manifest = json.loads((root / ".toolkit" / "manifest.json").read_text(encoding="utf-8"))
                owned = [rel for rel, entry in manifest["files"].items() if entry["adapter"] in ("python-app", "web-app")]
                self.assertGreaterEqual(len(owned), 24)
                for rel in owned:
                    self.assertEqual(manifest["files"][rel]["ownership"], "managed", rel)
                    self.assertTrue(rel.startswith("apps/"), rel)
                codes = [d["code"] for d in self.report["diagnostics"]]
                self.assertIn("web-app.typecheck-not-run", codes)
                self.assertFalse([c for c in codes if c.startswith("python-app.")])

    def test_packaged_fonts_ship_with_the_web_app_and_the_stylesheet_names_them(self) -> None:
        root = self.workspace(BIMXBERT, "fonts")
        web = web_dir(root, "bimxbert")
        for family in ("barlow-condensed", "geist", "geist-mono"):
            files = sorted(p.name for p in (web / "public" / "fonts" / family).iterdir())
            self.assertIn("OFL.txt", files)
            self.assertTrue(any(name.endswith(".ttf") for name in files), family)
        css = (web / "public" / "theme.css").read_text(encoding="utf-8")
        urls = re.findall(r'url\("([^"]+)"\)', css)
        self.assertEqual(len(urls), 7)
        for url in urls:
            self.assertTrue((web / "public" / url).is_file(), url)
        # The Python report is a single portable file: it embeds no font files.
        py_css = (report_dir(root, "bimxbert") / "src" / "bimxbert_report" / "theme.css").read_text(encoding="utf-8")
        self.assertNotIn("@font-face", py_css)
        self.assertFalse(list(report_dir(root, "bimxbert").rglob("*.ttf")))
        quill = self.workspace(QUILLMOOR, "no-fonts")
        self.assertFalse((web_dir(quill, "quillmoor") / "public" / "fonts").exists())
        self.assertNotIn("@font-face", (web_dir(quill, "quillmoor") / "public" / "theme.css").read_text(encoding="utf-8"))

    def test_stylesheets_share_the_html_guide_component_rules(self) -> None:
        for namespace, profile in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, namespace)
                diags = Diagnostics()
                loaded = load_profile(profile, diags)
                self.assertIsNotNone(loaded)
                components = web_theme.component_css(loaded).strip()
                guide = (root / "docs" / "guides" / "hello-button.html").read_text(encoding="utf-8")
                web_css = (web_dir(root, namespace) / "public" / "theme.css").read_text(encoding="utf-8")
                py_css = (report_dir(root, namespace) / "src" / (namespace + "_report") / "theme.css").read_text(encoding="utf-8")
                for page in (guide, web_css, py_css):
                    self.assertIn(components, page)
                for css in (web_css, py_css):
                    self.assertIn("--{}-color-surface-default:".format(namespace), css)
                    for status in ("info", "success", "warning", "danger"):
                        self.assertIn(".badge--" + status, css)
                    self.assertNotRegex(css, r"(?i)https?://")

    @unittest.skipIf(tomllib is None, "tomllib needs CPython 3.11+")
    def test_pyproject_and_package_json_parse_and_carry_stable_names(self) -> None:
        for namespace, profile in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, namespace)
                project = tomllib.loads((report_dir(root, namespace) / "pyproject.toml").read_text(encoding="utf-8"))
                self.assertEqual(project["project"]["name"], namespace + "-report")
                self.assertEqual(project["project"]["dependencies"], [])
                self.assertEqual(project["project"]["requires-python"], ">=3.10")
                self.assertEqual(
                    project["project"]["scripts"], {namespace + "-report": "{}_report.cli:main".format(namespace)}
                )
                self.assertEqual(
                    project["tool"]["setuptools"]["package-data"][namespace + "_report"], ["theme.css", "assets/*.svg"]
                )
                package = json.loads((web_dir(root, namespace) / "package.json").read_text(encoding="utf-8"))
                self.assertEqual(package["name"], namespace + "-web")
                self.assertEqual(package["type"], "module")
                self.assertEqual(package["scripts"], {"start": "node server.ts", "test": "node --test"})
                self.assertNotIn("dependencies", package)
                self.assertNotIn("devDependencies", package)

    def test_no_template_or_foundation_maintainer_identity_leaks(self) -> None:
        for namespace, profile in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, namespace)
                links = json.loads((profile / "firm.json").read_text(encoding="utf-8"))["identity"]["links"]
                files = app_text_files(root, namespace)
                self.assertGreaterEqual(len(files), 20)
                for path in files:
                    text = path.read_text(encoding="utf-8")
                    for url in links.values():  # a profile's own URLs may name its owner
                        text = text.replace(url, "")
                    self.assertIsNone(FORBIDDEN.search(text), str(path.relative_to(root)))

    def test_web_app_typescript_uses_only_erasable_syntax(self) -> None:
        root = self.workspace(QUILLMOOR, "erasable")
        web = web_dir(root, "quillmoor")
        for name in ("server.ts", "test/server.test.ts"):
            text = (web / name).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"(?m)^\s*(?:export\s+)?(?:const\s+)?enum\s", name)
            self.assertNotRegex(text, r"(?m)^\s*(?:export\s+)?(?:declare\s+)?(?:namespace|module)\s+\w", name)
            self.assertNotRegex(text, r"constructor\s*\([^)]*\b(?:public|private|protected|readonly)\b", name)
            self.assertNotRegex(text, r"(?m)^\s*@\w+", name)
            self.assertNotIn("import =", text)
        server = (web / "server.ts").read_text(encoding="utf-8")
        self.assertIn("'127.0.0.1'", server)
        self.assertIn("5173", server)
        self.assertIn("default-src 'self'", server)
        self.assertIn("nosniff", server)
        self.assertIn("405", server)

    def test_web_shell_is_csp_clean_and_branded(self) -> None:
        root = self.workspace(QUILLMOOR, "shell")
        page = (web_dir(root, "quillmoor") / "public" / "index.html").read_text(encoding="utf-8")
        self.assertNotRegex(page, r"(?i)<style|\sstyle\s*=|\son[a-z]+\s*=")
        self.assertNotRegex(page, r"(?i)<script(?![^>]*\ssrc=)")
        self.assertIn('href="theme.css"', page)
        self.assertIn('src="app.js"', page)
        self.assertIn('assets/wordmark-inverse.svg', page)
        for expected in ("btn btn--primary", "btn btn--secondary", "badge badge--success", "badge badge--danger"):
            self.assertIn(expected, page)
        self.assertIn("https://support.quillmoor.example/design-technology", page)
        self.assertIsNone(EXTERNAL_LOAD.search(page))

    def test_display_identity_is_escaped_and_package_names_do_not_follow_it(self) -> None:
        def rebrand(config) -> None:
            config["identity"]["display_name"] = 'Tom & "Jerry" <Studio>'
            config["identity"]["logo_alt"] = "Tom <Jerry>"
            config["identity"]["short_name"] = "TJ&Co"

        root = self.workspace(QUILLMOOR, "rebrand", rebrand)
        self.assertTrue((report_dir(root, "quillmoor")).is_dir())
        self.assertFalse((root / "apps" / "tom-report").exists())
        branding = (report_dir(root, "quillmoor") / "src" / "quillmoor_report" / "branding.py").read_text(encoding="utf-8")
        namespace: dict = {}
        exec(compile(branding, "branding.py", "exec"), namespace)
        self.assertEqual(namespace["DISPLAY_NAME"], 'Tom & "Jerry" <Studio>')
        self.assertEqual(namespace["SHORT_NAME"], "TJ&Co")
        page = (web_dir(root, "quillmoor") / "public" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Tom &amp; &quot;Jerry&quot; &lt;Studio&gt;", page)
        self.assertNotIn("<Studio>", page)
        self.assertNotIn("<Jerry>", page)
        if tomllib is not None:
            project = tomllib.loads((report_dir(root, "quillmoor") / "pyproject.toml").read_text(encoding="utf-8"))
            self.assertIn('Tom & "Jerry" <Studio>', project["project"]["description"])
            self.assertEqual(project["project"]["name"], "quillmoor-report")
        completed = subprocess.run(
            [sys.executable, "-m", "quillmoor_report", "report", "sample.csv", "--output", str(self.base / "r.html")],
            cwd=report_dir(root, "quillmoor"),
            env=dict(RUN_ENV, PYTHONPATH="src"),
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        html_text = (self.base / "r.html").read_text(encoding="utf-8")
        self.assertIn("Tom &amp; &quot;Jerry&quot; &lt;Studio&gt;", html_text)
        self.assertNotIn("<Studio>", html_text)

    def test_each_surface_stands_alone(self) -> None:
        only_py = self.workspace(QUILLMOOR, "only-python", lambda c: c.__setitem__("surfaces", ["python-app"]))
        self.assertTrue(report_dir(only_py, "quillmoor").is_dir())
        self.assertFalse((only_py / "apps" / "quillmoor-web").exists())
        self.assertFalse((only_py / "extensions").exists())
        only_web = self.workspace(QUILLMOOR, "only-web", lambda c: c.__setitem__("surfaces", ["web-app"]))
        self.assertTrue(web_dir(only_web, "quillmoor").is_dir())
        self.assertFalse((only_web / "apps" / "quillmoor-report").exists())

    def test_foundation_validators_still_pass_on_the_workspace(self) -> None:
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
        target = report_dir(root, "quillmoor") / "src" / "quillmoor_report" / "render.py"
        target.write_text(target.read_text(encoding="utf-8") + "# local edit\n", encoding="utf-8")
        report = render_workspace(root)
        self.assertEqual(report["summary"]["outcome"], "fail")
        self.assertIn("managed-modified", json.dumps(report))


class RunPythonAppTests(AppCase):
    def test_generated_unit_tests_pass_and_the_cli_renders_the_sample(self) -> None:
        for namespace, profile in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, namespace)
                app = report_dir(root, namespace)
                env = dict(RUN_ENV, PYTHONPATH=str(app / "src"))
                suite = subprocess.run(
                    [sys.executable, "-m", "unittest", "discover", "-s", str(app / "tests")],
                    cwd=app,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                self.assertEqual(suite.returncode, 0, suite.stdout + suite.stderr)
                self.assertIn("OK", suite.stderr)
                out = self.base / (namespace + "-report.html")
                run = subprocess.run(
                    [sys.executable, "-m", namespace + "_report", "report", str(app / "sample.csv"), "--output", str(out)],
                    cwd=app,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                self.assertEqual(run.returncode, 0, run.stderr)
                page = out.read_text(encoding="utf-8")
                config = json.loads((profile / "firm.json").read_text(encoding="utf-8"))
                self.assertIn(config["identity"]["display_name"], page)
                self.assertIsNone(EXTERNAL_LOAD.search(page))
                self.assertIn("badge badge--success", page)
                self.assertNotIn("<script", page.lower())
                self.assertFalse((app / "assets").exists() or (out.parent / "assets").exists())

    def test_cli_reports_bad_input_with_exit_code_two(self) -> None:
        root = self.workspace(QUILLMOOR, "bad-input")
        app = report_dir(root, "quillmoor")
        bad = self.base / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        run = subprocess.run(
            [sys.executable, "-m", "quillmoor_report", "report", str(bad), "--output", str(self.base / "x.html")],
            cwd=app,
            env=dict(RUN_ENV, PYTHONPATH="src"),
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(run.returncode, 2)
        self.assertIn("invalid JSON", run.stderr)
        self.assertFalse((self.base / "x.html").exists())


class RunWebAppTests(AppCase):
    def test_generated_node_tests_pass(self) -> None:
        version = node_version()
        if version is None:
            self.skipTest("node is not on PATH")
        if version < MINIMUM_NODE:
            self.skipTest("node {}.{} is older than {}.{}, where type stripping is on by default".format(*version, *MINIMUM_NODE))
        node = shutil.which("node")
        for namespace, profile in PROFILES:
            with self.subTest(profile=namespace):
                root = self.workspace(profile, namespace)
                completed = subprocess.run(
                    [node, "--test"],
                    cwd=web_dir(root, namespace),
                    env=RUN_ENV,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                self.assertRegex(completed.stdout, r"\bpass 7\b")
                self.assertRegex(completed.stdout, r"\bfail 0\b")


class CheckTests(unittest.TestCase):
    def codes(self, path: str, text: str) -> list[str]:
        diags = Diagnostics()
        check_outputs([text_file(path, text, "test")], diags)
        return [d.code for d in diags.items]

    def test_script_loads_from_a_network_are_rejected(self) -> None:
        for source in (
            "import x from 'https://cdn.example/x.js';\n",
            'import * as y from "http://cdn.example/y.mjs";\n',
            "import 'https://cdn.example/side-effect.js';\n",
            "const m = await import('//cdn.example/m.js');\n",
            "fetch('https://api.example/data');\n",
            "fetch(`//api.example/data`);\n",
        ):
            for suffix in ("ts", "js", "mjs"):
                with self.subTest(source=source, suffix=suffix):
                    self.assertEqual(self.codes("apps/x/app." + suffix, source), ["output.external-resource"])

    def test_local_and_builtin_script_imports_are_allowed(self) -> None:
        source = (
            "import http from 'node:http';\n"
            "import { createServer } from 'http';\n"
            "import { helper } from './helper.js';\n"
            "const reply = await fetch(`http://127.0.0.1:${port}/`);\n"
            "const other = await fetch('http://localhost:5173/x');\n"
            "const same = await fetch('/data.json');\n"
        )
        self.assertEqual(self.codes("apps/x/test.ts", source), [])

    @unittest.skipIf(tomllib is None, "tomllib needs CPython 3.11+")
    def test_toml_must_parse(self) -> None:
        self.assertEqual(self.codes("apps/x/pyproject.toml", '[project]\nname = "ok"\n'), [])
        self.assertEqual(self.codes("apps/x/pyproject.toml", "[project\nname = ok\n"), ["output.toml-invalid"])

    def test_generated_workspace_outputs_pass_every_check(self) -> None:
        for namespace, profile in PROFILES:
            diags = Diagnostics()
            loaded = load_profile(profile, diags)
            self.assertIsNotNone(loaded, namespace)
            result = render_all(loaded)
            check = Diagnostics()
            check_outputs(result.files, check)
            self.assertEqual([d.code for d in check.items], [], namespace)
            paths = {f.path for f in result.files}
            self.assertIn("apps/{}-report/pyproject.toml".format(namespace), paths)
            self.assertIn("apps/{}-web/server.ts".format(namespace), paths)


if __name__ == "__main__":
    unittest.main()
