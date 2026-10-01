"""Manifest handling and change planning (FOUNDATION_SPEC sections 4.2-4.3)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from toolkit_engine import MANIFEST_SCHEMA_VERSION
from toolkit_engine.jsonio import JsonInputError, dumps_canonical, load_strict
from toolkit_engine.outputs import OWNERSHIP_MANAGED, OWNERSHIP_SEED, OutputFile, content_hash, is_reserved_path
from toolkit_engine.paths import UnsafePathError, check_relative_path, guard_target

MANIFEST_PATH = ".toolkit/manifest.json"
MANIFEST_KIND = "toolkit-generation-manifest"

WRITE_ACTIONS = ("create", "restore", "update")
CHANGE_ACTIONS = WRITE_ACTIONS + ("adopt", "delete", "forget")
CONFLICT_REASONS = {
    "managed-modified": (
        "This generated file was edited after the last render.",
        "Revert your edit, delete the file to accept regeneration, or move the customization to a firm-owned file.",
    ),
    "unmanaged-at-managed-path": (
        "A file the generator did not create occupies a path it now needs.",
        "Move or rename your file, or delete it if the generated version should replace it.",
    ),
    "retired-modified": (
        "A generated file that is no longer produced was edited, so it is not deleted automatically.",
        "Keep it by moving it to a firm-owned location, or delete it yourself.",
    ),
}


class ManifestError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Action:
    path: str
    action: str
    ownership: str
    adapter: str
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v != ""}


@dataclass
class Plan:
    actions: list[Action] = field(default_factory=list)
    manifest_files: dict[str, dict[str, str]] = field(default_factory=dict)
    retired_hashes: dict[str, str] = field(default_factory=dict)

    @property
    def conflicts(self) -> list[Action]:
        return [a for a in self.actions if a.action == "conflict"]

    @property
    def changes(self) -> list[Action]:
        return [a for a in self.actions if a.action in CHANGE_ACTIONS]

    def counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for action in self.actions:
            result[action.action] = result.get(action.action, 0) + 1
        return dict(sorted(result.items()))


def load_manifest(root: Path, known_adapters: frozenset[str] | None = None) -> dict[str, Any] | None:
    """Return the manifest dict, None when absent; raise ManifestError when unusable."""
    path = root / ".toolkit" / "manifest.json"
    if not path.exists():
        return None
    try:
        data = load_strict(path)
    except (JsonInputError, OSError) as exc:
        raise ManifestError("manifest.invalid", "Cannot read {}: {}".format(MANIFEST_PATH, exc)) from exc
    if not isinstance(data, dict) or data.get("kind") != MANIFEST_KIND:
        raise ManifestError("manifest.invalid", "{} is not a generation manifest.".format(MANIFEST_PATH))
    version = data.get("schema_version")
    if not isinstance(version, int) or version < 1:
        raise ManifestError("manifest.invalid", "Manifest schema_version is missing or invalid.")
    if version > MANIFEST_SCHEMA_VERSION:
        raise ManifestError(
            "manifest.schema-too-new",
            "Manifest schema {} was written by a newer foundation.".format(version),
        )
    files = data.get("files")
    if not isinstance(files, dict):
        raise ManifestError("manifest.invalid", "Manifest has no files mapping.")
    for rel, entry in files.items():
        problem = check_relative_path(rel)
        if problem or is_reserved_path(rel):
            raise ManifestError("manifest.invalid", "Manifest lists an unsafe path {!r}.".format(rel))
        if not isinstance(entry, dict) or entry.get("ownership") not in (OWNERSHIP_MANAGED, OWNERSHIP_SEED):
            raise ManifestError("manifest.invalid", "Manifest entry for {!r} is malformed.".format(rel))
        if entry["ownership"] == OWNERSHIP_MANAGED and not isinstance(entry.get("sha256"), str):
            raise ManifestError("manifest.invalid", "Managed entry {!r} has no hash.".format(rel))
        if known_adapters is not None and entry.get("adapter") not in known_adapters:
            # A retired file may only be deleted on behalf of an adapter this
            # engine knows; an unknown adapter means the manifest was edited.
            raise ManifestError(
                "manifest.invalid", "Manifest entry {!r} names unknown adapter {!r}.".format(rel, entry.get("adapter"))
            )
    return data


def render_manifest(
    *, foundation_version: str, workspace_id: str, profile_id: str, inputs_sha256: str, files: dict[str, dict[str, str]]
) -> str:
    return dumps_canonical(
        {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "kind": MANIFEST_KIND,
            "foundation_version": foundation_version,
            "workspace_id": workspace_id,
            "profile_id": profile_id,
            "inputs_sha256": inputs_sha256,
            "files": files,
        }
    )


def _disk_hash(root: Path, rel: str, text: bool) -> str | None:
    target = guard_target(root, rel)
    if not target.exists():
        return None
    if not target.is_file():
        raise UnsafePathError("path.not-file", "Expected a file at {!r}, found a directory.".format(rel))
    return content_hash(target.read_bytes(), text)


def plan_changes(root: Path, desired: list[OutputFile], previous: dict[str, dict[str, str]]) -> Plan:
    """Classify every desired and previously managed path. Read-only."""
    plan = Plan()
    desired_paths = {item.path for item in desired}

    for item in sorted(desired, key=lambda o: o.path):
        new_hash = item.sha256
        recorded = previous.get(item.path)
        disk = _disk_hash(root, item.path, item.text)
        if item.ownership == OWNERSHIP_SEED:
            if disk is None and recorded is None:
                action = "create"
            else:
                action = "skip"
            plan.actions.append(Action(item.path, action, OWNERSHIP_SEED, item.adapter))
            plan.manifest_files[item.path] = {"adapter": item.adapter, "ownership": OWNERSHIP_SEED}
            continue

        managed_record = recorded if recorded and recorded.get("ownership") == OWNERSHIP_MANAGED else None
        reason = ""
        if disk is None:
            action = "restore" if managed_record else "create"
        elif managed_record:
            if disk == managed_record["sha256"]:
                action = "unchanged" if disk == new_hash else "update"
            elif disk == new_hash:
                action = "adopt"
            else:
                action, reason = "conflict", "managed-modified"
        elif disk == new_hash:
            action = "adopt"
        else:
            action, reason = "conflict", "unmanaged-at-managed-path"
        plan.actions.append(Action(item.path, action, OWNERSHIP_MANAGED, item.adapter, reason))
        plan.manifest_files[item.path] = {
            "adapter": item.adapter,
            "ownership": OWNERSHIP_MANAGED,
            "sha256": new_hash,
        }

    for rel in sorted(set(previous) - desired_paths):
        entry = previous[rel]
        if entry.get("ownership") != OWNERSHIP_MANAGED:
            continue  # seeds belong to the firm once written; never delete them
        disk = _disk_hash(root, rel, True)
        disk_binary = _disk_hash(root, rel, False)
        adapter = entry.get("adapter", "")
        if disk is None:
            plan.actions.append(Action(rel, "forget", OWNERSHIP_MANAGED, adapter))
        elif entry["sha256"] in (disk, disk_binary):
            plan.actions.append(Action(rel, "delete", OWNERSHIP_MANAGED, adapter))
            plan.retired_hashes[rel] = entry["sha256"]
        else:
            plan.actions.append(Action(rel, "conflict", OWNERSHIP_MANAGED, adapter, "retired-modified"))
            plan.manifest_files[rel] = dict(entry)
    plan.actions.sort(key=lambda a: a.path)
    return plan
