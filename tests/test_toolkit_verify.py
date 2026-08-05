from __future__ import annotations

from contextlib import contextmanager
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import sys
import tempfile
import threading
from typing import Any, Iterator
import unittest
from unittest import mock

from toolkit_cli import verify


SECRET_PROJECT = "Museum of Extremely Secret Things"
SECRET_USER = "super-secret-owner@example.test"
SECRET_PATH = r"C:\Users\super-secret-owner\Models\classified.rvt"
SECRET_SESSION = "2b38d330-secret-session-never-retain"
TEST_SHA = "a" * 40


def _envelope(
    tool: str,
    *,
    status: str = "ok",
    risk_class: str = "read_only",
    observed_tool: str | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    data_by_tool: dict[str, dict[str, Any]] = {
        "revit_health_ping": {
            "revit_version": "2026",
            "revit_build": "20260701",
            "pyrevit_version": "5.2",
            "document_open": True,
            "extension_identity": {
                "component": "pyrevit-extension",
                "root": SECRET_PATH,
                "branch": "secret-branch",
                "sha": TEST_SHA,
                "short_sha": TEST_SHA[:8],
                "any_stale": False,
            },
        },
        "revit_project_info": {
            "title": SECRET_PROJECT,
            "path": SECRET_PATH,
            "is_workshared": True,
            "project_number": "A-100",
            "project_name": SECRET_PROJECT,
            "client_name": SECRET_USER,
            "project_address": None,
            "project_status": None,
            "issue_date": None,
        },
        "revit_project_levels": {
            "count": 1,
            "levels": [
                {"name": "Secret Level", "elevation_feet": 12.5, "id": 101}
            ],
        },
        "revit_project_worksets": {
            "workshared": True,
            "count": 1,
            "worksets": [
                {
                    "name": "Secret Workset",
                    "id": 102,
                    "is_open": True,
                    "owner": SECRET_USER,
                }
            ],
        },
        "revit_project_links": {
            "count": 1,
            "links": [
                {
                    "name": "Secret Link",
                    "id": 103,
                    "type": "revit",
                    "loaded": True,
                    "load_state": "loaded",
                    "path": SECRET_PATH,
                    "is_overlay": False,
                }
            ],
        },
    }
    payload: dict[str, Any] = {
        "status": status,
        "tool": observed_tool or tool,
        "risk_class": risk_class,
        "document": {
            "title": SECRET_PROJECT,
            "path": SECRET_PATH,
            "is_workshared": True,
        },
        "data": data_by_tool[tool],
        "messages": [],
        "next_actions": [],
    }
    if status == "error":
        payload["data"] = {}
        payload["error"] = {
            "code": error_code or "revit_error",
            "message": "Sensitive failure for " + SECRET_PROJECT,
            "checks": ["Ask " + SECRET_USER],
        }
    elif tool == "revit_health_ping":
        payload["build_identity"] = {
            "server": {
                "root": SECRET_PATH,
                "branch": "secret-branch",
                "sha": TEST_SHA,
                "short_sha": TEST_SHA[:8],
            }
        }
    return payload


def _host_status() -> dict[str, str]:
    return {
        "host": "Autodesk Revit 2026.1 build 20260701",
        "username": SECRET_USER,
        "session_id": SECRET_SESSION,
    }


def _route_responses(
    overrides: dict[str, tuple[int, str, bytes]] | None = None,
) -> dict[str, tuple[int, str, bytes]]:
    responses: dict[str, tuple[int, str, bytes]] = {
        "/routes/status": (
            200,
            "application/json",
            json.dumps(_host_status()).encode("utf-8"),
        )
    }
    for route in verify.ROUTES:
        responses["/placeholder" + route.path] = (
            200,
            "application/json",
            json.dumps(_envelope(route.tool)).encode("utf-8"),
        )
    responses.update(overrides or {})
    return responses


@contextmanager
def _serve(
    responses: dict[str, tuple[int, str, bytes]],
) -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
            status, content_type, body = responses.get(
                self.path,
                (404, "application/json", b'{"error":"not found"}'),
            )
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:{}/placeholder".format(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _mcp_protocol(
    overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    results = []
    for tool in verify.MCP_TOOLS:
        item: dict[str, Any] = {
            "requested_tool": tool,
            "observed_tool": tool,
            "risk_class": "read_only",
            "status": "ok",
            "error_code": None,
            "invocation_ok": True,
            "envelope_valid": True,
            "issues": [],
            # Unknown fields are ignored instead of leaking into evidence.
            "raw_debug": {"project": SECRET_PROJECT, "owner": SECRET_USER},
        }
        if tool == "revit_health_ping":
            item.update(
                extension_sha=TEST_SHA,
                extension_any_stale=False,
                server_sha=TEST_SHA,
            )
        item.update((overrides or {}).get(tool, {}))
        results.append(item)
    return {
        "protocol": verify.MCP_PROBE_PROTOCOL,
        "python_version": "3.12.9",
        "catalog_valid": True,
        "catalog_count": len(verify.MCP_TOOLS),
        "results": results,
        "debug_path": SECRET_PATH,
    }


def _runner_with(protocol: dict[str, Any]):
    def runner(python_executable: str, base_url: str, timeout: float):
        del python_executable, base_url, timeout
        return protocol

    return runner


def _check(report: dict[str, Any], check_id: str) -> dict[str, Any]:
    return next(item for item in report["checks"] if item["check_id"] == check_id)


class LiveVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch(
            "toolkit_cli.verify._git_provenance", return_value=(TEST_SHA, False)
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_fake_routes_and_all_mcp_tools_pass_without_retaining_data(self) -> None:
        with _serve(_route_responses()) as base_url:
            report = verify.run_verification(
                base_url,
                "/Users/super-secret-owner/.venv/bin/python",
                expected_context="project",
                timestamp="2026-08-05T02:00:00Z",
                mcp_runner=_runner_with(_mcp_protocol()),
            )

        self.assertEqual("pass", report["summary"]["outcome"])
        self.assertEqual(0, report["exit_code"])
        route_checks = [
            check
            for check in report["checks"]
            if check["check_id"].startswith("routes.revit_")
        ]
        self.assertEqual(5, len(route_checks))
        self.assertEqual(5, len([c for c in report["checks"] if c["check_id"].startswith("mcp.")]))
        host_check = _check(report, "routes.host_status")
        self.assertEqual("pass", _check(report, "context.consistency")["status"])
        self.assertEqual("pass", host_check["status"])
        self.assertEqual("2026", report["metadata"]["revit_version"])
        self.assertEqual("20260701", report["metadata"]["revit_build"])
        self.assertEqual("5.2", report["metadata"]["pyrevit_version"])
        self.assertEqual(
            "Autodesk Revit 2026.1 build 20260701",
            host_check["details"]["host_application"],
        )
        self.assertRegex(
            host_check["details"]["session_fingerprint"], r"^sha256:[0-9a-f]{16}$"
        )

        serialized = json.dumps(report, sort_keys=True)
        for sensitive in (
            SECRET_PROJECT,
            SECRET_USER,
            SECRET_PATH,
            SECRET_SESSION,
            "super-secret-owner",
        ):
            self.assertNotIn(sensitive, serialized)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = verify.write_evidence(report, temp_dir)
            first_json = paths["json"].read_text(encoding="utf-8")
            first_markdown = paths["markdown"].read_text(encoding="utf-8")
            verify.write_evidence(report, temp_dir)
            self.assertEqual(first_json, paths["json"].read_text(encoding="utf-8"))
            self.assertEqual(
                first_markdown, paths["markdown"].read_text(encoding="utf-8")
            )
            self.assertIn("- Revit version: `2026`", first_markdown)
            self.assertIn("- Revit build: `20260701`", first_markdown)
            self.assertIn("- pyRevit version: `5.2`", first_markdown)
            for sensitive in (SECRET_PROJECT, SECRET_USER, SECRET_PATH, SECRET_SESSION):
                self.assertNotIn(sensitive, first_json)
                self.assertNotIn(sensitive, first_markdown)

    def test_non_loopback_url_is_refused_without_network_or_mcp_calls(self) -> None:
        runner = mock.Mock(side_effect=AssertionError("runner must not be called"))

        report = verify.run_verification(
            "http://192.0.2.25:48884/placeholder",
            "python",
            mcp_runner=runner,
            timestamp="2026-08-05T02:00:00Z",
        )

        runner.assert_not_called()
        self.assertEqual("fail", report["summary"]["outcome"])
        self.assertEqual(1, report["exit_code"])
        self.assertEqual("fail", _check(report, "security.loopback_url")["status"])
        self.assertEqual("skip", _check(report, "routes.host_status")["status"])
        self.assertNotIn("192.0.2.25", json.dumps(report))

    def test_unreachable_routes_are_explicit_failures(self) -> None:
        with socket.socket() as probe_socket:
            probe_socket.bind(("127.0.0.1", 0))
            unused_port = probe_socket.getsockname()[1]

        report = verify.run_verification(
            "http://127.0.0.1:{}/placeholder".format(unused_port),
            "python",
            timeout=0.1,
            timestamp="2026-08-05T02:00:00Z",
            mcp_runner=_runner_with(_mcp_protocol()),
        )

        self.assertEqual("fail", _check(report, "routes.host_status")["status"])
        for route in verify.ROUTES:
            route_check = _check(report, "routes." + route.tool)
            self.assertEqual("fail", route_check["status"])
            self.assertEqual("unreachable", route_check["details"]["issue"])

    def test_malformed_json_wrong_risk_and_tool_mismatch_are_distinct(self) -> None:
        overrides = {
            "/placeholder/health/": (200, "application/json", b"{not-json"),
            "/placeholder/project/info/": (
                200,
                "application/json",
                json.dumps(
                    _envelope("revit_project_info", risk_class="write")
                ).encode("utf-8"),
            ),
            "/placeholder/project/levels/": (
                200,
                "application/json",
                json.dumps(
                    _envelope(
                        "revit_project_levels",
                        observed_tool="revit_project_links",
                    )
                ).encode("utf-8"),
            ),
        }
        with _serve(_route_responses(overrides)) as base_url:
            report = verify.run_verification(
                base_url,
                "python",
                expected_context="project",
                timestamp="2026-08-05T02:00:00Z",
                mcp_runner=_runner_with(_mcp_protocol()),
            )

        self.assertEqual(
            "malformed_json",
            _check(report, "routes.revit_health_ping")["details"]["issue"],
        )
        self.assertIn(
            "risk_class_not_read_only",
            _check(report, "routes.revit_project_info")["details"]["issues"],
        )
        self.assertIn(
            "tool_id_mismatch",
            _check(report, "routes.revit_project_levels")["details"]["issues"],
        )

    def test_per_tool_shapes_reject_nonfinite_counts_and_success_errors(self) -> None:
        levels = _envelope("revit_project_levels")
        levels["data"]["count"] = 2
        levels["data"]["levels"][0]["elevation_feet"] = float("nan")
        info = _envelope("revit_project_info")
        info["error"] = {
            "code": "secret_code",
            "message": SECRET_PROJECT,
            "checks": [],
        }
        overrides = {
            "/placeholder/project/levels/": (
                200,
                "application/json",
                json.dumps(levels).encode("utf-8"),
            ),
            "/placeholder/project/info/": (
                200,
                "application/json",
                json.dumps(info).encode("utf-8"),
            ),
        }
        with _serve(_route_responses(overrides)) as base_url:
            report = verify.run_verification(
                base_url,
                "python",
                expected_context="project",
                mcp_runner=_runner_with(_mcp_protocol()),
            )

        level_issues = _check(
            report, "routes.revit_project_levels"
        )["details"]["issues"]
        self.assertIn("levels_count_mismatch", level_issues)
        self.assertIn("invalid_level_elevation", level_issues)
        self.assertIn(
            "success_has_error",
            _check(report, "routes.revit_project_info")["details"]["issues"],
        )
        self.assertNotIn(SECRET_PROJECT, json.dumps(report))

    def test_health_identity_fields_use_printable_ascii_allow_lists(self) -> None:
        self.assertIsNone(
            verify._safe_host_application("Autodesk Revit `unsafe` build")
        )
        self.assertIsNone(
            verify._safe_host_application("Autodesk Revit\x01 2026")
        )
        self.assertIsNone(
            verify._safe_host_application("Museum of Extremely Secret Things")
        )

        health = _envelope("revit_health_ping")
        health["data"]["revit_build"] = SECRET_PATH
        overrides = {
            "/placeholder/health/": (
                200,
                "application/json",
                json.dumps(health).encode("utf-8"),
            )
        }
        with _serve(_route_responses(overrides)) as base_url:
            report = verify.run_verification(
                base_url,
                "python",
                expected_context="project",
                mcp_runner=_runner_with(_mcp_protocol()),
            )

        route_health = _check(report, "routes.revit_health_ping")
        self.assertEqual("fail", route_health["status"])
        self.assertIn("invalid_health_revit_build", route_health["details"]["issues"])
        self.assertNotIn(SECRET_PATH, json.dumps(report))

    def test_context_specific_error_envelopes_are_accepted_and_redacted(self) -> None:
        overrides: dict[str, tuple[int, str, bytes]] = {}
        protocol_overrides: dict[str, dict[str, Any]] = {}
        for route in verify.ROUTES[1:]:
            overrides["/placeholder" + route.path] = (
                200,
                "application/json",
                json.dumps(
                    _envelope(
                        route.tool,
                        status="error",
                        error_code="family_document_not_supported",
                    )
                ).encode("utf-8"),
            )
            protocol_overrides[route.tool] = {
                "status": "error",
                "error_code": "family_document_not_supported",
            }
        with _serve(_route_responses(overrides)) as base_url:
            report = verify.run_verification(
                base_url,
                "python",
                expected_context="family",
                timestamp="2026-08-05T02:00:00Z",
                mcp_runner=_runner_with(_mcp_protocol(protocol_overrides)),
            )

        for route in verify.ROUTES[1:]:
            self.assertEqual("pass", _check(report, "routes." + route.tool)["status"])
            self.assertEqual("pass", _check(report, "mcp." + route.tool)["status"])
        self.assertNotIn(SECRET_PROJECT, json.dumps(report))
        self.assertNotIn(SECRET_USER, json.dumps(report))

    def test_mcp_wrong_risk_and_tool_id_fail_without_leaking_observed_values(self) -> None:
        secret_tool = "secret_project_tool"
        protocol = _mcp_protocol(
            {
                "revit_project_links": {
                    "observed_tool": secret_tool,
                    "risk_class": "write",
                    "envelope_valid": False,
                    "issues": ["tool_id_mismatch", "risk_class_not_read_only"],
                }
            }
        )
        with _serve(_route_responses()) as base_url:
            report = verify.run_verification(
                base_url,
                "python",
                expected_context="project",
                timestamp="2026-08-05T02:00:00Z",
                mcp_runner=_runner_with(protocol),
            )

        mcp_check = _check(report, "mcp.revit_project_links")
        self.assertEqual("fail", mcp_check["status"])
        self.assertIn("tool_id_mismatch", mcp_check["details"]["issues"])
        self.assertIn("risk_class_not_read_only", mcp_check["details"]["issues"])
        self.assertNotIn(secret_tool, json.dumps(report))

    def test_mcp_catalog_must_be_exact(self) -> None:
        protocol = _mcp_protocol()
        protocol.update(catalog_valid=False, catalog_count=6)
        with _serve(_route_responses()) as base_url:
            report = verify.run_verification(
                base_url,
                "python",
                expected_context="project",
                mcp_runner=_runner_with(protocol),
            )

        for tool in verify.MCP_TOOLS:
            self.assertIn(
                "tool_catalog_mismatch",
                _check(report, "mcp." + tool)["details"]["issues"],
            )

    def test_provenance_requires_matching_clean_known_checkout(self) -> None:
        mismatched = _mcp_protocol(
            {"revit_health_ping": {"server_sha": "b" * 40}}
        )
        with _serve(_route_responses()) as base_url:
            mismatch_report = verify.run_verification(
                base_url,
                "python",
                expected_context="project",
                expected_git_sha=TEST_SHA,
                expected_git_dirty=False,
                mcp_runner=_runner_with(mismatched),
            )
            dirty_report = verify.run_verification(
                base_url,
                "python",
                expected_context="project",
                expected_git_sha=TEST_SHA,
                expected_git_dirty=True,
                mcp_runner=_runner_with(_mcp_protocol()),
            )
            unknown_report = verify.run_verification(
                base_url,
                "python",
                expected_context="project",
                expected_git_sha=None,
                expected_git_dirty=None,
                mcp_runner=_runner_with(_mcp_protocol()),
            )
            unknown_disagreement_report = verify.run_verification(
                base_url,
                "python",
                expected_context="project",
                expected_git_sha=None,
                expected_git_dirty=None,
                mcp_runner=_runner_with(mismatched),
            )

        mismatch = _check(mismatch_report, "provenance.build_identity")
        self.assertEqual("fail", mismatch["status"])
        self.assertIn("mcp_server_sha_mismatch", mismatch["details"]["issues"])
        self.assertEqual("incomplete", dirty_report["summary"]["outcome"])
        self.assertEqual(
            "warn", _check(dirty_report, "provenance.build_identity")["status"]
        )
        self.assertEqual("incomplete", unknown_report["summary"]["outcome"])
        unknown = _check(unknown_report, "provenance.build_identity")
        self.assertIn("checkout_sha_unknown", unknown["details"]["issues"])
        self.assertIn("checkout_dirty_unknown", unknown["details"]["issues"])
        disagreement = _check(
            unknown_disagreement_report, "provenance.build_identity"
        )
        self.assertEqual("fail", disagreement["status"])
        self.assertIn("component_sha_disagreement", disagreement["details"]["issues"])
        serialized = json.dumps(mismatch_report)
        self.assertNotIn(SECRET_PATH, serialized)
        self.assertNotIn("secret-branch", serialized)

    def test_provenance_rejects_stale_loaded_extension_modules(self) -> None:
        health = _envelope("revit_health_ping")
        health["data"]["extension_identity"]["any_stale"] = True
        overrides = {
            "/placeholder/health/": (
                200,
                "application/json",
                json.dumps(health).encode("utf-8"),
            )
        }
        protocol = _mcp_protocol(
            {"revit_health_ping": {"extension_any_stale": True}}
        )
        with _serve(_route_responses(overrides)) as base_url:
            report = verify.run_verification(
                base_url,
                "python",
                expected_context="project",
                expected_git_sha=TEST_SHA,
                expected_git_dirty=False,
                mcp_runner=_runner_with(protocol),
            )

        provenance = _check(report, "provenance.build_identity")
        self.assertEqual("fail", provenance["status"])
        self.assertIn("extension_modules_stale", provenance["details"]["issues"])

    def test_any_context_still_rejects_mixed_route_and_mcp_observations(self) -> None:
        protocol = _mcp_protocol(
            {
                "revit_project_links": {
                    "status": "error",
                    "error_code": "no_document",
                }
            }
        )
        with _serve(_route_responses()) as base_url:
            report = verify.run_verification(
                base_url,
                "python",
                expected_context="any",
                timestamp="2026-08-05T02:00:00Z",
                mcp_runner=_runner_with(protocol),
            )

        consistency = _check(report, "context.consistency")
        self.assertEqual("fail", consistency["status"])
        self.assertEqual("mixed_document_contexts", consistency["details"]["issue"])

    def test_required_manual_pending_check_makes_report_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manual_path = Path(temp_dir) / "manual.json"
            manual_path.write_text(
                json.dumps(
                    {
                        "checks": [
                            {
                                "id": "ribbon-visible",
                                "status": "pending",
                                "required": True,
                                "title": SECRET_PROJECT,
                                "note": "Ask " + SECRET_USER,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with _serve(_route_responses()) as base_url:
                report = verify.run_verification(
                    base_url,
                    "python",
                    expected_context="project",
                    manual_checks_path=manual_path,
                    timestamp="2026-08-05T02:00:00Z",
                    mcp_runner=_runner_with(_mcp_protocol()),
                )

        pending = _check(report, "manual.ribbon-visible")
        self.assertEqual("warn", pending["status"])
        self.assertTrue(pending["required"])
        self.assertEqual("incomplete", report["summary"]["outcome"])
        self.assertEqual(2, report["exit_code"])
        self.assertNotIn(SECRET_PROJECT, json.dumps(report))
        self.assertNotIn(SECRET_USER, json.dumps(report))

    def test_empty_manual_checklist_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manual_path = Path(temp_dir) / "manual.json"
            manual_path.write_text('{"checks": []}', encoding="utf-8")
            with _serve(_route_responses()) as base_url:
                report = verify.run_verification(
                    base_url,
                    "python",
                    expected_context="project",
                    manual_checks_path=manual_path,
                    mcp_runner=_runner_with(_mcp_protocol()),
                )

        invalid = _check(report, "manual.input")
        self.assertEqual("fail", invalid["status"])
        self.assertTrue(invalid["required"])

    def test_subprocess_protocol_parser_ignores_logs_and_uses_supplied_python(self) -> None:
        protocol = _mcp_protocol()
        stdout = "dependency log\n" + verify.MCP_PROBE_PREFIX + json.dumps(protocol) + "\n"
        with mock.patch(
            "toolkit_cli.verify._execute_bounded_process",
            return_value=(stdout.encode("utf-8"), 0),
        ) as run:
            parsed = verify._run_mcp_probe(
                r"C:\Secret Runtime\python.exe",
                "http://127.0.0.1:48884/placeholder",
                0.25,
            )

        self.assertEqual(verify.MCP_PROBE_PROTOCOL, parsed["protocol"])
        command, environment, process_timeout = run.call_args.args
        self.assertEqual(r"C:\Secret Runtime\python.exe", command[0])
        self.assertEqual("live_probe.py", Path(command[1]).name)
        self.assertEqual("--base-url", command[2])
        self.assertEqual("0.25", environment["REVIT_ROUTES_TIMEOUT"])
        self.assertGreaterEqual(process_timeout, 10.0)
        with self.assertRaises(verify.ProbeProtocolError):
            verify.parse_mcp_probe_output("ordinary log only", returncode=0)
        with self.assertRaises(verify.ProbeProtocolError):
            verify.parse_mcp_probe_output(stdout, returncode=7)
        with self.assertRaises(verify.ProbeProtocolError):
            verify.parse_mcp_probe_output(
                "x" * (verify.MAX_PROBE_OUTPUT_BYTES + 1), returncode=0
            )

    def test_subprocess_output_is_killed_at_live_combined_limit(self) -> None:
        with self.assertRaises(verify.ProbeProtocolError):
            verify._execute_bounded_process(
                [
                    sys.executable,
                    "-c",
                    (
                        "import sys; "
                        "sys.stdout.buffer.write(b'x' * {}); "
                        "sys.stdout.buffer.flush()"
                    ).format(verify.MAX_PROBE_OUTPUT_BYTES + 1),
                ],
                os.environ.copy(),
                5.0,
            )

    def test_invalid_expected_context_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            verify.run_verification(
                "http://127.0.0.1:48884/placeholder",
                "python",
                expected_context="sheet",
            )
        with self.assertRaises(ValueError):
            verify.run_verification(
                "http://127.0.0.1:48884/placeholder",
                "python",
                timeout=float("nan"),
            )
        with self.assertRaises(ValueError):
            verify.run_verification(
                "http://127.0.0.1:48884/placeholder",
                "python",
                timeout=120.1,
            )

    def test_context_acceptance_rules_cover_none_family_project_and_any(self) -> None:
        project_tool = "revit_project_info"
        self.assertEqual(
            ("pass", None, "none"),
            verify._expected_response(
                project_tool, "error", "no_document", "none"
            ),
        )
        self.assertEqual(
            ("pass", None, "family"),
            verify._expected_response(
                project_tool,
                "error",
                "family_document_not_supported",
                "any",
            ),
        )
        self.assertEqual(
            ("pass", None, "project"),
            verify._expected_response(project_tool, "ok", None, "project"),
        )
        self.assertEqual(
            "fail",
            verify._expected_response(
                project_tool, "error", "no_document", "project"
            )[0],
        )
        self.assertEqual(
            "fail",
            verify._expected_response(
                "revit_health_ping", "error", "no_document", "any"
            )[0],
        )

    def test_routes_url_requires_an_explicit_loopback_port(self) -> None:
        self.assertEqual(
            "http://localhost:48884/placeholder",
            verify.validate_loopback_url("http://localhost:48884/placeholder/"),
        )
        self.assertEqual(
            "http://[::1]:48884/placeholder",
            verify.validate_loopback_url("http://[::1]:48884/placeholder"),
        )
        with self.assertRaises(ValueError):
            verify.validate_loopback_url("http://localhost/placeholder")


if __name__ == "__main__":
    unittest.main()
