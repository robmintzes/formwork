"""CLI adapters for workspace generation: ``config validate``, ``init``, ``render``.

Thin presentation over toolkit_engine.workspace. Exit codes: 0 success
(including no-change and clean dry runs), 1 blocked (invalid configuration or
conflicts), 2 cannot run (usage, unsafe path, unreadable workspace state).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from toolkit_cli.results import report_exit_code
from toolkit_engine.workspace import EngineError, init_workspace, render_workspace, validate_firm


def add_generation_commands(commands: Any) -> None:
    config = commands.add_parser("config", help="Validate firm configuration.")
    config_targets = config.add_subparsers(dest="config_target", required=True)
    validate = config_targets.add_parser("validate", help="Validate firm.json, tokens, assets, and fonts.")
    validate.add_argument("--firm", type=Path, required=True, help="Folder containing firm.json.")
    _output_options(validate)

    init = commands.add_parser("init", help="Create a workspace from a profile; does not render.")
    init.add_argument("--profile", type=Path, required=True, help="Profile folder containing firm.json.")
    init.add_argument("--workspace", type=Path, required=True, help="Missing or empty destination folder.")
    _output_options(init)

    render = commands.add_parser("render", help="Plan and apply generation for a workspace.")
    render.add_argument("--workspace", type=Path, required=True)
    render.add_argument("--dry-run", action="store_true", help="Show the plan without writing anything.")
    _output_options(render)


def _output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--output", type=Path, help="Also write the complete JSON report here.")


def run_generation_command(args: argparse.Namespace) -> int:
    try:
        if args.command == "config":
            report = validate_firm(args.firm)
        elif args.command == "init":
            report = init_workspace(args.profile, args.workspace)
        else:
            report = render_workspace(args.workspace, dry_run=args.dry_run)
    except EngineError as exc:
        print("toolkit: error [{}]: {}".format(exc.code, exc), file=sys.stderr)
        return 2
    except OSError as exc:
        print("toolkit: error [io]: {}".format(exc), file=sys.stderr)
        return 2

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_text(report))
    return report_exit_code(report)


def format_text(report: dict[str, Any]) -> str:
    summary = report["summary"]
    kind = report["kind"]
    lines = []
    if kind == "toolkit-render":
        mode = "dry run" if report.get("dry_run") else "render"
        lines.append("Workspace {} ({}): {}".format(mode, report.get("workspace_id", "?"), summary["outcome"].upper()))
        actions = report.get("plan", {}).get("actions", [])
        shown = [a for a in actions if a["action"] not in ("unchanged", "skip")]
        for action in shown:
            reason = " ({})".format(action["reason"]) if action.get("reason") else ""
            lines.append("  {:<9} {}{}".format(action["action"], action["path"], reason))
        if actions and not shown:
            lines.append("  No changes: {} managed and seeded files are current.".format(len(actions)))
        if report.get("plan", {}).get("manifest_changes"):
            lines.append("  {:<9} .toolkit/manifest.json".format("write"))
        if summary.get("written"):
            lines.append("Applied {} change(s).".format(summary["changes"]))
            for directory in summary.get("empty_directories", []):
                lines.append("  Left empty directory: {}".format(directory))
        elif report.get("dry_run") and summary["outcome"] == "pass":
            lines.append("Dry run only; nothing was written.")
    elif kind == "toolkit-init":
        lines.append("Workspace init: {}".format(summary["outcome"].upper()))
        if summary.get("written"):
            lines.append("  Copied {} firm input file(s); run 'toolkit render' next.".format(len(report["firm_files"])))
    else:
        lines.append("Configuration ({}): {}".format(report.get("profile_id") or "?", summary["outcome"].upper()))

    for item in report["diagnostics"]:
        lines.append("[{}] {} {} - {}".format(item["severity"].upper(), item["code"], item["location"], item["message"]))
        if item.get("hint"):
            lines.append("        hint: {}".format(item["hint"]))
    return "\n".join(lines)
