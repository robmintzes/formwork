"""Portable live verification for the read-only Revit bridge.

The verifier deliberately retains contract metadata only. Route and MCP payloads
are inspected in memory, then discarded; project, model, link, workset, and user
values never enter the returned report or written evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import threading
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from formwork_cli.results import CheckResult, report_exit_code, summarize
from formwork_cli.revit_contract import (
    ALLOWED_STATUSES,
    CONTEXT_ERROR_CODES,
    assess_envelope,
)


EVIDENCE_SCHEMA_VERSION = 1
MCP_PROBE_PROTOCOL = "formwork-live-probe-v1"
MCP_PROBE_PREFIX = "FORMWORK_LIVE_PROBE_V1:"
MAX_HTTP_BYTES = 1024 * 1024
MAX_MANUAL_BYTES = 256 * 1024
MAX_PROBE_OUTPUT_BYTES = 1024 * 1024


@dataclass(frozen=True)
class RouteSpec:
    path: str
    tool: str


ROUTES: tuple[RouteSpec, ...] = (
    RouteSpec("/health/", "revit_health_ping"),
    RouteSpec("/project/info/", "revit_project_info"),
    RouteSpec("/project/levels/", "revit_project_levels"),
    RouteSpec("/project/worksets/", "revit_project_worksets"),
    RouteSpec("/project/links/", "revit_project_links"),
)
MCP_TOOLS: tuple[str, ...] = tuple(route.tool for route in ROUTES)
PROJECT_TOOLS = frozenset(MCP_TOOLS[1:])

_ALLOWED_RESPONSE_STATUSES = ALLOWED_STATUSES
_ALLOWED_CONTEXTS = frozenset(("any", "none", "family", "project"))
_CONTEXT_ERROR_CODES = CONTEXT_ERROR_CODES
_SAFE_MANUAL_ID = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_SAFE_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+ -]{0,79}$")
_SAFE_SHA = re.compile(r"^[0-9a-fA-F]{7,40}$")
_SAFE_HOST_APPLICATION = re.compile(
    r"^(?:Autodesk )?Revit [A-Za-z0-9][A-Za-z0-9 ._+()-]{0,99}$"
)


class ProbeProtocolError(RuntimeError):
    """Raised when the external MCP probe does not honor its JSON protocol."""


class _NoRedirect(HTTPRedirectHandler):
    """Keep an allowed loopback URL from redirecting the verifier elsewhere."""

    def redirect_request(
        self,
        request: Any,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        del request, file_pointer, code, message, headers, new_url
        return None


McpRunner = Callable[[str, str, float], Mapping[str, Any]]
_AUTO_PROVENANCE = object()


def validate_loopback_url(base_url: str) -> str:
    """Validate and normalize a loopback-only HTTP(S) Routes base URL."""
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("a Routes base URL is required")

    candidate = base_url.strip()
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("the Routes base URL has an invalid port") from exc

    if parsed.scheme not in ("http", "https"):
        raise ValueError("the Routes base URL must use HTTP or HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("credentials are not allowed in the Routes base URL")
    if parsed.query or parsed.fragment:
        raise ValueError("query strings and fragments are not allowed")
    if port is None:
        raise ValueError("the Routes base URL must include an explicit port")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("the Routes base URL must include a host")
    if hostname.lower() != "localhost":
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError as exc:
            raise ValueError("the Routes host must be a loopback address") from exc
        if not address.is_loopback:
            raise ValueError("the Routes host must be a loopback address")

    if any(segment == ".." for segment in parsed.path.split("/")):
        raise ValueError("parent path segments are not allowed")

    # Accessing parsed.port above validates its range. Preserve the namespace
    # while trimming only separator slashes used to append routes.
    return candidate.rstrip("/")


def _expected_response(
    tool: str,
    response_status: str | None,
    error_code: str | None,
    expected_context: str,
) -> tuple[str, str | None, str]:
    """Classify an operational response using only safe context metadata."""
    if tool == "revit_health_ping":
        if response_status == "ok":
            return "pass", None, "health"
        return "fail", "unexpected_health_status", "unknown"

    if response_status == "ok":
        observed_context = "project"
    elif response_status == "error" and error_code == "no_document":
        observed_context = "none"
    elif (
        response_status == "error"
        and error_code == "family_document_not_supported"
    ):
        observed_context = "family"
    else:
        return "fail", "unexpected_project_status", "unknown"

    if expected_context == "any" or expected_context == observed_context:
        return "pass", None, observed_context
    return "fail", "document_context_mismatch", observed_context


def _routes_origin(base_url: str) -> str:
    parsed = urlsplit(base_url)
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def _safe_host_application(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value if _SAFE_HOST_APPLICATION.fullmatch(value) else None


def _host_status_check(base_url: str, timeout: float, opener: Any) -> CheckResult:
    """Verify pyRevit's built-in host route without retaining its user identity."""
    check_id = "routes.host_status"
    title = "Routes host status"
    details: dict[str, Any] = {"endpoint": "/routes/status"}
    request = Request(
        _routes_origin(base_url) + "/routes/status",
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            content_type = response.headers.get_content_type().lower()
            raw = response.read(MAX_HTTP_BYTES + 1)
    except HTTPError as exc:
        details.update(issue="http_error", http_status=int(exc.code))
        return CheckResult(
            check_id,
            title,
            "fail",
            "The pyRevit host-status endpoint returned an HTTP error.",
            required=True,
            details=details,
        )
    except (URLError, TimeoutError, OSError):
        details["issue"] = "unreachable"
        return CheckResult(
            check_id,
            title,
            "fail",
            "The pyRevit host-status endpoint was unreachable.",
            required=True,
            details=details,
        )
    if len(raw) > MAX_HTTP_BYTES:
        details["issue"] = "response_too_large"
        return CheckResult(
            check_id,
            title,
            "fail",
            "The pyRevit host-status response exceeded the size limit.",
            required=True,
            details=details,
        )
    if content_type != "application/json" and not content_type.endswith("+json"):
        details["issue"] = "non_json_content_type"
        return CheckResult(
            check_id,
            title,
            "fail",
            "The pyRevit host-status endpoint did not return JSON.",
            required=True,
            details=details,
        )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        details["issue"] = "malformed_json"
        return CheckResult(
            check_id,
            title,
            "fail",
            "The pyRevit host-status endpoint returned malformed JSON.",
            required=True,
            details=details,
        )
    del raw

    host_application = (
        _safe_host_application(payload.get("host")) if isinstance(payload, dict) else None
    )
    username_valid = (
        isinstance(payload.get("username"), str) if isinstance(payload, dict) else False
    )
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    session_valid = isinstance(session_id, str) and bool(session_id)
    if host_application is None or not username_valid or not session_valid:
        del payload
        details["issue"] = "invalid_host_status_contract"
        return CheckResult(
            check_id,
            title,
            "fail",
            "The pyRevit host-status response violated its contract.",
            required=True,
            details=details,
        )

    # HOST_APP.pretty_name identifies the Revit application, not the machine.
    # Username is intentionally discarded and session identity is one-way hashed.
    details["host_application"] = host_application
    details["session_fingerprint"] = "sha256:" + hashlib.sha256(
        session_id.encode("utf-8")
    ).hexdigest()[:16]
    del payload, session_id
    return CheckResult(
        check_id,
        title,
        "pass",
        "The pyRevit host-status endpoint returned a valid session contract.",
        required=True,
        details=details,
    )


def _route_check(
    base_url: str,
    route: RouteSpec,
    timeout: float,
    opener: Any,
    expected_context: str,
) -> CheckResult:
    check_id = "routes." + route.tool
    title = "Routes: " + route.tool
    details: dict[str, Any] = {
        "endpoint": route.path,
        "expected_tool": route.tool,
    }
    request = Request(
        base_url + route.path,
        headers={"Accept": "application/json"},
        method="GET",
    )

    try:
        with opener.open(request, timeout=timeout) as response:
            content_type = response.headers.get_content_type().lower()
            raw = response.read(MAX_HTTP_BYTES + 1)
    except HTTPError as exc:
        details.update(issue="http_error", http_status=int(exc.code))
        return CheckResult(
            check_id,
            title,
            "fail",
            "The endpoint returned an HTTP error.",
            required=True,
            details=details,
        )
    except (URLError, TimeoutError, OSError):
        details["issue"] = "unreachable"
        return CheckResult(
            check_id,
            title,
            "fail",
            "The endpoint was unreachable.",
            required=True,
            details=details,
        )

    if len(raw) > MAX_HTTP_BYTES:
        details["issue"] = "response_too_large"
        return CheckResult(
            check_id,
            title,
            "fail",
            "The endpoint response exceeded the verification size limit.",
            required=True,
            details=details,
        )
    if content_type != "application/json" and not content_type.endswith("+json"):
        details["issue"] = "non_json_content_type"
        return CheckResult(
            check_id,
            title,
            "fail",
            "The endpoint did not identify its response as JSON.",
            required=True,
            details=details,
        )

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        details["issue"] = "malformed_json"
        return CheckResult(
            check_id,
            title,
            "fail",
            "The endpoint returned malformed JSON.",
            required=True,
            details=details,
        )
    del raw

    assessment = assess_envelope(payload, route.tool)
    # Do not attach payload (or any nested values) to the result.
    del payload
    if route.tool == "revit_health_ping":
        if assessment.extension_sha is not None:
            details["extension_sha"] = assessment.extension_sha
        if assessment.extension_any_stale is not None:
            details["extension_any_stale"] = assessment.extension_any_stale
        if assessment.revit_version is not None:
            details["revit_version"] = assessment.revit_version
        if assessment.revit_build is not None:
            details["revit_build"] = assessment.revit_build
        if assessment.pyrevit_version is not None:
            details["pyrevit_version"] = assessment.pyrevit_version
    if assessment.issues:
        details["issues"] = list(assessment.issues)
        return CheckResult(
            check_id,
            title,
            "fail",
            "The endpoint violated the read-only response contract.",
            required=True,
            details=details,
        )

    details["response_status"] = assessment.status
    result_status, context_issue, observed_context = _expected_response(
        route.tool, assessment.status, assessment.error_code, expected_context
    )
    details["observed_context"] = observed_context
    if context_issue is not None:
        details["issue"] = context_issue
        return CheckResult(
            check_id,
            title,
            result_status,
            "The endpoint response did not match the expected document context.",
            required=True,
            details=details,
        )
    return CheckResult(
        check_id,
        title,
        "pass",
        "The endpoint returned a valid read-only envelope for the expected context.",
        required=True,
        details=details,
    )


def parse_mcp_probe_output(stdout: str, returncode: int = 0) -> dict[str, Any]:
    """Parse the redacted, line-delimited protocol emitted by ``live_probe.py``."""
    if returncode != 0:
        raise ProbeProtocolError("the external MCP probe exited unsuccessfully")
    if not isinstance(stdout, str):
        raise ProbeProtocolError("the external MCP probe did not emit text")
    if len(stdout.encode("utf-8", errors="replace")) > MAX_PROBE_OUTPUT_BYTES:
        raise ProbeProtocolError("the external MCP probe output exceeded the size limit")

    protocol_line = next(
        (
            line[len(MCP_PROBE_PREFIX) :]
            for line in reversed(stdout.splitlines())
            if line.startswith(MCP_PROBE_PREFIX)
        ),
        None,
    )
    if protocol_line is None:
        raise ProbeProtocolError("the external MCP probe omitted its protocol record")
    try:
        payload = json.loads(protocol_line)
    except json.JSONDecodeError as exc:
        raise ProbeProtocolError("the external MCP probe emitted malformed JSON") from exc
    if not isinstance(payload, dict) or payload.get("protocol") != MCP_PROBE_PROTOCOL:
        raise ProbeProtocolError("the external MCP probe used an unknown protocol")
    if not isinstance(payload.get("results"), list):
        raise ProbeProtocolError("the external MCP probe omitted tool results")
    return payload


def _run_mcp_probe(
    python_executable: str,
    base_url: str,
    timeout: float,
) -> dict[str, Any]:
    """Run the dedicated MCP helper with the caller-supplied Python runtime."""
    if not isinstance(python_executable, str) or not python_executable.strip():
        raise ProbeProtocolError("an external Python executable is required")

    helper = (
        Path(__file__).resolve().parents[1]
        / "servers"
        / "revit-mcp"
        / "mcp-server"
        / "live_probe.py"
    )
    environment = os.environ.copy()
    environment.update(
        {
            "ENABLE_WRITE_TOOLS": "false",
            "PYTHONIOENCODING": "utf-8",
            "REVIT_ROUTES_BASE_URL": base_url,
            "REVIT_ROUTES_TIMEOUT": str(timeout),
        }
    )
    process_timeout = max(10.0, timeout * len(MCP_TOOLS) + 10.0)
    try:
        raw, returncode = _execute_bounded_process(
            [python_executable, str(helper), "--base-url", base_url],
            environment,
            process_timeout,
        )
    except ProbeProtocolError:
        raise
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProbeProtocolError("the external MCP probe could not run") from exc
    return parse_mcp_probe_output(
        raw.decode("utf-8", errors="replace"), returncode
    )


def _execute_bounded_process(
    command: list[str], environment: Mapping[str, str], timeout: float
) -> tuple[bytes, int]:
    """Run a subprocess while enforcing a live combined output byte ceiling."""
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=dict(environment),
    )
    if process.stdout is None or process.stderr is None:
        process.kill()
        process.wait()
        raise ProbeProtocolError("the external MCP probe pipes were unavailable")

    lock = threading.Lock()
    exceeded = threading.Event()
    reader_failed = threading.Event()
    total_bytes = 0
    stdout_bytes = bytearray()

    def drain(stream: Any, retain: bool) -> None:
        nonlocal total_bytes
        try:
            while True:
                chunk = stream.read(64 * 1024)
                if not chunk:
                    break
                with lock:
                    remaining = max(0, MAX_PROBE_OUTPUT_BYTES - total_bytes)
                    if retain and remaining:
                        stdout_bytes.extend(chunk[:remaining])
                    total_bytes += len(chunk)
                    over_limit = total_bytes > MAX_PROBE_OUTPUT_BYTES
                if over_limit:
                    exceeded.set()
                    try:
                        process.kill()
                    except OSError:
                        pass
        except (OSError, ValueError):
            reader_failed.set()
            try:
                process.kill()
            except OSError:
                pass
        finally:
            try:
                stream.close()
            except OSError:
                pass

    stdout_thread = threading.Thread(
        target=drain, args=(process.stdout, True), daemon=True
    )
    stderr_thread = threading.Thread(
        target=drain, args=(process.stderr, False), daemon=True
    )
    stdout_thread.start()
    stderr_thread.start()
    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        raise ProbeProtocolError("the external MCP probe timed out") from exc
    finally:
        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)

    if stdout_thread.is_alive() or stderr_thread.is_alive() or reader_failed.is_set():
        raise ProbeProtocolError("the external MCP probe output could not be read")
    if exceeded.is_set():
        raise ProbeProtocolError("the external MCP probe output exceeded the size limit")
    return bytes(stdout_bytes), returncode


