"""High-level operations shared by the CLI, the wizard, and agents: init and render."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Callable

from toolkit_engine import WORKSPACE_SCHEMA_VERSION, __version__
from toolkit_engine.adapters import render_all
from toolkit_engine.apply import Writer, apply_plan, atomic_write
from toolkit_engine.checks import check_outputs
from toolkit_engine.diagnostics import Diagnostics
from toolkit_engine.jsonio import JsonInputError, dumps_canonical, load_strict
from toolkit_engine.overrides import apply_overrides, collect_overrides
from toolkit_engine.planner import CONFLICT_REASONS, ManifestError, load_manifest, plan_changes, render_manifest
from toolkit_engine.profile import load_profile
from toolkit_engine.paths import UnsafePathError, check_workspace_root, guard_target

FIRM_DIR = "firm"
WORKSPACE_MARKER = ".toolkit/workspace.json"
WORKSPACE_KIND = "toolkit-workspace"


class EngineError(ValueError):
    """The operation cannot run (unsafe destination, unreadable state). Exit code 2."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def foundation_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _version_key(version: str) -> tuple[tuple[int, ...], int, str]:
    match = re.match(r"^(\d+(?:\.\d+)*)(?:-(.+))?$", version)
    if not match:
        return ((0,), 0, version)
    numbers = tuple(int(part) for part in match.group(1).split("."))
    prerelease = match.group(2)
    # A release sorts after its pre-releases.
    return (numbers, 0 if prerelease else 1, prerelease or "")


def _report(kind: str, diags: Diagnostics, **extra: Any) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": 1,
        "kind": kind,
        "toolkit_version": __version__,
        "diagnostics": diags.as_list(),
    }
    report.update(extra)
    return report


def _counts(diags: Diagnostics) -> dict[str, int]:
    counts = {"error": 0, "warning": 0, "info": 0}
    for item in diags.items:
        counts[item.severity] += 1
    return counts


def validate_firm(firm_dir: Path) -> dict[str, Any]:
    """Validate a firm configuration directory without rendering."""
    diags = Diagnostics()
    profile = load_profile(firm_dir, diags)
    if profile is not None:
        # Rendering in memory surfaces adapter-level diagnostics (unsupported choices).
        rendered = render_all(profile)
        diags.extend(rendered.diagnostics)
        desired, _ = apply_overrides(rendered.files, collect_overrides(firm_dir, diags), {}, diags)
        check_outputs(desired, diags)
    return _report(
        "toolkit-config-validation",
        diags,
        profile_id=profile.config.profile_id if profile else None,
        summary={"outcome": "fail" if diags.has_errors else "pass", "counts": _counts(diags)},
    )


def init_workspace(profile_dir: Path, workspace: Path, *, foundation: Path | None = None) -> dict[str, Any]:
    """Create a workspace and copy a validated profile into its firm/ folder."""
    root = _vet_root(workspace, foundation)
    if root.exists() and any(root.iterdir()):
        raise EngineError(
            "workspace.not-empty",
            "Initialization needs a missing or empty directory; use render for an existing workspace.",
        )
    diags = Diagnostics()
    profile = load_profile(profile_dir, diags)
    if profile is None:
        return _report(
            "toolkit-init", diags, summary={"outcome": "fail", "counts": _counts(diags), "written": False}
        )
    root.mkdir(parents=True, exist_ok=True)
    for rel in sorted(profile.files):
        atomic_write(guard_target(root, FIRM_DIR + "/" + rel), profile.files[rel])
    marker = dumps_canonical(
        {
            "schema_version": WORKSPACE_SCHEMA_VERSION,
            "kind": WORKSPACE_KIND,
            "workspace_id": profile.config.technical.workspace_id,
        }
    )
    atomic_write(guard_target(root, WORKSPACE_MARKER), marker.encode("utf-8"))
    return _report(
        "toolkit-init",
        diags,
        workspace_id=profile.config.technical.workspace_id,
        profile_id=profile.config.profile_id,
        firm_files=sorted(FIRM_DIR + "/" + rel for rel in profile.files),
        summary={"outcome": "pass", "counts": _counts(diags), "written": True},
    )


def _vet_root(workspace: Path, foundation: Path | None) -> Path:
    try:
        return check_workspace_root(workspace, foundation or foundation_root())
    except UnsafePathError as exc:
        raise EngineError(exc.code, str(exc)) from exc


def _read_marker(root: Path) -> dict[str, Any]:
    path = root / ".toolkit" / "workspace.json"
    if not path.is_file():
        raise EngineError(
            "workspace.not-initialized",
            "No {} found; run 'toolkit init' first.".format(WORKSPACE_MARKER),
        )
    try:
        marker = load_strict(path)
    except (JsonInputError, OSError) as exc:
        raise EngineError("workspace.marker-invalid", "Cannot read {}: {}".format(WORKSPACE_MARKER, exc)) from exc
    if not isinstance(marker, dict) or marker.get("kind") != WORKSPACE_KIND:
        raise EngineError("workspace.marker-invalid", "{} is not a workspace marker.".format(WORKSPACE_MARKER))
    if not isinstance(marker.get("schema_version"), int) or marker["schema_version"] > WORKSPACE_SCHEMA_VERSION:
        raise EngineError("workspace.schema-too-new", "The workspace was created by a newer foundation.")
    return marker


