"""Acceptance tests for the generated governance surface.

A generated workspace should be a governed repository on its own: real Git
hooks enforce the firm's maintainers' branch policy, vendored validators run
from the workspace root, and nothing names the foundation maintainer.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from formwork_engine.adapters import governance  # noqa: E402
from formwork_engine.diagnostics import Diagnostics  # noqa: E402
from formwork_engine.profile import load_profile  # noqa: E402
from formwork_engine.workspace import init_workspace, render_workspace  # noqa: E402

QUILLMOOR = REPO / "profiles" / "quillmoor"


def edit_json(path: Path, mutate) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class GovernanceCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="governance ")
        self.base = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def workspace(self, mutate=None, name: str = "Quillmoor DT") -> Path:
        firm = self.base / ("profile-" + name)
        shutil.copytree(QUILLMOOR, firm)
        if mutate:
            edit_json(firm / "firm.json", mutate)
        root = self.base / name
        init_workspace(firm, root)
        report = render_workspace(root)
        self.assertEqual(report["summary"]["outcome"], "pass", report["diagnostics"])
        self.report = report
        return root


class GeneratedRepositoryTests(GovernanceCase):
    def git(self, root: Path, *args: str, success: bool = True) -> subprocess.CompletedProcess:
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("ERROR:", result.stderr)
        return result

    def test_hooks_enforce_the_firm_maintainer_policy(self) -> None:
        root = self.workspace()
        for hook in (root / ".githooks").iterdir():
            hook.chmod(0o755)
        self.git(root, "init", "-b", "aquill/initial-workspace")
        self.git(root, "config", "user.name", "Test Developer")
        self.git(root, "config", "user.email", "test@example.invalid")
        self.git(root, "config", "core.hooksPath", ".githooks")
        self.git(root, "config", "branchPolicy.owner", "aquill")
        self.git(root, "add", ".")
        self.git(root, "commit", "-m", "Initial workspace")

        (root / "notes.txt").write_text("x\n", encoding="utf-8")
        self.git(root, "add", "notes.txt")
        self.git(root, "switch", "-c", "main")
        self.git(root, "commit", "-m", "Direct to main", success=False)
        self.git(root, "switch", "-c", "claude/sneaky")
        self.git(root, "commit", "-m", "Agent prefix", success=False)
        self.git(root, "switch", "-c", "jdoe/not-a-maintainer")
        self.git(root, "commit", "-m", "Wrong owner", success=False)
        self.git(root, "switch", "-c", "aquill/notes")
        self.git(root, "commit", "-m", "Owned branch")

    def test_vendored_validators_pass_from_the_workspace_root(self) -> None:
        root = self.workspace()
        for script in ("check_bundle_structure.py", "check_safety_rules.py", "validate_toolbar_spec.py"):
            result = subprocess.run([sys.executable, "validators/" + script], cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, script + result.stdout + result.stderr)
            self.assertIn("OK", result.stdout)

    def test_no_foundation_maintainer_defaults_leak(self) -> None:
        root = self.workspace()
        for path in root.rglob("*"):
            if path.is_file() and path.suffix not in (".png", ".ttf"):
                rel = path.relative_to(root).as_posix()
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("robmintzes", text, rel)
        installer = (root / "scripts" / "install-git-hooks.ps1").read_text(encoding="utf-8")
        self.assertIn("[Parameter(Mandatory = $true)][string]$Owner", installer)
        self.assertIn("aquill/fix-selection", (root / "validators" / "check_branch_policy.py").read_text(encoding="utf-8"))

    def test_agent_pointers_reference_canonical_instructions(self) -> None:
        root = self.workspace()
        self.assertIn("aquill", (root / "AGENTS.md").read_text(encoding="utf-8"))
        for pointer, target in (("CLAUDE.md", "AGENTS.md"), ("GEMINI.md", "AGENTS.md"), (".github/copilot-instructions.md", "../AGENTS.md")):
            text = (root / pointer).read_text(encoding="utf-8")
            self.assertIn("]({})".format(target), text)
            self.assertLess(len(text), 600)  # thin: no second copy of the rules
        self.assertTrue((root / target.replace("../", "")).is_file())

    def test_ruleset_checks_match_workflow_jobs(self) -> None:
        root = self.workspace()
        ruleset = json.loads((root / ".github" / "rulesets" / "main-branch-ruleset.json").read_text(encoding="utf-8"))
        checks = next(r for r in ruleset["rules"] if r["type"] == "required_status_checks")
        contexts = [c["context"] for c in checks["parameters"]["required_status_checks"]]
        workflow = (root / ".github" / "workflows" / "development-policy.yml").read_text(encoding="utf-8")
        for context in contexts:
            self.assertIn("\n  {}:\n".format(context), workflow)
        codes = [d["code"] for d in self.report["diagnostics"]]
        self.assertIn("governance.ruleset-not-applied", codes)

    def test_seeded_firm_rules_survive_rerender(self) -> None:
        root = self.workspace()
        rules = root / "docs" / "agents" / "FIRM_RULES.md"
        rules.write_text("# Our rules\n- Views use AIA numbering.\n", encoding="utf-8")
        self.assertEqual(render_workspace(root)["summary"]["outcome"], "pass")
        self.assertEqual(rules.read_text(encoding="utf-8"), "# Our rules\n- Views use AIA numbering.\n")


class ApprovalPolicyTests(GovernanceCase):
    def approvals(self, root: Path) -> int:
        ruleset = json.loads((root / ".github" / "rulesets" / "main-branch-ruleset.json").read_text(encoding="utf-8"))
        pr = next(r for r in ruleset["rules"] if r["type"] == "pull_request")
        return pr["parameters"]["required_approving_review_count"]

    def test_defaults_follow_team_size(self) -> None:
        self.assertEqual(self.approvals(self.workspace(name="Solo")), 0)
        team = self.workspace(
            lambda c: c["maintainers"].append({"name": "Second Reviewer", "branch_prefix": "sreviewer"}), name="Team"
        )
        self.assertEqual(self.approvals(team), 1)
        self.assertIn("sreviewer", (team / "docs" / "onboarding" / "BRANCH_POLICY.md").read_text(encoding="utf-8"))

    def test_explicit_choice_wins_and_impossible_policy_warns(self) -> None:
        firm = self.base / "unreachable"
        shutil.copytree(QUILLMOOR, firm)
        edit_json(firm / "firm.json", lambda c: c.__setitem__("governance", {"required_approvals": 2}))
        diags = Diagnostics()
        profile = load_profile(firm, diags)
        self.assertEqual(profile.config.governance.required_approvals, 2)
        self.assertIn("governance.approvals-unreachable", diags.codes())


class VendoringDriftTests(unittest.TestCase):
    def test_changed_foundation_file_fails_loudly(self) -> None:
        with tempfile.TemporaryDirectory(prefix="drift ") as tmp:
            fake = Path(tmp)
            for rel in governance.VENDORED + (".github/main-branch-ruleset.json",):
                (fake / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(REPO / rel, fake / rel)
            installer = fake / "scripts" / "install-git-hooks.ps1"
            installer.write_text(installer.read_text(encoding="utf-8").replace('"robmintzes"', '"someone"'), encoding="utf-8")
            diags = Diagnostics()
            profile = load_profile(QUILLMOOR, diags)
            original = governance.FOUNDATION
            governance.FOUNDATION = fake
            try:
                with self.assertRaises(governance.VendoringError):
                    governance.render(profile)
            finally:
                governance.FOUNDATION = original


if __name__ == "__main__":
    unittest.main()
