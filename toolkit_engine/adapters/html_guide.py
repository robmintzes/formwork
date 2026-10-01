"""HTML surface: a self-contained, offline Hello Button guide with a component specimen."""

from __future__ import annotations

from toolkit_engine import __version__
from toolkit_engine.adapters import RenderResult
from toolkit_engine.adapters import layout
from toolkit_engine.outputs import text_file
from toolkit_engine.profile import Profile
from toolkit_engine.textutil import css_string, html, number, render_file
from toolkit_engine.tokens import STATUS_NAMES

ADAPTER_ID = "html-guide"
GENERIC_FAMILIES = {"serif", "sans-serif", "monospace", "system-ui", "ui-monospace", "cursive"}


def css_var(namespace: str, token_path: str) -> str:
    return "--{}-{}".format(namespace, token_path.replace(".", "-"))


def _font_stack(stack: tuple[str, ...]) -> str:
    return ", ".join(name if name in GENERIC_FAMILIES else css_string(name) for name in stack)


def _token_declarations(profile: Profile) -> str:
    ns = profile.config.technical.namespace
    lines = []
    for path, token in profile.tokens.items():
        if token.type == "color":
            value = token.value.css
        elif token.type == "dimension":
            value = number(token.value) + "px"
        elif token.type == "fontFamily":
            value = _font_stack(token.value)
        else:
            value = number(token.value) if token.type == "number" else str(token.value)
        lines.append("  {}: {};".format(css_var(ns, path), value))
    return "\n".join(lines)


def _font_faces(profile: Profile) -> str:
    blocks = []
    for font in profile.config.fonts:
        for font_file in font.files:
            fmt = "truetype" if font_file.path.lower().endswith(".ttf") else "opentype"
            blocks.append(
                "@font-face {{ font-family: {}; src: url({}) format(\"{}\"); font-weight: {}; font-style: {}; font-display: swap; }}".format(
                    css_string(font.family),
                    css_string(layout.relative(layout.GUIDE, layout.font_path(font, font_file))),
                    fmt,
                    font_file.weight,
                    font_file.style,
                )
            )
    return "\n".join(blocks)


def _component_css(profile: Profile) -> str:
    ns = profile.config.technical.namespace
    a = profile.config.appearance
    t = profile.tokens

    def v(path: str) -> str:
        return "var({})".format(css_var(ns, path))

    height = t.px("size.control-height")
    radius = {"square": "0", "rounded": v("radius.rounded"), "pill": number(height / 2.0) + "px"}[a.button_shape]
    badge_radius = {"square": "0", "rounded": v("radius.rounded"), "pill": "999px"}[a.badge_shape]
    if a.button_primary == "solid":
        primary = (v("color.action.primary.bg"), v("color.action.primary.fg"), v("color.action.primary.bg"))
    else:
        primary = ("transparent", v("color.action.primary.bg"), v("color.action.primary.bg"))
    secondary = {
        "outline": (v("color.action.secondary.bg"), v("color.action.secondary.fg"), v("color.action.secondary.border")),
        "tonal": (v("color.accent.soft"), v("color.action.secondary.fg"), v("color.accent.soft")),
        "ghost": ("transparent", v("color.action.secondary.fg"), "transparent"),
    }[a.button_secondary]

    badges = []
    for status in STATUS_NAMES:
        fg, bg = v("color.status.{}.fg".format(status)), v("color.status.{}.bg".format(status))
        fill, text, border = {
            "soft": (bg, fg, bg),
            "solid": (fg, v("color.surface.card"), fg),
            "outline": ("transparent", fg, fg),
        }[a.badge_style]
        badges.append(
            ".badge--{s} {{ background: {f}; color: {t}; border-color: {b}; }}".format(s=status, f=fill, t=text, b=border)
        )

    marks = ""
    if a.registration_marks:
        mark = v("color.text.secondary")
        marks = (
            ".btn--primary { position: relative; }\n"
            ".btn--primary::before { content: \"\"; position: absolute; inset: -6px; pointer-events: none;\n"
            "  background:\n"
            "    linear-gradient(MARK, MARK) left top / 9px 1px no-repeat,\n"
            "    linear-gradient(MARK, MARK) left top / 1px 9px no-repeat,\n"
            "    linear-gradient(MARK, MARK) right top / 9px 1px no-repeat,\n"
            "    linear-gradient(MARK, MARK) right top / 1px 9px no-repeat,\n"
            "    linear-gradient(MARK, MARK) left bottom / 9px 1px no-repeat,\n"
            "    linear-gradient(MARK, MARK) left bottom / 1px 9px no-repeat,\n"
            "    linear-gradient(MARK, MARK) right bottom / 9px 1px no-repeat,\n"
            "    linear-gradient(MARK, MARK) right bottom / 1px 9px no-repeat; }\n"
            ".actions { gap: 20px; }"
        ).replace("MARK", mark)

    return render_file(
        "html/components.css.tmpl",
        {
            "button_radius": radius,
            "badge_radius": badge_radius,
            "button_case": "uppercase" if a.button_label_case == "uppercase" else "none",
            "badge_case": "uppercase" if a.badge_label_case == "uppercase" else "none",
            "primary_bg": primary[0],
            "primary_fg": primary[1],
            "primary_border": primary[2],
            "secondary_bg": secondary[0],
            "secondary_fg": secondary[1],
            "secondary_border": secondary[2],
            "badge_rules": "\n".join(badges),
            "registration_marks": marks,
            "control_height": number(height) + "px",
            **{key.replace(".", "_").replace("-", "_"): v(key) for key in _CSS_ROLES},
        },
    )


