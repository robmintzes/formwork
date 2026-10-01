"""Wizard draft state and operations, independent of HTTP so they are testable.

All writes go through the engine: ``init_workspace`` / ``render_workspace`` for
workspaces, plus atomic writes of draft inputs into an initialized workspace's
``firm/`` folder after a successful dry-run plan.
"""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import tempfile
from typing import Any

from toolkit_engine.adapters import render_all
from toolkit_engine.apply import atomic_write
from toolkit_engine.checks import check_outputs
from toolkit_engine.diagnostics import Diagnostics
from toolkit_engine.jsonio import JsonInputError, loads_strict
from toolkit_engine.paths import UnsafePathError, check_relative_path, check_workspace_root, guard_target
from toolkit_engine.profile import CONFIG_FILE, load_profile
from toolkit_engine.workspace import (
    FIRM_DIR,
    WORKSPACE_MARKER,
    EngineError,
    foundation_root,
    init_workspace,
    render_workspace,
)

DRAFT_SUFFIXES = (".json", ".svg", ".png", ".ttf", ".otf", ".txt", ".md")
TEXT_SUFFIXES = (".json", ".svg", ".txt", ".md")
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_DRAFT_BYTES = 48 * 1024 * 1024
MAX_DRAFT_FILES = 200


class WizardError(ValueError):
    """A request the wizard refuses; carries a stable code for the client."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _diag_report(diags: Diagnostics) -> dict[str, Any]:
    counts = {"error": 0, "warning": 0, "info": 0}
    for item in diags.items:
        counts[item.severity] += 1
    return {"diagnostics": diags.as_list(), "counts": counts, "outcome": "fail" if diags.has_errors else "pass"}


class WizardSession:
    def __init__(self, foundation: Path | None = None) -> None:
        self.foundation = (foundation or foundation_root()).resolve()
        self.source: str | None = None
        self.files: dict[str, bytes] = {}
        self.preview: dict[str, bytes] = {}

    # ----- starters -------------------------------------------------------
    def starters(self) -> list[dict[str, Any]]:
        result = []
        for config in sorted((self.foundation / "profiles").glob("*/firm.json")):
            try:
                data = loads_strict(config.read_text(encoding="utf-8-sig"))
                profile = data.get("profile", {})
                identity = data.get("identity", {})
            except (JsonInputError, OSError, AttributeError):
                continue
            result.append(
                {
                    "id": config.parent.name,
                    "display_name": identity.get("display_name", config.parent.name),
                    "description": profile.get("description", ""),
                    "fictional": bool(profile.get("fictional", False)),
                }
            )
        return result

    def start_from_profile(self, profile_id: str) -> dict[str, Any]:
        ids = {item["id"] for item in self.starters()}
        if profile_id not in ids:
            raise WizardError("starter.unknown", "Unknown starter profile {!r}.".format(profile_id))
        return self._start(self.foundation / "profiles" / profile_id, "profile:" + profile_id)

    def start_from_workspace(self, workspace: str) -> dict[str, Any]:
        root = self._vet(workspace)
        if not (root / WORKSPACE_MARKER).is_file():
            raise WizardError("workspace.not-initialized", "That folder is not an initialized workspace.")
        return self._start(root / FIRM_DIR, "workspace")

    def _start(self, firm_dir: Path, source: str) -> dict[str, Any]:
        diags = Diagnostics()
        profile = load_profile(firm_dir, diags)
        if profile is None:
            raise WizardError("starter.invalid", "The starting configuration does not validate; fix it with toolkit config validate first.")
        self.files = dict(profile.files)
        self.source = source
        self.preview = {}
        return self.state()

    # ----- draft ------------------------------------------------------------
    def _require_draft(self) -> None:
        if self.source is None:
            raise WizardError("draft.missing", "Start from a profile or workspace first.")

    def state(self) -> dict[str, Any]:
        if self.source is None:
            return {"source": None, "files": {}}
        listing = {}
        for path, content in sorted(self.files.items()):
            entry: dict[str, Any] = {"size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
            if path.lower().endswith(TEXT_SUFFIXES):
                entry["text"] = content.decode("utf-8", errors="replace")
            listing[path] = entry
        return {"source": self.source, "files": listing}

    def put_files(self, files: dict[str, Any], remove: list[str]) -> dict[str, Any]:
        self._require_draft()
        if not isinstance(files, dict) or not isinstance(remove, list):
            raise WizardError("request.invalid", "Expected {files: {...}, remove: [...]}.")
        staged = dict(self.files)
        for path in remove:
            if not isinstance(path, str) or path not in staged:
                raise WizardError("draft.unknown-file", "Cannot remove {!r}: not in the draft.".format(path))
            if path == CONFIG_FILE:
                raise WizardError("draft.config-required", "firm.json cannot be removed.")
            del staged[path]
        for path, payload in files.items():
            staged[self._safe_draft_path(path)] = self._decode(path, payload)
        total = sum(len(content) for content in staged.values())
        if total > MAX_DRAFT_BYTES or len(staged) > MAX_DRAFT_FILES:
            raise WizardError("draft.too-large", "The draft exceeds the size or file-count limit.")
        self.files = staged
        self.preview = {}
        return self.state()

    @staticmethod
    def _safe_draft_path(path: Any) -> str:
        if not isinstance(path, str):
            raise WizardError("draft.path-invalid", "File paths must be strings.")
        problem = check_relative_path(path)
        if problem:
            raise WizardError("draft.path-invalid", "Path {!r} {}.".format(path, problem))
        if not path.lower().endswith(DRAFT_SUFFIXES):
            raise WizardError("draft.type-unsupported", "Draft files must be one of: {}.".format(", ".join(DRAFT_SUFFIXES)))
        return path

    @staticmethod
    def _decode(path: str, payload: Any) -> bytes:
        if not isinstance(payload, dict) or set(payload) not in ({"text"}, {"base64"}):
            raise WizardError("draft.payload-invalid", "Each file needs exactly one of 'text' or 'base64'.")
        if "text" in payload:
            if not isinstance(payload["text"], str):
                raise WizardError("draft.payload-invalid", "'text' must be a string.")
            content = payload["text"].replace("\r\n", "\n").encode("utf-8")
        else:
            try:
                content = base64.b64decode(str(payload["base64"]), validate=True)
            except (ValueError, TypeError) as exc:
                raise WizardError("draft.payload-invalid", "Invalid base64 for {}.".format(path)) from exc
        if len(content) > MAX_FILE_BYTES:
            raise WizardError("draft.too-large", "{} exceeds {} MiB.".format(path, MAX_FILE_BYTES // 1048576))
        return content

    def _materialize(self, directory: Path) -> None:
        for path, content in self.files.items():
            atomic_write(guard_target(directory, path), content)

    # ----- validate and preview ---------------------------------------------
    def validate(self) -> dict[str, Any]:
        self._require_draft()
        diags = Diagnostics()
        with tempfile.TemporaryDirectory(prefix="toolkit-wizard-") as tmp:
            draft = Path(tmp)
            self._materialize(draft)
            profile = load_profile(draft, diags)
            self.preview = {}
            if profile is not None:
                rendered = render_all(profile)
                diags.extend(rendered.diagnostics)
                check_outputs(rendered.files, diags)
                if not diags.has_errors:
                    self.preview = {item.path: item.content for item in rendered.files}
        report = _diag_report(diags)
        report["preview_files"] = sorted(self.preview)
        return report

    # ----- plan and apply ---------------------------------------------------
    def _vet(self, workspace: Any) -> Path:
        if not isinstance(workspace, str) or not workspace.strip():
            raise WizardError("workspace.path-invalid", "Enter an absolute folder path for the workspace.")
        candidate = Path(workspace.strip())
        if not candidate.is_absolute():
            raise WizardError("workspace.path-invalid", "The workspace path must be absolute.")
        try:
            return check_workspace_root(candidate, self.foundation)
        except UnsafePathError as exc:
            raise WizardError(exc.code, str(exc)) from exc

    def plan(self, workspace: str) -> dict[str, Any]:
        self._require_draft()
        root = self._vet(workspace)
        if not (root / WORKSPACE_MARKER).is_file():
            if root.exists() and any(root.iterdir()):
                raise WizardError("workspace.not-empty", "That folder is not empty and is not a workspace; choose an empty or new folder.")
            validation = self.validate()
            actions = [{"path": FIRM_DIR + "/" + p, "action": "create", "ownership": "input"} for p in sorted(self.files)]
            actions += [{"path": p, "action": "create", "ownership": "generated"} for p in validation["preview_files"]]
            return {"initialized": False, "outcome": validation["outcome"], "diagnostics": validation["diagnostics"], "actions": actions}
        with tempfile.TemporaryDirectory(prefix="toolkit-wizard-") as tmp:
            draft = Path(tmp)
            self._materialize(draft)
            try:
                report = render_workspace(root, dry_run=True, firm_dir=draft, foundation=self.foundation)
            except EngineError as exc:
                raise WizardError(exc.code, str(exc)) from exc
        firm_changes = self._firm_changes(root)
        return {
            "initialized": True,
            "outcome": report["summary"]["outcome"],
            "diagnostics": report["diagnostics"],
            "actions": firm_changes + report["plan"]["actions"],
            "summary": report["summary"],
        }

    def _firm_changes(self, root: Path) -> list[dict[str, Any]]:
        changes = []
        for path, content in sorted(self.files.items()):
            target = root / FIRM_DIR / Path(*path.split("/"))
            if not target.exists():
                changes.append({"path": FIRM_DIR + "/" + path, "action": "create", "ownership": "input"})
            elif target.read_bytes() != content:
                changes.append({"path": FIRM_DIR + "/" + path, "action": "update", "ownership": "input"})
        return changes

    def apply(self, workspace: str) -> dict[str, Any]:
        """Save the draft and render. Refuses unless a fresh plan passes."""
        plan = self.plan(workspace)
        if plan["outcome"] != "pass":
            raise WizardError("plan.blocked", "The plan has errors or conflicts; resolve them before generating.")
        root = self._vet(workspace)
        try:
            if not plan["initialized"]:
                with tempfile.TemporaryDirectory(prefix="toolkit-wizard-") as tmp:
                    draft = Path(tmp)
                    self._materialize(draft)
                    init_report = init_workspace(draft, root, foundation=self.foundation)
                if init_report["summary"]["outcome"] != "pass":
                    raise WizardError("init.failed", "Workspace initialization failed.")
            else:
                for path, content in sorted(self.files.items()):
                    atomic_write(guard_target(root, FIRM_DIR + "/" + path), content)
            report = render_workspace(root, foundation=self.foundation)
        except (EngineError, UnsafePathError) as exc:
            raise WizardError(getattr(exc, "code", "apply.failed"), str(exc)) from exc
        self.source = "workspace"
        return {"outcome": report["summary"]["outcome"], "diagnostics": report["diagnostics"], "summary": report["summary"]}
