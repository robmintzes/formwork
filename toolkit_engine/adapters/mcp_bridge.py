"""MCP bridge surface: the read-only Revit MCP bridge, re-identified for a firm.

Vendors the foundation's pyRevit Routes side (extension startup and the
``revit_mcp_bridge`` package) into the firm's generated extension and the
external FastMCP server under ``servers/revit-mcp/``. Foundation sources are
read as-is and changed only by asserted, exact substitutions (the pyRevit
Routes API name and the default Routes URL derive from ``technical.namespace``;
``__author__`` becomes ``identity.author``). A foundation file that changes
shape, or a new unlisted file, fails generation loudly. Reads foundation
resources only, never the workspace. Nothing here is live-verified in Revit.
"""

from __future__ import annotations

from pathlib import Path

from toolkit_engine.adapters import RenderResult, layout
from toolkit_engine.diagnostics import Diagnostic
from toolkit_engine.outputs import text_file
from toolkit_engine.profile import Profile
from toolkit_engine.textutil import md, py_string, render_file
from toolkit_engine.vendoring import VendoringError, read_foundation_text, substitute

ADAPTER_ID = "mcp-bridge"
FOUNDATION = Path(__file__).resolve().parents[2]

# The foundation's own sample extension, the source of the pyRevit side.
SOURCE_EXTENSION = "extensions/Placeholder.extension"
BRIDGE_PACKAGE = "lib/revit_mcp_bridge"
BRIDGE_MODULES = (
    "__init__.py",
    "compat.py",
    "dispatch.py",
    "handlers_health.py",
    "handlers_project.py",
    "handlers_registry.py",
    "identity.py",
    "response.py",
    "routes_dispatch.py",
    "routes_health.py",
    "routes_project.py",
    "startup.py",
)
ROUTE_MODULES = ("routes_dispatch.py", "routes_health.py", "routes_project.py")

SERVER_SOURCE = "servers/revit-mcp"
SERVER_TARGET = "servers/revit-mcp"
SERVER_FILES = (
    "mcp-server/app.py",
    "mcp-server/build_identity.py",
    "mcp-server/main.py",
    "mcp-server/requirements.txt",
    "mcp-server/revit_client.py",
    "mcp-server/schemas.py",
    "mcp-server/settings.py",
    "mcp-server/tools/__init__.py",
    "mcp-server/tools/health.py",
    "mcp-server/tools/project.py",
    "mcp-server/tests/conftest.py",
    "mcp-server/tests/test_revit_client.py",
    "mcp-server/tests/test_server_contract.py",
    "mcp-server/tests/test_settings.py",
    "mcp-server/tests/test_smoke.py",
    "mcp-server/tests/test_tool_results.py",
    "scripts/setup-mcp-server.ps1",
    "scripts/start-local-http.ps1",
    "scripts/start-stdio.ps1",
)
# Deliberately not vendored: the live probe imports the foundation's own
# toolkit_cli package, which a generated workspace does not contain.
SERVER_EXCLUDED = (
    "mcp-server/live_probe.py",
    "mcp-server/tests/test_live_probe.py",
)
IGNORED_DIRS = (".venv", "__pycache__", ".pytest_cache")

GUIDE = "docs/onboarding/MCP_GUIDE.md"
SERVER_GITIGNORE = SERVER_TARGET + "/.gitignore"
SERVER_GITIGNORE_TEXT = (
    "# Local MCP server environment and caches (created by setup-mcp-server.ps1).\n"
    "mcp-server/.venv/\n"
    "__pycache__/\n"
    ".pytest_cache/\n"
)
EXTENSION_TEST = "tests/test_mcp_bridge_runtime.py"
ROUTES_DEFAULT_ORIGIN = "http://127.0.0.1:48884/"


def routes_url(namespace: str) -> str:
    return ROUTES_DEFAULT_ORIGIN + namespace


