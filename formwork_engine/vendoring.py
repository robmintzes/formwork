"""Shared helpers for adapters that vendor foundation files with asserted edits.

A vendored file is read from the foundation checkout and changed only by exact
substitutions. A substitution that does not match the expected number of times
raises ``VendoringError``, so a foundation file that changes shape fails
generation loudly instead of rendering a half-rebranded workspace.
"""

from __future__ import annotations

from pathlib import Path


class VendoringError(RuntimeError):
    """A vendored foundation file no longer matches the substitutions expected here."""


def substitute(path: str, text: str, old: str, new: str, *, required: bool = True, count: int = 1) -> str:
    """Replace ``old`` with ``new``, asserting it occurs exactly ``count`` times.

    ``required=False`` additionally tolerates zero occurrences (never a different
    non-zero count).
    """
    found = text.count(old)
    if found == 0 and not required:
        return text
    if found != count:
        raise VendoringError(
            "{}: expected exactly {} of {!r}, found {}; update the vendoring adapter".format(
                path, "one" if count == 1 else count, old, found
            )
        )
    return text.replace(old, new)


def read_foundation_text(root: Path, rel: str) -> str:
    """Read a foundation file as UTF-8 with LF line endings."""
    return (root / rel).read_text(encoding="utf-8").replace("\r\n", "\n")