_CSS_ROLES = (
    "color.surface.default",
    "color.surface.card",
    "color.surface.sunken",
    "color.surface.inverse",
    "color.text.primary",
    "color.text.secondary",
    "color.text.inverse",
    "color.line.subtle",
    "color.line.strong",
    "color.accent.default",
    "color.accent.soft",
    "color.focus.ring",
    "font.display",
    "font.body",
    "font.label",
    "font.code",
    "font-weight.display",
    "font-weight.body",
    "font-weight.strong",
    "font-weight.label",
    "font-size.display",
    "font-size.title",
    "font-size.body",
    "font-size.small",
    "font-size.label",
    "font-size.code",
    "space.xs",
    "space.sm",
    "space.md",
    "space.lg",
    "space.xl",
    "stroke.hairline",
    "stroke.control",
    "stroke.focus",
    "tracking.label",
)


def render(profile: Profile) -> RenderResult:
    config = profile.config
    identity = config.identity
    technical = config.technical
    a = config.appearance

    def badge(label: str) -> str:
        return html(label)

    documentation = (
        '<a href="{0}">{1}</a>'.format(html(identity.documentation_url), html(identity.documentation_url))
        if identity.documentation_url
        else "Not configured"
    )
    page = render_file(
        "html/guide.html.tmpl",
        {
            "title": html("Hello Button - {} tool guide".format(identity.display_name)),
            "display_name": html(identity.display_name),
            "short_name": html(identity.short_name),
            "logo_alt": html(identity.logo_alt),
            "wordmark_inverse": html(layout.relative(layout.GUIDE, layout.brand_path("wordmark", "inverse", "svg"))),
            "symbol_light": html(layout.relative(layout.GUIDE, layout.brand_path("symbol", "light", "svg"))),
            "font_faces": _font_faces(profile),
            "tokens": _token_declarations(profile),
            "components": _component_css(profile),
            "tab": html(technical.tab),
            "panel": html(technical.sample_panel),
            "support_url": html(identity.support_url),
            "documentation": documentation,
            "notices_href": html(layout.relative(layout.GUIDE, layout.NOTICES_FILE)),
            "foundation_version": html(__version__),
            "badge_info": badge("Info"),
            "badge_success": badge("Read-only"),
            "badge_warning": badge("Review"),
            "badge_danger": badge("Blocked"),
            "marks_note": "on" if a.registration_marks else "off",
        },
    )
    result = RenderResult()
    result.files.append(text_file(layout.GUIDE, page, ADAPTER_ID))
    return result
