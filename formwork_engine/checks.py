"""Validate rendered outputs in memory before anything is written (spec 4.4 step 3)."""

from __future__ import annotations

import ast
import re
import xml.etree.ElementTree as ElementTree

try:  # CPython 3.11+; on 3.10 TOML outputs are not parsed.
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

from formwork_engine.diagnostics import Diagnostics
from formwork_engine.jsonio import JsonInputError, loads_strict
from formwork_engine.outputs import OutputFile, is_reserved_path
from formwork_engine.paths import check_relative_path, find_case_collisions
from formwork_engine.png import PngError, read_png_size

# What counts as a remote reference: a network or file scheme, a
# protocol-relative or backslash-relative host, or a UNC path (which also leaks
# NTLM credentials when WPF or a browser resolves it).
_REMOTE = r"""(?:(?:https?|wss?|ftp|file)\s*:|//[A-Za-z0-9\[]|/\\|\\\\[A-Za-z0-9])"""
_LOOPBACK = r"(?!(?:(?:https?|wss?)\s*:\s*//)?(?:127\.0\.0\.1|localhost|\[::1\])[:/'\"`])"
# Resource loads in markup, styles, SVG, and XAML. Navigation links (<a>...</a>)
# are removed before scanning, so support and documentation links stay legal.
MARKUP_EXTERNAL_LOADS = (
    re.compile(
        r"""\b(?:src|srcset|href|poster|data|action|formaction|background|xlink:href|Source|ImageSource|UriSource)\s*=\s*["']?[^"'>]*?"""
        + _REMOTE,
        re.IGNORECASE,
    ),
    re.compile(r"""\burl\(\s*["']?\s*""" + _REMOTE, re.IGNORECASE),
    re.compile(r"""\bimage-set\([^)]*""" + _REMOTE, re.IGNORECASE),
    re.compile(r"""@import\b""", re.IGNORECASE),
    re.compile(r"""<base\b""", re.IGNORECASE),
    re.compile(r"""\bSource\s*=\s*["']\s*pack:""", re.IGNORECASE),
)
_ANCHORS = re.compile(r"<a\b[^>]*>.*?</a\s*>", re.IGNORECASE | re.DOTALL)
# The web-host surface maps two virtual hosts, ``<namespace>-tool.test`` and
# ``<namespace>-assets.test``, to folders inside the extension; a tool page loads its own
# assets through them and the names never leave the machine. Only that exact shape is
# exempt: any other host (including a firm's own ``.test`` name) still fails the check.
_VIRTUAL_HOSTS = re.compile(r"https://[a-z][a-z0-9]{1,23}-(?:tool|assets)\.test(?=[/'\";\s>])", re.IGNORECASE)
# Network loads from script: any quoted remote reference except loopback (the
# generated web app's own tests talk to the server they start on 127.0.0.1).
SCRIPT_EXTERNAL_LOADS = (re.compile(r"""["'`]\s*""" + _LOOPBACK + _REMOTE, re.IGNORECASE),)


def references_remote(text: str, kind: str) -> bool:
    """True if *text* (markup/css/svg/xaml or script) would load something remotely."""
    if kind == "script":
        return any(pattern.search(text) for pattern in SCRIPT_EXTERNAL_LOADS)
    scrubbed = _VIRTUAL_HOSTS.sub("", _ANCHORS.sub("<a></a>", text))
    return any(pattern.search(scrubbed) for pattern in MARKUP_EXTERNAL_LOADS)


IRONPYTHON_INCOMPATIBLE = (
    (ast.AnnAssign, "variable annotation"),
    (ast.JoinedStr, "f-string"),
    (ast.NamedExpr, "walrus operator"),
    (ast.AsyncFunctionDef, "async function"),
    (ast.Await, "await"),
    (ast.Nonlocal, "nonlocal"),
)