def _mcp_checks(
    python_executable: str,
    base_url: str,
    timeout: float,
    runner: McpRunner,
    expected_context: str,
) -> tuple[list[CheckResult], str | None]:
    try:
        protocol = runner(python_executable, base_url, timeout)
    except Exception:
        return (
            [
                CheckResult(
                    "mcp." + tool,
                    "MCP: " + tool,
                    "fail",
                    "The external MCP probe did not complete.",
                    required=True,
                    details={"expected_tool": tool, "issue": "probe_process_error"},
                )
                for tool in MCP_TOOLS
            ],
            None,
        )

    if not isinstance(protocol, Mapping) or protocol.get("protocol") != MCP_PROBE_PROTOCOL:
        return _failed_mcp_protocol("invalid_protocol"), None
    raw_results = protocol.get("results")
    if not isinstance(raw_results, list):
        return _failed_mcp_protocol("missing_results"), None

    catalog_count = protocol.get("catalog_count")
    result_names = [
        item.get("requested_tool")
        for item in raw_results
        if isinstance(item, Mapping)
    ]
    catalog_valid = (
        protocol.get("catalog_valid") is True
        and isinstance(catalog_count, int)
        and not isinstance(catalog_count, bool)
        and catalog_count == len(MCP_TOOLS)
        and len(raw_results) == len(MCP_TOOLS)
        and len(result_names) == len(MCP_TOOLS)
        and all(name in MCP_TOOLS for name in result_names)
        and set(result_names) == set(MCP_TOOLS)
    )

    safe_python_version = _safe_version_value(protocol.get("python_version"))
    indexed: dict[str, Mapping[str, Any]] = {}
    duplicates: set[str] = set()
    for item in raw_results:
        if not isinstance(item, Mapping):
            continue
        requested = item.get("requested_tool")
        if requested not in MCP_TOOLS:
            continue
        if requested in indexed:
            duplicates.add(requested)
        else:
            indexed[requested] = item

    checks: list[CheckResult] = []
    for tool in MCP_TOOLS:
        check_id = "mcp." + tool
        title = "MCP: " + tool
        details: dict[str, Any] = {"expected_tool": tool}
        item = indexed.get(tool)
        if item is None:
            details["issue"] = "missing_tool_result"
            checks.append(
                CheckResult(
                    check_id,
                    title,
                    "fail",
                    "The MCP probe omitted this tool result.",
                    required=True,
                    details=details,
                )
            )
            continue
        if tool in duplicates:
            details["issue"] = "duplicate_tool_result"
            checks.append(
                CheckResult(
                    check_id,
                    title,
                    "fail",
                    "The MCP probe duplicated this tool result.",
                    required=True,
                    details=details,
                )
            )
            continue

        issues = _safe_issue_codes(item.get("issues"))
        if item.get("observed_tool") != tool:
            issues.append("tool_id_mismatch")
        if item.get("risk_class") != "read_only":
            issues.append("risk_class_not_read_only")
        response_status = item.get("status")
        if response_status not in _ALLOWED_RESPONSE_STATUSES:
            issues.append("invalid_status")
            response_status = None
        if item.get("invocation_ok") is not True:
            issues.append("invocation_failed")
        if item.get("envelope_valid") is not True:
            issues.append("invalid_envelope")
        if not catalog_valid:
            issues.append("tool_catalog_mismatch")
        issues = sorted(set(issues))

        error_code = item.get("error_code")
        if error_code not in _CONTEXT_ERROR_CODES:
            error_code = None
        if issues:
            details["issues"] = issues
            checks.append(
                CheckResult(
                    check_id,
                    title,
                    "fail",
                    "The MCP tool violated the read-only response contract.",
                    required=True,
                    details=details,
                )
            )
        else:
            details["response_status"] = response_status
            if tool == "revit_health_ping":
                extension_sha = _safe_sha_value(item.get("extension_sha"))
                server_sha = _safe_sha_value(item.get("server_sha"))
                extension_any_stale = item.get("extension_any_stale")
                if extension_sha is not None:
                    details["extension_sha"] = extension_sha
                if server_sha is not None:
                    details["server_sha"] = server_sha
                if isinstance(extension_any_stale, bool):
                    details["extension_any_stale"] = extension_any_stale
            result_status, context_issue, observed_context = _expected_response(
                tool, response_status, error_code, expected_context
            )
            details["observed_context"] = observed_context
            if context_issue is not None:
                details["issue"] = context_issue
            checks.append(
                CheckResult(
                    check_id,
                    title,
                    result_status,
                    (
                        "The MCP tool returned a valid read-only envelope "
                        "for the expected context."
                        if context_issue is None
                        else "The MCP response did not match the expected document context."
                    ),
                    required=True,
                    details=details,
                )
            )
    return checks, safe_python_version


