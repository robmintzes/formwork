#!/usr/bin/env python3
"""Enforce human-owned development branches locally and in pull requests."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

__author__ = "Template Author"
ROOT = Path(__file__).resolve().parents[1]
PROTECTED = {"main", "stable"}
AGENT_PREFIXES = {"ai", "agent", "antigravity", "chatgpt", "claude", "codex", "copilot", "gemini"}
BRANCH_PATTERN = re.compile(r"([a-z0-9]+(?:-[a-z0-9]+)*)/([a-z0-9]+(?:-[a-z0-9]+)*)")


def branch_error(branch: str, owner: str | None = None) -> str | None:
    if branch in PROTECTED:
        return f"Direct development on {branch!r} is blocked. Create an owner/task branch."
    match = BRANCH_PATTERN.fullmatch(branch)
    if not match or match[1] in AGENT_PREFIXES:
        return f"Branch {branch!r} must use a human owner and lowercase task slug (e.g. robmintzes/fix-selection)."
    if owner and match[1] != owner:
        return f"Branch owner {match[1]!r} does not match configured human owner {owner!r}."
    return None


def git_output(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def push_errors(lines: list[str], owner: str) -> list[str]:
    errors = []
    for line in lines:
        parts = line.split()
        if len(parts) != 4:
            errors.append("Malformed Git pre-push input; refusing to push.")
            continue
        local_ref, local_sha, remote_ref, _ = parts
        if not remote_ref.startswith("refs/heads/"):
            continue  # Branch policy does not govern release tags.
        remote_branch = remote_ref.removeprefix("refs/heads/")
        error = branch_error(remote_branch, owner)
        if error:
            errors.append(error)
        if set(local_sha) == {"0"}:
            continue  # Deleting a non-protected, owned development branch is allowed.
        if local_ref.startswith("refs/heads/"):
            error = branch_error(local_ref.removeprefix("refs/heads/"), owner)
            if error:
                errors.append(error)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", help="Check a PR head branch instead of the local checkout.")
    parser.add_argument("--owner", help="Expected accountable human prefix.")
    parser.add_argument("--pre-push", action="store_true", help="Also validate destination refs from Git stdin.")
    args = parser.parse_args()
    errors = []
    if args.branch is not None:
        branch = args.branch
        owner = args.owner
    else:
        branch = git_output("symbolic-ref", "--quiet", "--short", "HEAD")
        owner = args.owner or git_output("config", "--get", "branchPolicy.owner")
        if not branch:
            errors.append("Detached HEAD or unavailable Git checkout; switch to an owned development branch.")
        if not owner:
            errors.append("Human owner is not configured. Run scripts/install-git-hooks.ps1 -Owner <username>.")
    if branch:
        error = branch_error(branch, owner)
        if error:
            errors.append(error)
    if args.pre_push:
        errors.extend(push_errors(sys.stdin.read().splitlines(), owner or ""))
    if errors:
        for error in errors:
            print("ERROR: " + error, file=sys.stderr)
        return 1
    print("OK: Human-owned development branch policy passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
