"""UI kit surface: a themed WPF dialog kit for the firm's pyRevit extension.

Generates, inside the firm extension, an IronPython 2.7 package
(``lib/<namespace>_ui``) with a result dialog (M1), a chooser (M0) and a
searchable selector (M2-lite), plus the resource dictionaries they use and a
read-only ``UI Kit Demo`` pushbutton that shows all three.

Token logic is shared with the WPF specimen (``wpf_common``): the same key
scheme (``<Ns>.Color.Surface.Default``) and the same shape rules, so a button
in a generated dialog is the button in the specimen. The only differences are
where fonts resolve from (copies packaged inside the extension, because pyRevit
loads the extension folder and extension code must not reach into the
workspace's top-level ``assets/``) and the extra controls this kit needs.

Ported from Rob Mintzes's Rockwell Group pyRevit UI library under the scoped
permission recorded in ADR 0005; see docs/product/RELEASE_RECORD.md (R05).
Nothing here is live-verified in Revit.
"""

from __future__ import annotations

from toolkit_engine import __version__
from toolkit_engine.adapters import RenderResult, layout, wpf_common
from toolkit_engine.adapters.pyrevit_sample import ICON_SIZE
from toolkit_engine.config import FontSpec
from toolkit_engine.diagnostics import Diagnostic
from toolkit_engine.outputs import OutputFile, binary_file, text_file
from toolkit_engine.png import Canvas, ring, rounded_rect
from toolkit_engine.profile import Profile
from toolkit_engine.textutil import kebab, md, pascal, py_string, render_file, xml, yaml_scalar
from toolkit_engine.tokens import Color

ADAPTER_ID = "ui-kit"
TOOLTIP = "Shows the generated UI kit: a chooser, a searchable selector over view names, and a result dialog. Read-only."

PURE_MODULES = ("result_model.py",)
THEMED_MODULES = ("bootstrap.py", "result_dialog.py", "chooser_dialog.py", "selection_dialog.py")
DIALOG_XAML = ("ResultDialog.xaml", "ChooserDialog.xaml", "SelectionDialog.xaml")


def _font_folder(font: FontSpec) -> str:
    """Folder of a packaged family relative to the package's Theme.xaml."""
    return "fonts/" + kebab(font.family)


def _case(text: str, uppercase: bool) -> str:
    return text.upper() if uppercase else text


def _dialog_values(profile: Profile) -> dict[str, str]:
    a = profile.config.appearance
    upper = a.button_label_case == "uppercase"

    def label(text: str) -> str:
        return xml(_case(text, upper))

    return {
        "ns": pascal(profile.config.technical.namespace),
        "logo_alt": xml(profile.config.identity.logo_alt),
        "label_copy_log": label("Copy log"),
        "label_close": label("Close"),
        "label_continue": label("Continue"),
        "label_cancel": label("Cancel"),
        "label_use_selection": label("Use selection"),
        "label_check_visible": label("Check visible"),
        "label_clear_all": label("Clear all"),
        "label_filter": xml("Filter choices"),
    }


def _dialog_xaml(profile: Profile, name: str) -> str:
    template = "ui_kit/{}.tmpl".format(name)
    values = _dialog_values(profile)
    used = {
        "ResultDialog.xaml": ("ns", "logo_alt", "label_copy_log", "label_close", "label_continue"),
        "ChooserDialog.xaml": ("ns", "logo_alt", "label_cancel", "label_continue"),
        "SelectionDialog.xaml": (
            "ns",
            "logo_alt",
            "label_filter",
            "label_check_visible",
            "label_clear_all",
            "label_cancel",
            "label_use_selection",
        ),
    }[name]
    return render_file(template, {key: values[key] for key in used})


def _python_module(profile: Profile, name: str) -> str:
    technical = profile.config.technical
    a = profile.config.appearance
    values = {"package": layout.ui_kit_package(technical), "ns": pascal(technical.namespace)}
    if name == "__init__.py":
        return render_file("ui_kit/__init__.py.tmpl", {"package": values["package"]})
    if name == "result_model.py":
        return render_file("ui_kit/result_model.py.tmpl", {})
    if name == "bootstrap.py":
        upper_badge = a.badge_label_case == "uppercase"
        return render_file(
            "ui_kit/bootstrap.py.tmpl",
            {
                "ns": values["ns"],
                "button_uppercase": repr(a.button_label_case == "uppercase"),
                "badge_uppercase": repr(upper_badge),
                "usage_reusable_label": py_string(_case("Reusable", upper_badge)),
                "usage_setup_label": py_string(_case("Setup", upper_badge)),
                "usage_one_time_label": py_string(_case("One-time", upper_badge)),
            },
        )
    return render_file("ui_kit/{}.tmpl".format(name), values)