def _failed_mcp_protocol(issue: str) -> list[CheckResult]:
    return [
        CheckResult(
            "mcp." + tool,
            "MCP: " + tool,
            "fail",
            "The MCP probe returned an invalid protocol record.",
            required=True,
            details={"expected_tool": tool, "issue": issue},
        )
        for tool in MCP_TOOLS
    ]


def _context_consistency_check(
    checks: list[CheckResult], expected_context: str
) -> CheckResult:
    """Require Routes and MCP to agree on the active document context."""
    relevant_ids = {
        prefix + tool
        for prefix in ("routes.", "mcp.")
        for tool in PROJECT_TOOLS
    }
    observations = [
        check.details.get("observed_context")
        for check in checks
        if check.check_id in relevant_ids
        and check.details.get("observed_context") in ("none", "family", "project")
    ]
    details: dict[str, Any] = {
        "expected_context": expected_context,
        "expected_observations": len(relevant_ids),
        "valid_observations": len(observations),
    }
    if len(observations) != len(relevant_ids):
        details["issue"] = "context_evidence_incomplete"
        return CheckResult(
            "context.consistency",
            "Document context consistency",
            "skip",
            "Document context consistency could not be established.",
            required=True,
            details=details,
        )

    distinct = sorted(set(observations))
    if len(distinct) != 1:
        details["issue"] = "mixed_document_contexts"
        return CheckResult(
            "context.consistency",
            "Document context consistency",
            "fail",
            "Routes and MCP reported inconsistent document contexts.",
            required=True,
            details=details,
        )

    observed_context = distinct[0]
    details["observed_context"] = observed_context
    if expected_context != "any" and observed_context != expected_context:
        details["issue"] = "document_context_mismatch"
        return CheckResult(
            "context.consistency",
            "Document context consistency",
            "fail",
            "The observed document context did not match the expected context.",
            required=True,
            details=details,
        )
    return CheckResult(
        "context.consistency",
        "Document context consistency",
        "pass",
        "Routes and MCP agreed on the active document context.",
        required=True,
        details=details,
    )


