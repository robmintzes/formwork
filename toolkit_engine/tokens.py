"""DTCG 2025.10 subset: parsing, alias resolution, and the required role contract.

See docs/product/FOUNDATION_SPEC.md section 3 for the supported subset.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from toolkit_engine.diagnostics import Diagnostics, did_you_mean

SUPPORTED_TYPES = ("color", "dimension", "fontFamily", "fontWeight", "number")
KNOWN_DTCG_TYPES = SUPPORTED_TYPES + (
    "duration",
    "cubicBezier",
    "strokeStyle",
    "border",
    "transition",
    "shadow",
    "gradient",
    "typography",
)
TOKEN_PROPERTIES = ("$value", "$type", "$description", "$extensions", "$deprecated")
GROUP_PROPERTIES = ("$type", "$description", "$extensions", "$deprecated")
UNSUPPORTED_FEATURES = ("$ref", "$extends", "$root")
FONT_WEIGHT_ALIASES = {
    "thin": 100,
    "hairline": 100,
    "extra-light": 200,
    "ultra-light": 200,
    "light": 300,
    "normal": 400,
    "regular": 400,
    "book": 400,
    "medium": 500,
    "semi-bold": 600,
    "demi-bold": 600,
    "bold": 700,
    "extra-bold": 800,
    "ultra-bold": 800,
    "black": 900,
    "heavy": 900,
    "extra-black": 950,
    "ultra-black": 950,
}
ALIAS_PATTERN = re.compile(r"^\{([^{}]+)\}$")
HEX_PATTERN = re.compile(r"^#([0-9a-fA-F]{6})$")

_STATUS = ("info", "success", "warning", "danger")
REQUIRED_ROLES: dict[str, str] = {}
for _name in ("default", "card", "sunken", "inverse"):
    REQUIRED_ROLES["color.surface." + _name] = "color"
for _name in ("primary", "secondary", "inverse"):
    REQUIRED_ROLES["color.text." + _name] = "color"
for _name in ("subtle", "strong"):
    REQUIRED_ROLES["color.line." + _name] = "color"
for _name in ("default", "strong", "soft"):
    REQUIRED_ROLES["color.accent." + _name] = "color"
for _name in ("bg", "fg"):
    REQUIRED_ROLES["color.action.primary." + _name] = "color"
for _name in ("bg", "fg", "border"):
    REQUIRED_ROLES["color.action.secondary." + _name] = "color"
REQUIRED_ROLES["color.focus.ring"] = "color"
for _status in _STATUS:
    for _name in ("fg", "bg"):
        REQUIRED_ROLES["color.status.{}.{}".format(_status, _name)] = "color"
for _name in ("display", "body", "label", "code"):
    REQUIRED_ROLES["font." + _name] = "fontFamily"
for _name in ("display", "body", "strong", "label"):
    REQUIRED_ROLES["font-weight." + _name] = "fontWeight"
for _name in ("display", "title", "body", "small", "label", "code"):
    REQUIRED_ROLES["font-size." + _name] = "dimension"
for _name in ("xs", "sm", "md", "lg", "xl"):
    REQUIRED_ROLES["space." + _name] = "dimension"
REQUIRED_ROLES["radius.rounded"] = "dimension"
for _name in ("hairline", "control", "focus"):
    REQUIRED_ROLES["stroke." + _name] = "dimension"
REQUIRED_ROLES["size.control-height"] = "dimension"
REQUIRED_ROLES["tracking.label"] = "number"
STATUS_NAMES = _STATUS


@dataclass(frozen=True)
class Color:
    """An sRGB color with 8-bit channels and a 0-1 alpha."""

    red: int
    green: int
    blue: int
    alpha: float = 1.0

    @property
    def hex(self) -> str:
        return "#{:02X}{:02X}{:02X}".format(self.red, self.green, self.blue)

    @property
    def argb_hex(self) -> str:
        """WPF ``#AARRGGBB`` form (``#RRGGBB`` when opaque)."""
        if self.alpha >= 1.0:
            return self.hex
        return "#{:02X}{:02X}{:02X}{:02X}".format(
            int(round(self.alpha * 255)), self.red, self.green, self.blue
        )

    @property
    def css(self) -> str:
        if self.alpha >= 1.0:
            return self.hex
        return "rgba({}, {}, {}, {})".format(
            self.red, self.green, self.blue, _trim_number(self.alpha)
        )

    @property
    def rgba(self) -> tuple[int, int, int, int]:
        return (self.red, self.green, self.blue, int(round(self.alpha * 255)))

    @classmethod
    def from_hex(cls, value: str) -> "Color":
        match = HEX_PATTERN.match(value)
        if not match:
            raise ValueError("expected #RRGGBB, got {!r}".format(value))
        digits = match.group(1)
        return cls(int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))

    def relative_luminance(self) -> float:
        def channel(value: int) -> float:
            c = value / 255.0
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

        return (
            0.2126 * channel(self.red)
            + 0.7152 * channel(self.green)
            + 0.0722 * channel(self.blue)
        )


