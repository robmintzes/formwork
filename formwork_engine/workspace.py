"""High-level operations shared by the CLI, the wizard, and agents: init and render."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Callable

from formwork_engine import WORKSPACE_SCHEMA_VERSION, __version__
from formwork_engine.adapters import known_adapters, render_all
from formwork_engine.apply import Writer, apply_plan, atomic_write
from formwork_engine.checks import check_outputs
from formwork_engine.diagnostics import Diagnostics
from formwork_engine.jsonio import JsonInputError, dumps_canonical, load_strict
from formwork_engine.overrides import apply_overrides, collect_overrides
from formwork_engine.planner import CONFLICT_REASONS, ManifestError, load_manifest, plan_changes, render_manifest
from formwork_engine.profile import load_profile
from formwork_engine.paths import UnsafePathError, check_workspace_root, guard_target
from formwork_engine.state import LEGACY_STATE_DIR, STATE_DIR, locate_state, migrate_state

FIRM_DIR = "firm"
WORKSPACE_MARKER = STATE_DIR + "/workspace.json"
WORKSPACE_KIND = "formwork-workspace"
# Written by engines before 0.3.0 (ADR 0010); read, then rewritten on migration.
LEGACY_WORKSPACE_KIND = "toolkit-workspace"


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
        "formwork_version": __version__,
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
        "formwork-config-validation",
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
            "formwork-init", diags, summary={"outcome": "fail", "counts": _counts(diags), "written": False}
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
        "formwork-init",
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


def is_workspace(root: Path) -> bool:
    """True when *root* holds a workspace marker, under either state folder name."""
    return any((root / name / "workspace.json").is_file() for name in (STATE_DIR, LEGACY_STATE_DIR))


def _locate_state(root: Path) -> str:
    try:
        return locate_state(root)
    except UnsafePathError as exc:
        raise EngineError(exc.code, str(exc)) from exc


def _read_marker(root: Path, state_dir: str) -> dict[str, Any]:
    path = root / state_dir / "workspace.json"
    if not path.is_file():
        raise EngineError(
            "workspace.not-initialized",
            "No {} found; run 'formwork init' first.".format(WORKSPACE_MARKER),
        )
    try:
        marker = load_strict(path)
    except (JsonInputError, OSError) as exc:
        raise EngineError("workspace.marker-invalid", "Cannot read {}: {}".format(WORKSPACE_MARKER, exc)) from exc
    if not isinstance(marker, dict) or marker.get("kind") not in (WORKSPACE_KIND, LEGACY_WORKSPACE_KIND):
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
    state_dir = _locate_state(root)
    legacy_state = state_dir == LEGACY_STATE_DIR
    marker = _read_marker(root, state_dir)
    diags = Diagnostics()

    def blocked(**extra: Any) -> dict[str, Any]:
        return _report(
            "formwork-render",
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
        manifest = load_manifest(root, known_adapters(), state_dir=state_dir)
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
    manifest_file = root / state_dir / "manifest.json"
    manifest_current = manifest_file.is_file() and (
        manifest_file.read_bytes().replace(b"\r\n", b"\n") == manifest_text.encode("utf-8")
    )
    if legacy_state:
        diags.info(
            "workspace.state-migration",
            LEGACY_STATE_DIR + "/",
            "This workspace predates Formwork 0.3; rendering moves {}/ to {}/.".format(LEGACY_STATE_DIR, STATE_DIR),
        )
    changes = [a.as_dict() for a in plan.changes]
    summary: dict[str, Any] = {
        "outcome": "fail" if diags.has_errors else "pass",
        "counts": _counts(diags),
        "actions": plan.counts(),
        "changes": len(changes) + (0 if manifest_current else 1) + (1 if legacy_state else 0),
        "conflicts": len(plan.conflicts),
        "written": False,
    }
    report = _report(
        "formwork-render",
        diags,
        dry_run=dry_run,
        workspace_id=workspace_id,
        profile_id=profile.config.profile_id,
        plan={
            "actions": [a.as_dict() for a in plan.actions],
            "manifest_changes": not manifest_current,
            "state_migration": {"from": LEGACY_STATE_DIR + "/", "to": STATE_DIR + "/"} if legacy_state else None,
        },
        summary=summary,
    )
    if diags.has_errors or dry_run:
        return report
    if summary["changes"] == 0:
        return report
    try:
        if legacy_state:
            # Move first: apply_plan writes the manifest under STATE_DIR. A failure
            # after this point leaves a readable workspace that the next render finishes.
            migrate_state(root)
            write(
                guard_target(root, WORKSPACE_MARKER),
                dumps_canonical(dict(marker, kind=WORKSPACE_KIND)).encode("utf-8"),
            )
        emptied = apply_plan(root, plan, desired, manifest_text, write=write)
    except UnsafePathError as exc:
        raise EngineError(exc.code, str(exc)) from exc
    summary["written"] = True
    summary["empty_directories"] = emptied
    return report