def _provenance_check(
    checks: list[CheckResult], expected_sha: str | None, checkout_dirty: bool | None
) -> CheckResult:
    """Require loaded extension/server code to match one clean checkout."""
    route_health = next(
        (check for check in checks if check.check_id == "routes.revit_health_ping"),
        None,
    )
    mcp_health = next(
        (check for check in checks if check.check_id == "mcp.revit_health_ping"),
        None,
    )
    observations = {
        "routes_extension": (
            _safe_sha_value(route_health.details.get("extension_sha"))
            if route_health is not None
            else None
        ),
        "mcp_extension": (
            _safe_sha_value(mcp_health.details.get("extension_sha"))
            if mcp_health is not None
            else None
        ),
        "mcp_server": (
            _safe_sha_value(mcp_health.details.get("server_sha"))
            if mcp_health is not None
            else None
        ),
    }
    stale = (
        route_health.details.get("extension_any_stale")
        if route_health is not None
        else None
    )
    mcp_stale = (
        mcp_health.details.get("extension_any_stale")
        if mcp_health is not None
        else None
    )
    stale_values = [value for value in (stale, mcp_stale) if isinstance(value, bool)]

    details: dict[str, Any] = {
        "checkout_sha": expected_sha or "unknown",
        "checkout_dirty": checkout_dirty if isinstance(checkout_dirty, bool) else "unknown",
        "routes_extension_sha": observations["routes_extension"] or "unknown",
        "mcp_extension_sha": observations["mcp_extension"] or "unknown",
        "mcp_server_sha": observations["mcp_server"] or "unknown",
    }
    failures: list[str] = []
    incomplete: list[str] = []
    if expected_sha is None:
        incomplete.append("checkout_sha_unknown")
    if checkout_dirty is None:
        incomplete.append("checkout_dirty_unknown")
    elif checkout_dirty:
        incomplete.append("checkout_dirty")

    for name, observed_sha in observations.items():
        if observed_sha is None:
            incomplete.append(name + "_sha_unknown")
        elif expected_sha is not None and observed_sha != expected_sha:
            failures.append(name + "_sha_mismatch")
    known_component_shas = {
        observed_sha for observed_sha in observations.values() if observed_sha is not None
    }
    if len(known_component_shas) > 1:
        failures.append("component_sha_disagreement")
    if len(stale_values) != 2:
        incomplete.append("extension_staleness_unknown")
    if any(stale_values):
        failures.append("extension_modules_stale")

    if failures:
        details["issues"] = sorted(set(failures + incomplete))
        return CheckResult(
            "provenance.build_identity",
            "Build identity",
            "fail",
            "Loaded extension or MCP code does not match the verifier checkout.",
            required=True,
            details=details,
        )
    if incomplete:
        details["issues"] = sorted(set(incomplete))
        return CheckResult(
            "provenance.build_identity",
            "Build identity",
            "warn",
            "Build provenance is dirty or incomplete.",
            required=True,
            details=details,
        )
    return CheckResult(
        "provenance.build_identity",
        "Build identity",
        "pass",
        "Extension, MCP server, and verifier use the same clean checkout.",
        required=True,
        details=details,
    )


