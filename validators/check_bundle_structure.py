#!/usr/bin/env python3
"""Static validator to check pyRevit extension and bundle structures.

Stdlib only. Ensures that:
- Every folder ending in .pushbutton contains script.py and bundle.yaml.
- Every bundle.yaml contains title and tooltip metadata keys.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT_DIR = ROOT / "extensions"
REQUIRED_BUTTON_FILES = {"script.py", "bundle.yaml"}


def parse_yaml_metadata(text: str) -> dict[str, str]:
    """Simple key-value regex parser for basic YAML metadata (to avoid yaml dependency)."""
    data = {}
    for line in text.splitlines():
        line = line.split("#")[0].strip()  # Remove comments
        if not line:
            continue
        m = re.match(r"^([a-zA-Z0-9_\-]+)\s*:\s*(.+)$", line)
        if m:
            data[m.group(1).strip()] = m.group(2).strip().strip("'\"")
    return data


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


def main() -> None:
    if not EXT_DIR.exists() or not any(EXT_DIR.iterdir()):
        fail("No extensions/ directory found or it is empty.")

    # Find all .extension folders
    extensions = list(EXT_DIR.glob("*.extension"))
    if not extensions:
        fail("Missing *.extension folder inside extensions/")

    for ext in extensions:
        if not (ext / "extension.json").exists():
            fail(f"Missing extension.json in {ext.relative_to(ROOT)}")

        # Audit pushbuttons
        buttons = list(ext.rglob("*.pushbutton"))
        if not buttons:
            print(f"WARNING: No pushbuttons found in {ext.name}")

        for button in buttons:
            rel_button = button.relative_to(ROOT)
            present = {p.name for p in button.iterdir() if p.is_file()}
            missing = REQUIRED_BUTTON_FILES - present
            if missing:
                fail(f"Button '{rel_button}' is missing required files: {sorted(missing)}")

            # Read and parse bundle.yaml
            bundle_file = button / "bundle.yaml"
            try:
                content = bundle_file.read_text(encoding="utf-8")
                metadata = parse_yaml_metadata(content)
            except Exception as e:
                fail(f"Failed to read/parse {bundle_file.relative_to(ROOT)}: {e}")

            if "title" not in metadata:
                fail(f"Metadata in {bundle_file.relative_to(ROOT)} is missing 'title' key.")
            if "tooltip" not in metadata:
                fail(f"Metadata in {bundle_file.relative_to(ROOT)} is missing 'tooltip' key.")

    print("OK: Bundle structures look correct.")
    sys.exit(0)


if __name__ == "__main__":
    main()
