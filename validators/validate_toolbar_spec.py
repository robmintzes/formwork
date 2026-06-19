#!/usr/bin/env python3
"""Coverage / required-field / ID validator for toolbar_spec.md.

Ensures that:
- Every folder ending in .pushbutton has a registered spec entry.
- Every spec entry has a corresponding folder on disk.
- Required metadata fields are populated.
- Target confirmations are set for High-risk tools.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_FILE = ROOT / "docs" / "toolbar" / "toolbar_spec.md"
REQUIRED_FIELDS = [
    "id",
    "display_name",
    "type",
    "category",
    "risk",
    "lifecycle_stage",
    "description",
    "source_path",
]


def parse_spec_entries(text: str) -> list[dict[str, str]]:
    """Simple parser to extract tools metadata from YAML blocks in markdown."""
    entries = []
    current_entry = None
    lines = text.splitlines()

    for line in lines:
        # Detect start of a tool item in a YAML list (e.g. "  - id: hello-button")
        m_start = re.match(r"^\s*-\s*id:\s*(.+)$", line)
        if m_start:
            if current_entry:
                entries.append(current_entry)
            current_entry = {"id": m_start.group(1).strip().strip("'\"")}
            continue

        if current_entry is not None:
            # Check if we are still inside tool fields
            # A field is structured as "key: value"
            m_field = re.match(r"^\s*([a-zA-Z0-9_\-]+)\s*:\s*(.+)$", line)
            if m_field:
                key = m_field.group(1).strip()
                val = m_field.group(2).strip().split("#")[0].strip().strip("'\"")
                current_entry[key] = val
            elif line.strip() == "" or line.startswith("#") or line.startswith("---"):
                # End of current tool list segment
                entries.append(current_entry)
                current_entry = None

    if current_entry:
        entries.append(current_entry)

    return entries


def main() -> None:
    if not SPEC_FILE.exists():
        print(f"ERROR: Spec file not found at {SPEC_FILE}")
        sys.exit(1)

    text = SPEC_FILE.read_text(encoding="utf-8")
    entries = parse_spec_entries(text)

    errors = []

    # 1. Validate fields on each tool
    for e in entries:
        tool_id = e.get("id", "<unknown>")
        missing = [f for f in REQUIRED_FIELDS if f not in e or not e[f]]
        if missing:
            errors.append(f"[fields] Tool '{tool_id}' is missing required fields: {missing}")

        if e.get("risk") == "High" and e.get("requires_confirmation") != "true":
            errors.append(
                f"[confirm] Tool '{tool_id}' is risk:High but 'requires_confirmation' is not set to true."
            )

    # 2. Check for duplicate IDs
    ids = [e["id"] for e in entries if "id" in e]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        errors.append(f"[ids] Duplicate tool IDs found in spec: {duplicates}")

    # 3. Check folder coverage alignment
    # Gather paths from spec
    spec_paths = {
        e["source_path"].replace("\\", "/") for e in entries if "source_path" in e
    }

    # Verify each source_path exists on disk
    for path_str in sorted(spec_paths):
        if not (ROOT / path_str).is_dir():
            errors.append(
                f"[stale] Spec entry points to non-existent folder: '{path_str}'"
            )

    # Gather actual pushbutton folders on disk under extensions/
    disk_paths = set()
    for sub in (ROOT / "extensions").rglob("*"):
        if sub.is_dir() and sub.suffix in (".pushbutton", ".urlbutton"):
            rel_path = sub.relative_to(ROOT).as_posix()
            disk_paths.add(rel_path)

    # Find untracked folders
    untracked = disk_paths - spec_paths
    for path_str in sorted(untracked):
        errors.append(
            f"[missing] Tool folder exists on disk but is not registered in toolbar_spec.md: '{path_str}'"
        )

    print(
        f"Spec Audit: entries_found={len(entries)} spec_paths={len(spec_paths)} disk_paths={len(disk_paths)}"
    )

    if errors:
        print("\nToolbar validation FAILED:")
        for err in errors:
            print(" -", err)
        sys.exit(1)

    print("OK: Toolbar spec matches disk directories and required fields are valid.")
    sys.exit(0)


if __name__ == "__main__":
    main()
