from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from formwork_cli.doctor import (
    PROFILE_AUTHORING,
    PROFILE_REVIT_HOST,
    _discover_revit,
    _extension_path_listed,
    run_doctor,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeRunner:
    def __init__(self, *, failing_commands: set[tuple[str, ...]] | None = None) -> None:
        self.failing_commands = failing_commands or set()
        self.calls: list[tuple[str, ...]] = []

    def __call__(
        self, command: list[str], *, cwd: Path, timeout: float
    ) -> subprocess.CompletedProcess[str]:
        del cwd, timeout
        key = tuple(command)
        self.calls.append(key)
        return_code = 1 if key in self.failing_commands else 0
        stdout = ""
        if "--version" in command:
            stdout = "fake 1.0\n"
        elif command[-2:] == ["rev-parse", "HEAD"]:
            stdout = "a" * 40 + "\n"
        elif command[-2:] == ["branch", "--show-current"]:
            stdout = "owner/test\n"
        elif command[-2:] == ["status", "--porcelain"]:
            stdout = ""
        elif command[-2:] == ["extensions", "paths"]:
            stdout = str(REPO_ROOT / "extensions") + "\n"
        elif command[-3:] == ["configs", "routes", "port"]:
            stdout = "Routes Port: 48884\n"
        elif command[-2:] == ["configs", "routes"]:
            stdout = "Routes Server is Enabled\n"
        else:
            stdout = "ok\n"
        return subprocess.CompletedProcess(command, return_code, stdout, "")


class DoctorTests(unittest.TestCase):
    def test_authoring_profile_skips_windows_host_checks_without_failing(self) -> None:
        runner = FakeRunner()

        report = run_doctor(
            REPO_ROOT,
            profile=PROFILE_AUTHORING,
            system_name="Darwin",
            which=lambda name: "/usr/bin/{}".format(name)
            if name in {"git", "pwsh"}
            else None,
            run_command=runner,
            connect=lambda host, port, timeout: False,
            timestamp="2026-08-05T00:00:00+00:00",
        )

        by_id = {check["check_id"]: check for check in report["checks"]}
        self.assertEqual("skip", by_id["revit.installation"]["status"])
        self.assertEqual("skip", by_id["pyrevit.cli"]["status"])
        self.assertEqual("pass", report["summary"]["outcome"])
        self.assertNotIn(str(Path.home()), str(report))

    def test_revit_host_profile_on_mac_is_honestly_incomplete(self) -> None:
        report = run_doctor(
            REPO_ROOT,
            profile=PROFILE_REVIT_HOST,
            system_name="Darwin",
            which=lambda name: "/usr/bin/git" if name == "git" else None,
            run_command=FakeRunner(),
            connect=lambda host, port, timeout: False,
            timestamp="2026-08-05T00:00:00+00:00",
        )

        self.assertEqual("incomplete", report["summary"]["outcome"])
        self.assertGreater(report["summary"]["incomplete_required"], 0)

    def test_windows_profile_checks_current_pyrevit_commands(self) -> None:
        runner = FakeRunner()

        report = run_doctor(
            REPO_ROOT,
            profile=PROFILE_REVIT_HOST,
            system_name="Windows",
            environ={},
            which=lambda name: "C:/bin/{}.exe".format(name)
            if name in {"git", "powershell", "pyrevit"}
            else None,
            run_command=runner,
            connect=lambda host, port, timeout: True,
            timestamp="2026-08-05T00:00:00+00:00",
        )

        commands = [call[1:] for call in runner.calls if "pyrevit" in call[0]]
        self.assertIn(("extensions", "paths"), commands)
        self.assertIn(("configs", "routes"), commands)
        self.assertIn(("configs", "routes", "port"), commands)
        self.assertNotIn(("paths", "add", "link"), commands)
        by_id = {check["check_id"]: check for check in report["checks"]}
        self.assertEqual("pass", by_id["pyrevit.extension-path"]["status"])
        self.assertEqual("pass", by_id["pyrevit.routes-config"]["status"])

    def test_windows_profile_detects_disabled_or_wrong_port_routes(self) -> None:
        class MisconfiguredRunner(FakeRunner):
            def __call__(self, command, *, cwd, timeout):
                result = super().__call__(command, cwd=cwd, timeout=timeout)
                if command[-2:] == ["configs", "routes"]:
                    result.stdout = "Routes Server is Disabled\n"
                elif command[-3:] == ["configs", "routes", "port"]:
                    result.stdout = "Routes Port: 49999\n"
                return result

        report = run_doctor(
            REPO_ROOT,
            profile=PROFILE_REVIT_HOST,
            system_name="Windows",
            environ={},
            which=lambda name: "C:/bin/{}.exe".format(name)
            if name in {"git", "powershell", "pyrevit"}
            else None,
            run_command=MisconfiguredRunner(),
            connect=lambda host, port, timeout: False,
            timestamp="2026-08-05T00:00:00+00:00",
        )

        routes = next(
            check
            for check in report["checks"]
            if check["check_id"] == "pyrevit.routes-config"
        )
        self.assertEqual("warn", routes["status"])
        self.assertTrue(routes["required"])
        self.assertFalse(routes["details"]["enabled"])
        self.assertEqual(49999, routes["details"]["configured_port"])

    def test_extension_registration_requires_an_exact_normalized_line(self) -> None:
        expected = REPO_ROOT / "extensions"

        self.assertTrue(
            _extension_path_listed(
                '==> Extension Search Paths\n"{}"\n'.format(expected),
                expected,
                "Darwin",
            )
        )
        self.assertFalse(
            _extension_path_listed(str(expected) + "-old\n", expected, "Darwin")
        )

    def test_non_loopback_endpoint_fails_network_check(self) -> None:
        report = run_doctor(
            REPO_ROOT,
            routes_url="http://0.0.0.0:48884/placeholder",
            system_name="Darwin",
            which=lambda name: "/usr/bin/git" if name == "git" else None,
            run_command=FakeRunner(),
            timestamp="2026-08-05T00:00:00+00:00",
        )

        by_id = {check["check_id"]: check for check in report["checks"]}
        self.assertEqual("fail", by_id["network.routes"]["status"])

    def test_rejected_endpoint_does_not_leak_credentials_into_report(self) -> None:
        secret = "do-not-retain"
        report = run_doctor(
            REPO_ROOT,
            routes_url="http://user:{}@localhost:48884/placeholder?token={}".format(
                secret, secret
            ),
            system_name="Darwin",
            which=lambda name: "/usr/bin/git" if name == "git" else None,
            run_command=FakeRunner(),
            timestamp="2026-08-05T00:00:00+00:00",
        )

        self.assertNotIn(secret, str(report))
        routes = next(
            check
            for check in report["checks"]
            if check["check_id"] == "network.routes"
        )
        self.assertEqual(
            "invalid_or_non_loopback_url", routes["details"]["issue"]
        )

    def test_revit_discovery_reports_version_without_recording_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            executable = Path(temp_dir) / "Autodesk/Revit 2025/Revit.exe"
            executable.parent.mkdir(parents=True)
            executable.touch()

            versions = _discover_revit({"ProgramFiles": temp_dir})

        self.assertEqual(["2025"], versions)


if __name__ == "__main__":
    unittest.main()