def _safe_issue_codes(value: Any) -> list[str]:
    if not isinstance(value, list):
        return ["invalid_issue_codes"]
    safe: list[str] = []
    for item in value:
        if isinstance(item, str) and _SAFE_MANUAL_ID.fullmatch(item):
            safe.append(item)
        else:
            safe.append("invalid_issue_code")
    return safe


def _manual_checks(path: str | os.PathLike[str] | None) -> list[CheckResult]:
    if path is None:
        return [
            CheckResult(
                "manual.checks",
                "Manual verification checks",
                "skip",
                "No manual verification checklist was supplied.",
                required=False,
            )
        ]

    try:
        raw = Path(path).read_bytes()
        if len(raw) > MAX_MANUAL_BYTES:
            raise ValueError("manual checklist is too large")
        decoded = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return [_manual_input_failure()]

    items = decoded.get("checks") if isinstance(decoded, dict) else decoded
    if not isinstance(items, list):
        return [_manual_input_failure()]

    checks: list[CheckResult] = []
    seen: set[str] = set()
    status_map = {
        "pass": ("pass", "The manual verification check passed."),
        "fail": ("fail", "The manual verification check failed."),
        "warn": ("warn", "The manual verification check needs attention."),
        "skip": ("skip", "The manual verification check was skipped."),
        "pending": ("warn", "The manual verification check is pending."),
        "not_run": ("skip", "The manual verification check was not run."),
    }
    for item in items:
        if not isinstance(item, dict):
            return [_manual_input_failure()]
        manual_id = item.get("id")
        manual_status = item.get("status")
        required = item.get("required", True)
        if (
            not isinstance(manual_id, str)
            or not _SAFE_MANUAL_ID.fullmatch(manual_id)
            or manual_id in seen
            or manual_status not in status_map
            or not isinstance(required, bool)
        ):
            return [_manual_input_failure()]
        seen.add(manual_id)
        status, summary = status_map[manual_status]
        checks.append(
            CheckResult(
                "manual." + manual_id,
                "Manual: " + manual_id,
                status,
                summary,
                required=required,
                details={"source": "manual"},
            )
        )
    if not checks:
        return [_manual_input_failure()]
    return sorted(checks, key=lambda check: check.check_id)


