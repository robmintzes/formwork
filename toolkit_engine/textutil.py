"""Strict templating and context-specific escaping for generated files."""

from __future__ import annotations

from html import escape as _html_escape
import json
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


def json_string(value: str) -> str:
    """Double-quoted string literal that is also a valid TOML basic string and Python str literal.

    Non-ASCII text stays literal (the files are UTF-8); quotes, backslashes and control
    characters are escaped with the JSON escapes both languages share.
    """
    return json.dumps(value, ensure_ascii=False)


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


def cs_string(value: str) -> str:
    """Double-quoted C# string literal; non-ASCII and control characters become C# unicode escapes."""
    escapes = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}
    parts = ['"']
    for ch in value:
        if ch in escapes:
            parts.append(escapes[ch])
        elif 32 <= ord(ch) <= 126:
            parts.append(ch)
        else:
            code = ord(ch)
            units = [code]
            if code > 0xFFFF:
                code -= 0x10000
                units = [0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF)]
            parts.extend("\\u{:04X}".format(unit) for unit in units)
    parts.append('"')
    return "".join(parts)


def msbuild_text(value: str) -> str:
    """Text safe as an MSBuild property value (special characters %-escaped), then XML-escaped."""
    escaped = "".join(
        "%{:02X}".format(ord(ch)) if ch in "%$@';*?" else ch for ch in value
    )
    return xml(escaped)
