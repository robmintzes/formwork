"""Record live-host evidence for a generated firm workspace.

Automated checks prove the workspace is current and valid and that pyRevit
can see it; the human checklist records what only a person in Revit can
observe (ribbon, icons, contexts, read-only behaviour). Evidence carries
outcomes and versions only: no absolute paths, user names, or model data.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
from typing import Any, Callable, Mapping, Sequence

from toolkit_cli import __version__ as toolkit_version
from toolkit_cli.results import CheckResult, report_exit_code, summarize
from toolkit_cli.verify import _generated_at, _git_provenance, _manual_checks
from toolkit_engine import __version__ as engine_version
from toolkit_engine.workspace import EngineError, render_workspace

MANUAL_TEMPLATE = Path(__file__).resolve().parents[1] / "docs" / "verification" / "workspace-manual-checks.template.json"
REVIT_VERSION = re.compile(r"^20[2-9][0-9]$")
PYREVIT_VERSION = re.compile(r"pyrevit\s+v?(\d+(?:\.\d+){1,3})", re.IGNORECASE)
CommandRunner = Callable[[Sequence[str]], "subprocess.CompletedProcess[str]"]


def _default_run(command: Sequence[str]) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )


def _comparable(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.expandvars(path.strip()))).rstrip("\\/")


def _workspace_checks(workspace: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    from validators.check_bundle_structure import validate_bundle_structure
    from validators.validate_toolbar_spec import validate_toolbar_spec

    checks: list[CheckResult] = []
    metadata: dict[str, Any] = {"workspace_id": None, "profile_id": None}
    try:
        report = render_workspace(workspace, dry_run=True)
    except EngineError as exc:
        checks.append(
            CheckResult(
                "workspace.render-current",
                "Workspace matches its inputs",
                "fail",
                "The workspace could not be planned.",
                required=True,
                details={"code": exc.code},
            )
        )
        return checks, metadata

    metadata["workspace_id"] = report.get("workspace_id")
    metadata["profile_id"] = report.get("profile_id")
    summary = report["summary"]
    codes = sorted({d["code"] for d in report["diagnostics"] if d["severity"] == "error"})
    if summary["outcome"] != "pass":
        status, text = "fail", "Planning reported errors or conflicts; resolve them before testing in Revit."
    elif summary.get("changes", 0):
        status, text = "fail", "The workspace differs from its inputs; run toolkit render before testing."
    else:
        status, text = "pass", "A dry-run render reports no changes."
    checks.append(
        CheckResult(
            "workspace.render-current",
            "Workspace matches its inputs",
            status,
            text,
            required=True,
            details={"changes": summary.get("changes", 0), "error_codes": codes},
        )
    )

    bundle_errors, _ = validate_bundle_structure(workspace)
    _, spec_errors = validate_toolbar_spec(workspace)
    checks.append(
        CheckResult(
            "workspace.validators",
            "Bundle and toolbar spec validators",
            "fail" if bundle_errors or spec_errors else "pass",
            "{} bundle and {} spec error(s).".format(len(bundle_errors), len(spec_errors)),
            required=True,
            details={"bundle_errors": len(bundle_errors), "spec_errors": len(spec_errors)},
        )
    )
    return checks, metadata


def _host_checks(
    workspace: Path, revit_version: str | None, run_command: CommandRunner, which: Callable[[str], str | None]
) -> tuple[list[CheckResult], dict[str, Any]]:
    checks: list[CheckResult] = []
    metadata: dict[str, Any] = {"pyrevit_version": None, "revit_version": None}

    if revit_version and REVIT_VERSION.fullmatch(revit_version):
        metadata["revit_version"] = revit_version
        checks.append(CheckResult("host.revit-version", "Declared Revit version", "pass", "Revit " + revit_version, required=True))
    else:
        checks.append(
            CheckResult(
                "host.revit-version",
                "Declared Revit version",
                "warn",
                "Pass --revit-version (for example 2026) so the evidence names the host.",
                required=True,
            )
        )

    executable = which("pyrevit")
    if not executable:
        checks.append(CheckResult("host.pyrevit-cli", "pyRevit CLI", "fail", "The pyrevit CLI is not on PATH.", required=True))
        return checks, metadata
    version = run_command([executable, "--version"])
    match = PYREVIT_VERSION.search(version.stdout or "")
    metadata["pyrevit_version"] = match.group(1) if match else None
    checks.append(
        CheckResult(
            "host.pyrevit-cli",
            "pyRevit CLI",
            "pass" if version.returncode == 0 and match else "fail",
            "pyRevit {}".format(match.group(1)) if match else "Could not read the pyRevit version.",
            required=True,
        )
    )

    listed = run_command([executable, "extensions", "paths"])
    expected = _comparable(str(workspace / "extensions"))
    registered = listed.returncode == 0 and any(
        _comparable(line) == expected
        for line in (listed.stdout or "").splitlines()
        if line.strip() and not line.strip().startswith("==>")
    )
    checks.append(
        CheckResult(
            "host.extension-path-registered",
            "Workspace extensions registered with pyRevit",
            "pass" if registered else "fail",
            "pyRevit lists the workspace extensions folder."
            if registered
            else "pyRevit does not list the workspace extensions folder; run: pyrevit extensions paths add <workspace>\\extensions",
            required=True,
        )
    )
    return checks, metadata


def _coverage_check(manual_checks_path: str | os.PathLike[str] | None, template: Path) -> CheckResult:
    """The filled checklist must keep every template check and its required flag."""
    title = "Manual checklist covers the template"
    if manual_checks_path is None:
        return CheckResult("manual.coverage", title, "warn", "No filled checklist was supplied.", required=True)
    try:
        expected = json.loads(template.read_text(encoding="utf-8"))["checks"]
        supplied = json.loads(Path(manual_checks_path).read_text(encoding="utf-8"))
        supplied = supplied.get("checks") if isinstance(supplied, dict) else supplied
        supplied_by_id = {item.get("id"): item for item in supplied if isinstance(item, dict)}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return CheckResult("manual.coverage", title, "fail", "The checklist or its template could not be read.", required=True)
    missing = [item["id"] for item in expected if item["id"] not in supplied_by_id]
    downgraded = [
        item["id"]
        for item in expected
        if item.get("required", True) and supplied_by_id.get(item["id"], {}).get("required", True) is not True
    ]
    if missing or downgraded:
        return CheckResult(
            "manual.coverage",
            title,
            "fail",
            "Checks were removed or made optional.",
            required=True,
            details={"missing": missing, "downgraded": downgraded},
        )
    return CheckResult("manual.coverage", title, "pass", "All {} template checks are present.".format(len(expected)), required=True)


def run_workspace_verification(
    workspace: Path,
    *,
    manual_checks_path: str | os.PathLike[str] | None = None,
    revit_version: str | None = None,
    timestamp: datetime | str | None = None,
    run_command: CommandRunner = _default_run,
    which: Callable[[str], str | None] = shutil.which,
    manual_template: Path = MANUAL_TEMPLATE,
) -> dict[str, Any]:
    workspace_checks, workspace_meta = _workspace_checks(workspace)
    host_checks, host_meta = _host_checks(workspace, revit_version, run_command, which)
    checks = (
        workspace_checks
        + host_checks
        + [_coverage_check(manual_checks_path, manual_template)]
        + _manual_checks(manual_checks_path)
    )
    sha, dirty = _git_provenance()
    report: dict[str, Any] = {
        "schema_version": 1,
        "kind": "toolkit-workspace-verification",
        "generated_at": _generated_at(timestamp),
        "metadata": {
            "toolkit_version": toolkit_version,
            "engine_version": engine_version,
            "git_sha": sha,
            "git_dirty": dirty,
            "os": platform.system(),
            "os_version": platform.release(),
            **workspace_meta,
            **host_meta,
        },
        "checks": [check.as_dict() for check in checks],
        "summary": summarize(checks),
    }
    report["exit_code"] = report_exit_code(report)
    return report


def write_workspace_evidence(report: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "workspace-verification.json"
    markdown_path = output_dir / "workspace-verification.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    markdown_path.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    return {"json": json_path, "markdown": markdown_path}


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("`", "'").replace("\n", " ")


def render_markdown(report: Mapping[str, Any]) -> str:
    meta = report["metadata"]
    summary = report["summary"]
    lines = [
        "# Generated workspace verification",
        "",
        "Outcomes and versions only; no paths, user names, or model data are retained.",
        "",
        "- Outcome: **{}**".format(_cell(summary["outcome"]).upper()),
        "- Generated (UTC): `{}`".format(_cell(report["generated_at"])),
        "- Workspace / profile: `{}` / `{}`".format(_cell(meta.get("workspace_id")), _cell(meta.get("profile_id"))),
        "- Revit: `{}`; pyRevit: `{}`; OS: `{} {}`".format(
            _cell(meta.get("revit_version")), _cell(meta.get("pyrevit_version")), _cell(meta.get("os")), _cell(meta.get("os_version"))
        ),
        "- Foundation: toolkit `{}`, engine `{}`, git `{}` (dirty: `{}`)".format(
            _cell(meta.get("toolkit_version")), _cell(meta.get("engine_version")), _cell(meta.get("git_sha")), _cell(meta.get("git_dirty"))
        ),
        "",
        "| Status | Check | Required | Summary |",
        "| --- | --- | --- | --- |",
    ]
    for check in report["checks"]:
        lines.append(
            "| {} | {} | {} | {} |".format(
                _cell(check["status"]).upper(), _cell(check["title"]), "yes" if check.get("required") else "no", _cell(check["summary"])
            )
        )
    return "\n".join(lines) + "\n"


def format_text(report: Mapping[str, Any], paths: Mapping[str, Path]) -> str:
    lines = ["Generated workspace verification", "Outcome: {}".format(str(report["summary"]["outcome"]).upper()), ""]
    for check in report["checks"]:
        lines.append(
            "[{:<4}] {}{} - {}".format(
                str(check["status"]).upper(), check["title"], " required" if check.get("required") else "", check["summary"]
            )
        )
    lines += ["", "JSON evidence: {}".format(paths["json"]), "Markdown evidence: {}".format(paths["markdown"])]
    return "\n".join(lines)
