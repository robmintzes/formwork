"""CSS generated from firm tokens and appearance, shared by every web-flavoured surface.

The HTML guide, the Python report starter and the TypeScript web starter all
build their stylesheet from these helpers, so a button in one is the button in
the others. Pure functions: nothing here touches the filesystem.
"""

from __future__ import annotations

from typing import Callable

from toolkit_engine.config import FontFile, FontSpec
from toolkit_engine.profile import Profile
from toolkit_engine.textutil import css_string, number, render_file
from toolkit_engine.tokens import STATUS_NAMES

GENERIC_FAMILIES = {"serif", "sans-serif", "monospace", "system-ui", "ui-monospace", "cursive"}

# Role tokens the shared component stylesheet reads; each becomes a ``var(--ns-...)``.
CSS_ROLES = (
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

FontUrl = Callable[[FontSpec, FontFile], str]


def css_var(namespace: str, token_path: str) -> str:
    return "--{}-{}".format(namespace, token_path.replace(".", "-"))


def var_ref(profile: Profile, token_path: str) -> str:
    return "var({})".format(css_var(profile.config.technical.namespace, token_path))


def role_values(profile: Profile, names: tuple[str, ...]) -> dict[str, str]:
    """Template values for *names* (``color.surface.card`` -> ``color_surface_card``)."""
    return {name.replace(".", "_").replace("-", "_"): var_ref(profile, name) for name in names}


def font_stack(stack: tuple[str, ...]) -> str:
    return ", ".join(name if name in GENERIC_FAMILIES else css_string(name) for name in stack)


def token_declarations(profile: Profile) -> str:
    ns = profile.config.technical.namespace
    lines = []
    for path, token in profile.tokens.items():
        if token.type == "color":
            value = token.value.css
        elif token.type == "dimension":
            value = number(token.value) + "px"
        elif token.type == "fontFamily":
            value = font_stack(token.value)
        else:
            value = number(token.value) if token.type == "number" else str(token.value)
        lines.append("  {}: {};".format(css_var(ns, path), value))
    return "\n".join(lines)


def font_faces(profile: Profile, url_for: FontUrl) -> str:
    """One ``@font-face`` per packaged font file; *url_for* gives the stylesheet-relative URL."""
    blocks = []
    for font in profile.config.fonts:
        for font_file in font.files:
            fmt = "truetype" if font_file.path.lower().endswith(".ttf") else "opentype"
            blocks.append(
                "@font-face {{ font-family: {}; src: url({}) format(\"{}\"); font-weight: {}; font-style: {}; font-display: swap; }}".format(
                    css_string(font.family),
                    css_string(url_for(font, font_file)),
                    fmt,
                    font_file.weight,
                    font_file.style,
                )
            )
    return "\n".join(blocks)


def component_css(profile: Profile) -> str:
    """Base page, button, chip, badge and table rules from ``html/components.css.tmpl``."""
    a = profile.config.appearance
    t = profile.tokens

    def v(path: str) -> str:
        return var_ref(profile, path)

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
            **role_values(profile, CSS_ROLES),
        },
    )


def app_stylesheet(
    profile: Profile,
    *,
    extras_template: str,
    extras_roles: tuple[str, ...],
    font_url: FontUrl | None,
    header: str,
) -> str:
    """A complete standalone stylesheet: fonts, tokens, shared components, then app-specific rules."""
    parts = ["/* {} */".format(header)]
    if font_url is not None:
        faces = font_faces(profile, font_url)
        if faces:
            parts.append(faces)
    parts.append(":root {\n" + token_declarations(profile) + "\n}")
    parts.append(component_css(profile).rstrip("\n"))
    parts.append(render_file(extras_template, role_values(profile, extras_roles)).rstrip("\n"))
    return "\n".join(parts) + "\n"
