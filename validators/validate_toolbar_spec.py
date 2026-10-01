#!/usr/bin/env python3
"""Validate toolbar specification fields, coverage, and bundle alignment.

The toolbar spec is intentionally Markdown with small YAML blocks. This module
parses only the flat tool-entry schema used by the repository, keeping local and
CI validation free of a YAML dependency.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path, PurePosixPath

try:  # Direct script execution and package import use different module roots.
    from .check_bundle_structure import parse_yaml_metadata
except ImportError:  # pragma: no cover - exercised by the CLI invocation
    from check_bundle_structure import parse_yaml_metadata

ROOT = Path(__file__).resolve().parents[1]
SPEC_RELATIVE_PATH = Path("docs/toolbar/toolbar_spec.md")
# Generated workspaces keep managed spec blocks in fragments beside the firm-owned spec.
SPEC_FRAGMENTS_RELATIVE_PATH = Path("docs/toolbar/spec.d")
TOOLS_DOCS_RELATIVE_PATH = Path("docs/toolbar/tools")
REQUIRED_TAB_FIELDS = (
    "id",
    "display_name",
    "purpose",
    "audience",
    "lifecycle_stage",
    "repo_extension_path",
    "source_path",
)
REQUIRED_FIELDS = (
    "id",
    "display_name",
    "type",
    "category",
    "risk",
    "lifecycle_stage",
    "description",
    "source_path",
)
ALLOWED_RISKS = {"Low", "Medium", "High"}
ALLOWED_LIFECYCLE_STAGES = {"sandbox", "beta", "production"}
TOOL_TYPE_SUFFIXES = {
    "PushButton": ".pushbutton",
    "URLButton": ".urlbutton",
    "SplitButton": ".splitbutton",
    "Dropdown": ".pulldown",
}
TOOL_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def parse_spec_entries(text: str) -> list[dict[str, str]]:
    """Extract flat tool entries from fenced ``yaml`` blocks."""
    entries: list[dict[str, str]] = []
    current_entry: dict[str, str] | None = None
    in_yaml_block = False
    in_tools_list = False

    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "```yaml":
            in_yaml_block = True
            in_tools_list = False
            continue
        if in_yaml_block and stripped == "```":
            if current_entry is not None:
                entries.append(current_entry)
                current_entry = None
            in_yaml_block = False
            in_tools_list = False
            continue
        if not in_yaml_block:
            continue
        if re.match(r"^\s*tools\s*:\s*$", line):
            in_tools_list = True
            continue
        if not in_tools_list:
            continue

        start = re.match(r"^\s*-\s*id\s*:\s*(.*)$", line)
        if start:
            if current_entry is not None:
                entries.append(current_entry)
            current_entry = {"id": _clean_scalar(start.group(1))}
            continue

        if current_entry is not None:
            field = re.match(r"^\s+([a-zA-Z0-9_-]+)\s*:\s*(.*)$", line)
            if field:
                current_entry[field.group(1)] = _clean_scalar(field.group(2))

    if current_entry is not None:
        entries.append(current_entry)
    return entries


def parse_tab_entries(text: str) -> list[dict[str, str]]:
    """Extract flat ``tab:`` metadata from fenced ``yaml`` blocks."""
    entries: list[dict[str, str]] = []
    current_entry: dict[str, str] | None = None
    in_yaml_block = False

    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "```yaml":
            in_yaml_block = True
            current_entry = None
            continue
        if in_yaml_block and stripped == "```":
            if current_entry is not None:
                entries.append(current_entry)
            current_entry = None
            in_yaml_block = False
            continue
        if not in_yaml_block:
            continue
        if re.match(r"^\s*tab\s*:\s*$", line):
            current_entry = {}
            continue
        if current_entry is not None:
            field = re.match(r"^\s+([a-zA-Z0-9_-]+)\s*:\s*(.*)$", line)
            if field:
                current_entry[field.group(1)] = _clean_scalar(field.group(2))

    if current_entry is not None:
        entries.append(current_entry)
    return entries


def _clean_scalar(value: str) -> str:
    """Normalize the simple unquoted/quoted scalars supported by the spec."""
    return value.split("#", 1)[0].strip().strip("'\"")


def _normalized_source_path(value: str) -> str | None:
    normalized = value.replace("\\", "/")
    pure_path = PurePosixPath(normalized)
    if pure_path.is_absolute() or ".." in pure_path.parts:
        return None
    return pure_path.as_posix()


def validate_toolbar_spec(root: Path = ROOT) -> tuple[dict[str, int], list[str]]:
    """Return summary statistics and all validation errors below *root*."""
    errors: list[str] = []
    spec_path = root / SPEC_RELATIVE_PATH
    if not spec_path.is_file():
        return ({"tabs": 0, "tab_paths": 0, "entries": 0, "spec_paths": 0, "disk_paths": 0}, [f"Spec file not found: {SPEC_RELATIVE_PATH.as_posix()}."])

    spec_files = [spec_path] + sorted((root / SPEC_FRAGMENTS_RELATIVE_PATH).glob("*.md"))
    texts: list[str] = []
    for path in spec_files:
        try:
            texts.append(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            return ({"tabs": 0, "tab_paths": 0, "entries": 0, "spec_paths": 0, "disk_paths": 0}, [f"Could not read {path.relative_to(root).as_posix()}: {exc}."])
    spec_text = "\n".join(texts)

    tabs = parse_tab_entries(spec_text)
    entries = parse_spec_entries(spec_text)

    if not tabs:
        errors.append("[tabs] No tab metadata blocks were found in the toolbar spec.")

    tab_ids: list[str] = []
    tab_extension_paths: list[str] = []
    tab_source_paths: list[str] = []
    for tab in tabs:
        tab_id = tab.get("id", "<unknown>") or "<unknown>"
        missing_tab_fields = [
            field for field in REQUIRED_TAB_FIELDS if not tab.get(field, "").strip()
        ]
        if missing_tab_fields:
            errors.append(
                f"[tab-fields] Tab '{tab_id}' is missing required fields: "
                f"{missing_tab_fields}."
            )

        if tab.get("id"):
            tab_ids.append(tab["id"])
            if not TOOL_ID_PATTERN.fullmatch(tab["id"]):
                errors.append(
                    f"[tab-id-format] Tab ID '{tab['id']}' must use lowercase kebab-case."
                )

        tab_lifecycle = tab.get("lifecycle_stage")
        if tab_lifecycle and tab_lifecycle not in ALLOWED_LIFECYCLE_STAGES:
            errors.append(
                f"[tab-lifecycle] Tab '{tab_id}' has invalid lifecycle_stage "
                f"'{tab_lifecycle}'; expected one of {sorted(ALLOWED_LIFECYCLE_STAGES)}."
            )

        extension_value = tab.get("repo_extension_path")
        extension_path: str | None = None
        if extension_value:
            extension_path = _normalized_source_path(extension_value)
            if extension_path is None:
                errors.append(
                    f"[tab-path] Tab '{tab_id}' repo_extension_path must be "
                    f"repository-relative without '..': '{extension_value}'."
                )
            else:
                tab_extension_paths.append(extension_path)
                pure_extension_path = PurePosixPath(extension_path)
                if (
                    not pure_extension_path.parts
                    or pure_extension_path.parts[0] != "extensions"
                    or pure_extension_path.suffix != ".extension"
                ):
                    errors.append(
                        f"[tab-path] Tab '{tab_id}' repo_extension_path must point to "
                        f"an extensions/*.extension directory: '{extension_path}'."
                    )
                if not (root / extension_path).is_dir():
                    errors.append(
                        f"[tab-stale] Tab '{tab_id}' points to a non-existent extension "
                        f"directory: '{extension_path}'."
                    )

        tab_source_value = tab.get("source_path")
        if tab_source_value:
            tab_source_path = _normalized_source_path(tab_source_value)
            if tab_source_path is None:
                errors.append(
                    f"[tab-source-path] Tab '{tab_id}' source_path must be "
                    f"repository-relative without '..': '{tab_source_value}'."
                )
            else:
                tab_source_paths.append(tab_source_path)
                pure_tab_source = PurePosixPath(tab_source_path)
                if pure_tab_source.suffix != ".tab":
                    errors.append(
                        f"[tab-source-path] Tab '{tab_id}' source_path must point "
                        f"to a .tab directory: '{tab_source_path}'."
                    )
                if extension_path is not None and (
                    pure_tab_source.parent != PurePosixPath(extension_path)
                ):
                    errors.append(
                        f"[tab-parent] Tab '{tab_id}' source_path must be directly "
                        f"inside repo_extension_path '{extension_path}'."
                    )
                if not (root / tab_source_path).is_dir():
                    errors.append(
                        f"[tab-source-stale] Tab '{tab_id}' points to a non-existent "
                        f"tab directory: '{tab_source_path}'."
                    )

    duplicate_tab_ids = sorted(
        {value for value in tab_ids if tab_ids.count(value) > 1}
    )
    if duplicate_tab_ids:
        errors.append(f"[tab-ids] Duplicate tab IDs found in spec: {duplicate_tab_ids}.")

    duplicate_tab_source_paths = sorted(
        {value for value in tab_source_paths if tab_source_paths.count(value) > 1}
    )
    if duplicate_tab_source_paths:
        errors.append(
            f"[tab-source-paths] Duplicate tab source paths found in spec: "
            f"{duplicate_tab_source_paths}."
        )

    if not entries:
        errors.append("[entries] No tool entries were found in the toolbar spec.")

    ids: list[str] = []
    normalized_paths: list[str] = []

    for entry in entries:
        tool_id = entry.get("id", "<unknown>") or "<unknown>"
        missing = [field for field in REQUIRED_FIELDS if not entry.get(field, "").strip()]
        if missing:
            errors.append(f"[fields] Tool '{tool_id}' is missing required fields: {missing}.")

        if entry.get("id"):
            ids.append(entry["id"])
            if not TOOL_ID_PATTERN.fullmatch(entry["id"]):
                errors.append(
                    f"[id-format] Tool ID '{entry['id']}' must use lowercase kebab-case."
                )

        risk = entry.get("risk")
        if risk and risk not in ALLOWED_RISKS:
            errors.append(
                f"[risk] Tool '{tool_id}' has invalid risk '{risk}'; "
                f"expected one of {sorted(ALLOWED_RISKS)}."
            )

        lifecycle = entry.get("lifecycle_stage")
        if lifecycle and lifecycle not in ALLOWED_LIFECYCLE_STAGES:
            errors.append(
                f"[lifecycle] Tool '{tool_id}' has invalid lifecycle_stage '{lifecycle}'; "
                f"expected one of {sorted(ALLOWED_LIFECYCLE_STAGES)}."
            )

        tool_type = entry.get("type")
        if tool_type and tool_type not in TOOL_TYPE_SUFFIXES:
            errors.append(
                f"[type] Tool '{tool_id}' has invalid type '{tool_type}'; "
                f"expected one of {sorted(TOOL_TYPE_SUFFIXES)}."
            )

        confirmation = entry.get("requires_confirmation")
        if confirmation is not None and confirmation not in {"true", "false"}:
            errors.append(
                f"[confirm] Tool '{tool_id}' has invalid requires_confirmation "
                f"value '{confirmation}'; expected true or false."
            )
        if risk == "High" and confirmation != "true":
            errors.append(
                f"[confirm] Tool '{tool_id}' is risk:High but requires_confirmation is not true."
            )

        source_value = entry.get("source_path")
        if source_value:
            source_path = _normalized_source_path(source_value)
            if source_path is None:
                errors.append(
                    f"[path] Tool '{tool_id}' source_path must be repository-relative "
                    f"without '..': '{source_value}'."
                )
            else:
                normalized_paths.append(source_path)
                source_directory = root / source_path
                if not source_directory.is_dir():
                    errors.append(
                        f"[stale] Spec entry '{tool_id}' points to a non-existent folder: "
                        f"'{source_path}'."
                    )

                expected_suffix = TOOL_TYPE_SUFFIXES.get(tool_type or "")
                actual_suffix = PurePosixPath(source_path).suffix
                if expected_suffix and actual_suffix != expected_suffix:
                    errors.append(
                        f"[type-path] Tool '{tool_id}' type '{tool_type}' expects a "
                        f"'{expected_suffix}' folder, not '{actual_suffix or '<none>'}'."
                    )

                bundle_path = source_directory / "bundle.yaml"
                if bundle_path.is_file() and entry.get("display_name"):
                    try:
                        bundle = parse_yaml_metadata(bundle_path.read_text(encoding="utf-8"))
                    except (OSError, UnicodeError) as exc:
                        errors.append(
                            f"[bundle] Could not read {bundle_path.relative_to(root)}: {exc}."
                        )
                    else:
                        bundle_title = bundle.get("title", "")
                        if bundle_title and bundle_title != entry["display_name"]:
                            errors.append(
                                f"[bundle-title] Tool '{tool_id}' display_name "
                                f"'{entry['display_name']}' does not match bundle title "
                                f"'{bundle_title}'."
                            )

        if entry.get("id"):
            guide_path = root / TOOLS_DOCS_RELATIVE_PATH / f"{entry['id']}.md"
            if not guide_path.is_file():
                errors.append(
                    f"[docs] Tool '{tool_id}' is missing guide "
                    f"'{guide_path.relative_to(root).as_posix()}'."
                )
            else:
                try:
                    guide_text = guide_path.read_text(encoding="utf-8")
                except (OSError, UnicodeError) as exc:
                    errors.append(
                        f"[docs] Could not read {guide_path.relative_to(root)}: {exc}."
                    )
                else:
                    if not guide_text.strip():
                        errors.append(
                            f"[docs] Tool guide '{guide_path.relative_to(root)}' is empty."
                        )

    duplicate_ids = sorted({value for value in ids if ids.count(value) > 1})
    if duplicate_ids:
        errors.append(f"[ids] Duplicate tool IDs found in spec: {duplicate_ids}.")

    duplicate_paths = sorted(
        {value for value in normalized_paths if normalized_paths.count(value) > 1}
    )
    if duplicate_paths:
        errors.append(f"[paths] Duplicate source paths found in spec: {duplicate_paths}.")

    spec_paths = set(normalized_paths)
    disk_paths: set[str] = set()
    extension_root = root / "extensions"
    disk_extension_paths: set[str] = set()
    disk_tab_paths: set[str] = set()
    if extension_root.is_dir():
        for extension in extension_root.glob("*.extension"):
            if extension.is_dir():
                disk_extension_paths.add(extension.relative_to(root).as_posix())
        known_suffixes = set(TOOL_TYPE_SUFFIXES.values())
        for candidate in extension_root.rglob("*"):
            if candidate.is_dir() and candidate.suffix == ".tab":
                disk_tab_paths.add(candidate.relative_to(root).as_posix())
            if candidate.is_dir() and candidate.suffix in known_suffixes:
                disk_paths.add(candidate.relative_to(root).as_posix())

    for path_value in sorted(disk_paths - spec_paths):
        errors.append(
            f"[missing] Tool folder exists on disk but is not registered in "
            f"toolbar_spec.md: '{path_value}'."
        )

    for path_value in sorted(disk_extension_paths - set(tab_extension_paths)):
        errors.append(
            f"[extension-missing] Extension folder exists on disk but is not registered "
            f"by a tab block: '{path_value}'."
        )

    for path_value in sorted(disk_tab_paths - set(tab_source_paths)):
        errors.append(
            f"[tab-missing] Tab folder exists on disk but has no tab metadata block: "
            f"'{path_value}'."
        )

    return (
        {
            "tabs": len(tabs),
            "tab_paths": len(set(tab_source_paths)),
            "entries": len(entries),
            "spec_paths": len(spec_paths),
            "disk_paths": len(disk_paths),
        },
        errors,
    )


def main() -> None:
    stats, errors = validate_toolbar_spec()
    print(
        "Spec Audit: "
        f"tabs_found={stats['tabs']} "
        f"tab_paths={stats['tab_paths']} "
        f"entries_found={stats['entries']} "
        f"spec_paths={stats['spec_paths']} "
        f"disk_paths={stats['disk_paths']}"
    )
    if errors:
        print("\nToolbar validation FAILED:")
        for error in errors:
            print(f" - {error}")
        sys.exit(1)

    print("OK: Toolbar spec, bundle metadata, and tool guides are aligned.")


if __name__ == "__main__":
    main()
