"""Platform adapters: pure functions from a Profile to rendered files.

Each adapter returns a RenderResult and never touches the filesystem
(FOUNDATION_SPEC section 6). ``common`` always runs; the rest run when their
surface id is listed in firm.json ``surfaces``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from formwork_engine.diagnostics import Diagnostic
from formwork_engine.outputs import OutputFile
from formwork_engine.profile import Profile


@dataclass
class RenderResult:
    files: list[OutputFile] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)


Adapter = Callable[[Profile], RenderResult]


def _registry() -> dict[str, Adapter]:
    from formwork_engine.adapters import (
        common,
        governance,
        html_guide,
        mcp_bridge,
        pyrevit_sample,
        python_app,
        revit_addin,
        ui_kit,
        web_host,
        web_app,
        wpf_specimen,
    )

    return {
        "common": common.render,
        "pyrevit-sample": pyrevit_sample.render,
        "wpf-specimen": wpf_specimen.render,
        "html-guide": html_guide.render,
        "governance": governance.render,
        "mcp-bridge": mcp_bridge.render,
        "ui-kit": ui_kit.render,
        "web-host": web_host.render,
        "revit-addin": revit_addin.render,
        "python-app": python_app.render,
        "web-app": web_app.render,
    }


def known_adapters() -> frozenset[str]:
    """Adapter ids a manifest may legitimately name."""
    return frozenset(_registry())


def render_all(profile: Profile) -> RenderResult:
    """Run ``common`` plus every enabled surface adapter, in a fixed order."""
    registry = _registry()
    combined = RenderResult()
    for adapter_id in ("common",) + tuple(s for s in registry if s in profile.config.surfaces):
        result = registry[adapter_id](profile)
        combined.files.extend(result.files)
        combined.diagnostics.extend(result.diagnostics)
    return combined
