"""pyRevit surface: extension manifest, read-only sample bundle, icons, spec, docs."""

from __future__ import annotations

import json

from formwork_engine.adapters import RenderResult
from formwork_engine.adapters import layout
from formwork_engine.outputs import OWNERSHIP_SEED, binary_file, text_file
from formwork_engine.png import Canvas, circle, ring, rounded_rect, triangle
from formwork_engine.profile import Profile
from formwork_engine.textutil import kebab, md, py_string, render_file, yaml_scalar
from formwork_engine.tokens import Color

ADAPTER_ID = "pyrevit-sample"
ICON_SIZE = 96
TOOLTIP = "Displays a read-only summary of the active Revit project and its views."
UI_KIT_DEMO_DESCRIPTION = "Read-only demonstration of the generated UI kit with a chooser, a searchable selector over view names, and a result dialog."
WEB_TOOL_DEMO_DESCRIPTION = "Read-only HTML report console in a WebView2 window: view and template counts by view type, a client-side filter, and a copy-summary action."
DESCRIPTION = "Displays a read-only greeting with the active project, active view, and non-template view count."


def render(profile: Profile) -> RenderResult:
    result = RenderResult()
    config = profile.config
    technical = config.technical
    identity = config.identity
    button_dir = layout.sample_button_dir(technical)
    extension_dir = layout.extension_dir(technical)

    manifest = {
        "name": technical.extension,
        "description": "{} pyRevit extension".format(identity.display_name),
        "version": "1.0.0",
        "author": identity.author,
        "min_pyrevit_version": "4.8.10",
    }
    result.files.append(
        text_file(extension_dir + "/extension.json", json.dumps(manifest, indent=2, ensure_ascii=False), ADAPTER_ID)
    )
    result.files.append(
        text_file(
            button_dir + "/bundle.yaml",
            "title: {}\ntooltip: {}\nauthor: {}\nhelp_url: {}\n".format(
                layout.SAMPLE_TOOL_TITLE,
                yaml_scalar(TOOLTIP),
                yaml_scalar(identity.author),
                yaml_scalar(identity.support_url),
            ),
            ADAPTER_ID,
        )
    )
    result.files.append(
        text_file(
            button_dir + "/script.py",
            render_file("hello_button_script.py.tmpl", {"author_literal": py_string(identity.author)}),
            ADAPTER_ID,
        )
    )
    result.files.append(binary_file(button_dir + "/icon.png", draw_icon(profile, dark=False), ADAPTER_ID))
    result.files.append(binary_file(button_dir + "/icon.dark.png", draw_icon(profile, dark=True), ADAPTER_ID))

    values = {
        "tab_id": kebab(technical.tab),
        "tab_display": technical.tab,
        "panel_display": technical.sample_panel,
        "extension_path": extension_dir,
        "tab_path": layout.tab_dir(technical),
        "tool_id": layout.SAMPLE_TOOL_ID,
        "tool_title": layout.SAMPLE_TOOL_TITLE,
        "description": DESCRIPTION,
        "button_path": button_dir,
        "extra_tools": (_ui_kit_demo_spec(profile) if "ui-kit" in config.surfaces else "")
        + (_web_tool_demo_spec(profile) if "web-host" in config.surfaces else ""),
    }
    result.files.append(text_file(layout.SPEC_FRAGMENT, render_file("spec-fragment.md.tmpl", values), ADAPTER_ID))
    result.files.append(
        text_file(
            layout.TOOL_DOC,
            render_file(
                "hello-button-doc.md.tmpl",
                {
                    "tab_display": md(technical.tab),
                    "panel_display": md(technical.sample_panel),
                    "support_url": identity.support_url,
                },
            ),
            ADAPTER_ID,
        )
    )
    result.files.append(text_file(layout.SPEC_SEED, render_file("toolbar_spec.md.tmpl", {}), ADAPTER_ID, OWNERSHIP_SEED))
    return result


def _ui_kit_demo_spec(profile: Profile) -> str:
    """Second tool entry in the managed spec fragment; present only with the ui-kit surface."""
    return (
        "\n  - id: {id}\n    display_name: {title}\n    type: PushButton\n    category: utility\n"
        "    risk: Low\n    lifecycle_stage: sandbox\n    description: {description}\n    source_path: {path}"
    ).format(
        id=layout.UI_KIT_DEMO_TOOL_ID,
        title=layout.UI_KIT_DEMO_TITLE,
        description=UI_KIT_DEMO_DESCRIPTION,
        path=layout.ui_kit_demo_dir(profile.config.technical),
    )


def _web_tool_demo_spec(profile: Profile) -> str:
    """Further tool entry in the managed spec fragment; present only with the web-host surface."""
    return (
        "\n  - id: {id}\n    display_name: {title}\n    type: PushButton\n    category: utility\n"
        "    risk: Low\n    lifecycle_stage: sandbox\n    description: {description}\n    source_path: {path}"
    ).format(
        id=layout.WEB_TOOL_DEMO_TOOL_ID,
        title=layout.WEB_TOOL_DEMO_TITLE,
        description=WEB_TOOL_DEMO_DESCRIPTION,
        path=layout.web_tool_demo_dir(profile.config.technical),
    )


def _corner_radius(profile: Profile, height: float) -> float:
    shape = profile.config.appearance.button_shape
    if shape == "square":
        return 1.5
    if shape == "pill":
        return height / 2.0
    return min(profile.tokens.px("radius.rounded") * 2.0, height / 3.0)


def draw_icon(profile: Profile, *, dark: bool) -> bytes:
    """A speech-bubble glyph whose corners follow the button shape choice.

    Light variant: text color outline with accent dots (for the light ribbon).
    Dark variant: light-surface outline with soft-accent dots.
    """
    tokens = profile.tokens
    stroke_color: Color = tokens.color("color.surface.default" if dark else "color.text.primary")
    dot_color: Color = tokens.color("color.accent.soft" if dark else "color.accent.default")
    canvas = Canvas(ICON_SIZE, ICON_SIZE)
    x0, y0, x1, y1, width = 12.0, 14.0, 84.0, 66.0, 7.0
    radius = _corner_radius(profile, y1 - y0)
    outer = rounded_rect(x0, y0, x1, y1, radius)
    inner = rounded_rect(x0 + width, y0 + width, x1 - width, y1 - width, max(0.0, radius - width))
    canvas.fill(ring(outer, inner), stroke_color.rgba)
    canvas.fill(triangle((26.0, y1 - 1), (26.0, 84.0), (46.0, y1 - 1)), stroke_color.rgba, (24, 60, 48, 86))
    for cx in (32.0, 48.0, 64.0):
        canvas.fill(circle(cx, 40.0, 5.5), dot_color.rgba, (cx - 7, 32, cx + 7, 48))
    return canvas.to_png()
