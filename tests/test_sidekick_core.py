import unittest
from pathlib import Path
from sidekick.task_parser import TaskDefinition
from sidekick.security import SecurityPolicy

class TestTaskParser(unittest.TestCase):
    def test_parse_task(self):
        sample = """# Current Task

## Goal
Implement a calculator function.

## Background
Need basic math operations.

## Allowed Files
- src/calc.py
- tests/test_calc.py

## Forbidden Operations
- Do not delete any existing tests

## Requirements
- Add add(a, b) function
- Return float or int

## Acceptance Criteria
- pytest passes

## Allowed Commands
- python -m unittest
- pytest

## Review Points
- Type annotations
"""
        task = TaskDefinition.parse(sample)
        self.assertEqual(task.goal, "Implement a calculator function.")
        self.assertEqual(task.background, "Need basic math operations.")
        self.assertEqual(task.allowed_files, ["src/calc.py", "tests/test_calc.py"])
        self.assertEqual(task.forbidden_operations, ["Do not delete any existing tests"])
        self.assertEqual(task.requirements, ["Add add(a, b) function", "Return float or int"])
        self.assertEqual(task.acceptance_criteria, ["pytest passes"])
        self.assertEqual(task.allowed_commands, ["python -m unittest", "pytest"])
        self.assertEqual(task.review_points, ["Type annotations"])

class TestSecurityPolicy(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parent.parent
        self.policy = SecurityPolicy(
            repo_root=self.root,
            allowed_files=["src/calc.py", "tests/test_calc.py"],
            allowed_commands=["pytest", "python -m unittest"]
        )

    def test_file_allowlist(self):
        allowed, _ = self.policy.is_path_allowed("src/calc.py")
        self.assertTrue(allowed)

        # Disallowed file
        disallowed, reason = self.policy.is_path_allowed("src/other.py")
        self.assertFalse(disallowed)

        # Git and env are blocked
        dotgit, _ = self.policy.is_path_allowed(".git/config")
        self.assertFalse(dotgit)

        dotenv, _ = self.policy.is_path_allowed(".env")
        self.assertFalse(dotenv)

        # Decisions.md is immutable
        dec, _ = self.policy.is_path_allowed(".ai/DECISIONS.md")
        self.assertFalse(dec)

        # Result is always allowed
        res, _ = self.policy.is_path_allowed(".ai/RESULT.md")
        self.assertTrue(res)

    def test_command_allowlist_and_forbidden(self):
        allowed, _ = self.policy.is_command_allowed("pytest")
        self.assertTrue(allowed)

        # Disallowed command
        disallowed, _ = self.policy.is_command_allowed("git commit -m 'test'")
        self.assertFalse(disallowed)

        # Forbidden destructive patterns
        rm_cmd, _ = self.policy.is_command_allowed("rm -rf src")
        self.assertFalse(rm_cmd)

        tf_cmd, _ = self.policy.is_command_allowed("terraform apply")
        self.assertFalse(tf_cmd)

        gcloud_cmd, _ = self.policy.is_command_allowed("gcloud compute instances delete foo")
        self.assertFalse(gcloud_cmd)

    def test_sanitize_output(self):
        raw = "Error with token gho_123456789012345678901234 and password: mysecretpassword123"
        sanitized = SecurityPolicy.sanitize_output(raw)
        self.assertNotIn("gho_123456789012345678901234", sanitized)
        self.assertIn("[REDACTED_GH_TOKEN]", sanitized)
        self.assertNotIn("mysecretpassword123", sanitized)

if __name__ == "__main__":
    unittest.main()
