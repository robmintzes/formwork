#!/usr/bin/env python3
"""Cross-platform Python bootstrapper to rebrand the template for your firm.

Usage:
  python scripts/bootstrap.py
  python scripts/bootstrap.py --firm "AcmeCorp" --extension "BimTools"
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAFE_EXTENSION_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*$")
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
FIRM_PUNCTUATION = set(" .,&'()_-")


def prompt_input(prompt: str, default: str) -> str:
    val = input(f"{prompt} [{default}]: ").strip()
    return val if val else default


def _valid_firm_name(value: str) -> bool:
    return (
        1 <= len(value) <= 80
        and value[0].isalnum()
        and all(character.isalnum() or character in FIRM_PUNCTUATION for character in value)
    )


def _render(text: str, firm_name: str, extension_name: str) -> str:
    """Apply branding replacements from most specific to most general."""
    text = text.replace("Placeholder Tools", extension_name)
    text = text.replace("placeholder-tools", extension_name.lower())
    text = text.replace("PlaceholderPanel", f"{extension_name}Panel")
    text = text.replace("PlaceholderTab", f"{extension_name}Tab")
    text = text.replace("Template Author", firm_name)
    text = text.replace("PLACEHOLDER", extension_name.upper())
    text = text.replace("Placeholder", extension_name)
    return text.replace("placeholder", extension_name.lower())


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap pyRevit Toolbar Template")
    parser.add_argument("--firm", help="Firm Name (e.g. AcmeCorp)")
    parser.add_argument("--extension", help="Extension Name (e.g. BimTools)")
    args = parser.parse_args()

    print("==========================================")
    print("      pyRevit Extension Bootstrapper      ")
    print("==========================================")

    # 1. Resolve inputs
    firm_name = args.firm
    if not firm_name:
        try:
            firm_name = prompt_input("Enter your Firm Name (e.g. AcmeCorp)", "MyFirm")
        except (KeyboardInterrupt, EOFError):
            print("\nCanceled.")
            sys.exit(0)

    extension_name = args.extension
    if not extension_name:
        try:
            extension_name = prompt_input("Enter your Extension Name (e.g. BimTools)", "BimTools")
        except (KeyboardInterrupt, EOFError):
            print("\nCanceled.")
            sys.exit(0)

    # Preserve human-facing firm spacing; extension names are safe identifiers.
    firm_name = " ".join(firm_name.split())
    extension_name = "".join(extension_name.split())

    if not _valid_firm_name(firm_name):
        print(
            "\nERROR: Firm name must start with a letter or number and use only "
            "letters, numbers, spaces, or . , & ' ( ) _ - characters.",
            file=sys.stderr,
        )
        sys.exit(2)
    if (
        len(extension_name) > 64
        or not SAFE_EXTENSION_NAME.fullmatch(extension_name)
        or extension_name.upper() in WINDOWS_RESERVED_NAMES
        or extension_name.lower() == "placeholder"
    ):
        print(
            "\nERROR: Extension name must be a non-reserved identifier beginning "
            "with a letter and containing alphanumeric segments separated by "
            "single hyphens.",
            file=sys.stderr,
        )
        sys.exit(2)

    ext_folder = f"{extension_name}.extension"
    tab_folder = f"{extension_name}Tab.tab"
    panel_folder = f"{extension_name}Panel.panel"

    placeholder_ext_path = ROOT / "extensions" / "Placeholder.extension"
    if not placeholder_ext_path.exists():
        print(f"\nERROR: Placeholder extension folder not found at {placeholder_ext_path}.")
        print("Has bootstrap already been run?")
        sys.exit(1)

    print(f"\nRebranding codebase to:")
    print(f"  Firm Name:      {firm_name}")
    print(f"  Extension Name: {extension_name}")
    print(f"  Extension Dir:  extensions/{ext_folder}")

    # 2. Text Replacements
    files_to_update = [
        "README.md",
        "AGENTS.md",
        ".github/workflows/ci.yml",
        "docs/toolbar/toolbar_spec.md",
        "docs/toolbar/tools/hello-button.md",
        "docs/onboarding/MCP_GUIDE.md",
        "docs/handoffs/mcp-bridge-onboarding-2026-06-19.md",
        "extensions/Placeholder.extension/extension.json",
        "extensions/Placeholder.extension/startup.py",
        "extensions/Placeholder.extension/PlaceholderTab.tab/PlaceholderPanel.panel/HelloButton.pushbutton/script.py",
        "extensions/Placeholder.extension/PlaceholderTab.tab/PlaceholderPanel.panel/HelloButton.pushbutton/bundle.yaml",
        "extensions/Placeholder.extension/lib/revit_mcp_bridge/__init__.py",
        "extensions/Placeholder.extension/lib/revit_mcp_bridge/compat.py",
        "extensions/Placeholder.extension/lib/revit_mcp_bridge/dispatch.py",
        "extensions/Placeholder.extension/lib/revit_mcp_bridge/handlers_health.py",
        "extensions/Placeholder.extension/lib/revit_mcp_bridge/handlers_project.py",
        "extensions/Placeholder.extension/lib/revit_mcp_bridge/handlers_registry.py",
        "extensions/Placeholder.extension/lib/revit_mcp_bridge/identity.py",
        "extensions/Placeholder.extension/lib/revit_mcp_bridge/response.py",
        "extensions/Placeholder.extension/lib/revit_mcp_bridge/routes_health.py",
        "extensions/Placeholder.extension/lib/revit_mcp_bridge/routes_project.py",
        "extensions/Placeholder.extension/lib/revit_mcp_bridge/routes_dispatch.py",
        "extensions/Placeholder.extension/lib/revit_mcp_bridge/startup.py",
        "extensions/Placeholder.extension/tests/test_runtime_stabilization.py",
        "servers/revit-mcp/mcp-server/settings.py",
    ]

    old_tab = placeholder_ext_path / "PlaceholderTab.tab"
    old_panel = old_tab / "PlaceholderPanel.panel"
    new_tab = placeholder_ext_path / tab_folder
    new_panel = old_tab / panel_folder
    new_ext_path = ROOT / "extensions" / ext_folder

    missing_paths = [
        rel_path for rel_path in files_to_update if not (ROOT / rel_path).is_file()
    ]
    if not old_tab.is_dir():
        missing_paths.append(old_tab.relative_to(ROOT).as_posix())
    if not old_panel.is_dir():
        missing_paths.append(old_panel.relative_to(ROOT).as_posix())
    if missing_paths:
        print(
            "\nERROR: Bootstrap source paths are missing:\n  - "
            + "\n  - ".join(missing_paths),
            file=sys.stderr,
        )
        sys.exit(1)
    for destination in (new_panel, new_tab, new_ext_path):
        if destination.exists():
            print(
                "\nERROR: Bootstrap destination already exists: {}".format(destination),
                file=sys.stderr,
            )
            sys.exit(1)

    print("\nUpdating text references across repository files...")
    for rel_path in files_to_update:
        file_path = ROOT / rel_path
        try:
            text = file_path.read_text(encoding="utf-8")
            file_path.write_text(_render(text, firm_name, extension_name), encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(f"ERROR: Failed to update {rel_path}: {exc}", file=sys.stderr)
            sys.exit(1)
        print(f"  Updated: {rel_path}")

    # 3. Directory Renames
    print("\nRenaming folders on disk...")
    try:
        # Rename panel
        old_panel.rename(new_panel)
        print("  Renamed Panel folder.")

        # Rename tab
        old_tab.rename(new_tab)
        print("  Renamed Tab folder.")

        # Rename extension
        placeholder_ext_path.rename(new_ext_path)
        print("  Renamed Extension root folder.")

    except Exception as e:
        print(f"ERROR: Failed to rename directories: {e}")
        sys.exit(1)

    print("\n==========================================")
    print("Bootstrap completed successfully!")
    print("To link your custom extension to pyRevit, run:")
    print("  powershell -File scripts/install-extension.ps1")
    print("  or register this repository's extensions/ folder in pyRevit.")
    print("==========================================")


if __name__ == "__main__":
    main()
