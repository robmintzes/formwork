"""Firm overrides of generated (managed) files (FOUNDATION_SPEC section 4.7).

A firm that wants to own the content of one generated file puts its version at
``firm/overrides/<workspace-relative path>``. Rendering then uses the override
instead of the generated content, records both hashes in the manifest, and
warns when the generated version changes later so the firm can review it.
Overrides are deliberate, reviewable inputs: unlike editing a managed file in
place, they never produce a conflict and they survive upgrades.
"""

from __future__ import annotations

from pathlib import Path

from formwork_engine.diagnostics import Diagnostics
from formwork_engine.outputs import OWNERSHIP_MANAGED, OutputFile, content_hash
from formwork_engine.paths import UnsafePathError, check_relative_path, guard_target, is_reparse_point

OVERRIDES_DIR = "overrides"
MAX_OVERRIDE_BYTES = 8 * 1024 * 1024


def collect_overrides(firm_dir: Path, diags: Diagnostics) -> dict[str, bytes]:
    """Read every file under ``firm/overrides/`` (safe paths only)."""
    base = firm_dir / OVERRIDES_DIR
    if not base.exists():
        return {}
    if is_reparse_point(base) or not base.is_dir():
        diags.error("override.path-invalid", "firm/" + OVERRIDES_DIR, "firm/overrides must be a real directory, not a link or file.")
        return {}
    result: dict[str, bytes] = {}
    for path in sorted(base.rglob("*")):
        if path.is_dir() and not is_reparse_point(path):
            continue
        rel = path.relative_to(base).as_posix()
        location = "firm/{}/{}".format(OVERRIDES_DIR, rel)
        problem = check_relative_path(rel)
        if problem:
            diags.error("override.path-invalid", location, "Override path {}.".format(problem))
            continue
        try:
            target = guard_target(base, rel)
        except UnsafePathError as exc:
            diags.error(exc.code, location, str(exc))
            continue
        if target.stat().st_size > MAX_OVERRIDE_BYTES:
            diags.error("override.too-large", location, "Overrides are limited to {} MiB.".format(MAX_OVERRIDE_BYTES // 1048576))
            continue
        result[rel] = target.read_bytes()
    return result


def apply_overrides(
    files: list[OutputFile],
    overrides: dict[str, bytes],
    previous: dict[str, dict[str, object]],
    diags: Diagnostics,
) -> tuple[list[OutputFile], dict[str, str]]:
    """Replace generated content with overrides.

    Returns the new file list and ``{path: generated_sha256}`` for overridden files.
    """
    by_path = {item.path: index for index, item in enumerate(files)}
    result = list(files)
    generated: dict[str, str] = {}
    for rel, content in sorted(overrides.items()):
        location = "firm/{}/{}".format(OVERRIDES_DIR, rel)
        index = by_path.get(rel)
        if index is None:
            diags.error(
                "override.orphan",
                location,
                "No generated file exists at {}; an override can only replace generated output.".format(rel),
                "Remove the override, or add the file as a firm-owned file directly in the workspace (outside firm/).",
            )
            continue
        item = files[index]
        if item.ownership != OWNERSHIP_MANAGED:
            diags.error(
                "override.not-managed",
                location,
                "{} is a seed file and already belongs to the firm.".format(rel),
                "Delete the override and edit {} directly.".format(rel),
            )
            continue
        generated[rel] = item.sha256
        body = content.replace(b"\r\n", b"\n") if item.text else content
        result[index] = OutputFile(rel, body, item.adapter, OWNERSHIP_MANAGED, item.text)
        earlier = previous.get(rel, {})
        if earlier.get("override") and earlier.get("generated_sha256") not in (None, item.sha256):
            diags.warning(
                "override.upstream-changed",
                location,
                "The generated version of {} changed since this override was last reviewed.".format(rel),
                "Compare the override with the new generated output (for example, render a scratch copy without the override) and update it.",
            )
        elif content_hash(body, item.text) == item.sha256:
            diags.info("override.redundant", location, "The override is identical to the generated content; it can be removed.")
        else:
            diags.info("override.applied", location, "Using the firm's override instead of the generated content.")
    return result, generated
