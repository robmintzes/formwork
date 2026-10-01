"""Revit add-in surface: a C# (.NET) add-in starter, themed like the firm's other UI.

Generates ``addins/<Extension>.Addin/``: an SDK-style project, an
``IExternalApplication`` that adds a ribbon button, a read-only
``IExternalCommand`` with a small WPF window, the add-in manifest, and a README.

Identity. The assembly name, root namespace and ``AddInId`` come from the stable
technical identity (``technical.pyrevit.extension``, ``technical.namespace``,
``technical.workspace_id``), so rebranding never changes them. Display strings
(product, company, window text) follow ``identity``.

Theme. The window uses the same generated ``Theme.xaml`` and ``Controls.xaml``
as the pyRevit UI kit, produced by the shared ``wpf_common`` code, so a button
here is the button there. They are embedded in the DLL as text and parsed at run
time with ``XamlReader`` (the same loader the pyRevit kit uses), not
markup-compiled: that keeps the project free of the WPF XAML compiler's temporary
project and lets packaged fonts resolve by relative URI beside the DLL.

Nothing here is live-verified in Revit; a successful compile is not proof that the
add-in loads (see the generated README and FOUNDATION_SPEC section 8.3).
"""

from __future__ import annotations

import re
import uuid

from toolkit_engine import __version__
from toolkit_engine.adapters import RenderResult, layout, wpf_common
from toolkit_engine.config import FontSpec
from toolkit_engine.diagnostics import Diagnostic
from toolkit_engine.outputs import binary_file, text_file
from toolkit_engine.png import Canvas, circle, rounded_rect, triangle
from toolkit_engine.profile import Profile
from toolkit_engine.textutil import cs_string, kebab, md, msbuild_text, pascal, render_file, xml
from toolkit_engine.tokens import Color

ADAPTER_ID = "revit-addin"
# Fixed, never regenerated: uuid5(NAMESPACE_DNS, "revit-addin.pyrevit-toolbar-template.foundation").
# Changing it changes every generated AddInId, so treat it as a published constant.
FOUNDATION_ADDIN_NAMESPACE = uuid.UUID("14c252b8-76a6-57e0-9467-d802f0ada553")
PANEL_SUFFIX = " Add-in"
CSHARP_KEYWORDS = frozenset(
    """abstract as base bool break byte case catch char checked class const continue decimal default delegate
    do double else enum event explicit extern false finally fixed float for foreach goto if implicit in int
    interface internal is lock long namespace new null object operator out override params private protected
    public readonly ref return sbyte sealed short sizeof stackalloc static string struct switch this throw true
    try typeof uint ulong unchecked unsafe ushort using virtual void volatile while""".split()
)
CSHARP_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def addin_id(workspace_id: str) -> str:
    """Stable AddInId: depends only on ``technical.workspace_id`` (never on branding)."""
    return str(uuid.uuid5(FOUNDATION_ADDIN_NAMESPACE, workspace_id + ":revit-addin")).upper()


def root_namespace(namespace: str) -> str:
    return pascal(namespace) + ".Addin"


def panel_name(sample_panel: str) -> str:
    return sample_panel + PANEL_SUFFIX


def _font_folder(font: FontSpec) -> str:
    """Folder of a packaged family relative to the DLL (and to Theme.xaml's BaseUri)."""
    return "fonts/" + kebab(font.family)


def _case(text: str, uppercase: bool) -> str:
    return text.upper() if uppercase else text


def draw_ribbon_icon(profile: Profile, size: int) -> bytes:
    """A filled speech-bubble glyph at ``size`` px (16 or 32).

    Filled with the accent colour and punched with surface-colour dots so it reads on
    both the light and the dark Revit ribbon (a ribbon image cannot swap by theme).
    Corners follow the firm's button shape. Pure geometry: identical bytes every run.
    """
    tokens = profile.tokens
    fill: Color = tokens.color("color.accent.default")
    dots: Color = tokens.color("color.surface.default")
    scale = size / 96.0
    canvas = Canvas(size, size)
    x0, y0, x1, y1 = 8.0, 12.0, 88.0, 68.0
    shape = profile.config.appearance.button_shape
    radius = 4.0 if shape == "square" else (y1 - y0) / 2.0 if shape == "pill" else min(tokens.px("radius.rounded") * 2.0, 18.0)
    bounds = (0.0, 0.0, float(size), float(size))
    canvas.fill(_scaled(rounded_rect(x0, y0, x1, y1, radius), scale), fill.rgba, bounds)
    canvas.fill(_scaled(triangle((24.0, y1 - 2), (24.0, 88.0), (48.0, y1 - 2)), scale), fill.rgba, bounds)
    for cx in (30.0, 48.0, 66.0):
        canvas.fill(_scaled(circle(cx, 40.0, 6.5), scale), dots.rgba, bounds)
    return canvas.to_png()


def _scaled(shape, scale: float):
    """Evaluate a 96-unit shape on a canvas drawn at ``scale`` (pixel -> design units)."""
    return lambda x, y: shape(x / scale, y / scale)


def _identifier_diagnostics(profile: Profile) -> list[Diagnostic]:
    technical = profile.config.technical
    parts = {
        "technical.namespace": root_namespace(technical.namespace).split("."),
        "technical.pyrevit.extension": [technical.extension],
    }
    result = []
    for source, segments in parts.items():
        for segment in segments:
            if not CSHARP_IDENTIFIER.match(segment) or segment in CSHARP_KEYWORDS:
                result.append(
                    Diagnostic(
                        "revit-addin.invalid-identifier",
                        "warning",
                        "revit-addin: " + source,
                        "{!r} is not a safe C# identifier (invalid characters or a reserved word); "
                        "code that uses it as a namespace or type name will not compile.".format(segment),
                        "The generated files use it only as {}; choose a different value if you add code that names it.".format(
                            "the assembly name" if source.endswith("extension") else "part of the root namespace"
                        ),
                    )
                )
    return result