def check_outputs(files: list[OutputFile], diags: Diagnostics) -> None:
    seen: dict[str, str] = {}
    for item in files:
        location = "output:" + item.path
        problem = check_relative_path(item.path)
        if problem:
            diags.error("output.path-invalid", location, "Generated path {}.".format(problem))
            continue
        if is_reserved_path(item.path):
            diags.error("output.path-reserved", location, "Adapters may not write inside firm/, .formwork/, or .toolkit/.")
        if item.path in seen:
            diags.error(
                "output.duplicate",
                location,
                "Both {} and {} produce this path.".format(seen[item.path], item.adapter),
            )
        seen[item.path] = item.adapter
        _check_content(item, location, diags)
    for first, second in find_case_collisions(list(seen)):
        diags.error("output.case-collision", "output:" + second, "Collides with {} on case-insensitive filesystems.".format(first))


def _check_content(item: OutputFile, location: str, diags: Diagnostics) -> None:
    suffix = item.path.rsplit(".", 1)[-1].lower() if "." in item.path else ""
    if item.text:
        try:
            text = item.content.decode("utf-8")
        except UnicodeDecodeError:
            diags.error("output.encoding", location, "Text output is not UTF-8.")
            return
        if suffix in ("html", "css", "svg", "xaml") and references_remote(text, "markup"):
            diags.error("output.external-resource", location, "Output loads an external resource; generated surfaces must work offline.")
        if suffix in ("ts", "js", "mjs") and references_remote(text, "script"):
            diags.error("output.external-resource", location, "Script loads an external resource; generated surfaces must work offline.")
        if suffix == "xaml":
            try:
                ElementTree.fromstring(item.content)
            except ElementTree.ParseError as exc:
                diags.error("output.xaml-invalid", location, "XAML is not well-formed: {}.".format(exc))
        elif suffix in ("csproj", "addin"):
            try:
                ElementTree.fromstring(item.content)
            except ElementTree.ParseError as exc:
                diags.error("output.xml-invalid", location, "{} file is not well-formed XML: {}.".format(suffix, exc))
        elif suffix == "json":
            try:
                loads_strict(text)
            except JsonInputError as exc:
                diags.error("output.json-invalid", location, str(exc))
        elif suffix == "toml" and tomllib is not None:
            try:
                tomllib.loads(text)
            except tomllib.TOMLDecodeError as exc:
                diags.error("output.toml-invalid", location, "TOML does not parse: {}.".format(exc))
        elif suffix == "py":
            # Only extension code runs inside Revit's embedded engine; tooling
            # such as vendored validators is CPython (FOUNDATION_SPEC 1.1).
            _check_python(text, location, diags, embedded=item.path.startswith("extensions/"))
        elif suffix == "ps1" and any(ord(ch) > 127 for ch in text):
            diags.error("output.ps1-non-ascii", location, "Windows PowerShell 5.1 misreads BOM-less UTF-8; keep generated scripts ASCII.")
    elif suffix == "png":
        try:
            read_png_size(item.content)
        except PngError as exc:
            diags.error("output.png-invalid", location, "Generated PNG is invalid: {}.".format(exc))
    elif suffix == "svg":
        try:
            ElementTree.fromstring(item.content)
        except ElementTree.ParseError as exc:
            diags.error("output.svg-invalid", location, "SVG is not well-formed: {}.".format(exc))
        if references_remote(item.content.decode("utf-8", errors="replace"), "markup"):
            diags.error("output.external-resource", location, "SVG loads an external resource; generated surfaces must work offline.")


def _check_python(text: str, location: str, diags: Diagnostics, *, embedded: bool) -> None:
    """CPython parse; for embedded (pyRevit) code also a conservative IronPython 2.7
    syntax guard (not a live compile)."""
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        diags.error("output.python-invalid", location, "Generated Python does not parse: {}.".format(exc))
        return
    if not embedded:
        return
    for node in ast.walk(tree):
        for kind, label in IRONPYTHON_INCOMPATIBLE:
            if isinstance(node, kind):
                diags.error("output.ironpython-syntax", location, "Uses {} (not IronPython 2.7 compatible).".format(label))
                return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            node.returns is not None or any(arg.annotation is not None for arg in node.args.args)
        ):
            diags.error("output.ironpython-syntax", location, "Uses function annotations (not IronPython 2.7 compatible).")
            return
