"""Generate a branded Array Along Path tool, using the shared offline web host.

Geometry and deterministic preview ported under ADR 0005; source recorded in R07.
The browser submits a plan. Model changes run after the web window closes, in
the original pyRevit command context, never from a browser event callback.
"""
from __future__ import annotations

from formwork_engine import __version__
from formwork_engine.adapters import RenderResult, layout, web_host
from formwork_engine.diagnostics import Diagnostic
from formwork_engine.outputs import binary_file, text_file
from formwork_engine.png import Canvas, circle, ring, rounded_rect
from formwork_engine.profile import Profile
from formwork_engine.textutil import PLACEHOLDER, TEMPLATE_DIR, html, kebab, py_string, render as render_text, render_file, yaml_scalar

ADAPTER_ID = "array-along-path"


def button_dir(profile: Profile) -> str:
    return layout.tab_dir(profile.config.technical) + "/Elements.panel/ArrayAlongPath.pushbutton"


def icon(profile: Profile, dark: bool) -> bytes:
    canvas = Canvas(32, 32)
    ink = profile.tokens.color("color.surface.default" if dark else "color.text.primary").rgba
    accent = profile.tokens.color("color.accent.soft" if dark else "color.accent.default").rgba
    # A curved distribution track with three station blocks. Original artwork.
    for x in range(5, 28):
        y = 24 - ((x - 5) / 22.0) ** 2 * 16
        canvas.fill(circle(x, y, 0.8), ink, (x-1, y-1, x+1, y+1))
    for x, y in ((6, 22), (16, 18), (26, 7)):
        canvas.fill(ring(rounded_rect(x-3, y-3, x+3, y+3, 0),
                         rounded_rect(x-1.5, y-1.5, x+1.5, y+1.5, 0)), accent)
    return canvas.to_png()


def render(profile: Profile) -> RenderResult:
    tech, identity = profile.config.technical, profile.config.identity
    folder = button_dir(profile)
    values = {
        "author_literal": py_string(identity.author),
        "package": layout.web_host_package(tech),
        "ui_package": layout.ui_kit_package(tech),
        "ns": tech.namespace,
        "logo_alt": html(identity.logo_alt),
        "brand_name": html(identity.short_name),
        "tab_id": kebab(tech.tab),
        "tab_display": tech.tab,
        "extension_path": layout.extension_dir(tech),
        "tab_path": layout.tab_dir(tech),
        "button_path": folder,
    }
    result = RenderResult()
    def render_template(name: str) -> str:
        source = (TEMPLATE_DIR / "array_along_path" / (name + ".tmpl")).read_text(encoding="utf-8")
        used = set(PLACEHOLDER.findall(source))
        return render_text(source, {key: values[key] for key in used})
    for target, template in (("script.py", "script.py"), (tech.namespace + "_array_plan.py", "plan.py"),
                             ("tool.html", "tool.html"), ("tool.js", "tool.js"),
                             ("tool.css", "tool.css"), ("motion.js", "motion.js")):
        result.files.append(text_file(folder + "/" + target,
                            render_template(template), ADAPTER_ID))
    # Bundle-local generated theme supports both the virtual host and an
    # offline browser preview with the same files and strict CSP.
    result.files.append(text_file(folder + "/theme.css", web_host.tool_css(profile), ADAPTER_ID))
    result.files.append(text_file(folder + "/bridge.js",
        render_file("web_host/bridge.js.tmpl", {"ns": tech.namespace, "foundation_version": __version__}), ADAPTER_ID))
    for slot in ("wordmark", "symbol"):
        _, data = profile.asset(slot, "light", "svg")
        result.files.append(binary_file(folder + "/" + slot + ".svg", data, ADAPTER_ID))
    for font in profile.config.fonts:
        for item in font.files:
            result.files.append(binary_file(folder + "/fonts/" + kebab(font.family) + "/" + item.path.rsplit("/", 1)[-1], profile.files[item.path], ADAPTER_ID))
        result.files.append(text_file(folder + "/fonts/" + kebab(font.family) + "/" + font.license_file.rsplit("/", 1)[-1], profile.files[font.license_file].decode("utf-8-sig"), ADAPTER_ID))
    result.files.append(text_file(folder + "/bundle.yaml",
        "title: Array Along Path\ntooltip: Array a family instance or group along path curves with a live preview.\nauthor: {}\nhelp_url: {}\n".format(
            yaml_scalar(identity.author), yaml_scalar(identity.support_url)), ADAPTER_ID))
    for dark in (False, True):
        result.files.append(binary_file(folder + ("/icon.dark.png" if dark else "/icon.png"), icon(profile, dark), ADAPTER_ID))
    result.files.append(text_file("docs/toolbar/spec.d/array-along-path.md",
        render_template("spec.md"), ADAPTER_ID))
    result.files.append(text_file("docs/toolbar/tools/array-along-path.md",
        render_template("doc.md"), ADAPTER_ID))
    result.diagnostics.append(Diagnostic("array-along-path.live-gate", "info", folder,
        "Array Along Path needs a live Revit placement and Undo check; browser verification covers preview and motion only."))
    return result
