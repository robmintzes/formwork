"""Workspace-relative locations shared by adapters (the generated layout contract)."""

from __future__ import annotations

from posixpath import relpath

from formwork_engine.config import FontFile, FontSpec, Technical
from formwork_engine.textutil import kebab

FONTS_DIR = "assets/fonts"
BRAND_DIR = "assets/brand"
NOTICES_FILE = "THIRD_PARTY_NOTICES.md"
BRAND_NOTICES_DIR = "notices"
README_FILE = "README.md"
GITATTRIBUTES_FILE = ".gitattributes"
SPEC_SEED = "docs/toolbar/toolbar_spec.md"
SPEC_FRAGMENT = "docs/toolbar/spec.d/foundation-sample.md"
TOOL_DOC = "docs/toolbar/tools/hello-button.md"
GUIDE = "docs/guides/hello-button.html"
WPF_DIR = "specimens/wpf"
SAMPLE_TOOL_ID = "hello-button"
SAMPLE_TOOL_TITLE = "Hello Button"
UI_KIT_DEMO_TOOL_ID = "ui-kit-demo"
UI_KIT_DEMO_TITLE = "UI Kit Demo"
UI_KIT_DEMO_DOC = "docs/toolbar/tools/ui-kit-demo.md"
WEB_TOOL_DEMO_TOOL_ID = "web-tool-demo"
WEB_TOOL_DEMO_TITLE = "Web Tool Demo"
WEB_TOOL_DEMO_DOC = "docs/toolbar/tools/web-tool-demo.md"


def extension_dir(technical: Technical) -> str:
    return "extensions/{}.extension".format(technical.extension)


def tab_dir(technical: Technical) -> str:
    return "{}/{}.tab".format(extension_dir(technical), technical.tab)


def sample_button_dir(technical: Technical) -> str:
    return "{}/{}.panel/HelloButton.pushbutton".format(tab_dir(technical), technical.sample_panel)


def sample_panel_dir(technical: Technical) -> str:
    return "{}/{}.panel".format(tab_dir(technical), technical.sample_panel)


def ui_kit_demo_dir(technical: Technical) -> str:
    return "{}/UIKitDemo.pushbutton".format(sample_panel_dir(technical))


def ui_kit_package(technical: Technical) -> str:
    """Importable Python package name of the generated UI kit."""
    return "{}_ui".format(technical.namespace)


def ui_kit_dir(technical: Technical) -> str:
    return "{}/lib/{}".format(extension_dir(technical), ui_kit_package(technical))


def web_tool_demo_dir(technical: Technical) -> str:
    return "{}/WebToolDemo.pushbutton".format(sample_panel_dir(technical))


def web_host_package(technical: Technical) -> str:
    """Importable Python package name of the generated web tool host."""
    return "{}_web".format(technical.namespace)


def web_host_dir(technical: Technical) -> str:
    return "{}/lib/{}".format(extension_dir(technical), web_host_package(technical))


def web_host_names(technical: Technical) -> tuple[str, str]:
    """(tool host, assets host): the two virtual host names the web host maps.

    ``.test`` is reserved (RFC 6761); Microsoft advises against ``.local`` because it can
    delay navigations. WebView2 maps one folder per host name, hence two names.
    """
    return ("{}-tool.test".format(technical.namespace), "{}-assets.test".format(technical.namespace))


def addin_project(technical: Technical) -> str:
    """Assembly and project name of the generated Revit add-in (never changes with branding)."""
    return "{}.Addin".format(technical.extension)


def addin_dir(technical: Technical) -> str:
    return "addins/{}".format(addin_project(technical))


def python_app_package(technical: Technical) -> str:
    """Importable package name of the generated Python report app."""
    return "{}_report".format(technical.namespace)


def python_app_dir(technical: Technical) -> str:
    return "apps/{}-report".format(technical.namespace)


def web_app_dir(technical: Technical) -> str:
    return "apps/{}-web".format(technical.namespace)


def font_path(font: FontSpec, font_file: FontFile) -> str:
    return "{}/{}/{}".format(FONTS_DIR, kebab(font.family), font_file.path.rsplit("/", 1)[-1])


def font_license_path(font: FontSpec) -> str:
    return "{}/{}/{}".format(FONTS_DIR, kebab(font.family), font.license_file.rsplit("/", 1)[-1])


def brand_path(slot: str, variant: str, fmt: str) -> str:
    return "{}/{}-{}.{}".format(BRAND_DIR, slot, variant, fmt)


def relative(from_file: str, to_file: str) -> str:
    """POSIX relative reference from one workspace file to another."""
    return relpath(to_file, from_file.rsplit("/", 1)[0] if "/" in from_file else ".")
