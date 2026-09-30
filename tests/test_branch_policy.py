"""Exercise policy decisions and actual Git hooks in disposable repositories."""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("branch_policy", ROOT / "validators/check_branch_policy.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class PolicyTests(unittest.TestCase):
    def test_valid_human_branches(self):
        for branch in ("robmintzes/add-tool", "jdoe/fix-selection", "jane-doe/task-42"):
            with self.subTest(branch=branch):
                self.assertIsNone(policy.branch_error(branch))

    def test_protected_agent_and_malformed_branches(self):
        for branch in ("main", "stable", "codex/add-tool", "claude/fix", "feature/tool", "robmintzes/", "robmintzes/Fix", "robmintzes/a/b", ""):
            with self.subTest(branch=branch):
                # 'feature' is a syntactically valid self-declared owner, but not Rob.
                self.assertIsNotNone(policy.branch_error(branch, "robmintzes"))

    def test_wrong_owner(self):
        self.assertIsNotNone(policy.branch_error("jdoe/fix", "robmintzes"))

    def test_push_blocks_main_destination_and_deletion(self):
        for sha in ("a" * 40, "0" * 40):
            line = f"refs/heads/robmintzes/task {sha} refs/heads/main {'b' * 40}"
            self.assertTrue(policy.push_errors([line], "robmintzes"))

    def test_owned_push_deletion_and_tags(self):
        for line in (
            f"refs/heads/robmintzes/task {'a' * 40} refs/heads/robmintzes/task {'b' * 40}",
            f"(delete) {'0' * 40} refs/heads/robmintzes/task {'b' * 40}",
            f"refs/tags/v1 {'a' * 40} refs/tags/v1 {'0' * 40}",
        ):
            self.assertEqual(policy.push_errors([line], "robmintzes"), [])

    def test_push_rejects_wrong_owner_and_malformed_input(self):
        self.assertTrue(policy.push_errors(["invalid"], "robmintzes"))
        line = f"refs/heads/robmintzes/task {'a' * 40} refs/heads/jdoe/task {'0' * 40}"
        self.assertTrue(policy.push_errors([line], "robmintzes"))


class GitHookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo with spaces"
        self.repo.mkdir()
        shutil.copytree(ROOT / ".githooks", self.repo / ".githooks")
        (self.repo / "validators").mkdir()
        shutil.copy2(ROOT / "validators/check_branch_policy.py", self.repo / "validators/check_branch_policy.py")
        for hook in (self.repo / ".githooks").iterdir():
            hook.chmod(0o755)
        self.git("init", "-b", "robmintzes/test-policy")
        self.git("config", "user.name", "Test Developer")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "core.hooksPath", ".githooks")
        self.git("config", "branchPolicy.owner", "robmintzes")
        (self.repo / "sample.txt").write_text("example\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-m", "Initial allowed commit")

    def git(self, *args, success=True):
        result = subprocess.run(["git", *args], cwd=self.repo, capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("ERROR:", result.stderr)
        return result

    def test_commit_blocks_protected_wrong_owner_and_detached_head(self):
        for branch in ("main", "stable", "jdoe/task", "codex/task"):
            self.git("switch", "-c", branch)
            self.git("commit", "--allow-empty", "-m", "Blocked", success=False)
        self.git("checkout", "--detach")
        self.git("commit", "--allow-empty", "-m", "Blocked detached", success=False)

    def test_push_checks_destination_and_leaves_remote_unchanged(self):
        remote = Path(self.temp.name) / "remote.git"
        subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
        self.git("remote", "add", "origin", str(remote))
        self.git("push", "origin", "HEAD:refs/heads/robmintzes/test-policy")
        self.git("push", "origin", "HEAD:refs/heads/main", success=False)
        self.git("push", "origin", "HEAD:refs/heads/jdoe/task", success=False)
        refs = self.git("ls-remote", "--heads", "origin").stdout
        self.assertIn("refs/heads/robmintzes/test-policy", refs)
        self.assertNotIn("refs/heads/main", refs)
        self.assertNotIn("refs/heads/jdoe/task", refs)

    def test_unconfigured_owner_fails_closed(self):
        self.git("config", "--unset", "branchPolicy.owner")
        self.git("commit", "--allow-empty", "-m", "Blocked unconfigured owner", success=False)


if __name__ == "__main__":
    unittest.main()
