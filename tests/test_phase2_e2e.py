import unittest
import tempfile
import shutil
import subprocess
from pathlib import Path
from sidekick.config import SidekickConfig
from sidekick.runner import SidekickRunner
from sidekick.watcher import TaskWatcher
from sidekick.state_manager import SidekickState

class TestPhase2E2E(unittest.TestCase):
    def setUp(self):
        self.root_dir = Path(tempfile.mkdtemp())
        self.remote_dir = Path(tempfile.mkdtemp())
        self.project_dir = self.root_dir / "target_repo"
        self.project_dir.mkdir()

        # Initialize bare remote
        subprocess.run(["git", "init", "--bare", "-b", "main"], cwd=self.remote_dir, capture_output=True)

        # Initialize target project
        subprocess.run(["git", "init", "-b", "main"], cwd=self.project_dir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "E2E Tester"], cwd=self.project_dir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=self.project_dir, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", str(self.remote_dir)], cwd=self.project_dir, capture_output=True)

        # Create basic directories
        (self.project_dir / ".ai").mkdir()
        (self.project_dir / "prompts").mkdir()
        (self.project_dir / "src").mkdir()
        (self.project_dir / "tests").mkdir()

        # Copy rules, decisions, system prompt
        src_root = Path(__file__).parent.parent
        shutil.copy(src_root / ".ai" / "RULES.md", self.project_dir / ".ai" / "RULES.md")
        shutil.copy(src_root / ".ai" / "DECISIONS.md", self.project_dir / ".ai" / "DECISIONS.md")
        shutil.copy(src_root / "prompts" / "sidekick-system.md", self.project_dir / "prompts" / "sidekick-system.md")

        # Initial commit & push to main
        (self.project_dir / "README.md").write_text("Target Repo Initialized", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.project_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=self.project_dir, capture_output=True)
        subprocess.run(["git", "push", "-u", "origin", "main"], cwd=self.project_dir, capture_output=True)

    def tearDown(self):
        shutil.rmtree(self.root_dir, ignore_errors=True)
        shutil.rmtree(self.remote_dir, ignore_errors=True)

    def test_e2e_watcher_to_ready_for_review(self):
        # 1. Lead AI writes TASK.md
        task_content = """# Current Task

## Task ID
e2e-task-001

## Goal
Implement a string capitalizer function.

## Background
We need to capitalize strings in src/cap.py.

## Allowed Files
- src/cap.py
- tests/test_cap.py

## Forbidden Operations
- Do not modify files outside Allowed Files

## Requirements
- Provide `capitalize_string(s: str) -> str` in `src/cap.py`.
- Handle empty string.
- Provide tests in `tests/test_cap.py`.

## Acceptance Criteria
- python -m unittest discover tests passes.

## Allowed Commands
- python -m unittest discover tests

## Review Points
- Clean typing and docstring.
"""
        task_file = self.project_dir / ".ai" / "TASK.md"
        task_file.write_text(task_content, encoding="utf-8")

        # 2. Configure watcher / runner
        config = SidekickConfig.load(self.project_dir)
        config.model = "qwen2.5:14b"
        config.auto_git = True
        config.auto_branch = True
        config.auto_commit = True
        config.auto_push = True
        config.require_clean_git = True # Validates that TASK.md does not block require_clean_git

        watcher = TaskWatcher(repo_root=self.project_dir, config=config)

        # 3. Trigger single watcher cycle
        res = watcher.run_once()
        self.assertIsNotNone(res)
        self.assertEqual(res.get("status"), "SUCCESS")
        self.assertEqual(res.get("automation_status"), "READY_FOR_REVIEW")
        self.assertEqual(res.get("branch"), "ai/e2e-task-001")
        self.assertTrue(len(res.get("commit_hash", "")) > 0)
        self.assertEqual(res.get("push_status"), "SUCCESS")

        # Verify remote received branch ai/e2e-task-001
        remote_branches = subprocess.run(
            ["git", "branch", "--list"], cwd=self.remote_dir, capture_output=True, text=True
        ).stdout
        self.assertIn("ai/e2e-task-001", remote_branches)

        # Verify committed RESULT.md contains READY_FOR_REVIEW and branch
        show_result = subprocess.run(
            ["git", "show", "HEAD:.ai/RESULT.md"], cwd=self.project_dir, capture_output=True, text=True
        ).stdout
        self.assertIn("READY_FOR_REVIEW", show_result)
        self.assertIn("ai/e2e-task-001", show_result)

        # Verify state.json
        state = SidekickState.load(self.project_dir / ".ai" / "state.json")
        self.assertEqual(state.task_id, "e2e-task-001")
        self.assertEqual(state.automation_status, "READY_FOR_REVIEW")

        # 4. Running watcher a second time without changing TASK.md should do nothing
        second_res = watcher.run_once()
        self.assertIsNone(second_res)

if __name__ == "__main__":
    unittest.main()
