"""WPF surface: token ResourceDictionary, control styles, specimen, runner.

XAML is loose (XamlReader.Parse) with a ParserContext BaseUri at the specimen
folder, so packaged fonts and brand PNGs resolve by relative URI.
"""

from __future__ import annotations

from toolkit_engine import __version__
from toolkit_engine.adapters import RenderResult
from toolkit_engine.adapters import layout
from toolkit_engine.diagnostics import Diagnostic
from toolkit_engine.outputs import text_file
from toolkit_engine.profile import Profile
from toolkit_engine.textutil import number, pascal, render_file, xml
from toolkit_engine.tokens import STATUS_NAMES

ADAPTER_ID = "wpf-specimen"
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
THEME = layout.WPF_DIR + "/Theme.xaml"


def resource_key(namespace: str, token_path: str) -> str:
    """``color.surface.default`` -> ``Ns.Color.Surface.Default``."""
    return ".".join([pascal(namespace)] + [pascal(part) for part in token_path.split(".")])


def weight_name(value: int) -> str:
    candidates = sorted(WEIGHT_NAMES)
    best = min(candidates, key=lambda w: (abs(w - value), w))
    return WEIGHT_NAMES[best]


def font_family_value(profile: Profile, stack: tuple[str, ...]) -> str:
    packaged = {font.family.casefold(): font for font in profile.config.fonts}
    parts = []
    for family in stack:
        if family.casefold() in GENERIC_FAMILIES:
            continue
        font = packaged.get(family.casefold())
        if font is not None:
            folder = layout.relative(THEME, layout.font_license_path(font)).rsplit("/", 1)[0]
            parts.append("{}/#{}".format(folder, family))
        else:
            parts.append(family)
    if "segoe ui" not in {p.casefold() for p in parts}:
        parts.append("Segoe UI")
    return ", ".join(parts)


def _theme(profile: Profile) -> str:
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
            lines.append('  <FontFamily x:Key="{}">{}</FontFamily>'.format(key, xml(font_family_value(profile, token.value))))
    return render_file(
        "wpf/Theme.xaml.tmpl",
        {"foundation_version": __version__, "profile_id": profile.config.profile_id, "resources": "\n".join(lines)},
    )


def _radius(shape: str, rounded: float, height: float) -> float:
    if shape == "square":
        return 0.0
    if shape == "pill":
        return height / 2.0
    return rounded


def _controls(profile: Profile) -> str:
    ns = profile.config.technical.namespace
    a = profile.config.appearance
    t = profile.tokens

    def key(path: str) -> str:
        return resource_key(ns, path)

    height = t.px("size.control-height")
    button_radius = _radius(a.button_shape, t.px("radius.rounded"), height)
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

    def brush(resource: str | None) -> str:
        return '{{DynamicResource {}}}'.format(resource) if resource else "Transparent"

    badge_radius = {"square": 0.0, "rounded": t.px("radius.rounded"), "pill": 999.0}[a.badge_shape]
    badge_styles = []
    for status in STATUS_NAMES:
        fg = key("color.status.{}.fg".format(status))
        bg = key("color.status.{}.bg".format(status))
        if a.badge_style == "soft":
            fill, text, border = brush(bg), brush(fg), brush(bg)
        elif a.badge_style == "solid":
            fill, text, border = brush(fg), brush(key("color.surface.card")), brush(fg)
        else:
            fill, text, border = "Transparent", brush(fg), brush(fg)
        badge_styles.append(
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

    values = {
        "foundation_version": __version__,
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
        "primary_bg": brush(primary[0]),
        "primary_fg": brush(primary[1]),
        "primary_border": brush(primary[2]),
        "secondary_bg": brush(secondary[0]),
        "secondary_fg": brush(secondary[1]),
        "secondary_border": brush(secondary[2]),
        "chip_radius": number(button_radius if a.button_shape != "pill" else (height - 4) / 2.0),
        "badge_styles": "\n".join(badge_styles),
    }
    return render_file("wpf/Controls.xaml.tmpl", values)


def _specimen(profile: Profile) -> str:
    config = profile.config
    ns = config.technical.namespace
    a = config.appearance

    def button_label(text: str) -> str:
        return xml(text.upper() if a.button_label_case == "uppercase" else text)

    def badge_label(text: str) -> str:
        return xml(text.upper() if a.badge_label_case == "uppercase" else text)

    return render_file(
        "wpf/Specimen.xaml.tmpl",
        {
            "ns": pascal(ns),
            "surface_default": resource_key(ns, "color.surface.default"),
            "surface_inverse": resource_key(ns, "color.surface.inverse"),
            "text_inverse": resource_key(ns, "color.text.inverse"),
            "title": xml("{} interface specimen".format(config.identity.display_name)),
            "display_name": xml(config.identity.display_name),
            "logo_alt": xml(config.identity.logo_alt),
            "wordmark_inverse": layout.relative(layout.WPF_DIR + "/Specimen.xaml", layout.brand_path("wordmark", "inverse", "png")),
            "symbol_light": layout.relative(layout.WPF_DIR + "/Specimen.xaml", layout.brand_path("symbol", "light", "png")),
            "label_primary": button_label("Run audit"),
            "label_secondary": button_label("Preview"),
            "label_disabled": button_label("Unavailable"),
            "label_focus": button_label("Keyboard focus"),
            "badge_info": badge_label("Info"),
            "badge_success": badge_label("Passed"),
            "badge_warning": badge_label("Review"),
            "badge_danger": badge_label("Blocked"),
            "footer": xml(
                "Generated by toolkit_engine {} for {}. Native rendering of this file is the WPF evidence; "
                "the HTML guide is checked separately.".format(__version__, config.identity.display_name)
            ),
        },
    )


def render(profile: Profile) -> RenderResult:
    result = RenderResult()
    a = profile.config.appearance
    if a.registration_marks:
        result.diagnostics.append(
            Diagnostic(
                "adapter.unsupported-choice",
                "warning",
                "wpf-specimen: appearance.decorations.registration_marks",
                "Registration marks are not rendered by the WPF adapter in this version; buttons render without them.",
                "The HTML guide renders the marks.",
            )
        )
    if "uppercase" in (a.button_label_case, a.badge_label_case):
        result.diagnostics.append(
            Diagnostic(
                "adapter.label-case-static",
                "info",
                "wpf-specimen: appearance label_case",
                "WPF has no text-transform; uppercase is applied to generated specimen labels only.",
                "Tool code must supply uppercase label text itself.",
            )
        )
    result.files.append(text_file(THEME, _theme(profile), ADAPTER_ID))
    result.files.append(text_file(layout.WPF_DIR + "/Controls.xaml", _controls(profile), ADAPTER_ID))
    result.files.append(text_file(layout.WPF_DIR + "/Specimen.xaml", _specimen(profile), ADAPTER_ID))
    result.files.append(text_file(layout.WPF_DIR + "/show-specimen.ps1", render_file("wpf/show-specimen.ps1.tmpl", {}), ADAPTER_ID))
    return result
