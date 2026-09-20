import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from sidekick.git_manager import GitAutomationManager
from sidekick.secret_scanner import SecretScanner
from sidekick.state_manager import LockManager, SidekickState
from sidekick.task_parser import TaskDefinition


class TestTaskParserPhase2(unittest.TestCase):
    def test_parse_task_with_id(self):
        sample = """# Current Task

## Task ID
task-101

## Goal
Implement greeting function.

## Background
Greeting feature.

## Allowed Files
- src/hello.py

## Forbidden Operations
- None

## Requirements
- Add hello()

## Acceptance Criteria
- test passes

## Allowed Commands
- python -m unittest

## Review Points
- none
"""
        task = TaskDefinition.parse(sample)
        self.assertEqual(task.task_id, "task-101")
        self.assertEqual(task.goal, "Implement greeting function.")
        self.assertEqual(task.allowed_files, ["src/hello.py"])

    def test_parse_task_auto_generated_id(self):
        sample = """# Current Task

## Goal
Implement something without ID.
"""
        task = TaskDefinition.parse(sample)
        self.assertTrue(len(task.task_id) > 0)

class TestSecretScanner(unittest.TestCase):
    def test_detect_github_token(self):
        text = "token = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890'"
        findings = SecretScanner.scan_text(text, "config.py")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0][1], "GitHub Token")

    def test_detect_aws_key(self):
        text = "aws_key = 'AKIAIOSFODNN7EXAMPLE'"
        findings = SecretScanner.scan_text(text, "creds.py")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0][1], "AWS Access Key")

    def test_detect_private_key(self):
        text = "-----BEGIN OPENSSH PRIVATE KEY-----\ntest\n"
        findings = SecretScanner.scan_text(text, "id_rsa")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0][1], "Private Key Header")

    def test_clean_file_passes(self):
        text = "def hello():\n    return 'world'\n"
        findings = SecretScanner.scan_text(text, "hello.py")
        self.assertEqual(len(findings), 0)

class TestGitAutomation(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        # Init git repo with remote origin
        subprocess.run(["git", "init", "-b", "main"], cwd=self.test_dir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "TestUser"], cwd=self.test_dir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.test_dir, capture_output=True)
        # Create dummy remote
        self.remote_dir = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "--bare", "-b", "main"], cwd=self.remote_dir, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", str(self.remote_dir)], cwd=self.test_dir, capture_output=True)

        # Initial commit
        (self.test_dir / "README.md").write_text("init", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.test_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.test_dir, capture_output=True)
        subprocess.run(["git", "push", "-u", "origin", "main"], cwd=self.test_dir, capture_output=True)

        self.git_mgr = GitAutomationManager(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        shutil.rmtree(self.remote_dir, ignore_errors=True)

    def test_preflight_clean(self):
        ok, msg = self.git_mgr.preflight_check(require_clean=True)
        self.assertTrue(ok, msg)

    def test_preflight_allows_task_and_result_files(self):
        (self.test_dir / ".ai").mkdir(exist_ok=True)
        (self.test_dir / ".ai" / "TASK.md").write_text("# Current Task\n", encoding="utf-8")
        (self.test_dir / ".ai" / "RESULT.md").write_text("# Result\n", encoding="utf-8")
        ok, msg = self.git_mgr.preflight_check(require_clean=True)
        self.assertTrue(ok, f"Preflight should permit TASK.md/RESULT.md but got: {msg}")

    def test_preflight_dirty_blocked(self):
        (self.test_dir / "uncommitted.txt").write_text("dirty", encoding="utf-8")
        ok, msg = self.git_mgr.preflight_check(require_clean=True)
        self.assertFalse(ok)
        self.assertIn("dirty", msg.lower())

    def test_ensure_task_branch(self):
        ok, branch_name, msg = self.git_mgr.ensure_task_branch("task-001")
        self.assertTrue(ok)
        self.assertEqual(branch_name, "ai/task-001")
        self.assertEqual(self.git_mgr.get_current_branch(), "ai/task-001")

    def test_diff_guard_allowed_and_violation(self):
        self.git_mgr.ensure_task_branch("task-002")
        (self.test_dir / "src").mkdir(exist_ok=True)
        (self.test_dir / "src" / "app.py").write_text("print(1)", encoding="utf-8")
        (self.test_dir / ".ai").mkdir(exist_ok=True)
        (self.test_dir / ".ai" / "TASK.md").write_text("# Task", encoding="utf-8")

        # Allowed Files: src/
        ok, changed, _ = self.git_mgr.validate_diff_guard(allowed_files=["src/"])
        self.assertTrue(ok)
        self.assertIn("src/app.py", [p.replace("\\", "/") for p in changed])

        # Create disallowed file
        (self.test_dir / "unauthorized.txt").write_text("bad", encoding="utf-8")
        bad_ok, violations, err = self.git_mgr.validate_diff_guard(allowed_files=["src/"])
        self.assertFalse(bad_ok)
        self.assertIn("unauthorized.txt", [v.replace("\\", "/") for v in violations])

    def test_safe_push_blocks_main_and_allows_task_branch(self):
        # Blocking main direct push
        main_ok, _ = self.git_mgr.safe_push("main")
        self.assertFalse(main_ok)

        # Allow task branch push
        self.git_mgr.ensure_task_branch("task-003")
        (self.test_dir / "src").mkdir(exist_ok=True)
        (self.test_dir / "src" / "test.py").write_text("pass", encoding="utf-8")
        c_ok, c_hash, _ = self.git_mgr.commit_changes("task-003", ["src/test.py"])
        self.assertTrue(c_ok)

        push_ok, p_msg = self.git_mgr.safe_push("ai/task-003")
        self.assertTrue(push_ok, p_msg)

class TestStateAndLock(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_state_persistence(self):
        state_file = self.temp_dir / "state.json"
        state = SidekickState(
            task_id="task-999",
            status="SUCCESS",
            branch="ai/task-999",
            automation_status="READY_FOR_REVIEW"
        )
        state.save(state_file)

        loaded = SidekickState.load(state_file)
        self.assertEqual(loaded.task_id, "task-999")
        self.assertEqual(loaded.automation_status, "READY_FOR_REVIEW")

    def test_lock_manager(self):
        lock_file = self.temp_dir / "test.lock"
        lm1 = LockManager(lock_file, stale_timeout_seconds=60)
        self.assertTrue(lm1.acquire())

        # Second acquire fails while locked
        lm2 = LockManager(lock_file, stale_timeout_seconds=60)
        self.assertFalse(lm2.acquire())

        lm1.release()
        self.assertTrue(lm2.acquire())
        lm2.release()

if __name__ == "__main__":
    unittest.main()