def _manual_input_failure() -> CheckResult:
    return CheckResult(
        "manual.input",
        "Manual verification input",
        "fail",
        "The manual verification checklist was invalid or unreadable.",
        required=True,
        details={"issue": "invalid_manual_input"},
    )


def _safe_version_value(value: Any) -> str | None:
    if isinstance(value, str) and _SAFE_VERSION.fullmatch(value):
        return value
    return None


def _safe_sha_value(value: Any) -> str | None:
    if isinstance(value, str) and _SAFE_SHA.fullmatch(value):
        return value.lower()
    return None


def _git_provenance() -> tuple[str | None, bool | None]:
    repo_root = Path(__file__).resolve().parents[1]
    try:
        sha_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None, None
    candidate = sha_result.stdout.strip()
    sha = (
        candidate.lower()
        if sha_result.returncode == 0 and _SAFE_SHA.fullmatch(candidate)
        else None
    )
    dirty = bool(status_result.stdout.strip()) if status_result.returncode == 0 else None
    return sha, dirty


def _generated_at(timestamp: datetime | str | None) -> str:
    if timestamp is None:
        value = datetime.now(timezone.utc)
    elif isinstance(timestamp, datetime):
        value = timestamp
    elif isinstance(timestamp, str):
        try:
            value = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("timestamp must be ISO 8601") from exc
    else:
        raise TypeError("timestamp must be a datetime, ISO 8601 string, or None")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc).replace(microsecond=0)
    return value.isoformat().replace("+00:00", "Z")


