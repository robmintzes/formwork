from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class BootstrapSmokeTests(unittest.TestCase):
    def _require_template_source(self) -> None:
        if not (
            REPOSITORY_ROOT / "extensions" / "Placeholder.extension"
        ).is_dir():
            self.skipTest("Bootstrap generation tests apply only to the template source.")

    def test_python_and_powershell_replace_the_same_files(self) -> None:
        python_source = (REPOSITORY_ROOT / "scripts" / "bootstrap.py").read_text(
            encoding="utf-8"
        )
        python_tree = ast.parse(python_source)
        python_files: set[str] | None = None
        for node in ast.walk(python_tree):
            if not isinstance(node, ast.Assign):
                continue
            if any(
                isinstance(target, ast.Name) and target.id == "files_to_update"
                for target in node.targets
            ):
                python_files = set(ast.literal_eval(node.value))
                break
        self.assertIsNotNone(python_files, "Python replacement file list was not found.")

        powershell_source = (
            REPOSITORY_ROOT / "scripts" / "bootstrap.ps1"
        ).read_text(encoding="utf-8")
        powershell_block = re.search(
            r"\$FilesToUpdate\s*=\s*@\((.*?)\n\)",
            powershell_source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(
            powershell_block, "PowerShell replacement file list was not found."
        )
        powershell_files = {
            value.replace("\\", "/")
            for value in re.findall(
                r'^\s*"([^"]+)"\s*,?\s*$',
                powershell_block.group(1),
                flags=re.MULTILINE,
            )
        }

        self.assertEqual(python_files, powershell_files)

    def _generate(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        self._require_template_source()
        temporary_directory: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        generated_root = Path(temporary_directory.name) / "generated-toolkit"
        shutil.copytree(
            REPOSITORY_ROOT,
            generated_root,
            ignore=shutil.ignore_patterns(
                ".git",
                ".venv",
                "__pycache__",
                ".pytest_cache",
                "dist",
            ),
        )
        result = subprocess.run(
            [
                sys.executable,
                str(generated_root / "scripts" / "bootstrap.py"),
                "--firm",
                "Test Firm",
                "--extension",
                "TestTools",
            ],
            cwd=generated_root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return temporary_directory, generated_root

    def test_python_bootstrap_rejects_unsafe_extension_names(self) -> None:
        self._require_template_source()
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        generated_root = Path(temporary_directory.name) / "generated-toolkit"
        shutil.copytree(
            REPOSITORY_ROOT,
            generated_root,
            ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache"),
        )

        for extension_name in (
            "../Escaped",
            "Example_Tools",
            "Example--Tools",
            "Example-",
        ):
            with self.subTest(extension_name=extension_name):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(generated_root / "scripts" / "bootstrap.py"),
                        "--firm",
                        "Test Firm",
                        "--extension",
                        extension_name,
                    ],
                    cwd=generated_root,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                self.assertNotEqual(0, result.returncode)

        self.assertTrue(
            (generated_root / "extensions" / "Placeholder.extension").is_dir()
        )
        self.assertFalse((generated_root / "Escaped.extension").exists())

    def test_python_bootstrap_renames_core_extension_structure(self) -> None:
        temporary_directory, generated_root = self._generate()
        self.addCleanup(temporary_directory.cleanup)

        expected_panel = (
            generated_root
            / "extensions"
            / "TestTools.extension"
            / "TestToolsTab.tab"
            / "TestToolsPanel.panel"
        )
        self.assertTrue(expected_panel.is_dir())
        self.assertFalse(
            any("Placeholder" in path.name for path in generated_root.rglob("*")),
            "Generated path names still contain Placeholder.",
        )
        self.assertFalse((generated_root / ".toolkit-template").exists())
        self.assertTrue((generated_root / ".toolkit-generated").is_file())

        manifest = json.loads(
            (generated_root / "extensions" / "TestTools.extension" / "extension.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual("Test Firm", manifest["author"])

        toolbar_spec = (
            generated_root / "docs" / "toolbar" / "toolbar_spec.md"
        ).read_text(encoding="utf-8")
        self.assertIn("display_name: TestTools\n", toolbar_spec)
        self.assertNotIn("TestTools Tools", toolbar_spec)

        agent_instructions = (generated_root / "AGENTS.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("configured firm author value", agent_instructions)

    def test_python_bootstrap_rebrands_all_runtime_and_documentation_text(self) -> None:
        """Generated runtime and documentation should not retain template branding."""
        temporary_directory, generated_root = self._generate()
        self.addCleanup(temporary_directory.cleanup)

        remaining_references: list[str] = []
        for relative_root in ("extensions", "servers", "docs", ".github"):
            for path in (generated_root / relative_root).rglob("*"):
                if not path.is_file() or path.suffix.lower() not in {
                    ".json",
                    ".md",
                    ".py",
                    ".txt",
                    ".yaml",
                    ".yml",
                }:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                if any(
                    marker in text.lower()
                    for marker in ("placeholder", "template author")
                ):
                    remaining_references.append(path.relative_to(generated_root).as_posix())

        self.assertEqual(
            [],
            remaining_references,
            "Generated files still contain template branding: "
            + ", ".join(remaining_references),
        )

    def test_generated_repository_validation_commands_do_not_fail(self) -> None:
        temporary_directory, generated_root = self._generate()
        self.addCleanup(temporary_directory.cleanup)

        commands = [
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "extensions/TestTools.extension/tests",
                "-v",
            ],
            [sys.executable, "validators/check_bundle_structure.py"],
            [sys.executable, "validators/check_safety_rules.py"],
            [sys.executable, "validators/validate_toolbar_spec.py"],
        ]
        for command in commands:
            result = subprocess.run(
                command,
                cwd=generated_root,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(
                0,
                result.returncode,
                "Command failed: {}\n{}{}".format(
                    " ".join(command), result.stdout, result.stderr
                ),
            )

    def test_generated_ci_does_not_unconditionally_bootstrap_again(self) -> None:
        temporary_directory, generated_root = self._generate()
        self.addCleanup(temporary_directory.cleanup)

        workflow = (generated_root / ".github/workflows/ci.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("Detect template source repository", workflow)
        self.assertIn('Test-Path -LiteralPath ".toolkit-template"', workflow)
        self.assertIn(
            "if: steps.template-source.outputs.is_template == 'true'", workflow
        )
        self.assertIn('Get-ChildItem -LiteralPath "extensions"', workflow)
        self.assertNotIn(
            "extensions/BIM-Tools.extension/tests",
            workflow,
            "Generated CI must discover the configured extension instead of "
            "assuming the maintainer smoke-test name.",
        )


if __name__ == "__main__":
    unittest.main()
