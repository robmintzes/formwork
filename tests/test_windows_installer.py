from __future__ import annotations

import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
INSTALLER_PATH = REPOSITORY_ROOT / "scripts" / "install-extension.ps1"


class WindowsInstallerSourceTests(unittest.TestCase):
    """Validate the Windows-only installer without pretending macOS can run it."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = INSTALLER_PATH.read_text(encoding="utf-8")

    def test_uses_current_pyrevit_extension_path_commands(self) -> None:
        native_calls = re.findall(
            r"& \$PyRevitExecutable extensions paths(?: add \$ExtsDir)? 2>&1",
            self.source,
        )

        self.assertEqual(
            [
                "& $PyRevitExecutable extensions paths 2>&1",
                "& $PyRevitExecutable extensions paths add $ExtsDir 2>&1",
                "& $PyRevitExecutable extensions paths 2>&1",
            ],
            native_calls,
        )
        self.assertNotIn("paths add link", self.source)

    def test_lists_paths_before_attempting_registration(self) -> None:
        list_position = self.source.index(
            "& $PyRevitExecutable extensions paths 2>&1"
        )
        membership_position = self.source.index(
            "Test-ExtensionPathListed",
            self.source.index("$RegisteredPathsOutput"),
        )
        add_position = self.source.index(
            "& $PyRevitExecutable extensions paths add $ExtsDir 2>&1"
        )

        self.assertLess(list_position, membership_position)
        self.assertLess(membership_position, add_position)
        self.assertIn("Extension path is already registered", self.source)

    def test_each_native_call_checks_its_exit_code_before_another_call(self) -> None:
        call_matches = list(
            re.finditer(
                r"& \$PyRevitExecutable extensions paths(?: add \$ExtsDir)? 2>&1",
                self.source,
            )
        )
        self.assertEqual(3, len(call_matches))

        for index, call_match in enumerate(call_matches):
            segment_end = (
                call_matches[index + 1].start()
                if index + 1 < len(call_matches)
                else len(self.source)
            )
            segment = self.source[call_match.end() : segment_end]
            with self.subTest(call=call_match.group(0)):
                self.assertIn("$LASTEXITCODE", segment)
                self.assertRegex(segment, r"if \(\$\w+ExitCode -ne 0\)")

    def test_failure_paths_exit_nonzero(self) -> None:
        missing_cli_block = re.search(
            r"if \(\$null -eq \$PyRevitCommand\) \{(?P<body>.*?)\n\}",
            self.source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(missing_cli_block)
        self.assertIn("Write-Error", missing_cli_block.group("body"))
        self.assertIn("exit 1", missing_cli_block.group("body"))

        self.assertIn(
            "pyRevit returned success but did not list the registered extension path",
            self.source,
        )

    def test_path_comparison_is_normalized_and_case_insensitive(self) -> None:
        self.assertIn("[System.IO.Path]::GetFullPath", self.source)
        self.assertIn("[System.StringComparison]::OrdinalIgnoreCase", self.source)


if __name__ == "__main__":
    unittest.main()
