"""Validate rendered outputs in memory before anything is written (spec 4.4 step 3)."""

from __future__ import annotations

import ast
import re
import xml.etree.ElementTree as ElementTree

from toolkit_engine.diagnostics import Diagnostics
from toolkit_engine.jsonio import JsonInputError, loads_strict
from toolkit_engine.outputs import RESERVED_PREFIXES, OutputFile
from toolkit_engine.paths import check_relative_path, find_case_collisions
from toolkit_engine.png import PngError, read_png_size

# Resource loads that would need a network. Navigation links (<a href>) are allowed.
EXTERNAL_LOADS = (
    re.compile(r"""\bsrc\s*=\s*["']?\s*(?:https?:)?//""", re.IGNORECASE),
    re.compile(r"""<link\b[^>]*\bhref\s*=\s*["']?\s*(?:https?:)?//""", re.IGNORECASE),
    re.compile(r"""url\(\s*["']?\s*(?:https?:)?//""", re.IGNORECASE),
    re.compile(r"""@import\b""", re.IGNORECASE),
    re.compile(r"""\bSource\s*=\s*["']\s*(?:https?|pack):""", re.IGNORECASE),
)
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
        if item.path.startswith(RESERVED_PREFIXES):
            diags.error("output.path-reserved", location, "Adapters may not write inside firm/ or .toolkit/.")
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
        if suffix in ("html", "css", "svg", "xaml"):
            for pattern in EXTERNAL_LOADS:
                if pattern.search(text):
                    diags.error("output.external-resource", location, "Output loads an external resource; generated surfaces must work offline.")
                    break
        if suffix == "xaml":
            try:
                ElementTree.fromstring(item.content)
            except ElementTree.ParseError as exc:
                diags.error("output.xaml-invalid", location, "XAML is not well-formed: {}.".format(exc))
        elif suffix == "json":
            try:
                loads_strict(text)
            except JsonInputError as exc:
                diags.error("output.json-invalid", location, str(exc))
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