def run_verification(
    base_url: str,
    python_executable: str,
    *,
    manual_checks_path: str | os.PathLike[str] | None = None,
    timeout: float = 2.0,
    timestamp: datetime | str | None = None,
    mcp_runner: McpRunner | None = None,
    expected_context: str = "any",
    expected_git_sha: str | None | object = _AUTO_PROVENANCE,
    expected_git_dirty: bool | None | object = _AUTO_PROVENANCE,
) -> dict[str, Any]:
    """Run Routes, MCP, and optional manual checks and return a redacted report."""
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
        or timeout > 120
    ):
        raise ValueError("timeout must be greater than zero and at most 120 seconds")
    if expected_context not in _ALLOWED_CONTEXTS:
        raise ValueError("expected_context must be any, none, family, or project")

    discovered_sha: str | None = None
    discovered_dirty: bool | None = None
    if (
        expected_git_sha is _AUTO_PROVENANCE
        or expected_git_dirty is _AUTO_PROVENANCE
    ):
        discovered_sha, discovered_dirty = _git_provenance()
    checkout_sha = (
        discovered_sha
        if expected_git_sha is _AUTO_PROVENANCE
        else _safe_sha_value(expected_git_sha)
    )
    if expected_git_dirty is _AUTO_PROVENANCE:
        checkout_dirty = discovered_dirty
    elif expected_git_dirty is None or isinstance(expected_git_dirty, bool):
        checkout_dirty = expected_git_dirty
    else:
        raise ValueError("expected_git_dirty must be true, false, or None")

    checks: list[CheckResult] = []
    external_python_version: str | None = None
    try:
        safe_base_url = validate_loopback_url(base_url)
    except ValueError:
        checks.append(
            CheckResult(
                "security.loopback_url",
                "Loopback Routes URL",
                "fail",
                "The Routes base URL is not an allowed loopback URL.",
                required=True,
                details={"issue": "non_loopback_or_invalid_url"},
            )
        )
        checks.extend(
            CheckResult(
                "routes." + route.tool,
                "Routes: " + route.tool,
                "skip",
                "The endpoint was not contacted because the base URL was refused.",
                required=True,
                details={"endpoint": route.path, "expected_tool": route.tool},
            )
            for route in ROUTES
        )
        checks.append(
            CheckResult(
                "routes.host_status",
                "Routes host status",
                "skip",
                "The host-status endpoint was not contacted because the base URL was refused.",
                required=True,
                details={"endpoint": "/routes/status"},
            )
        )
        checks.extend(
            CheckResult(
                "mcp." + tool,
                "MCP: " + tool,
                "skip",
                "The MCP tool was not invoked because the base URL was refused.",
                required=True,
                details={"expected_tool": tool},
            )
            for tool in MCP_TOOLS
        )
    else:
        checks.append(
            CheckResult(
                "security.loopback_url",
                "Loopback Routes URL",
                "pass",
                "The Routes base URL is restricted to loopback.",
                required=True,
            )
        )
        opener = build_opener(ProxyHandler({}), _NoRedirect())
        checks.append(_host_status_check(safe_base_url, timeout, opener))
        checks.extend(
            _route_check(
                safe_base_url, route, timeout, opener, expected_context
            )
            for route in ROUTES
        )
        mcp_checks, external_python_version = _mcp_checks(
            python_executable,
            safe_base_url,
            timeout,
            mcp_runner or _run_mcp_probe,
            expected_context,
        )
        checks.extend(mcp_checks)

    checks.append(_context_consistency_check(checks, expected_context))
    checks.append(_provenance_check(checks, checkout_sha, checkout_dirty))
    checks.extend(_manual_checks(manual_checks_path))
    checks.sort(key=lambda check: check.check_id)

    metadata: dict[str, Any] = {
        "expected_context": expected_context,
        "git_sha": checkout_sha or "unknown",
        "git_dirty": checkout_dirty if checkout_dirty is not None else "unknown",
        "os": _safe_version_value(platform.system()) or "unknown",
        "os_version": _safe_version_value(platform.release()) or "unknown",
        "python_version": _safe_version_value(platform.python_version()) or "unknown",
    }
    if external_python_version is not None:
        metadata["mcp_python_version"] = external_python_version
    host_status = next(
        (check for check in checks if check.check_id == "routes.host_status"), None
    )
    if host_status is not None and host_status.status == "pass":
        host_application = host_status.details.get("host_application")
        session_fingerprint = host_status.details.get("session_fingerprint")
        if isinstance(host_application, str):
            metadata["revit_host_application"] = host_application
        if isinstance(session_fingerprint, str):
            metadata["revit_session_fingerprint"] = session_fingerprint
    routes_health = next(
        (check for check in checks if check.check_id == "routes.revit_health_ping"),
        None,
    )
    if routes_health is not None and routes_health.status == "pass":
        for key in ("revit_version", "revit_build", "pyrevit_version"):
            value = routes_health.details.get(key)
            if isinstance(value, str):
                metadata[key] = value

    report: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "generated_at": _generated_at(timestamp),
        "metadata": metadata,
        "checks": [check.as_dict() for check in checks],
        "summary": summarize(checks),
    }
    report["exit_code"] = report_exit_code(report)
    return report


