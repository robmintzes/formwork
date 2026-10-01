"""Cross-platform environment diagnostics for Formwork authoring and Revit hosts."""

from __future__ import annotations

import json
import ntpath
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse

from formwork_cli import __version__
from formwork_cli.results import CheckResult, summarize


PROFILE_AUTHORING = "authoring"
PROFILE_REVIT_HOST = "revit-host"
VALID_PROFILES = (PROFILE_AUTHORING, PROFILE_REVIT_HOST)
VALIDATORS = (
    "validators/check_bundle_structure.py",
    "validators/check_safety_rules.py",
    "validators/validate_toolbar_spec.py",
)
REPOSITORY_MARKERS = (
    "AGENTS.md",
    "extensions",
    "servers/revit-mcp/mcp-server",
    "validators",
)

RunCommand = Callable[..., subprocess.CompletedProcess[str]]
WhichCommand = Callable[[str], str | None]
ConnectProbe = Callable[[str, int, float], bool]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_run(
    command: Sequence[str], *, cwd: Path, timeout: float = 15.0
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def _default_connect(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _safe_command_version(
    command_path: str,
    args: Sequence[str],
    *,
    cwd: Path,
    run_command: RunCommand,
) -> tuple[bool, str]:
    try:
        result = run_command([command_path, *args], cwd=cwd, timeout=10.0)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, type(exc).__name__
    output = (result.stdout or result.stderr or "").strip().splitlines()
    summary = output[0][:200] if output else "no version output"
    return result.returncode == 0, summary


def _command_check(
    check_id: str,
    title: str,
    names: Sequence[str],
    version_args: Sequence[str],
    *,
    required: bool,
    cwd: Path,
    which: WhichCommand,
    run_command: RunCommand,
) -> CheckResult:
    for name in names:
        command_path = which(name)
        if not command_path:
            continue
        ok, version = _safe_command_version(
            command_path, version_args, cwd=cwd, run_command=run_command
        )
        if ok:
            return CheckResult(
                check_id,
                title,
                "pass",
                "{} is available.".format(name),
                required=required,
                details={"command": name, "version": version},
            )
        return CheckResult(
            check_id,
            title,
            "fail" if required else "warn",
            "{} was found but could not run.".format(name),
            required=required,
            details={"command": name, "result": version},
        )
    return CheckResult(
        check_id,
        title,
        "fail" if required else "warn",
        "No supported command was found on PATH.",
        required=required,
        details={"tried": list(names)},
    )


def _repository_check(repo_root: Path) -> CheckResult:
    missing = [marker for marker in REPOSITORY_MARKERS if not (repo_root / marker).exists()]
    if missing:
        return CheckResult(
            "repository.layout",
            "Repository layout",
            "fail",
            "Required repository markers are missing.",
            required=True,
            details={"missing": missing},
        )
    return CheckResult(
        "repository.layout",
        "Repository layout",
        "pass",
        "Formwork repository markers are present.",
        required=True,
    )


def _python_check() -> CheckResult:
    supported = sys.version_info >= (3, 10)
    return CheckResult(
        "runtime.python",
        "CPython runtime",
        "pass" if supported else "fail",
        "Python {}.{}.{} is {}.".format(
            sys.version_info.major,
            sys.version_info.minor,
            sys.version_info.micro,
            "supported" if supported else "unsupported; 3.10 or newer is required",
        ),
        required=True,
        details={
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
    )


def _validator_check(repo_root: Path, run_command: RunCommand) -> CheckResult:
    results: list[dict[str, Any]] = []
    failed: list[str] = []
    for relative_path in VALIDATORS:
        try:
            result = run_command(
                [sys.executable, str(repo_root / relative_path)],
                cwd=repo_root,
                timeout=30.0,
            )
            code = result.returncode
        except (OSError, subprocess.SubprocessError):
            code = -1
        results.append({"validator": relative_path, "exit_code": code})
        if code != 0:
            failed.append(relative_path)
    return CheckResult(
        "repository.validators",
        "Static repository validators",
        "fail" if failed else "pass",
        (
            "Validators failed: {}.".format(", ".join(failed))
            if failed
            else "All static repository validators passed."
        ),
        required=True,
        details={"commands": results},
    )


def _git_state(repo_root: Path, run_command: RunCommand) -> tuple[CheckResult, dict[str, Any]]:
    git = shutil.which("git")
    if not git:
        return (
            CheckResult(
                "runtime.git",
                "Git",
                "fail",
                "Git was not found on PATH.",
                required=True,
            ),
            {"sha": None, "branch": None, "dirty": None},
        )
    try:
        version = run_command([git, "--version"], cwd=repo_root, timeout=10.0)
        sha = run_command([git, "rev-parse", "HEAD"], cwd=repo_root, timeout=10.0)
        branch = run_command(
            [git, "branch", "--show-current"], cwd=repo_root, timeout=10.0
        )
        status = run_command(
            [git, "status", "--porcelain"], cwd=repo_root, timeout=10.0
        )
    except (OSError, subprocess.SubprocessError):
        return (
            CheckResult(
                "runtime.git",
                "Git",
                "fail",
                "Git was found but repository inspection failed.",
                required=True,
            ),
            {"sha": None, "branch": None, "dirty": None},
        )
    commands_ok = all(
        item.returncode == 0 for item in (version, sha, branch, status)
    )
    identity = {
        "sha": sha.stdout.strip() if sha.returncode == 0 else None,
        "branch": branch.stdout.strip() if branch.returncode == 0 else None,
        "dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
    }
    return (
        CheckResult(
            "runtime.git",
            "Git",
            "pass" if commands_ok else "fail",
            "Git and repository identity are available."
            if commands_ok
            else "Git could not inspect this repository.",
            required=True,
            details={
                "version": (version.stdout or version.stderr).strip()[:200],
                "branch": identity["branch"],
                "dirty": identity["dirty"],
            },
        ),
        identity,
    )


def _mcp_environment_check(
    repo_root: Path,
    *,
    required: bool,
    system_name: str,
    run_command: RunCommand,
) -> CheckResult:
    executable = (
        repo_root / "servers/revit-mcp/mcp-server/.venv/Scripts/python.exe"
        if system_name == "Windows"
        else repo_root / "servers/revit-mcp/mcp-server/.venv/bin/python"
    )
    if not executable.is_file():
        return CheckResult(
            "mcp.environment",
            "MCP virtual environment",
            "warn",
            "The MCP virtual environment has not been created.",
            required=required,
            details={
                "remediation": "Run servers/revit-mcp/scripts/setup-mcp-server.ps1 on Windows."
            },
        )
    try:
        result = run_command(
            [
                str(executable),
                "-c",
                "from mcp.server import MCPServer; import httpx, pydantic",
            ],
            cwd=repo_root / "servers/revit-mcp/mcp-server",
            timeout=20.0,
        )
    except (OSError, subprocess.SubprocessError):
        result = None
    passed = result is not None and result.returncode == 0
    return CheckResult(
        "mcp.environment",
        "MCP virtual environment",
        "pass" if passed else ("fail" if required else "warn"),
        "MCP dependencies import successfully."
        if passed
        else "The MCP environment exists but its dependency import check failed.",
        required=required,
    )


def _discover_revit(environ: Mapping[str, str]) -> list[str]:
    installations: set[str] = set()
    for env_name in ("ProgramW6432", "ProgramFiles"):
        base = environ.get(env_name)
        if not base:
            continue
        autodesk = Path(base) / "Autodesk"
        if not autodesk.is_dir():
            continue
        for executable in autodesk.glob("Revit 20??/Revit.exe"):
            version = executable.parent.name.removeprefix("Revit ")
            installations.add(version)
    return sorted(installations)


def _revit_check(
    *, system_name: str, profile: str, environ: Mapping[str, str]
) -> CheckResult:
    required = profile == PROFILE_REVIT_HOST
    if system_name != "Windows":
        return CheckResult(
            "revit.installation",
            "Autodesk Revit installation",
            "skip",
            "Revit installation discovery only applies on Windows.",
            required=required,
        )
    versions = _discover_revit(environ)
    return CheckResult(
        "revit.installation",
        "Autodesk Revit installation",
        "pass" if versions else "warn",
        "Discovered Revit {}.".format(", ".join(versions))
        if versions
        else "No supported Revit installation was discovered.",
        required=required,
        details={"versions": versions},
    )


def _pyrevit_checks(
    *,
    repo_root: Path,
    profile: str,
    system_name: str,
    routes_url: str,
    which: WhichCommand,
    run_command: RunCommand,
) -> list[CheckResult]:
    required = profile == PROFILE_REVIT_HOST
    if system_name != "Windows":
        return [
            CheckResult(
                "pyrevit.cli",
                "pyRevit CLI",
                "skip",
                "pyRevit CLI inspection only applies on Windows.",
                required=required,
            ),
            CheckResult(
                "pyrevit.routes-config",
                "pyRevit Routes configuration",
                "skip",
                "Routes configuration inspection only applies on Windows.",
                required=required,
            ),
            CheckResult(
                "pyrevit.extension-path",
                "pyRevit extension registration",
                "skip",
                "Extension registration inspection only applies on Windows.",
                required=required,
            ),
        ]

    executable = which("pyrevit")
    if not executable:
        missing = CheckResult(
            "pyrevit.cli",
            "pyRevit CLI",
            "warn",
            "pyRevit CLI was not found on PATH.",
            required=required,
        )
        return [
            missing,
            CheckResult(
                "pyrevit.routes-config",
                "pyRevit Routes configuration",
                "skip",
                "Cannot inspect Routes without the pyRevit CLI.",
                required=required,
            ),
            CheckResult(
                "pyrevit.extension-path",
                "pyRevit extension registration",
                "skip",
                "Cannot inspect extension paths without the pyRevit CLI.",
                required=required,
            ),
        ]

    try:
        version = run_command([executable, "--version"], cwd=repo_root, timeout=10.0)
        routes = run_command(
            [executable, "configs", "routes"], cwd=repo_root, timeout=10.0
        )
        paths = run_command(
            [executable, "extensions", "paths"], cwd=repo_root, timeout=10.0
        )
        routes_port = run_command(
            [executable, "configs", "routes", "port"],
            cwd=repo_root,
            timeout=10.0,
        )
    except (OSError, subprocess.SubprocessError):
        version = routes = paths = routes_port = None

    cli_ok = version is not None and version.returncode == 0
    routes_commands_ok = all(
        result is not None and result.returncode == 0
        for result in (routes, routes_port)
    )
    paths_ok = paths is not None and paths.returncode == 0
    routes_enabled = _parse_routes_enabled(routes.stdout if routes_commands_ok else "")
    configured_port = _parse_routes_port(
        routes_port.stdout if routes_commands_ok else ""
    )
    try:
        expected_port = urlparse(routes_url).port
    except ValueError:
        expected_port = None
    routes_ready = bool(
        routes_commands_ok
        and routes_enabled is True
        and configured_port is not None
        and configured_port == expected_port
    )
    registered = bool(
        paths_ok
        and _extension_path_listed(
            paths.stdout or "", repo_root / "extensions", system_name
        )
    )
    return [
        CheckResult(
            "pyrevit.cli",
            "pyRevit CLI",
            "pass" if cli_ok else ("fail" if required else "warn"),
            "pyRevit CLI responded."
            if cli_ok
            else "pyRevit CLI was found but did not respond successfully.",
            required=required,
            details={
                "version": ((version.stdout or version.stderr).strip()[:200] if version else None)
            },
        ),
        CheckResult(
            "pyrevit.routes-config",
            "pyRevit Routes configuration",
            "pass"
            if routes_ready
            else ("fail" if not routes_commands_ok else "warn"),
            (
                "pyRevit Routes is enabled on the expected port."
                if routes_ready
                else (
                    "Could not read a valid pyRevit Routes configuration."
                    if not routes_commands_ok
                    else "pyRevit Routes is disabled or configured on a different port."
                )
            ),
            required=required,
            details={
                "enabled": routes_enabled,
                "configured_port": configured_port,
                "expected_port": expected_port,
            },
        ),
        CheckResult(
            "pyrevit.extension-path",
            "pyRevit extension registration",
            "pass" if registered else "warn",
            "This repository's extensions directory is registered."
            if registered
            else "This repository's extensions directory is not registered.",
            required=required,
        ),
    ]


def _parse_routes_enabled(output: str) -> bool | None:
    match = re.search(
        r"^\s*Routes Server is (Enabled|Disabled)\s*$",
        output,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if not match:
        return None
    return match.group(1).lower() == "enabled"


def _parse_routes_port(output: str) -> int | None:
    match = re.search(
        r"^\s*Routes Port:\s*(\d+)\s*$", output, flags=re.IGNORECASE | re.MULTILINE
    )
    if not match:
        return None
    port = int(match.group(1))
    return port if 1 <= port <= 65535 else None


def _extension_path_listed(
    output: str, expected_path: Path, system_name: str
) -> bool:
    """Match a pyRevit extension path as a normalized complete output line."""
    path_module = ntpath if system_name == "Windows" else os.path
    expected = path_module.normcase(path_module.normpath(str(expected_path.resolve())))
    for raw_line in output.splitlines():
        line = raw_line.strip().strip('"\'')
        if not line or line.startswith("==>"):
            continue
        candidate = path_module.normcase(path_module.normpath(line))
        if candidate == expected:
            return True
    return False


def _port_check(
    check_id: str,
    title: str,
    url: str,
    *,
    connect: ConnectProbe,
) -> CheckResult:
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port
    except (TypeError, ValueError):
        host = None
        port = None
        parsed = None
    if (
        parsed is None
        or parsed.scheme not in ("http", "https")
        or host not in ("127.0.0.1", "localhost", "::1")
        or port is None
        or parsed.username is not None
        or parsed.password is not None
        or bool(parsed.query)
        or bool(parsed.fragment)
    ):
        return CheckResult(
            check_id,
            title,
            "fail",
            "Configured endpoint must be an explicit loopback URL with a port.",
            details={"issue": "invalid_or_non_loopback_url"},
        )
    listening = connect(host, port, 0.25)
    return CheckResult(
        check_id,
        title,
        "pass" if listening else "warn",
        "A loopback listener accepted a connection."
        if listening
        else "No loopback listener is active; this is expected before the host starts.",
        details={"host": host, "port": port},
    )


def run_doctor(
    repo_root: Path,
    *,
    profile: str = PROFILE_AUTHORING,
    routes_url: str = "http://127.0.0.1:48884/placeholder",
    mcp_url: str = "http://127.0.0.1:3001/mcp",
    timestamp: str | None = None,
    system_name: str | None = None,
    environ: Mapping[str, str] | None = None,
    which: WhichCommand = shutil.which,
    run_command: RunCommand = _default_run,
    connect: ConnectProbe = _default_connect,
) -> dict[str, Any]:
    """Run portable diagnostics and return a serializable report."""
    if profile not in VALID_PROFILES:
        raise ValueError("unknown doctor profile: {!r}".format(profile))

    root = repo_root.resolve()
    current_system = system_name or platform.system()
    current_environ = environ if environ is not None else os.environ
    host_required = profile == PROFILE_REVIT_HOST

    checks: list[CheckResult] = [_python_check(), _repository_check(root)]
    git_check, git_identity = _git_state(root, run_command)
    checks.append(git_check)
    checks.append(_validator_check(root, run_command))
    checks.append(
        _command_check(
            "runtime.powershell",
            "PowerShell",
            ("pwsh", "powershell"),
            ("-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"),
            required=current_system == "Windows",
            cwd=root,
            which=which,
            run_command=run_command,
        )
    )
    checks.append(
        _mcp_environment_check(
            root,
            required=host_required,
            system_name=current_system,
            run_command=run_command,
        )
    )
    checks.append(
        _revit_check(
            system_name=current_system, profile=profile, environ=current_environ
        )
    )
    checks.extend(
        _pyrevit_checks(
            repo_root=root,
            profile=profile,
            system_name=current_system,
            routes_url=routes_url,
            which=which,
            run_command=run_command,
        )
    )
    checks.extend(
        (
            _port_check(
                "network.routes",
                "pyRevit Routes listener",
                routes_url,
                connect=connect,
            ),
            _port_check(
                "network.mcp-http", "MCP HTTP listener", mcp_url, connect=connect
            ),
        )
    )

    check_dicts = [check.as_dict() for check in checks]
    return {
        "schema_version": 1,
        "kind": "formwork-doctor",
        "generated_at": timestamp or _utc_now(),
        "formwork_version": __version__,
        "profile": profile,
        "environment": {
            "system": current_system,
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "repository": {
            "branch": git_identity["branch"],
            "sha": git_identity["sha"],
            "dirty": git_identity["dirty"],
        },
        "checks": check_dicts,
        "summary": summarize(check_dicts),
    }


def format_text(report: Mapping[str, Any]) -> str:
    """Render a compact terminal report without ANSI formatting."""
    lines = [
        "Formwork doctor ({})".format(report["profile"]),
        "Outcome: {}".format(str(report["summary"]["outcome"]).upper()),
        "",
    ]
    for check in report["checks"]:
        required = " required" if check.get("required") else ""
        lines.append(
            "[{status:<4}] {title}{required} - {summary}".format(
                status=str(check["status"]).upper(),
                title=check["title"],
                required=required,
                summary=check["summary"],
            )
        )
    counts = report["summary"]["counts"]
    lines.extend(
        (
            "",
            "Checks: {pass_count} pass, {warn} warn, {fail} fail, {skip} skip".format(
                pass_count=counts["pass"],
                warn=counts["warn"],
                fail=counts["fail"],
                skip=counts["skip"],
            ),
        )
    )
    return "\n".join(lines)


def write_json(report: Mapping[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
