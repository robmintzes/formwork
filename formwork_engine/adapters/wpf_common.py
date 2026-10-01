"""Token-to-WPF logic shared by every adapter that emits XAML resources.

``wpf-specimen`` and ``ui-kit`` both generate a Theme.xaml (one resource per
token) and a Controls.xaml (styles resolved from appearance choices). The key
scheme and the shape rules live here so the two cannot drift: a button is the
same button in the specimen and in a generated dialog.
"""

from __future__ import annotations

from typing import Callable

from formwork_engine import __version__
from formwork_engine.adapters import layout
from formwork_engine.profile import Profile
from formwork_engine.textutil import number, pascal, render_file, xml
from formwork_engine.config import FontSpec
from formwork_engine.tokens import STATUS_NAMES

WEIGHT_NAMES = {
    100: "Thin",
    200: "ExtraLight",
    300: "Light",
    400: "Normal",
    500: "Medium",
    600: "SemiBold",
    700: "Bold",
    800: "ExtraBold",
    900: "Black",
    950: "ExtraBlack",
}
GENERIC_FAMILIES = {"serif", "sans-serif", "monospace", "system-ui", "ui-monospace", "cursive"}
FontFolder = Callable[[FontSpec], str]


def resource_key(namespace: str, token_path: str) -> str:
    """``color.surface.default`` -> ``Ns.Color.Surface.Default``."""
    return ".".join([pascal(namespace)] + [pascal(part) for part in token_path.split(".")])


def weight_name(value: int) -> str:
    candidates = sorted(WEIGHT_NAMES)
    best = min(candidates, key=lambda w: (abs(w - value), w))
    return WEIGHT_NAMES[best]


def specimen_font_folder(font: FontSpec) -> str:
    """Folder of a packaged family, relative to the specimen's Theme.xaml."""
    return layout.relative(layout.WPF_DIR + "/Theme.xaml", layout.font_license_path(font)).rsplit("/", 1)[0]


def font_family_value(profile: Profile, stack: tuple[str, ...], font_folder: FontFolder = specimen_font_folder) -> str:
    packaged = {font.family.casefold(): font for font in profile.config.fonts}
    parts = []
    for family in stack:
        if family.casefold() in GENERIC_FAMILIES:
            continue
        font = packaged.get(family.casefold())
        if font is not None:
            parts.append("{}/#{}".format(font_folder(font), family))
        else:
            parts.append(family)
    if "segoe ui" not in {p.casefold() for p in parts}:
        parts.append("Segoe UI")
    return ", ".join(parts)


def render_theme(profile: Profile, font_folder: FontFolder = specimen_font_folder) -> str:
    ns = profile.config.technical.namespace
    lines = []
    for path, token in profile.tokens.items():
        key = xml(resource_key(ns, path))
        if token.type == "color":
            lines.append('  <SolidColorBrush x:Key="{}" Color="{}"/>'.format(key, token.value.argb_hex))
        elif token.type in ("dimension", "number"):
            lines.append('  <sys:Double x:Key="{}">{}</sys:Double>'.format(key, number(token.value)))
        elif token.type == "fontWeight":
            lines.append('  <FontWeight x:Key="{}">{}</FontWeight>'.format(key, weight_name(token.value)))
        elif token.type == "fontFamily":
            lines.append('  <FontFamily x:Key="{}">{}</FontFamily>'.format(key, xml(font_family_value(profile, token.value, font_folder))))
    return render_file(
        "wpf/Theme.xaml.tmpl",
        {"foundation_version": __version__, "profile_id": profile.config.profile_id, "resources": "\n".join(lines)},
    )


def shape_radius(shape: str, rounded: float, height: float) -> float:
    if shape == "square":
        return 0.0
    if shape == "pill":
        return height / 2.0
    return rounded


def _brush(resource: str | None) -> str:
    return '{{DynamicResource {}}}'.format(resource) if resource else "Transparent"


