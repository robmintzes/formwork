"""Convergent application of a conflict-free plan (FOUNDATION_SPEC section 4.4)."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import tempfile
from typing import Callable

from toolkit_engine.outputs import OutputFile, content_hash
from toolkit_engine.paths import guard_target
from toolkit_engine.planner import MANIFEST_PATH, WRITE_ACTIONS, Plan

Writer = Callable[[Path, bytes], None]


def atomic_write(target: Path, content: bytes) -> None:
    """Write via a temporary sibling and os.replace; never leaves a partial file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=".toolkit-", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, target)
    except BaseException:
        try:
            os.remove(temp_name)
        except OSError:
            pass
        raise


def apply_plan(
    root: Path,
    plan: Plan,
    desired: list[OutputFile],
    manifest_text: str,
    *,
    write: Writer = atomic_write,
) -> list[str]:
    """Apply *plan*. Returns directories emptied by deletions (left in place).

    Precondition: the plan has no conflicts. Writes happen first, deletions
    second, and the manifest last, so an interrupted run converges on retry.
    """
    if plan.conflicts:
        raise ValueError("refusing to apply a plan with conflicts")
    by_path = {item.path: item for item in desired}

    for action in plan.actions:
        if action.action in WRITE_ACTIONS:
            item = by_path[action.path]
            write(guard_target(root, action.path), item.content)

    emptied: list[str] = []
    for action in plan.actions:
        if action.action != "delete":
            continue
        target = guard_target(root, action.path)
        expected = plan.retired_hashes[action.path]
        current = target.read_bytes()
        if expected not in (content_hash(current, True), content_hash(current, False)):
            raise RuntimeError("{} changed during apply; not deleted".format(action.path))
        target.unlink()
        parent = PurePosixPath(action.path).parent
        while str(parent) not in ("", "."):
            directory = root.joinpath(*parent.parts)
            if directory.is_dir() and not any(directory.iterdir()):
                emptied.append(parent.as_posix())
            parent = parent.parent

    write(guard_target(root, MANIFEST_PATH), manifest_text.encode("utf-8"))
    return sorted(set(emptied))