def _csproj(profile: Profile) -> str:
    config = profile.config
    technical = config.technical
    identity = config.identity
    assembly = layout.addin_project(technical)
    return render_file(
        "revit_addin/csproj.tmpl",
        {
            "foundation_version": __version__,
            "project_file": "addins\\{0}\\{0}.csproj".format(assembly),
            "assembly": assembly,
            "root_namespace": root_namespace(technical.namespace),
            "product": msbuild_text(identity.display_name),
            "company": msbuild_text(identity.author),
            "description": msbuild_text("{} Revit add-in".format(identity.display_name)),
        },
    )


def _manifest(profile: Profile) -> str:
    config = profile.config
    technical = config.technical
    identity = config.identity
    assembly = layout.addin_project(technical)
    return render_file(
        "revit_addin/addin.tmpl",
        {
            "foundation_version": __version__,
            "name": xml(identity.display_name),
            "assembly": xml(assembly),
            "addin_id": addin_id(technical.workspace_id),
            "root_namespace": root_namespace(technical.namespace),
            "vendor_id": xml(technical.namespace),
            "vendor_description": xml("{} ({})".format(identity.author, identity.support_url)),
        },
    )


def _window_xaml(profile: Profile) -> str:
    config = profile.config
    upper = config.appearance.button_label_case == "uppercase"
    return render_file(
        "revit_addin/SummaryWindow.xaml.tmpl",
        {
            "ns": pascal(config.technical.namespace),
            "logo_alt": xml(config.identity.logo_alt),
            "eyebrow": xml("Add-in / Hello"),
            "heading": xml("Project summary"),
            "label_project": xml("Project"),
            "label_view": xml("Active view"),
            "label_count": xml("Non-template views"),
            "label_close": xml(_case("Close", upper)),
        },
    )


def _csharp(profile: Profile, name: str) -> str:
    config = profile.config
    values = {"foundation_version": __version__, "root_namespace": root_namespace(config.technical.namespace)}
    if name == "App.cs":
        values["tab_literal"] = cs_string(config.technical.tab)
        values["panel_literal"] = cs_string(panel_name(config.technical.sample_panel))
        values["product_literal"] = cs_string(config.identity.display_name)
    return render_file("revit_addin/{}.tmpl".format(name), values)


def _readme(profile: Profile) -> str:
    config = profile.config
    technical = config.technical
    return render_file(
        "revit_addin/README.md.tmpl",
        {
            "foundation_version": __version__,
            "assembly": layout.addin_project(technical),
            "root_namespace": root_namespace(technical.namespace),
            "display_name": md(config.identity.display_name),
            "tab": md(technical.tab),
            "panel": md(panel_name(technical.sample_panel)),
            "addin_id": addin_id(technical.workspace_id),
        },
    )


def render(profile: Profile) -> RenderResult:
    config = profile.config
    technical = config.technical
    base = layout.addin_dir(technical)
    assembly = layout.addin_project(technical)
    result = RenderResult()
    add = result.files.append

    add(text_file("{}/{}.csproj".format(base, assembly), _csproj(profile), ADAPTER_ID))
    add(text_file("{}/{}.addin".format(base, assembly), _manifest(profile), ADAPTER_ID))
    for name in ("App.cs", "HelloCommand.cs", "SummaryWindow.cs", "ThemeResources.cs"):
        add(text_file("{}/{}".format(base, name), _csharp(profile, name), ADAPTER_ID))

    add(text_file(base + "/Resources/Theme.xaml", wpf_common.render_theme(profile, _font_folder), ADAPTER_ID))
    add(text_file(base + "/Resources/Controls.xaml", wpf_common.render_kit_controls(profile), ADAPTER_ID))
    add(text_file(base + "/Resources/SummaryWindow.xaml", _window_xaml(profile), ADAPTER_ID))
    for variant in ("light", "inverse"):
        _, symbol = profile.asset("symbol", variant, "png")
        add(binary_file("{}/Resources/symbol-{}.png".format(base, variant), symbol, ADAPTER_ID))
    for size in (32, 16):
        add(binary_file("{}/Resources/icon-{}.png".format(base, size), draw_ribbon_icon(profile, size), ADAPTER_ID))

    # Packaged fonts and their licences sit beside the DLL after the build.
    for font in config.fonts:
        folder = "{}/{}".format(base, _font_folder(font))
        for font_file in font.files:
            add(binary_file("{}/{}".format(folder, font_file.path.rsplit("/", 1)[-1]), profile.files[font_file.path], ADAPTER_ID))
        add(
            text_file(
                "{}/{}".format(folder, font.license_file.rsplit("/", 1)[-1]),
                profile.files[font.license_file].decode("utf-8-sig"),
                ADAPTER_ID,
            )
        )

    add(text_file(base + "/README.md", _readme(profile), ADAPTER_ID))
    add(text_file(base + "/.gitignore", render_file("revit_addin/gitignore.tmpl", {}), ADAPTER_ID))

    result.diagnostics.extend(_identifier_diagnostics(profile))
    result.diagnostics.append(
        Diagnostic(
            "revit-addin.not-live-verified",
            "info",
            "revit-addin: " + base,
            "The generated add-in is compile-checked and statically checked only; it has not been loaded in Revit.",
            "Build it, install it per {}/README.md, and run Hello Add-in in a live session before relying on it.".format(base),
        )
    )
    return result
