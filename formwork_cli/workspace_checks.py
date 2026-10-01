"""Checks shared by ``formwork validate --workspace`` and ``formwork verify workspace``."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from typing import Any

from formwork_cli.results import CheckResult
from formwork_engine.workspace import EngineError, render_workspace

FIRM_TEST_TIMEOUT = 600


def render_current_check(workspace: Path) -> tuple[CheckResult, dict[str, Any]]:
    """A dry-run render must report no changes and no errors."""
    metadata: dict[str, Any] = {"workspace_id": None, "profile_id": None}
    title = "Workspace matches its inputs"
    try:
        report = render_workspace(workspace, dry_run=True)
    except EngineError as exc:
        return (
            CheckResult(
                "workspace.render-current", title, "fail", "The workspace could not be planned.", required=True, details={"code": exc.code}
            ),
            metadata,
        )
    metadata["workspace_id"] = report.get("workspace_id")
    metadata["profile_id"] = report.get("profile_id")
    summary = report["summary"]
    codes = sorted({d["code"] for d in report["diagnostics"] if d["severity"] == "error"})
    if summary["outcome"] != "pass":
        status, text = "fail", "Planning reported errors or conflicts; run formwork render --dry-run for details."
    elif summary.get("changes", 0):
        status, text = "fail", "The workspace differs from its inputs; run formwork render."
    else:
        status, text = "pass", "A dry-run render reports no changes."
    return (
        CheckResult(
            "workspace.render-current", title, status, text, required=True, details={"changes": summary.get("changes", 0), "error_codes": codes}
        ),
        metadata,
    )


def validator_checks(workspace: Path) -> list[CheckResult]:
    """Run the foundation validators against the workspace root."""
    from validators.check_bundle_structure import validate_bundle_structure
    from validators.check_safety_rules import find_violations
    from validators.validate_toolbar_spec import validate_toolbar_spec

    bundle_errors, _ = validate_bundle_structure(workspace)
    _, spec_errors = validate_toolbar_spec(workspace)
    safety = find_violations(workspace)
    results = []
    for check_id, title, errors in (
        ("validators.bundle", "Bundle structure and metadata", bundle_errors),
        ("validators.spec", "Toolbar spec alignment", spec_errors),
        ("validators.safety", "Safety patterns in extension code", safety),
    ):
        results.append(
            CheckResult(
                check_id,
                title,
                "fail" if errors else "pass",
                "{} error(s).".format(len(errors)) if errors else "No errors.",
                required=True,
                # Messages are workspace-relative and contain no user data.
                details={"errors": [str(e) for e in errors[:50]]},
            )
        )
    return results


def firm_tests_check(workspace: Path) -> CheckResult:
    """Run the firm's own unittest suite when the workspace has one."""
    tests = workspace / "tests"
    title = "Firm tests"
    if not tests.is_dir():
        return CheckResult("firm.tests", title, "skip", "The workspace has no tests/ directory.")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=FIRM_TEST_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CheckResult("firm.tests", title, "fail", "Firm tests exceeded {} s.".format(FIRM_TEST_TIMEOUT), required=True)
    tail = (result.stderr or result.stdout).strip().splitlines()[-1:] or [""]
    return CheckResult(
        "firm.tests",
        title,
        "pass" if result.returncode == 0 else "fail",
        tail[0][:200],
        required=True,
        details={"exit_code": result.returncode},
    )
