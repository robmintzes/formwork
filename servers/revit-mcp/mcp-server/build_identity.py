# build_identity.py
# Server-side build identity + staleness.

import os
import time

_STARTED_AT = time.time()


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _git_dir(root: str) -> str | None:
    git = os.path.join(root, ".git")
    if os.path.isdir(git):
        return git
    if os.path.isfile(git):
        text = _read_text(git)
        if text.startswith("gitdir:"):
            p = text.split(":", 1)[1].strip()
            if not os.path.isabs(p):
                p = os.path.normpath(os.path.join(root, p))
            return p
    return None


def _resolve_ref(git: str, ref: str) -> str | None:
    loose = os.path.join(git, ref.replace("/", os.sep))
    if os.path.exists(loose):
        return _read_text(loose) or None
    packed = os.path.join(git, "packed-refs")
    if os.path.exists(packed):
        for line in _read_text(packed).splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("^"):
                continue
            parts = line.split(" ", 1)
            if len(parts) == 2 and parts[1] == ref:
                return parts[0]
    return None


def git_identity(root: str) -> dict[str, str | None]:
    git = _git_dir(root)
    if git is None:
        return {"branch": None, "sha": None}
    try:
        head = _read_text(os.path.join(git, "HEAD"))
    except Exception:
        return {"branch": None, "sha": None}
    if head.startswith("ref:"):
        ref = head.split(":", 1)[1].strip()
        prefix = "refs/heads/"
        if ref.find(prefix) == 0:
            branch = ref[len(prefix):]
        else:
            branch = ref
        return {"branch": branch, "sha": _resolve_ref(git, ref)}
    return {"branch": None, "sha": head or None}


def repo_root_from(start: str) -> str:
    cur = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.abspath(start)
        cur = parent


def summary() -> dict[str, str | float | None]:
    """Return a single-line summary dict of the current running checkout."""
    server_dir = os.path.dirname(os.path.abspath(__file__))
    root = repo_root_from(server_dir)
    git = git_identity(root)
    sha = git["sha"]
    return {
        "root": root,
        "branch": git["branch"],
        "sha": sha,
        "short_sha": (sha[:8] if sha else None),
        "started_at": _STARTED_AT,
    }


def identity() -> dict[str, str | float | dict[str, str | float | None] | None]:
    s = summary()
    return {
        "component": "mcp-server",
        "root": s["root"],
        "branch": s["branch"],
        "sha": s["sha"],
        "short_sha": s["short_sha"],
        "started_at": s["started_at"],
    }