def control_values(profile: Profile) -> dict[str, str]:
    """Resolved values for the shared Controls template (keys are placeholder names)."""
    ns = profile.config.technical.namespace
    a = profile.config.appearance
    t = profile.tokens

    def key(path: str) -> str:
        return resource_key(ns, path)

    height = t.px("size.control-height")
    button_radius = shape_radius(a.button_shape, t.px("radius.rounded"), height)
    focus = t.px("stroke.focus")
    gap = 2.0
    ring_radius = button_radius + focus + gap if button_radius else 0.0

    if a.button_primary == "solid":
        primary = (key("color.action.primary.bg"), key("color.action.primary.fg"), key("color.action.primary.bg"))
    else:
        primary = (None, key("color.action.primary.bg"), key("color.action.primary.bg"))
    secondary = {
        "outline": (key("color.action.secondary.bg"), key("color.action.secondary.fg"), key("color.action.secondary.border")),
        "tonal": (key("color.accent.soft"), key("color.action.secondary.fg"), key("color.accent.soft")),
        "ghost": (None, key("color.action.secondary.fg"), None),
    }[a.button_secondary]

    return {
        "ns": pascal(ns),
        "font_body": key("font.body"),
        "font_display": key("font.display"),
        "font_label": key("font.label"),
        "font_code": key("font.code"),
        "size_display": key("font-size.display"),
        "size_title": key("font-size.title"),
        "size_body": key("font-size.body"),
        "size_small": key("font-size.small"),
        "size_label": key("font-size.label"),
        "size_code": key("font-size.code"),
        "weight_display": key("font-weight.display"),
        "weight_body": key("font-weight.body"),
        "weight_strong": key("font-weight.strong"),
        "weight_label": key("font-weight.label"),
        "text_primary": key("color.text.primary"),
        "text_secondary": key("color.text.secondary"),
        "surface_card": key("color.surface.card"),
        "line_subtle": key("color.line.subtle"),
        "line_strong": key("color.line.strong"),
        "accent_default": key("color.accent.default"),
        "accent_soft": key("color.accent.soft"),
        "focus_ring": key("color.focus.ring"),
        "control_height": number(height),
        "button_radius": number(button_radius),
        "ring_radius": number(ring_radius),
        "ring_margin": number(-(focus + gap)),
        "focus_stroke": number(focus),
        "control_stroke": number(t.px("stroke.control")),
        "space_md": number(t.px("space.md")),
        "space_sm": number(t.px("space.sm")),
        "primary_bg": _brush(primary[0]),
        "primary_fg": _brush(primary[1]),
        "primary_border": _brush(primary[2]),
        "secondary_bg": _brush(secondary[0]),
        "secondary_fg": _brush(secondary[1]),
        "secondary_border": _brush(secondary[2]),
        "chip_radius": number(button_radius if a.button_shape != "pill" else (height - 4) / 2.0),
    }


def badge_styles(profile: Profile) -> str:
    ns = profile.config.technical.namespace
    a = profile.config.appearance
    t = profile.tokens

    def key(path: str) -> str:
        return resource_key(ns, path)

    badge_radius = {"square": 0.0, "rounded": t.px("radius.rounded"), "pill": 999.0}[a.badge_shape]
    styles = []
    for status in STATUS_NAMES:
        fg = key("color.status.{}.fg".format(status))
        bg = key("color.status.{}.bg".format(status))
        if a.badge_style == "soft":
            fill, text, border = _brush(bg), _brush(fg), _brush(bg)
        elif a.badge_style == "solid":
            fill, text, border = _brush(fg), _brush(key("color.surface.card")), _brush(fg)
        else:
            fill, text, border = "Transparent", _brush(fg), _brush(fg)
        styles.append(
            render_file(
                "wpf/badge-style.xaml.tmpl",
                {
                    "ns": pascal(ns),
                    "status": pascal(status),
                    "fill": fill,
                    "text": text,
                    "border": border,
                    "radius": number(badge_radius),
                    "stroke": number(t.px("stroke.control")),
                    "font_label": key("font.label"),
                    "size_label": key("font-size.label"),
                    "weight_label": key("font-weight.label"),
                },
            )
        )
    return "\n".join(styles)


def render_controls(profile: Profile) -> str:
    """The specimen's Controls dictionary: text, button, chip, list, card, badge styles."""
    values = control_values(profile)
    values["foundation_version"] = __version__
    values["badge_styles"] = badge_styles(profile)
    return render_file("wpf/Controls.xaml.tmpl", values)


def _kit_extra_controls(profile: Profile) -> str:
    t = profile.tokens
    a = profile.config.appearance
    rounded = t.px("radius.rounded")
    values = {
        "ns": pascal(profile.config.technical.namespace),
        "space_sm": number(t.px("space.sm")),
        "space_md": number(t.px("space.md")),
        "space_xl": number(t.px("space.xl")),
        "control_stroke": number(t.px("stroke.control")),
        "control_height": number(t.px("size.control-height")),
        "field_radius": number(0.0 if a.button_shape == "square" else rounded),
        "check_radius": number(0.0 if a.button_shape == "square" else min(rounded, 3.0)),
    }
    return render_file("ui_kit/Controls.extra.xaml.tmpl", values)


def render_kit_controls(profile: Profile) -> str:
    """The specimen's Controls dictionary extended with the UI kit's own styles.

    Shared by every surface that ships kit-styled windows (``ui-kit``, ``revit-addin``)."""
    closing = "</ResourceDictionary>"
    base = render_controls(profile).rstrip()
    if not base.endswith(closing):
        raise RuntimeError("the specimen Controls dictionary no longer ends with </ResourceDictionary>")
    return base[: -len(closing)].rstrip("\n") + "\n" + _kit_extra_controls(profile) + closing + "\n"
