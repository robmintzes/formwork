"""Redacted contract validation for Revit Routes and MCP responses.

The validator inspects domain payloads but returns only allow-listed contract
metadata, issue codes, and build SHAs. Project names, paths, users, element
names, and other model values are never retained by an assessment.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Callable


ALLOWED_STATUSES = frozenset(("ok", "warning", "error"))
CONTEXT_ERROR_CODES = frozenset(
    ("no_document", "family_document_not_supported")
)
_SAFE_SHA = re.compile(r"^[0-9a-fA-F]{7,40}$")
_SAFE_BUILD_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._+()-]{0,79}$")


@dataclass(frozen=True)
class ContractAssessment:
    """Safe, redacted result of inspecting one response envelope."""

    status: str | None
    error_code: str | None
    issues: tuple[str, ...]
    extension_sha: str | None = None
    extension_any_stale: bool | None = None
    server_sha: str | None = None
    revit_version: str | None = None
    revit_build: str | None = None
    pyrevit_version: str | None = None


def assess_envelope(payload: Any, expected_tool: str) -> ContractAssessment:
    """Validate one known tool envelope without returning domain values."""
    if not isinstance(payload, dict):
        return ContractAssessment(None, None, ("envelope_not_object",))

    issues: list[str] = []
    status = payload.get("status")
    safe_status = status if status in ALLOWED_STATUSES else None
    if safe_status is None:
        issues.append("invalid_status")
    if payload.get("tool") != expected_tool:
        issues.append("tool_id_mismatch")
    if payload.get("risk_class") != "read_only":
        issues.append("risk_class_not_read_only")

    _validate_document(payload.get("document"), issues)
    if not _is_string_list(payload.get("messages")):
        issues.append("invalid_messages")
    if not _is_string_list(payload.get("next_actions")):
        issues.append("invalid_next_actions")

    data = payload.get("data")
    if not isinstance(data, dict):
        issues.append("invalid_data_object")

    error_code = _validate_error(payload.get("error"), safe_status, issues)
    if safe_status == "error":
        if isinstance(data, dict) and data:
            issues.append("error_data_not_empty")
    elif safe_status is not None:
        if payload.get("error") is not None:
            issues.append("success_has_error")
        if isinstance(data, dict):
            validator = _DATA_VALIDATORS.get(expected_tool)
            if validator is None:
                issues.append("unknown_tool_contract")
            else:
                validator(data, issues)

    extension_sha: str | None = None
    extension_any_stale: bool | None = None
    server_sha: str | None = None
    revit_version: str | None = None
    revit_build: str | None = None
    pyrevit_version: str | None = None
    if expected_tool == "revit_health_ping":
        extension_sha, extension_any_stale = _extension_identity(data)
        server_sha = _server_identity(payload)
        if isinstance(data, dict):
            revit_version = _safe_build_value(data.get("revit_version"))
            revit_build = _safe_build_value(data.get("revit_build"))
            pyrevit_version = _safe_build_value(data.get("pyrevit_version"))

    return ContractAssessment(
        safe_status,
        error_code,
        tuple(sorted(set(issues))),
        extension_sha,
        extension_any_stale,
        server_sha,
        revit_version,
        revit_build,
        pyrevit_version,
    )


def _validate_document(value: Any, issues: list[str]) -> None:
    if not isinstance(value, dict):
        issues.append("invalid_document_context")
        return
    if "title" not in value or not _is_nullable_string(value.get("title")):
        issues.append("invalid_document_title")
    if "path" not in value or not _is_nullable_string(value.get("path")):
        issues.append("invalid_document_path")
    if not isinstance(value.get("is_workshared"), bool):
        issues.append("invalid_worksharing_flag")


def _validate_error(
    value: Any, status: str | None, issues: list[str]
) -> str | None:
    if value is None:
        if status == "error":
            issues.append("missing_error_object")
        return None
    if not isinstance(value, dict):
        issues.append("invalid_error_object")
        return None

    code = value.get("code")
    if not isinstance(code, str) or not code:
        issues.append("invalid_error_code")
        safe_code = None
    else:
        safe_code = code if code in CONTEXT_ERROR_CODES else None
    if not isinstance(value.get("message"), str):
        issues.append("invalid_error_message")
    if not _is_string_list(value.get("checks")):
        issues.append("invalid_error_checks")
    return safe_code


def _validate_health(data: dict[str, Any], issues: list[str]) -> None:
    for key in ("revit_version", "revit_build", "pyrevit_version"):
        if _safe_build_value(data.get(key)) is None:
            issues.append("invalid_health_" + key)
    if not isinstance(data.get("document_open"), bool):
        issues.append("invalid_health_document_open")
    if not isinstance(data.get("extension_identity"), dict):
        issues.append("invalid_health_extension_identity")


def _validate_info(data: dict[str, Any], issues: list[str]) -> None:
    for key in (
        "title",
        "path",
        "project_number",
        "project_name",
        "client_name",
        "project_address",
        "project_status",
        "issue_date",
    ):
        if key not in data or not _is_nullable_string(data.get(key)):
            issues.append("invalid_project_info_" + key)
    if not isinstance(data.get("is_workshared"), bool):
        issues.append("invalid_project_info_is_workshared")


def _validate_levels(data: dict[str, Any], issues: list[str]) -> None:
    levels = data.get("levels")
    _validate_counted_list(data.get("count"), levels, "levels", issues)
    if not isinstance(levels, list):
        return
    for item in levels:
        if not isinstance(item, dict):
            issues.append("invalid_level_item")
            continue
        if not isinstance(item.get("name"), str):
            issues.append("invalid_level_name")
        if not _is_finite_number(item.get("elevation_feet")):
            issues.append("invalid_level_elevation")
        if not _is_integer(item.get("id")):
            issues.append("invalid_level_id")


def _validate_worksets(data: dict[str, Any], issues: list[str]) -> None:
    workshared = data.get("workshared")
    worksets = data.get("worksets")
    if not isinstance(workshared, bool):
        issues.append("invalid_worksets_workshared")
    if not isinstance(worksets, list):
        issues.append("invalid_worksets_list")
        return

    count = data.get("count")
    if workshared is True or count is not None:
        _validate_counted_list(count, worksets, "worksets", issues)
    if workshared is False and worksets:
        issues.append("non_workshared_has_worksets")
    for item in worksets:
        if not isinstance(item, dict):
            issues.append("invalid_workset_item")
            continue
        if not isinstance(item.get("name"), str):
            issues.append("invalid_workset_name")
        if not _is_integer(item.get("id")):
            issues.append("invalid_workset_id")
        if not isinstance(item.get("is_open"), bool):
            issues.append("invalid_workset_is_open")
        if "owner" not in item or not _is_nullable_string(item.get("owner")):
            issues.append("invalid_workset_owner")


def _validate_links(data: dict[str, Any], issues: list[str]) -> None:
    links = data.get("links")
    _validate_counted_list(data.get("count"), links, "links", issues)
    if not isinstance(links, list):
        return
    for item in links:
        if not isinstance(item, dict):
            issues.append("invalid_link_item")
            continue
        if not isinstance(item.get("name"), str):
            issues.append("invalid_link_name")
        if not _is_integer(item.get("id")):
            issues.append("invalid_link_id")
        if item.get("type") not in ("revit", "cad"):
            issues.append("invalid_link_type")
        if not isinstance(item.get("loaded"), bool):
            issues.append("invalid_link_loaded")
        if not isinstance(item.get("load_state"), str):
            issues.append("invalid_link_load_state")
        if "path" not in item or not _is_nullable_string(item.get("path")):
            issues.append("invalid_link_path")
        if "is_overlay" not in item or (
            item.get("is_overlay") is not None
            and not isinstance(item.get("is_overlay"), bool)
        ):
            issues.append("invalid_link_is_overlay")


def _validate_counted_list(
    count: Any, value: Any, name: str, issues: list[str]
) -> None:
    if not _is_integer(count) or count < 0:
        issues.append("invalid_" + name + "_count")
    if not isinstance(value, list):
        issues.append("invalid_" + name + "_list")
    elif _is_integer(count) and count != len(value):
        issues.append(name + "_count_mismatch")


def _extension_identity(data: Any) -> tuple[str | None, bool | None]:
    if not isinstance(data, dict):
        return None, None
    identity = data.get("extension_identity")
    if not isinstance(identity, dict):
        return None, None
    if identity.get("component") != "pyrevit-extension":
        return None, None
    sha = _safe_sha(identity.get("sha")) or _safe_sha(identity.get("short_sha"))
    stale = identity.get("any_stale")
    return sha, stale if isinstance(stale, bool) else None


def _server_identity(payload: dict[str, Any]) -> str | None:
    build_identity = payload.get("build_identity")
    if not isinstance(build_identity, dict):
        return None
    server = build_identity.get("server")
    if not isinstance(server, dict):
        return None
    return _safe_sha(server.get("sha")) or _safe_sha(server.get("short_sha"))


def _safe_sha(value: Any) -> str | None:
    if isinstance(value, str) and _SAFE_SHA.fullmatch(value):
        return value.lower()
    return None


def _safe_build_value(value: Any) -> str | None:
    if isinstance(value, str) and _SAFE_BUILD_VALUE.fullmatch(value):
        return value
    return None


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _is_nullable_string(value: Any) -> bool:
    return value is None or isinstance(value, str)


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


_DATA_VALIDATORS: dict[str, Callable[[dict[str, Any], list[str]], None]] = {
    "revit_health_ping": _validate_health,
    "revit_project_info": _validate_info,
    "revit_project_levels": _validate_levels,
    "revit_project_worksets": _validate_worksets,
    "revit_project_links": _validate_links,
}
