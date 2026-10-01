"""Static contract for the wizard UI files.

The server sends ``script-src 'self'; style-src 'self'``. Anything inline in
the markup is silently blocked in a real browser, so these checks catch it
without needing one.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[1]
STATIC = REPO / "toolkit_wizard" / "static"
TEXT_SUFFIXES = (".html", ".css", ".js")
FONT_SUFFIXES = (".ttf", ".otf")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def code_only(source: str) -> str:
    """Drop block comments so prose about forbidden APIs is not mistaken for use."""
    return re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)


def text_files() -> list[Path]:
    return sorted(p for p in STATIC.rglob("*") if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES)


class _Markup(HTMLParser):
    """Collects what the CSP would block or what points off-box."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.inline_scripts: list[str] = []
        self.event_handlers: list[str] = []
        self.style_attributes: list[str] = []
        self.style_elements: list[str] = []
        self.stylesheets: list[str] = []
        self.scripts: list[str] = []
        self.urls: list[str] = []
        self._in_script = False
        self._in_style = False
        self._script_has_src = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        for name, value in attributes.items():
            if name.startswith("on"):
                self.event_handlers.append("{}[{}]".format(tag, name))
            if name == "style":
                self.style_attributes.append(tag)
            if name in ("src", "href", "action", "poster", "data", "srcset"):
                self.urls.append(value)
        if tag == "script":
            self._in_script = True
            self._script_has_src = "src" in attributes
            if "src" in attributes:
                self.scripts.append(attributes["src"])
        if tag == "style":
            self._in_style = True
            self.style_elements.append(tag)
        if tag == "link" and attributes.get("rel", "").lower() == "stylesheet":
            self.stylesheets.append(attributes.get("href", ""))

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_script = False
        if tag == "style":
            self._in_style = False

    def handle_data(self, data: str) -> None:
        if self._in_script and data.strip():
            self.inline_scripts.append(data.strip()[:60])


def parse_index() -> _Markup:
    parser = _Markup()
    parser.feed(read(STATIC / "index.html"))
    parser.close()
    return parser


class WizardStaticTests(unittest.TestCase):
    def test_expected_files_exist(self) -> None:
        for name in ("index.html", "app.css", "app.js"):
            self.assertTrue((STATIC / name).is_file(), name)

    def test_index_references_local_assets_with_static_urls(self) -> None:
        index = parse_index()
        self.assertEqual(index.stylesheets, ["/static/app.css"])
        self.assertIn("/static/app.js", index.scripts)
        for url in index.stylesheets + index.scripts:
            self.assertRegex(url, r"^/static/[A-Za-z0-9_./-]+$")
            self.assertTrue((STATIC / url[len("/static/"):]).is_file(), url)

    def test_index_has_no_inline_script_style_or_handlers(self) -> None:
        index = parse_index()
        self.assertEqual(index.inline_scripts, [], "inline <script> bodies are blocked by the CSP")
        self.assertEqual(index.event_handlers, [], "inline event handler attributes are blocked by the CSP")
        self.assertEqual(index.style_attributes, [], "style= attributes are blocked by the CSP")
        self.assertEqual(index.style_elements, [], "<style> elements are blocked by the CSP")

    def test_no_external_urls_anywhere(self) -> None:
        forbidden = re.compile(r"https?:|//")
        for path in text_files():
            with self.subTest(file=path.relative_to(STATIC).as_posix()):
                for number, line in enumerate(read(path).splitlines(), start=1):
                    self.assertIsNone(forbidden.search(line), "{}:{}: {}".format(path.name, number, line.strip()))
        for url in parse_index().urls:
            self.assertFalse(url.startswith("//") or re.match(r"^[a-z][a-z0-9+.-]*:", url, re.I), url)

    def test_every_local_reference_resolves(self) -> None:
        for path in text_files():
            text = read(path)
            if path.suffix == ".css":
                for ref in re.findall(r"url\(\s*[\"']?([^)\"']+)", text):
                    target = (path.parent / ref).resolve()
                    self.assertTrue(target.is_file(), "{} -> {}".format(path.name, ref))
            if path.suffix == ".js":
                for ref in re.findall(r"from\s+'(/static/[^']+)'", text):
                    self.assertTrue((STATIC / ref[len("/static/"):]).is_file(), "{} imports {}".format(path.name, ref))

    def test_app_reads_token_from_hash_and_sends_header(self) -> None:
        source = read(STATIC / "app.js")
        self.assertIn("location.hash", source)
        self.assertIn("sessionStorage", source)
        self.assertIn("toolkitWizardToken", source)
        self.assertIn("history.replaceState", source)
        self.assertIn("X-Toolkit-Token", source)
        self.assertIn("/api/session", source)

    def test_scripts_avoid_dynamic_html_and_code_evaluation(self) -> None:
        for path in text_files():
            if path.suffix != ".js":
                continue
            source = code_only(read(path))
            for needle in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function", "setAttribute('style'", 'setAttribute("style"'):
                self.assertNotIn(needle, source, "{} uses {}".format(path.name, needle))

    def test_browser_storage_holds_only_the_token(self) -> None:
        for path in text_files():
            if path.suffix != ".js":
                continue
            source = code_only(read(path))
            self.assertNotIn("localStorage", source)
            self.assertNotIn("indexedDB", source)
            keys = re.findall(r"sessionStorage\.(?:setItem|getItem|removeItem)\(\s*([A-Za-z_'\"]+)", source)
            self.assertTrue(all(key == "TOKEN_KEY" for key in keys), keys)
        keys = re.findall(r"sessionStorage\.setItem\(\s*([A-Za-z_'\"]+)", code_only(read(STATIC / "app.js")))
        self.assertEqual(keys, ["TOKEN_KEY"])

    def test_every_font_file_has_a_licence_beside_it(self) -> None:
        fonts = [p for p in STATIC.rglob("*") if p.is_file() and p.suffix.lower() in FONT_SUFFIXES]
        for font in fonts:
            with self.subTest(font=font.relative_to(STATIC).as_posix()):
                self.assertTrue((font.parent / "OFL.txt").is_file())


if __name__ == "__main__":
    unittest.main()
