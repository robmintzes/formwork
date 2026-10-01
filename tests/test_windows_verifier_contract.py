from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-windows.ps1"


class WindowsVerifierContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_live_routes_reset_gate_precedes_verifier_invocation(self) -> None:
        gate = self.source.index("if (-not $RoutesResetConfirmed)")
        invocation = self.source.index('"-m", "formwork_cli", "verify", "revit"')

        self.assertLess(gate, invocation)
        self.assertIn("exit 2", self.source[gate:invocation])
        self.assertIn('"--routes-reset-confirmed"', self.source[invocation:])

    def test_python_discovery_probes_python_then_py_launcher(self) -> None:
        python_candidate = self.source.index('Command = "python"; Prefix = @()')
        launcher_candidate = self.source.index('Command = "py"; Prefix = @("-3")')
        probe = self.source.index("sys.version_info >= (3, 10)")

        self.assertLess(python_candidate, launcher_candidate)
        self.assertLess(launcher_candidate, probe)
        self.assertIn("foreach ($Candidate in $Candidates)", self.source)
        self.assertIn("if ($ProbeExitCode -ne 0)", self.source)
        self.assertIn("continue", self.source[probe : self.source.index("function Invoke-FormworkPython")])

    def test_python_prefix_is_preserved_for_probe_and_formwork_calls(self) -> None:
        self.assertIn(
            "$ProbeArguments = @($Candidate.Prefix) + @(",
            self.source,
        )
        self.assertIn(
            "$NativeArguments = @($PythonInvocation.Prefix) + @($Arguments)",
            self.source,
        )
        self.assertIn("@ProbeArguments", self.source)
        self.assertIn("@NativeArguments", self.source)

    def test_configuration_mutation_requires_explicit_switch(self) -> None:
        install_block = re.search(
            r"if \(\$InstallExtension\) \{(?P<body>.*?)\n    \}",
            self.source,
            flags=re.DOTALL,
        )

        self.assertIsNotNone(install_block)
        self.assertIn("install-extension.ps1", install_block.group("body"))
        self.assertNotIn("configs routes enable", self.source)
        self.assertNotIn("configs routes port", self.source)

    def test_native_python_calls_check_exit_codes(self) -> None:
        self.assertIn("$ProbeExitCode = $LASTEXITCODE", self.source)
        self.assertIn("$NativeExitCode = $LASTEXITCODE", self.source)
        self.assertIn("$InstallExitCode = $LASTEXITCODE", self.source)
        self.assertIn("if ($ProbeExitCode -ne 0)", self.source)
        self.assertIn("if ($InstallExitCode -ne 0)", self.source)
        self.assertIn("Merge-ExitCode", self.source)

    def test_manual_input_is_validated_before_any_network_capable_command(self) -> None:
        validation = self.source.index(
            "$EffectiveManualData = Get-SanitizedManualChecklist"
        )
        doctor = self.source.index('"-m", "formwork_cli", "doctor"')
        live_verify = self.source.index('"-m", "formwork_cli", "verify", "revit"')
        validation_block = self.source[validation:doctor]

        self.assertLess(validation, doctor)
        self.assertLess(validation, live_verify)
        self.assertIn("catch", validation_block)
        self.assertIn("exit 2", validation_block)
        self.assertIn("Resolve-Path -LiteralPath", self.source)
        self.assertIn("[System.IO.File]::ReadAllText", self.source)
        self.assertIn("ConvertFrom-Json", self.source)

    def test_manual_schema_matches_portable_verifier(self) -> None:
        self.assertIn("'^[a-z0-9][a-z0-9_.-]{0,63}$'", self.source)
        self.assertIn(
            '$AllowedStatuses = @("pass", "fail", "warn", "skip", "pending", "not_run")',
            self.source,
        )
        self.assertIn("$Required -isnot [bool]", self.source)
        self.assertIn("$SeenIds.Add($ManualId)", self.source)

    def test_effective_manual_checklist_contains_only_whitelisted_fields(self) -> None:
        sanitized = re.search(
            r"\$SanitizedChecks \+= \[pscustomobject\]\[ordered\]@\{"
            r"(?P<body>.*?)\n        \}",
            self.source,
            flags=re.DOTALL,
        )

        self.assertIsNotNone(sanitized)
        fields = re.findall(r"^\s*([a-z]+)\s*=", sanitized.group("body"), re.MULTILINE)
        self.assertEqual(["id", "status", "required"], fields)
        self.assertNotIn("title =", sanitized.group("body"))
        self.assertNotIn("note =", sanitized.group("body"))
        self.assertIn('$ManualId -ceq "routes-reset-after-reload"', self.source)
        self.assertIn('$ManualStatus = "pass"', self.source)
        self.assertIn(
            "$EffectiveManualData | ConvertTo-Json",
            self.source,
        )
        self.assertNotIn("$ManualData | ConvertTo-Json", self.source)

    def test_evidence_defaults_to_ignored_logs_directory(self) -> None:
        self.assertIn('.logs\\windows-verification', self.source)
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".logs/", gitignore)

    def test_wrapper_never_starts_or_kills_unowned_processes(self) -> None:
        forbidden = ("Start-Process", "Stop-Process", "taskkill", "Remove-Item")
        for command in forbidden:
            with self.subTest(command=command):
                self.assertNotIn(command, self.source)

    def test_expected_exit_two_paths_do_not_emit_powershell_error_records(self) -> None:
        # A parent PowerShell with ErrorActionPreference=Stop treats child
        # Write-Error records as terminating before it can inspect LASTEXITCODE.
        self.assertNotIn("Write-Error", self.source)
        self.assertIn("Write-Warning", self.source)


if __name__ == "__main__":
    unittest.main()
