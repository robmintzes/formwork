from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "servers" / "revit-mcp" / "scripts" / "setup-mcp-server.ps1"


class WindowsPythonSetupContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_discovery_falls_back_from_python_to_py_launcher(self) -> None:
        python_candidate = self.source.index('Command = "python"; Prefix = @()')
        launcher_candidate = self.source.index('Command = "py"; Prefix = @("-3")')
        probe = self.source.index("sys.version_info >= (3, 10)")

        self.assertLess(python_candidate, launcher_candidate)
        self.assertLess(launcher_candidate, probe)
        self.assertIn("foreach ($Candidate in $Candidates)", self.source)
        self.assertIn("if ($ProbeExitCode -ne 0)", self.source)
        self.assertIn("continue", self.source[probe : self.source.index("$ScriptDir")])

    def test_candidate_probe_preserves_prefix_and_checks_native_exit(self) -> None:
        self.assertIn(
            "$ProbeArguments = @($Candidate.Prefix) + @(",
            self.source,
        )
        self.assertIn("& $PythonCommand.Path @ProbeArguments", self.source)
        self.assertIn("$ProbeExitCode = $LASTEXITCODE", self.source)
        self.assertIn("sys.version_info >= (3, 10)", self.source)

    def test_venv_creation_uses_selected_executable_and_prefix(self) -> None:
        self.assertIn(
            '$VenvArguments = @($Python.Prefix) + @("-m", "venv", $VenvDir)',
            self.source,
        )
        self.assertIn("& $Python.Executable @VenvArguments", self.source)
        self.assertIn("$VenvExitCode = $LASTEXITCODE", self.source)
        self.assertIn("if ($VenvExitCode -ne 0)", self.source)
        self.assertNotRegex(self.source, r"&\s+python(?:\.exe)?\b")

    def test_every_virtual_environment_python_call_checks_exit_code(self) -> None:
        calls = list(re.finditer(r"& \$PythonExe\b", self.source))
        self.assertEqual(5, len(calls))

        for index, call in enumerate(calls):
            segment_end = calls[index + 1].start() if index + 1 < len(calls) else len(
                self.source
            )
            segment = self.source[call.end() : segment_end]
            with self.subTest(call_index=index):
                self.assertIn("$LASTEXITCODE", segment)
                self.assertRegex(segment, r"if \(\$LASTEXITCODE -ne 0\)")

    def test_script_stays_within_windows_powershell_51_syntax(self) -> None:
        self.assertIn("Set-StrictMode -Version Latest", self.source)
        for unsupported in ("??", "?.", "ForEach-Object -Parallel"):
            with self.subTest(unsupported=unsupported):
                self.assertNotIn(unsupported, self.source)


if __name__ == "__main__":
    unittest.main()