def write_evidence(
    report: Mapping[str, Any],
    output_dir: str | os.PathLike[str],
) -> dict[str, Path]:
    """Write stable redacted JSON and Markdown evidence files."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "live-verification.json"
    markdown_path = destination / "live-verification.md"

    json_text = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    json_path.write_text(json_text, encoding="utf-8", newline="\n")
    markdown_path.write_text(
        _render_markdown(report), encoding="utf-8", newline="\n"
    )
    return {"json": json_path, "markdown": markdown_path}


def verify_and_write(
    base_url: str,
    python_executable: str,
    output_dir: str | os.PathLike[str],
    **kwargs: Any,
) -> tuple[dict[str, Any], dict[str, Path], int]:
    """Run verification, write evidence, and return the results-layer exit code."""
    report = run_verification(base_url, python_executable, **kwargs)
    paths = write_evidence(report, output_dir)
    return report, paths, report_exit_code(report)


def _render_markdown(report: Mapping[str, Any]) -> str:
    metadata = report.get("metadata", {})
    summary = report.get("summary", {})
    counts = summary.get("counts", {})
    lines = [
        "# Live verification evidence",
        "",
        "This evidence contains contract outcomes only. Project and user data are not retained.",
        "",
        "## Run metadata",
        "",
        "- Generated (UTC): `{}`".format(_markdown_cell(report.get("generated_at"))),
        "- Git SHA: `{}`".format(_markdown_cell(metadata.get("git_sha"))),
        "- Git dirty: `{}`".format(_markdown_cell(metadata.get("git_dirty"))),
        "- OS: `{}`".format(_markdown_cell(metadata.get("os"))),
        "- OS version: `{}`".format(_markdown_cell(metadata.get("os_version"))),
        "- Verifier Python: `{}`".format(
            _markdown_cell(metadata.get("python_version"))
        ),
        "- Expected Revit context: `{}`".format(
            _markdown_cell(metadata.get("expected_context"))
        ),
    ]
    if metadata.get("mcp_python_version"):
        lines.append(
            "- MCP Python: `{}`".format(
                _markdown_cell(metadata.get("mcp_python_version"))
            )
        )
    if metadata.get("revit_host_application"):
        lines.append(
            "- Revit host application: `{}`".format(
                _markdown_cell(metadata.get("revit_host_application"))
            )
        )
    for label, key in (
        ("Revit version", "revit_version"),
        ("Revit build", "revit_build"),
        ("pyRevit version", "pyrevit_version"),
    ):
        if metadata.get(key):
            lines.append(
                "- {}: `{}`".format(label, _markdown_cell(metadata.get(key)))
            )
    if metadata.get("revit_session_fingerprint"):
        lines.append(
            "- Revit session fingerprint: `{}`".format(
                _markdown_cell(metadata.get("revit_session_fingerprint"))
            )
        )
    lines.extend(
        [
            "",
            "## Summary",
            "",
            "- Outcome: `{}`".format(_markdown_cell(summary.get("outcome"))),
            "- Pass: {}".format(int(counts.get("pass", 0))),
            "- Warn: {}".format(int(counts.get("warn", 0))),
            "- Fail: {}".format(int(counts.get("fail", 0))),
            "- Skip: {}".format(int(counts.get("skip", 0))),
            "- Exit code: {}".format(int(report.get("exit_code", 1))),
            "",
            "## Checks",
            "",
            "| Check | Required | Status | Summary |",
            "| --- | --- | --- | --- |",
        ]
    )
    checks = report.get("checks", [])
    if isinstance(checks, list):
        for check in checks:
            if not isinstance(check, Mapping):
                continue
            lines.append(
                "| `{}` | {} | `{}` | {} |".format(
                    _markdown_cell(check.get("check_id")),
                    "yes" if check.get("required") else "no",
                    _markdown_cell(check.get("status")),
                    _markdown_cell(check.get("summary")),
                )
            )
    return "\n".join(lines) + "\n"


def _markdown_cell(value: Any) -> str:
    # Report strings are generated or allow-listed, but still escape Markdown
    # metacharacters so evidence rendering stays deterministic.
    return str(value if value is not None else "unknown").replace("|", "\\|").replace(
        "\n", " "
    )