def _check_inventory(root: Path, rel_dir: str, listed: tuple, excluded: tuple = ()) -> None:
    """Fail when the foundation directory holds files this adapter does not know about."""
    base = root / rel_dir
    found = set()
    if base.is_dir():
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            parts = path.relative_to(base).parts
            if any(part in IGNORED_DIRS for part in parts) or path.suffix in (".pyc", ".pyo"):
                continue
            found.add("/".join(parts))
    known = set(listed) | set(excluded)
    unknown = sorted(found - known)
    missing = sorted(set(listed) - found)
    if unknown or missing:
        raise VendoringError(
            "{}: unlisted foundation files {} / listed files missing {}; update the mcp-bridge adapter".format(
                rel_dir, unknown, missing
            )
        )


def _extension_files(profile: Profile) -> list:
    config = profile.config
    namespace = config.technical.namespace
    author = "__author__ = " + py_string(config.identity.author)
    target_root = layout.extension_dir(config.technical)
    files = []

    _check_inventory(FOUNDATION, SOURCE_EXTENSION + "/" + BRIDGE_PACKAGE, BRIDGE_MODULES)

    path = SOURCE_EXTENSION + "/startup.py"
    startup = read_foundation_text(FOUNDATION, path)
    startup = substitute(path, startup, '__author__ = "Template Author"', author)
    startup = substitute(
        path,
        startup,
        '"Placeholder extension loaded and MCP routes registered."',
        py_string("{} extension loaded and MCP routes registered.".format(config.technical.extension)),
    )
    files.append(text_file(target_root + "/startup.py", startup, ADAPTER_ID))

    for name in BRIDGE_MODULES:
        rel = "{}/{}/{}".format(SOURCE_EXTENSION, BRIDGE_PACKAGE, name)
        text = read_foundation_text(FOUNDATION, rel)
        text = substitute(rel, text, '__author__ = "Template Author"', author)
        if name in ROUTE_MODULES:
            text = substitute(rel, text, 'routes.API("placeholder")', "routes.API({})".format(py_string(namespace)))
        files.append(text_file("{}/{}/{}".format(target_root, BRIDGE_PACKAGE, name), text, ADAPTER_ID))

    files.append(
        text_file(
            "{}/{}".format(target_root, EXTENSION_TEST),
            render_file(
                "mcp_bridge/test_mcp_bridge_runtime.py.tmpl",
                {"namespace": namespace, "author_literal": py_string(config.identity.author)},
            ),
            ADAPTER_ID,
        )
    )
    return files


def _server_files(profile: Profile) -> list:
    namespace = profile.config.technical.namespace
    _check_inventory(FOUNDATION, SERVER_SOURCE, SERVER_FILES, SERVER_EXCLUDED)
    files = []
    for rel in SERVER_FILES:
        source = "{}/{}".format(SERVER_SOURCE, rel)
        text = read_foundation_text(FOUNDATION, source)
        if rel == "mcp-server/settings.py":
            text = substitute(source, text, "(/placeholder)", "(/{})".format(namespace))
            text = substitute(source, text, '48884/placeholder"', '48884/{}"'.format(namespace))
        elif rel == "mcp-server/tests/test_settings.py":
            # Seven URL literals in the loopback-validation tests all name the prefix.
            text = substitute(source, text, "/placeholder", "/" + namespace, count=7)
        files.append(text_file("{}/{}".format(SERVER_TARGET, rel), text, ADAPTER_ID))
    files.append(text_file(SERVER_GITIGNORE, SERVER_GITIGNORE_TEXT, ADAPTER_ID))
    return files


def render(profile: Profile) -> RenderResult:
    config = profile.config
    technical = config.technical
    result = RenderResult()
    result.files.extend(_extension_files(profile))
    result.files.extend(_server_files(profile))
    result.files.append(
        text_file(
            GUIDE,
            render_file(
                "mcp_bridge/MCP_GUIDE.md.tmpl",
                {
                    "display_name": md(config.identity.display_name),
                    "namespace": technical.namespace,
                    "extension": technical.extension,
                    "routes_url": routes_url(technical.namespace),
                },
            ),
            ADAPTER_ID,
        )
    )
    result.diagnostics.append(
        Diagnostic(
            "mcp-bridge.not-live-verified",
            "info",
            "mcp-bridge: " + layout.extension_dir(technical),
            "The generated MCP bridge is read-only and statically checked only; it has not run in a live Revit/pyRevit session.",
            "After any pyRevit Reload, restart Revit or toggle Routes off/on before the first route request. See " + GUIDE + ".",
        )
    )
    return result
