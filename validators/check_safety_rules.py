#!/usr/bin/env python3
"""Validator to enforce safety rules on all Revit scripts in the repo.

Stdlib only. Ensures that:
- Destructive operations (like shutil.rmtree or os.remove) are flagged.
- Transactions are wrapped in try-catch blocks with explicit rollbacks.
- Unsafe network writes are avoided.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BANNED_PATTERNS = {
    r"\bshutil\.rmtree\b": "Destructive filesystem deletion (use safe wrapper or request manual review)",
    r"\bos\.remove\b": "Raw file deletion (avoid raw OS file manipulation)",
    r"\brequests\.(post|put|delete)\b": "Direct network mutation (writes require explicit authorization)",
}


def find_violations(root: Path = ROOT) -> list[str]:
    """Return safety violations for Python files under *root*/extensions."""
    violations = []
    # Find all Python files in the extensions directory
    py_files = list((root / "extensions").rglob("*.py"))

    for py_file in py_files:
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"WARNING: Failed to read {py_file}: {e}")
            continue

        rel_path = py_file.relative_to(root)

        # Check banned patterns
        for pattern, reason in BANNED_PATTERNS.items():
            if re.search(pattern, text):
                violations.append(f"{rel_path}: Violation: {reason}")

        # Check transaction safety
        # If "Transaction(" is instantiated, we expect to see "rollback" or "Rollback"
        # and "try" in the file to handle failures.
        if "Transaction(" in text:
            text_lower = text.lower()
            if "rollback" not in text_lower:
                violations.append(
                    f"{rel_path}: Transaction opened without rollback handling. "
                    "Make sure to wrap database changes in a try-except block and call transaction.Rollback() on error."
                )
            if "try:" not in text_lower:
                violations.append(
                    f"{rel_path}: Transaction opened without try-except block wrapping."
                )

    return violations


def main() -> None:
    violations = find_violations()
    if violations:
        print("ERROR: Safety validation failed:")
        for v in violations:
            print(" -", v)
        sys.exit(1)

    print("OK: Safety validation passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