def render_workspace(
    workspace: Path,
    *,
    dry_run: bool = False,
    foundation: Path | None = None,
    write: Writer = atomic_write,
    on_planned: Callable[[Any], None] | None = None,
    firm_dir: Path | None = None,
) -> dict[str, Any]:
    """Plan and (unless *dry_run*) apply generation for an initialized workspace.

    *firm_dir* substitutes draft inputs for the workspace's ``firm/`` folder so
    a client (the wizard) can preview a plan before saving anything. It is only
    accepted for dry runs: applied output must always come from ``firm/``.
    """
    if firm_dir is not None and not dry_run:
        raise ValueError("firm_dir overrides are only allowed for dry runs")
    root = _vet_root(workspace, foundation)
    marker = _read_marker(root)
    diags = Diagnostics()

    def blocked(**extra: Any) -> dict[str, Any]:
        return _report(
            "toolkit-render",
            diags,
            dry_run=dry_run,
            summary={"outcome": "fail", "counts": _counts(diags), "written": False, **extra},
        )

    profile = load_profile(firm_dir if firm_dir is not None else root / FIRM_DIR, diags)
    if profile is None:
        return blocked()
    workspace_id = profile.config.technical.workspace_id
    if marker.get("workspace_id") != workspace_id:
        diags.error(
            "workspace.id-mismatch",
            "firm/firm.json#/technical/workspace_id",
            "firm.json names workspace {!r} but this workspace was initialized as {!r}.".format(
                workspace_id, marker.get("workspace_id")
            ),
            "workspace_id is stable technical identity; changing it is a migration, not a rebrand.",
        )
        return blocked()

    try:
        manifest = load_manifest(root)
    except ManifestError as exc:
        raise EngineError(exc.code, str(exc)) from exc
    previous_files: dict[str, dict[str, str]] = {}
    if manifest is not None:
        recorded_version = str(manifest.get("foundation_version", "0"))
        if _version_key(recorded_version) > _version_key(__version__):
            raise EngineError(
                "foundation.downgrade",
                "The workspace was rendered by foundation {} which is newer than this one ({}).".format(
                    recorded_version, __version__
                ),
            )
        previous_files = manifest["files"]

    rendered = render_all(profile)
    diags.extend(rendered.diagnostics)
    # Overrides are workspace inputs: always read them from the workspace's own
    # firm/, even when a draft supplies the rest of the inputs (wizard plans).
    desired, generated_hashes = apply_overrides(
        rendered.files, collect_overrides(root / FIRM_DIR, diags), previous_files, diags
    )
    check_outputs(desired, diags)
    if diags.has_errors:
        return blocked()

    try:
        plan = plan_changes(root, desired, previous_files)
    except UnsafePathError as exc:
        raise EngineError(exc.code, str(exc)) from exc
    if on_planned is not None:
        on_planned(plan)
    for conflict in plan.conflicts:
        message, hint = CONFLICT_REASONS[conflict.reason]
        diags.error("conflict." + conflict.reason, conflict.path, message, hint)

    for rel, generated_sha in generated_hashes.items():
        plan.manifest_files[rel].update({"override": True, "generated_sha256": generated_sha})
    manifest_text = render_manifest(
        foundation_version=__version__,
        workspace_id=workspace_id,
        profile_id=profile.config.profile_id,
        inputs_sha256=profile.inputs_sha256,
        files=plan.manifest_files,
    )
    manifest_current = (root / ".toolkit" / "manifest.json").is_file() and (
        (root / ".toolkit" / "manifest.json").read_bytes().replace(b"\r\n", b"\n") == manifest_text.encode("utf-8")
    )
    changes = [a.as_dict() for a in plan.changes]
    summary: dict[str, Any] = {
        "outcome": "fail" if diags.has_errors else "pass",
        "counts": _counts(diags),
        "actions": plan.counts(),
        "changes": len(changes) + (0 if manifest_current else 1),
        "conflicts": len(plan.conflicts),
        "written": False,
    }
    report = _report(
        "toolkit-render",
        diags,
        dry_run=dry_run,
        workspace_id=workspace_id,
        profile_id=profile.config.profile_id,
        plan={"actions": [a.as_dict() for a in plan.actions], "manifest_changes": not manifest_current},
        summary=summary,
    )
    if diags.has_errors or dry_run:
        return report
    if summary["changes"] == 0:
        return report
    try:
        emptied = apply_plan(root, plan, desired, manifest_text, write=write)
    except UnsafePathError as exc:
        raise EngineError(exc.code, str(exc)) from exc
    summary["written"] = True
    summary["empty_directories"] = emptied
    return report
