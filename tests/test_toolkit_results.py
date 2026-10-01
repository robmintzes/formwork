from __future__ import annotations

import unittest

from formwork_cli.results import CheckResult, report_exit_code, summarize


class ResultContractTests(unittest.TestCase):
    def test_required_failure_controls_outcome_and_exit_code(self) -> None:
        checks = [
            CheckResult("python", "Python", "pass", "Supported", required=True),
            CheckResult("routes", "Routes", "fail", "Unreachable", required=True),
            CheckResult("optional", "Optional", "fail", "Unavailable"),
        ]

        summary = summarize(checks)

        self.assertEqual("fail", summary["outcome"])
        self.assertEqual(2, summary["blocking_failures"])
        self.assertEqual(1, report_exit_code({"summary": summary}))

    def test_required_skip_is_incomplete(self) -> None:
        summary = summarize(
            [CheckResult("revit", "Revit", "skip", "Run on Windows", required=True)]
        )

        self.assertEqual("incomplete", summary["outcome"])
        self.assertEqual(2, report_exit_code({"summary": summary}))

    def test_optional_warning_does_not_fail_report(self) -> None:
        summary = summarize(
            [CheckResult("pwsh", "PowerShell", "warn", "Not installed")]
        )

        self.assertEqual("pass", summary["outcome"])
        self.assertEqual(0, report_exit_code({"summary": summary}))

    def test_fail_is_always_a_failure_even_when_not_required(self) -> None:
        summary = summarize(
            [CheckResult("security", "Security", "fail", "Unsafe setting")]
        )

        self.assertEqual("fail", summary["outcome"])
        self.assertEqual(1, report_exit_code({"summary": summary}))

    def test_unknown_status_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CheckResult("bad", "Bad", "maybe", "Nope")


if __name__ == "__main__":
    unittest.main()
