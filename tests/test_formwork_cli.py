from __future__ import annotations

import json
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from formwork_cli import cli


REPO_ROOT = Path(__file__).resolve().parents[1]


class FormworkCliTests(unittest.TestCase):
    def test_doctor_writes_machine_readable_report(self) -> None:
        report = {
            "kind": "formwork-doctor",
            "profile": "authoring",
            "checks": [],
            "summary": {"outcome": "pass"},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "doctor.json"
            with mock.patch("formwork_cli.cli.run_doctor", return_value=report):
                with redirect_stdout(io.StringIO()):
                    exit_code = cli.main(
                        [
                            "doctor",
                            "--profile",
                            "authoring",
                            "--repository",
                            str(REPO_ROOT),
                            "--format",
                            "json",
                            "--output",
                            str(output),
                        ]
                    )
            written = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(0, exit_code)
        self.assertEqual("formwork-doctor", written["kind"])
        self.assertEqual("pass", written["summary"]["outcome"])

    def test_verify_command_forwards_safe_live_options(self) -> None:
        report = {
            "checks": [],
            "summary": {"outcome": "incomplete"},
        }
        paths = {"json": Path("evidence.json"), "markdown": Path("evidence.md")}
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch(
                "formwork_cli.cli.verify_and_write",
                return_value=(report, paths, 2),
            ) as verify:
                with redirect_stdout(io.StringIO()):
                    exit_code = cli.main(
                        [
                            "verify",
                            "revit",
                            "--repository",
                            str(REPO_ROOT),
                            "--routes-url",
                            "http://127.0.0.1:48884/placeholder",
                            "--mcp-python",
                            "C:/MCP/python.exe",
                            "--expected-context",
                            "family",
                            "--routes-reset-confirmed",
                            "--output-dir",
                            temp_dir,
                        ]
                    )

        self.assertEqual(2, exit_code)
        self.assertEqual("http://127.0.0.1:48884/placeholder", verify.call_args.args[0])
        self.assertEqual(
            Path("C:/MCP/python.exe"), Path(verify.call_args.args[1])
        )
        self.assertEqual("family", verify.call_args.kwargs["expected_context"])

    def test_invalid_timeout_returns_usage_style_exit_code(self) -> None:
        with mock.patch(
            "formwork_cli.cli.verify_and_write",
            side_effect=ValueError("timeout must be greater than zero"),
        ):
            with redirect_stderr(io.StringIO()):
                exit_code = cli.main(
                    [
                        "verify",
                        "revit",
                        "--timeout",
                        "0",
                        "--routes-reset-confirmed",
                        "--output-dir",
                        ".logs/test",
                    ]
                )

        self.assertEqual(2, exit_code)

    def test_verify_refuses_to_call_routes_without_reset_confirmation(self) -> None:
        with mock.patch("formwork_cli.cli.verify_and_write") as verify:
            with redirect_stderr(io.StringIO()):
                exit_code = cli.main(["verify", "revit"])

        self.assertEqual(2, exit_code)
        verify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
