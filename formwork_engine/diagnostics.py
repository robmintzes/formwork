"""Coded, location-aware diagnostics shared by every engine stage."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import difflib
from typing import Any, Iterable

SEVERITIES = ("error", "warning", "info")


@dataclass(frozen=True)
class Diagnostic:
    """One finding. ``location`` is a file plus JSON pointer or a relative path."""

    code: str
    severity: str
    location: str
    message: str
    hint: str = ""

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError("invalid severity {!r}".format(self.severity))
        if not self.code:
            raise ValueError("diagnostic code must not be empty")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class Diagnostics:
    """Ordered collector with convenience constructors."""

    def __init__(self) -> None:
        self.items: list[Diagnostic] = []

    def error(self, code: str, location: str, message: str, hint: str = "") -> None:
        self.items.append(Diagnostic(code, "error", location, message, hint))

    def warning(self, code: str, location: str, message: str, hint: str = "") -> None:
        self.items.append(Diagnostic(code, "warning", location, message, hint))

    def info(self, code: str, location: str, message: str, hint: str = "") -> None:
        self.items.append(Diagnostic(code, "info", location, message, hint))

    def extend(self, other: Iterable[Diagnostic]) -> None:
        self.items.extend(other)

    @property
    def has_errors(self) -> bool:
        return any(item.severity == "error" for item in self.items)

    def codes(self) -> list[str]:
        return [item.code for item in self.items]

    def as_list(self) -> list[dict[str, Any]]:
        return [item.as_dict() for item in self.items]


def did_you_mean(value: str, options: Iterable[str]) -> str:
    """Return a hint naming the closest option, or an empty string."""
    matches = difflib.get_close_matches(value, list(options), n=1, cutoff=0.6)
    return "Did you mean '{}'?".format(matches[0]) if matches else ""
