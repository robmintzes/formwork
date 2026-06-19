# -*- coding: utf-8 -*-
"""Extension-side build identity + staleness for pyRevit MCP."""

import os
import time

_STARTED_AT = time.time()
_LOADED = {}  # module_name -> {"file": path, "loaded_mtime": float, "kind": str}


def record_loaded(module_name, module_obj, kind="route"):
    try:
        path = module_obj.__file__
        if path.endswith(".pyc") and os.path.exists(path[:-1]):
            path = path[:-1]
        _LOADED[module_name] = {
            "file": path,
            "loaded_mtime": os.path.getmtime(path),
            "kind": kind,
        }
    except Exception:
        pass


def _read_text(path):
    f = open(path)
    try:
        return f.read().strip()
    finally:
        f.close()


def _git_dir(root):
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


def _resolve_ref(git, ref):
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


def git_identity(root):
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


def extension_root():
    # identity.py is at <ext_root>/lib/mcp/identity.py
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def repo_root_from(start):
    cur = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.abspath(start)
        cur = parent


def staleness():
    out = []
    for name in sorted(_LOADED.keys()):
        rec = _LOADED[name]
        cur = None
        stale = False
        try:
            cur = os.path.getmtime(rec["file"])
            stale = cur > rec["loaded_mtime"]
        except Exception:
            pass
        out.append({
            "module": name,
            "file": rec["file"],
            "kind": rec.get("kind", "route"),
            "loaded_mtime": rec["loaded_mtime"],
            "current_mtime": cur,
            "stale": stale,
        })
    return out


def identity():
    ext_root = extension_root()
    root = repo_root_from(ext_root)
    git = git_identity(root)
    mods = staleness()
    sha = git["sha"]
    any_stale = False
    for m in mods:
        if m["stale"]:
            any_stale = True
            break
    return {
        "component": "pyrevit-extension",
        "extension_root": ext_root,
        "root": root,
        "branch": git["branch"],
        "sha": sha,
        "short_sha": (sha[:8] if sha else None),
        "loaded_at": _STARTED_AT,
        "any_stale": any_stale,
        "modules": mods,
    }
