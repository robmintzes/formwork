"""Output path rules and workspace-root safety (FOUNDATION_SPEC section 4.5)."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import re
import stat

# Device names Windows reserves regardless of extension, including the
# superscript-digit COM/LPT forms and the console/clock devices.
WINDOWS_RESERVED_NAMES = frozenset(
    ["CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", "CLOCK$"]
    + ["COM{}".format(i) for i in list(range(1, 10)) + ["¹", "²", "³"]]
    + ["LPT{}".format(i) for i in list(range(1, 10)) + ["¹", "²", "³"]]
)


def is_reserved_name(part: str) -> bool:
    """True if Windows treats *part* as a device (``CON``, ``con.txt``, ``CON .json``)."""
    return part.split(".", 1)[0].rstrip(" ").upper() in WINDOWS_RESERVED_NAMES
INVALID_CHARS = re.compile(r'[<>:"|?*\x00-\x1f\\]')
MAX_RELATIVE_LENGTH = 200
FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class UnsafePathError(ValueError):
    """A path or destination violates the output safety rules."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def check_relative_path(value: str) -> str:
    """Return a problem description, or an empty string when *value* is safe.

    Safe means: relative, forward slashes, no empty/``.``/``..`` components,
    no drive or reserved device names, no trailing dot/space, no characters
    Windows rejects, and a bounded length.
    """
    if not value:
        return "is empty"
    if len(value) > MAX_RELATIVE_LENGTH:
        return "is longer than {} characters".format(MAX_RELATIVE_LENGTH)
    if "\\" in value:
        return "must use forward slashes"
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        return "must be relative"
    for part in value.split("/"):
        if part in ("", ".", ".."):
            return "must not contain empty, '.', or '..' components"
        if INVALID_CHARS.search(part):
            return "contains a character Windows does not allow in file names"
        if part.endswith((".", " ")) or part.startswith(" "):
            return "has a component that starts with a space or ends with a dot or space"
        if is_reserved_name(part):
            return "uses the Windows reserved name {!r}".format(part)
    return ""


def is_reparse_point(path: Path) -> bool:
    """True for symlinks, junctions, and other reparse points (does not follow)."""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & FILE_ATTRIBUTE_REPARSE_POINT)


def guard_target(root: Path, relative: str) -> Path:
    """Return the absolute target for *relative* after checking every component.

    Raises UnsafePathError if the relative path is unsafe or any existing
    component between *root* and the target is a reparse point.
    """
    problem = check_relative_path(relative)
    if problem:
        raise UnsafePathError("path.invalid", "Output path {!r} {}.".format(relative, problem))
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if is_reparse_point(current):
            raise UnsafePathError(
                "path.reparse-point",
                "Refusing to write through link or junction at {!r}.".format(
                    current.relative_to(root).as_posix()
                ),
            )
        if not current.exists():
            break
    return root.joinpath(*PurePosixPath(relative).parts)


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def check_workspace_root(workspace: Path, foundation_root: Path, *, home: Path | None = None) -> Path:
    """Resolve and vet a workspace destination. Returns the resolved path."""
    if is_reparse_point(workspace):
        raise UnsafePathError("workspace.reparse-point", "The workspace path itself is a link or junction.")
    resolved = workspace.resolve()
    foundation = foundation_root.resolve()
    home_dir = (home or Path.home()).resolve()
    if resolved == Path(resolved.anchor):
        raise UnsafePathError("workspace.unsafe", "A drive or filesystem root cannot be a workspace.")
    if resolved == home_dir:
        raise UnsafePathError("workspace.unsafe", "The user's home directory cannot be a workspace.")
    for variable in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
        system_dir = os.environ.get(variable)
        if os.name == "nt" and system_dir and _is_within(resolved, Path(system_dir).resolve()):
            raise UnsafePathError(
                "workspace.unsafe",
                "A workspace cannot live inside a system folder ({}).".format(variable),
            )
    if _is_within(resolved, foundation):
        raise UnsafePathError(
            "workspace.overlaps-foundation",
            "The workspace must be outside the foundation checkout.",
        )
    if _is_within(foundation, resolved):
        raise UnsafePathError(
            "workspace.overlaps-foundation",
            "The workspace must not contain the foundation checkout.",
        )
    if resolved.exists() and not resolved.is_dir():
        raise UnsafePathError("workspace.not-directory", "The workspace path exists and is not a directory.")
    return resolved


def find_case_collisions(paths: list[str]) -> list[tuple[str, str]]:
    """Pairs of output paths that collide on case-insensitive filesystems."""
    seen: dict[str, str] = {}
    collisions: list[tuple[str, str]] = []
    for path in sorted(paths):
        key = path.casefold()
        if key in seen and seen[key] != path:
            collisions.append((seen[key], path))
        else:
            seen[key] = path
    return collisions
