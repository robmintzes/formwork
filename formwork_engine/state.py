"""Where a workspace keeps engine state, and the move from the pre-0.3 name.

Workspaces rendered before Formwork 0.3.0 keep their state in ``.toolkit/``.
Reads accept that folder; the first applied render moves it to ``.formwork/``
(ADR 0010). Dry runs never move anything.
"""

from __future__ import annotations

import os
from pathlib import Path

from formwork_engine.paths import UnsafePathError, is_reparse_point

STATE_DIR = ".formwork"
LEGACY_STATE_DIR = ".toolkit"


def locate_state(root: Path) -> str:
    """Return the state folder name in use under *root*.

    ``STATE_DIR`` unless only the legacy folder exists. Raises UnsafePathError
    when either folder is a link or junction, or when both exist.
    """
    current, legacy = root / STATE_DIR, root / LEGACY_STATE_DIR
    for path in (current, legacy):
        if is_reparse_point(path):
            raise UnsafePathError(
                "path.reparse-point", "Refusing to use link or junction at {!r}.".format(path.name + "/")
            )
    if not legacy.exists():
        return STATE_DIR
    if current.exists():
        raise UnsafePathError(
            "workspace.state-ambiguous",
            "Both {0}/ and {1}/ exist. {1}/ is the pre-0.3 name of {0}/; keep the one "
            "holding this workspace's manifest and delete the other.".format(STATE_DIR, LEGACY_STATE_DIR),
        )
    if not legacy.is_dir():
        raise UnsafePathError("path.not-directory", "{}/ exists but is not a folder.".format(LEGACY_STATE_DIR))
    return LEGACY_STATE_DIR


def migrate_state(root: Path) -> None:
    """Rename the legacy state folder to ``STATE_DIR`` (one atomic directory rename)."""
    if locate_state(root) == LEGACY_STATE_DIR:
        os.rename(root / LEGACY_STATE_DIR, root / STATE_DIR)
