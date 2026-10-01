"""HTML surface: a self-contained, offline Hello Button guide with a component specimen."""

from __future__ import annotations

from toolkit_engine import __version__
from toolkit_engine.adapters import RenderResult
from toolkit_engine.adapters import layout, web_theme
from toolkit_engine.outputs import text_file
from toolkit_engine.profile import Profile
from toolkit_engine.textutil import html, render_file

ADAPTER_ID = "html-guide"


def _font_url(font, font_file) -> str:
    return layout.relative(layout.GUIDE, layout.font_path(font, font_file))


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
            "font_faces": web_theme.font_faces(profile, _font_url),
            "tokens": web_theme.token_declarations(profile),
            "components": web_theme.component_css(profile),
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