def contrast_ratio(foreground: Color, background: Color) -> float:
    """WCAG 2.x contrast ratio of two opaque colors."""
    lighter = max(foreground.relative_luminance(), background.relative_luminance())
    darker = min(foreground.relative_luminance(), background.relative_luminance())
    return (lighter + 0.05) / (darker + 0.05)


def _trim_number(value: float) -> str:
    text = "{:.4f}".format(value).rstrip("0").rstrip(".")
    return text if text else "0"


@dataclass(frozen=True)
class Token:
    """A resolved token. ``alias_chain`` lists the paths followed, if any."""

    path: str
    type: str
    value: Any
    alias_chain: tuple[str, ...] = ()


@dataclass
class _Raw:
    path: str
    declared_type: str | None
    raw_value: Any
    pointer: str


def _pointer(parts: list[str]) -> str:
    escaped = [part.replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else ""


class TokenSet:
    """Resolved tokens keyed by dotted path."""

    def __init__(self, tokens: dict[str, Token]) -> None:
        self.tokens = tokens

    def __contains__(self, path: str) -> bool:
        return path in self.tokens

    def get(self, path: str) -> Token:
        return self.tokens[path]

    def value(self, path: str) -> Any:
        return self.tokens[path].value

    def color(self, path: str) -> Color:
        token = self.tokens[path]
        if token.type != "color":
            raise TypeError("{} is {}, not color".format(path, token.type))
        return token.value

    def px(self, path: str) -> float:
        token = self.tokens[path]
        if token.type != "dimension":
            raise TypeError("{} is {}, not dimension".format(path, token.type))
        return token.value

    def items(self) -> list[tuple[str, Token]]:
        return sorted(self.tokens.items())


def parse_tokens(document: Any, source: str, diags: Diagnostics) -> TokenSet | None:
    """Parse and resolve a token document. Returns None when errors were found."""
    errors_before = sum(1 for item in diags.items if item.severity == "error")
    raw: dict[str, _Raw] = {}
    if not isinstance(document, dict):
        diags.error("token.document-invalid", source, "Token file must contain a JSON object.")
        return None
    _walk(document, [], None, source, raw, diags)

    resolved: dict[str, Token | None] = {}
    for path in sorted(raw):
        _resolve(path, raw, resolved, source, diags, ())

    errors_after = sum(1 for item in diags.items if item.severity == "error")
    if errors_after > errors_before:
        return None
    return TokenSet({k: v for k, v in resolved.items() if v is not None})


def _walk(
    node: dict[str, Any],
    parts: list[str],
    inherited_type: str | None,
    source: str,
    raw: dict[str, _Raw],
    diags: Diagnostics,
) -> None:
    location = source + "#" + _pointer(parts)
    group_type = inherited_type
    for key, value in node.items():
        if not key.startswith("$"):
            continue
        if key in UNSUPPORTED_FEATURES:
            diags.error(
                "token.feature-unsupported",
                location,
                "DTCG feature {} is not supported by this foundation version.".format(key),
                "Use curly-brace aliases such as {color.brand.500} instead.",
            )
        elif key not in GROUP_PROPERTIES:
            diags.error(
                "token.property-unknown",
                location,
                "Unknown group property {}.".format(key),
                did_you_mean(key, GROUP_PROPERTIES),
            )
        elif key == "$type":
            if _check_type(value, location, diags):
                group_type = value

    for key, child in node.items():
        if key.startswith("$"):
            continue
        child_parts = parts + [key]
        child_location = source + "#" + _pointer(child_parts)
        if any(ch in key for ch in "{}.") or not key:
            diags.error(
                "token.name-invalid",
                child_location,
                "Token and group names must be non-empty and must not contain '{', '}', or '.'.",
            )
            continue
        if not isinstance(child, dict):
            diags.error(
                "token.node-invalid",
                child_location,
                "Expected a token (object with $value) or a group (object).",
            )
            continue
        if "$value" in child or "$ref" in child:
            _read_token(child, child_parts, group_type, source, raw, diags)
        else:
            _walk(child, child_parts, group_type, source, raw, diags)


def _check_type(value: Any, location: str, diags: Diagnostics) -> bool:
    if value in SUPPORTED_TYPES:
        return True
    if value in KNOWN_DTCG_TYPES:
        diags.error(
            "token.type-unsupported",
            location,
            "DTCG type {!r} is not supported by this foundation version.".format(value),
            "Supported types: {}.".format(", ".join(SUPPORTED_TYPES)),
        )
    else:
        diags.error(
            "token.type-unknown",
            location,
            "Unknown token type {!r}.".format(value),
            did_you_mean(str(value), KNOWN_DTCG_TYPES),
        )
    return False


def _read_token(
    node: dict[str, Any],
    parts: list[str],
    inherited_type: str | None,
    source: str,
    raw: dict[str, _Raw],
    diags: Diagnostics,
) -> None:
    location = source + "#" + _pointer(parts)
    for key in node:
        if key in UNSUPPORTED_FEATURES:
            diags.error(
                "token.feature-unsupported",
                location,
                "DTCG feature {} is not supported by this foundation version.".format(key),
                "Use curly-brace aliases such as {color.brand.500} instead.",
            )
            return
        if key not in TOKEN_PROPERTIES:
            diags.error(
                "token.property-unknown",
                location,
                "Unknown token property {!r}.".format(key),
                did_you_mean(key, TOKEN_PROPERTIES),
            )
    declared = inherited_type
    if "$type" in node:
        if not _check_type(node["$type"], location, diags):
            return
        declared = node["$type"]
    path = ".".join(parts)
    raw[path] = _Raw(path, declared, node.get("$value"), location)


def _resolve(
    path: str,
    raw: dict[str, _Raw],
    resolved: dict[str, Token | None],
    source: str,
    diags: Diagnostics,
    stack: tuple[str, ...],
) -> Token | None:
    """Resolve *path*, memoizing failures so one bad chain reports once."""
    if path in resolved:
        return resolved[path]
    token = _resolve_uncached(path, raw, resolved, source, diags, stack)
    if token is None and path not in resolved:
        resolved[path] = None
    return token


def _resolve_uncached(
    path: str,
    raw: dict[str, _Raw],
    resolved: dict[str, Token | None],
    source: str,
    diags: Diagnostics,
    stack: tuple[str, ...],
) -> Token | None:
    entry = raw[path]
    value = entry.raw_value
    alias = ALIAS_PATTERN.match(value) if isinstance(value, str) else None
    if alias:
        target = alias.group(1)
        if target in stack or target == path:
            chain = " -> ".join(stack + (path, target))
            diags.error(
                "token.alias-cycle",
                entry.pointer,
                "Circular alias: {}.".format(chain),
                "Point one token in the chain at a literal value.",
            )
            return None
        if target not in raw:
            diags.error(
                "token.alias-missing",
                entry.pointer,
                "Alias {{{}}} does not name a token.".format(target),
                did_you_mean(target, raw.keys()),
            )
            return None
        target_token = _resolve(target, raw, resolved, source, diags, stack + (path,))
        if target_token is None:
            return None
        if entry.declared_type and entry.declared_type != target_token.type:
            diags.error(
                "token.alias-type-mismatch",
                entry.pointer,
                "{} is declared {} but its alias {} is {}.".format(
                    path, entry.declared_type, target, target_token.type
                ),
            )
            return None
        token = Token(path, target_token.type, target_token.value, (target,) + target_token.alias_chain)
        resolved[path] = token
        return token

    if entry.declared_type is None:
        diags.error(
            "token.type-missing",
            entry.pointer,
            "Token has no $type on itself or any parent group.",
        )
        return None
    parsed = _parse_value(entry.declared_type, value, entry.pointer, diags)
    if parsed is None:
        return None
    token = Token(path, entry.declared_type, parsed)
    resolved[path] = token
    return token


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _parse_value(kind: str, value: Any, location: str, diags: Diagnostics) -> Any:
    if kind == "color":
        return _parse_color(value, location, diags)
    if kind == "dimension":
        if not isinstance(value, dict) or set(value) != {"value", "unit"} or not _is_number(value.get("value")):
            diags.error(
                "token.dimension-invalid",
                location,
                "Dimension must be {\"value\": <number>, \"unit\": \"px\"}.",
            )
            return None
        if value["unit"] == "rem":
            diags.error(
                "token.unit-unsupported",
                location,
                "rem dimensions are not supported because WPF has no root font size.",
                "Use px (device-independent pixels).",
            )
            return None
        if value["unit"] != "px":
            diags.error("token.dimension-invalid", location, "Unknown unit {!r}.".format(value["unit"]))
            return None
        return float(value["value"])
    if kind == "fontFamily":
        if isinstance(value, str) and value.strip():
            return (value.strip(),)
        if isinstance(value, list) and value and all(isinstance(v, str) and v.strip() for v in value):
            return tuple(v.strip() for v in value)
        diags.error("token.font-family-invalid", location, "fontFamily must be a non-empty string or list of strings.")
        return None
    if kind == "fontWeight":
        if _is_number(value) and 1 <= value <= 1000:
            return int(value)
        if isinstance(value, str) and value in FONT_WEIGHT_ALIASES:
            return FONT_WEIGHT_ALIASES[value]
        diags.error(
            "token.font-weight-invalid",
            location,
            "fontWeight must be 1-1000 or a DTCG weight alias.",
            did_you_mean(str(value), FONT_WEIGHT_ALIASES),
        )
        return None
    if kind == "number":
        if _is_number(value):
            return float(value)
        diags.error("token.number-invalid", location, "number tokens must be JSON numbers.")
        return None
    raise AssertionError(kind)


def _parse_color(value: Any, location: str, diags: Diagnostics) -> Color | None:
    if not isinstance(value, dict):
        diags.error(
            "token.color-invalid",
            location,
            "Color must be an object with colorSpace and components.",
            "Example: {\"colorSpace\": \"srgb\", \"components\": [0.18, 0.27, 0.32], \"hex\": \"#2F4452\"}",
        )
        return None
    unknown = set(value) - {"colorSpace", "components", "alpha", "hex"}
    if unknown:
        diags.error("token.color-invalid", location, "Unknown color fields: {}.".format(sorted(unknown)))
        return None
    if value.get("colorSpace") != "srgb":
        diags.error(
            "token.color-space-unsupported",
            location,
            "Color space {!r} is not supported; use srgb.".format(value.get("colorSpace")),
        )
        return None
    components = value.get("components")
    if (
        not isinstance(components, list)
        or len(components) != 3
        or not all(_is_number(c) and 0 <= c <= 1 for c in components)
    ):
        diags.error("token.color-invalid", location, "components must be three numbers between 0 and 1.")
        return None
    alpha = value.get("alpha", 1.0)
    if not _is_number(alpha) or not 0 <= alpha <= 1:
        diags.error("token.color-invalid", location, "alpha must be a number between 0 and 1.")
        return None
    channels = [int(round(c * 255)) for c in components]
    color = Color(channels[0], channels[1], channels[2], float(alpha))
    if "hex" in value:
        try:
            declared = Color.from_hex(str(value["hex"]))
        except ValueError:
            diags.error("token.color-invalid", location, "hex must be #RRGGBB.")
            return None
        if max(
            abs(declared.red - color.red),
            abs(declared.green - color.green),
            abs(declared.blue - color.blue),
        ) > 1:
            diags.error(
                "token.color-hex-mismatch",
                location,
                "hex {} disagrees with components ({}).".format(value["hex"], color.hex),
                "Regenerate one from the other.",
            )
            return None
        color = Color(declared.red, declared.green, declared.blue, float(alpha))
    return color


def color_value(hex_value: str, alpha: float | None = None) -> dict[str, Any]:
    """Build a DTCG color value from ``#RRGGBB`` (used by profile tooling and tests)."""
    color = Color.from_hex(hex_value)
    result: dict[str, Any] = {
        "colorSpace": "srgb",
        "components": [round(color.red / 255.0, 4), round(color.green / 255.0, 4), round(color.blue / 255.0, 4)],
        "hex": color.hex,
    }
    if alpha is not None:
        result["alpha"] = alpha
    return result


def check_required_roles(tokens: TokenSet, source: str, diags: Diagnostics) -> None:
    for path, kind in sorted(REQUIRED_ROLES.items()):
        if path not in tokens:
            diags.error(
                "token.role-missing",
                source,
                "Required role {} ({}) is missing.".format(path, kind),
                "Add it, usually as an alias into palette.*.",
            )
        elif tokens.get(path).type != kind:
            diags.error(
                "token.role-type",
                source,
                "Role {} must be {}, found {}.".format(path, kind, tokens.get(path).type),
            )
