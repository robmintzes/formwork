"""Shared, machine-readable result contracts for toolkit diagnostics."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


VALID_STATUSES = ("pass", "warn", "fail", "skip")


@dataclass(frozen=True)
class CheckResult:
    """One diagnostic or verification check."""

    check_id: str
    title: str
    status: str
    summary: str
    required: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(
                "status must be one of {}; got {!r}".format(
                    ", ".join(VALID_STATUSES), self.status
                )
            )
        if not self.check_id:
            raise ValueError("check_id must not be empty")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def summarize(checks: Iterable[CheckResult | dict[str, Any]]) -> dict[str, Any]:
    """Summarize statuses and compute the report outcome."""
    counts = {status: 0 for status in VALID_STATUSES}
    blocking_failures = 0
    incomplete_required = 0

    for check in checks:
        if isinstance(check, CheckResult):
            status = check.status
            required = check.required
        else:
            status = str(check["status"])
            required = bool(check.get("required", False))
        if status not in counts:
            raise ValueError("unknown check status: {!r}".format(status))
        counts[status] += 1
        if status == "fail":
            blocking_failures += 1
        elif required and status in ("warn", "skip"):
            incomplete_required += 1

    if blocking_failures:
        outcome = "fail"
    elif incomplete_required:
        outcome = "incomplete"
    else:
        outcome = "pass"

    return {
        "outcome": outcome,
        "counts": counts,
        "blocking_failures": blocking_failures,
        "incomplete_required": incomplete_required,
    }


def report_exit_code(report: dict[str, Any]) -> int:
    """Return 0 for pass, 1 for failure, and 2 for incomplete evidence."""
    outcome = report.get("summary", {}).get("outcome")
    if outcome == "pass":
        return 0
    if outcome == "incomplete":
        return 2
    return 1
