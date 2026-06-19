#!/usr/bin/env python3
"""Cross-platform Python bootstrapper to rebrand the template for your firm.

Usage:
  python scripts/bootstrap.py
  python scripts/bootstrap.py --firm "AcmeCorp" --extension "BimTools"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prompt_input(prompt: str, default: str) -> str:
    val = input(f"{prompt} [{default}]: ").strip()
    return val if val else default


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

    # Clean inputs (remove whitespace)
    firm_name = "".join(firm_name.split())
    extension_name = "".join(extension_name.split())

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
        "docs/toolbar/toolbar_spec.md",
        "extensions/Placeholder.extension/extension.json",
        "extensions/Placeholder.extension/startup.py",
        "extensions/Placeholder.extension/PlaceholderTab.tab/PlaceholderPanel.panel/HelloButton.pushbutton/script.py",
        "extensions/Placeholder.extension/PlaceholderTab.tab/PlaceholderPanel.panel/HelloButton.pushbutton/bundle.yaml"
    ]

    print("\nUpdating text references across repository files...")
    for rel_path in files_to_update:
        file_path = ROOT / rel_path
        if file_path.exists():
            try:
                text = file_path.read_text(encoding="utf-8")
                # Perform substitutions
                text = text.replace("Placeholder", extension_name)
                text = text.replace("placeholder-tools", extension_name.lower())
                text = text.replace("Placeholder Tools", f"{extension_name} Tools")
                text = text.replace("PlaceholderPanel", f"{extension_name}Panel")
                text = text.replace("PlaceholderTab", f"{extension_name}Tab")
                text = text.replace("Template Author", f"{firm_name} Design Technology")
                file_path.write_text(text, encoding="utf-8")
                print(f"  Updated: {rel_path}")
            except Exception as e:
                print(f"  Failed to update {rel_path}: {e}")

    # 3. Directory Renames
    print("\nRenaming folders on disk...")
    try:
        # Rename panel
        old_panel = placeholder_ext_path / "PlaceholderTab.tab" / "PlaceholderPanel.panel"
        new_panel = placeholder_ext_path / "PlaceholderTab.tab" / panel_folder
        if old_panel.exists():
            old_panel.rename(new_panel)
            print("  Renamed Panel folder.")

        # Rename tab
        old_tab = placeholder_ext_path / "PlaceholderTab.tab"
        new_tab = placeholder_ext_path / tab_folder
        if old_tab.exists():
            old_tab.rename(new_tab)
            print("  Renamed Tab folder.")

        # Rename extension
        new_ext_path = ROOT / "extensions" / ext_folder
        placeholder_ext_path.rename(new_ext_path)
        print("  Renamed Extension root folder.")

    except Exception as e:
        print(f"ERROR: Failed to rename directories: {e}")
        sys.exit(1)

    print("\n==========================================")
    print("Bootstrap completed successfully!")
    print("To link your custom extension to pyRevit, run:")
    print("  python scripts/bootstrap.py (this setup)")
    print("  or register the extensions/ folder in Revit.")
    print("==========================================")


if __name__ == "__main__":
    main()