def draw_demo_icon(profile: Profile, *, dark: bool) -> bytes:
    """A window-with-list glyph; corners follow the firm's button shape choice."""
    tokens = profile.tokens
    stroke: Color = tokens.color("color.surface.default" if dark else "color.text.primary")
    accent: Color = tokens.color("color.accent.soft" if dark else "color.accent.default")
    canvas = Canvas(ICON_SIZE, ICON_SIZE)
    x0, y0, x1, y1, width = 12.0, 14.0, 84.0, 82.0, 6.0
    shape = profile.config.appearance.button_shape
    radius = 1.5 if shape == "square" else 9.0 if shape == "pill" else min(tokens.px("radius.rounded") * 2.0, 12.0)
    outer = rounded_rect(x0, y0, x1, y1, radius)
    inner = rounded_rect(x0 + width, y0 + width, x1 - width, y1 - width, max(0.0, radius - width))
    canvas.fill(ring(outer, inner), stroke.rgba)
    # Title strip, then three list rows; the first row is the "selected" one.
    canvas.fill(rounded_rect(x0 + width, y0 + width, x1 - width, y0 + width + 12.0, 0.0), accent.rgba, (x0, y0, x1, y0 + 24))
    soft = (stroke.red, stroke.green, stroke.blue, 120)
    for index, top in enumerate((44.0, 55.0, 66.0)):
        canvas.fill(rounded_rect(24.0, top, 72.0, top + 6.0, 3.0), accent.rgba if index == 0 else soft, (22, top - 1, 74, top + 8))
    return canvas.to_png()


def _demo_files(profile: Profile) -> list[OutputFile]:
    config = profile.config
    technical = config.technical
    identity = config.identity
    button_dir = layout.ui_kit_demo_dir(technical)
    package = layout.ui_kit_package(technical)
    return [
        text_file(
            button_dir + "/bundle.yaml",
            "title: {}\ntooltip: {}\nauthor: {}\nhelp_url: {}\n".format(
                layout.UI_KIT_DEMO_TITLE,
                yaml_scalar(TOOLTIP),
                yaml_scalar(identity.author),
                yaml_scalar(identity.support_url),
            ),
            ADAPTER_ID,
        ),
        text_file(
            button_dir + "/script.py",
            render_file("ui_kit/ui_kit_demo_script.py.tmpl", {"package": package, "author_literal": py_string(identity.author)}),
            ADAPTER_ID,
        ),
        binary_file(button_dir + "/icon.png", draw_demo_icon(profile, dark=False), ADAPTER_ID),
        binary_file(button_dir + "/icon.dark.png", draw_demo_icon(profile, dark=True), ADAPTER_ID),
        text_file(
            layout.UI_KIT_DEMO_DOC,
            render_file(
                "ui_kit/ui-kit-demo-doc.md.tmpl",
                {
                    "package": package,
                    "tab_display": md(technical.tab),
                    "panel_display": md(technical.sample_panel),
                    "support_url": identity.support_url,
                },
            ),
            ADAPTER_ID,
        ),
    ]


def render(profile: Profile) -> RenderResult:
    config = profile.config
    technical = config.technical
    package_dir = layout.ui_kit_dir(technical)
    result = RenderResult()
    add = result.files.append

    for name in ("__init__.py",) + PURE_MODULES + THEMED_MODULES:
        add(text_file("{}/{}".format(package_dir, name), _python_module(profile, name), ADAPTER_ID))

    add(text_file(package_dir + "/Theme.xaml", wpf_common.render_theme(profile, _font_folder), ADAPTER_ID))
    add(text_file(package_dir + "/Controls.xaml", wpf_common.render_kit_controls(profile), ADAPTER_ID))
    add(
        text_file(
            package_dir + "/Icons.xaml",
            render_file("ui_kit/Icons.xaml.tmpl", {"foundation_version": __version__, "ns": pascal(technical.namespace)}),
            ADAPTER_ID,
        )
    )
    for name in DIALOG_XAML:
        add(text_file("{}/{}".format(package_dir, name), _dialog_xaml(profile, name), ADAPTER_ID))

    # Packaged fonts and the brand symbol are copied into the extension: pyRevit
    # loads the extension folder, so the UI may only reference files inside it.
    for font in config.fonts:
        folder = "{}/{}".format(package_dir, _font_folder(font))
        for font_file in font.files:
            add(binary_file("{}/{}".format(folder, font_file.path.rsplit("/", 1)[-1]), profile.files[font_file.path], ADAPTER_ID))
        add(
            text_file(
                "{}/{}".format(folder, font.license_file.rsplit("/", 1)[-1]),
                profile.files[font.license_file].decode("utf-8-sig"),
                ADAPTER_ID,
            )
        )
    _, symbol = profile.asset("symbol", "inverse", "png")
    add(binary_file(package_dir + "/assets/symbol-inverse.png", symbol, ADAPTER_ID))

    add(
        text_file(
            "{}/tests/test_ui_kit_contract.py".format(layout.extension_dir(technical)),
            render_file(
                "ui_kit/test_ui_kit_contract.py.tmpl",
                {
                    "package": layout.ui_kit_package(technical),
                    "ns": pascal(technical.namespace),
                    "extension": technical.extension,
                },
            ),
            ADAPTER_ID,
        )
    )
    result.files.extend(_demo_files(profile))

    result.diagnostics.append(
        Diagnostic(
            "ui-kit.not-live-verified",
            "info",
            "ui-kit: " + package_dir,
            "The generated UI kit is statically checked and rendered natively in a harness only; it has not run inside Revit/pyRevit.",
            "Run UI Kit Demo from the {} tab in a live session before relying on the kit.".format(technical.tab),
        )
    )
    return result
