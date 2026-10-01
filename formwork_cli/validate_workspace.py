"""``formwork validate --workspace``: is this generated workspace healthy right now?

Static and automated checks only. Live Revit behavior is ``formwork verify workspace``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from formwork_cli import __version__ as formwork_version
from formwork_cli.results import report_exit_code, summarize
from formwork_cli.workspace_checks import firm_tests_check, render_current_check, validator_checks
from formwork_engine import __version__ as engine_version


def run_workspace_validation(workspace: Path, *, run_tests: bool = True) -> dict[str, Any]:
    current, metadata = render_current_check(workspace)
    checks = [current] + validator_checks(workspace)
    if run_tests:
        checks.append(firm_tests_check(workspace))
    report: dict[str, Any] = {
        "schema_version": 1,
        "kind": "formwork-workspace-validation",
        "formwork_version": formwork_version,
        "engine_version": engine_version,
        "metadata": metadata,
        "checks": [check.as_dict() for check in checks],
        "summary": summarize(checks),
    }
    report["exit_code"] = report_exit_code(report)
    return report


def format_text(report: Mapping[str, Any]) -> str:
    meta = report["metadata"]
    lines = [
        "Workspace validation ({}): {}".format(meta.get("workspace_id") or "?", str(report["summary"]["outcome"]).upper()),
    ]
    for check in report["checks"]:
        lines.append("[{:<4}] {} - {}".format(str(check["status"]).upper(), check["title"], check["summary"]))
        for error in check.get("details", {}).get("errors", [])[:10]:
            lines.append("         " + error)
    return "\n".join(lines)
