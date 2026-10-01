"""Argument parser and terminal presentation for the toolkit CLI."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import sys
from typing import Any, Mapping, Sequence

from toolkit_cli import __version__
from toolkit_cli.doctor import (
    PROFILE_AUTHORING,
    PROFILE_REVIT_HOST,
    format_text as format_doctor_text,
    run_doctor,
    write_json,
)
from toolkit_cli.generate import add_generation_commands, run_generation_command
from toolkit_cli.results import report_exit_code
from toolkit_cli.verify import verify_and_write


def _default_mcp_python(repo_root: Path) -> Path:
    relative = (
        Path("servers/revit-mcp/mcp-server/.venv/Scripts/python.exe")
        if platform.system() == "Windows"
        else Path("servers/revit-mcp/mcp-server/.venv/bin/python")
    )
    candidate = repo_root / relative
    return candidate if candidate.is_file() else Path(sys.executable)


def _default_evidence_dir(repo_root: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return repo_root / ".logs" / "live-verification" / timestamp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="toolkit",
        description="Firm-neutral diagnostics, workspace generation, and live verification tooling.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    doctor = commands.add_parser(
        "doctor", help="Inspect authoring or Revit-host prerequisites."
    )
    doctor.add_argument(
        "--profile",
        choices=(PROFILE_AUTHORING, PROFILE_REVIT_HOST),
        default=PROFILE_AUTHORING,
    )
    doctor.add_argument("--repository", type=Path, default=Path.cwd())
    doctor.add_argument(
        "--routes-url",
        default=os.environ.get(
            "REVIT_ROUTES_BASE_URL", "http://127.0.0.1:48884/placeholder"
        ),
    )
    doctor.add_argument(
        "--mcp-url",
        default="http://127.0.0.1:3001/mcp",
    )
    doctor.add_argument("--format", choices=("text", "json"), default="text")
    doctor.add_argument(
        "--output", type=Path, help="Also write the complete JSON report here."
    )

    verify = commands.add_parser(
        "verify", help="Run live host checks and write redacted evidence."
    )
    verify_targets = verify.add_subparsers(dest="verify_target", required=True)
    revit = verify_targets.add_parser(
        "revit", help="Exercise the read-only Revit Routes and MCP contracts."
    )
    revit.add_argument("--repository", type=Path, default=Path.cwd())
    revit.add_argument(
        "--routes-url",
        default=os.environ.get(
            "REVIT_ROUTES_BASE_URL", "http://127.0.0.1:48884/placeholder"
        ),
    )
    revit.add_argument(
        "--mcp-python",
        type=Path,
        help="Python executable from the prepared MCP virtual environment.",
    )
    revit.add_argument(
        "--expected-context",
        choices=("any", "none", "family", "project"),
        default="any",
    )
    revit.add_argument("--manual-checks", type=Path)
    revit.add_argument("--output-dir", type=Path)
    revit.add_argument("--timeout", type=float, default=2.0)
    revit.add_argument(
        "--routes-reset-confirmed",
        action="store_true",
        help=(
            "Confirm Revit was restarted or Routes was toggled off/on after "
            "the most recent pyRevit Reload."
        ),
    )
    workspace = verify_targets.add_parser(
        "workspace",
        help="Record live-host evidence for a generated firm workspace.",
    )
    workspace.add_argument("--workspace", type=Path, required=True)
    workspace.add_argument("--manual-checks", type=Path, help="Filled checklist (see docs/verification).")
    workspace.add_argument("--revit-version", help="Revit year tested, for example 2026.")
    workspace.add_argument("--output-dir", type=Path)
    add_generation_commands(commands)
    serve = commands.add_parser("serve", help="Run the local onboarding wizard (loopback only).")
    serve.add_argument("--port", type=int, default=0, help="Port on 127.0.0.1 (default: a free port).")
    serve.add_argument("--no-open", action="store_true", help="Print the URL without opening a browser.")
    return parser


def _format_verify_text(
    report: Mapping[str, Any], paths: Mapping[str, Path]
) -> str:
    lines = [
        "Live Revit verification",
        "Outcome: {}".format(str(report["summary"]["outcome"]).upper()),
        "",
    ]
    for check in report["checks"]:
        required = " required" if check.get("required") else ""
        lines.append(
            "[{status:<4}] {title}{required} - {summary}".format(
                status=str(check["status"]).upper(),
                title=check["title"],
                required=required,
                summary=check["summary"],
            )
        )
    lines.extend(
        (
            "",
            "JSON evidence: {}".format(paths["json"]),
            "Markdown evidence: {}".format(paths["markdown"]),
        )
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "serve":
        from toolkit_wizard.server import serve as serve_wizard

        serve_wizard(args.port, open_browser=not args.no_open)
        return 0

    if args.command in ("config", "init", "render", "validate"):
        return run_generation_command(args)

    try:
        if args.command == "doctor":
            report = run_doctor(
                args.repository,
                profile=args.profile,
                routes_url=args.routes_url,
                mcp_url=args.mcp_url,
            )
            if args.output:
                write_json(report, args.output)
            if args.format == "json":
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                print(format_doctor_text(report))
            return report_exit_code(report)

        if args.command == "verify" and args.verify_target == "workspace":
            from toolkit_cli.verify_workspace import format_text, run_workspace_verification, write_workspace_evidence

            repo_root = Path(__file__).resolve().parents[1]
            output_dir = args.output_dir or (
                repo_root / ".logs" / "workspace-verification" / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            )
            report = run_workspace_verification(
                args.workspace, manual_checks_path=args.manual_checks, revit_version=args.revit_version
            )
            paths = write_workspace_evidence(report, output_dir)
            print(format_text(report, paths))
            return report["exit_code"]

        if args.command == "verify" and args.verify_target == "revit":
            if not args.routes_reset_confirmed:
                print(
                    "toolkit: live verification refused: restart Revit or toggle "
                    "Routes off/on after pyRevit Reload, then pass "
                    "--routes-reset-confirmed.",
                    file=sys.stderr,
                )
                return 2
            repo_root = args.repository.resolve()
            mcp_python = args.mcp_python or _default_mcp_python(repo_root)
            output_dir = args.output_dir or _default_evidence_dir(repo_root)
            report, paths, exit_code = verify_and_write(
                args.routes_url,
                str(mcp_python),
                output_dir,
                manual_checks_path=args.manual_checks,
                timeout=args.timeout,
                expected_context=args.expected_context,
            )
            print(_format_verify_text(report, paths))
            return exit_code
    except (OSError, ValueError) as exc:
        print("toolkit: error: {}".format(exc), file=sys.stderr)
        return 2

    parser.error("unknown command")
    return 2
