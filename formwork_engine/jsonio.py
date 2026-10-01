"""Strict JSON reading and canonical JSON writing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonInputError(ValueError):
    """Raised when a JSON input cannot be parsed under the strict rules."""


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise JsonInputError("duplicate key {!r}".format(key))
        result[key] = value
    return result


def _reject_constant(name: str) -> Any:
    raise JsonInputError("non-standard JSON constant {}".format(name))


def loads_strict(text: str) -> Any:
    """Parse JSON rejecting duplicate keys and NaN/Infinity."""
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise JsonInputError(
            "invalid JSON at line {} column {}: {}".format(exc.lineno, exc.colno, exc.msg)
        ) from exc


def load_strict(path: Path) -> Any:
    """Read a UTF-8 (optionally BOM-prefixed) JSON file strictly."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise JsonInputError("file is not valid UTF-8: {}".format(exc)) from exc
    return loads_strict(text)


def dumps_canonical(value: Any) -> str:
    """Deterministic JSON: sorted keys, two-space indent, LF, trailing newline."""
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
