"""Strict templating and context-specific escaping for generated files."""

from __future__ import annotations

from html import escape as _html_escape
from pathlib import Path
import re

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
PLACEHOLDER = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")


class TemplateError(ValueError):
    pass


def render(template: str, values: dict[str, str]) -> str:
    """Replace ``{{ name }}`` placeholders; unknown or unused names are errors."""
    used: set[str] = set()

    def substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            raise TemplateError("template placeholder {!r} has no value".format(name))
        used.add(name)
        return values[name]

    result = PLACEHOLDER.sub(substitute, template)
    unused = set(values) - used
    if unused:
        raise TemplateError("values not used by template: {}".format(sorted(unused)))
    return result


def render_file(name: str, values: dict[str, str]) -> str:
    return render((TEMPLATE_DIR / name).read_text(encoding="utf-8"), values)


def html(value: str) -> str:
    return _html_escape(value, quote=True)


def xml(value: str) -> str:
    return _html_escape(value, quote=True)


def py_string(value: str) -> str:
    """Double-quoted Python literal valid in IronPython 2.7 and CPython 3."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def yaml_scalar(value: str) -> str:
    """Plain YAML scalar when safe, otherwise double-quoted."""
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .,()&'/_+-]*", value) and not value.endswith(" ") and ": " not in value:
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def md(value: str) -> str:
    """Escape Markdown control characters in inline text."""
    return re.sub(r"([\\`*_{}\[\]<>#|])", r"\\\1", value)


def css_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def kebab(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def pascal(value: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in re.split(r"[^A-Za-z0-9]+", value) if part)


def number(value: float) -> str:
    """Compact decimal without trailing zeros ("16", "0.5")."""
    text = "{:.4f}".format(value).rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text
