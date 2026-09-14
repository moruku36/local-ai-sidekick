import unittest
import tempfile
import shutil
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
            allowed_files=["src/calc.py", "tests/test_calc.py", "src/"],
            allowed_commands=["python -m unittest", "terraform validate", "pytest"]
        )

    def test_file_allowlist(self):
        allowed, _ = self.policy.is_path_allowed("src/calc.py")
        self.assertTrue(allowed)

        # Directory prefix matching
        allowed_sub, _ = self.policy.is_path_allowed("src/sub/helper.py")
        self.assertTrue(allowed_sub)

        # Disallowed file
        disallowed, reason = self.policy.is_path_allowed("docs/readme.md")
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

    def test_command_allowlist_positive(self):
        # Allowed exact and arguments
        self.assertTrue(self.policy.is_command_allowed("python -m unittest")[0])
        self.assertTrue(self.policy.is_command_allowed("python -m unittest discover tests")[0])
        self.assertTrue(self.policy.is_command_allowed("terraform validate")[0])

    def test_command_allowlist_blocked_shell_metacharacters(self):
        blocked_cases = [
            "python -m unittest && whoami",
            "python -m unittest ; whoami",
            "python -m unittest | more",
            "python -m unittest > result.txt",
            "python -m unittest >> result.txt",
            "python -m unittest < input.txt",
            "terraform validate && terraform apply",
            "python -m unittest $(whoami)",
            "python -m unittest `whoami`",
            "python -m unittest || exit 1"
        ]
        for cmd in blocked_cases:
            allowed, reason = self.policy.is_command_allowed(cmd)
            self.assertFalse(allowed, f"Expected '{cmd}' to be blocked, but was allowed.")

    def test_command_allowlist_unauthorized_and_destructive(self):
        self.assertFalse(self.policy.is_command_allowed("rm -rf src")[0])
        self.assertFalse(self.policy.is_command_allowed("terraform apply")[0])
        self.assertFalse(self.policy.is_command_allowed("gcloud compute instances delete foo")[0])
        self.assertFalse(self.policy.is_command_allowed("git commit -m 'test'")[0])

    def test_excluded_paths(self):
        self.assertTrue(self.policy.is_path_excluded(".git/HEAD"))
        self.assertTrue(self.policy.is_path_excluded(".env"))
        self.assertTrue(self.policy.is_path_excluded(".env.production"))
        self.assertTrue(self.policy.is_path_excluded("node_modules/pkg/index.js"))
        self.assertTrue(self.policy.is_path_excluded(".venv/bin/python"))
        self.assertTrue(self.policy.is_path_excluded("src/__pycache__/app.cpython-311.pyc"))
        self.assertTrue(self.policy.is_path_excluded("terraform.tfstate"))
        self.assertTrue(self.policy.is_path_excluded("secrets/server.key"))
        self.assertTrue(self.policy.is_path_excluded("certs/app.pem"))
        self.assertTrue(self.policy.is_path_excluded("logs/app.log"))

        # Valid source files should not be excluded
        self.assertFalse(self.policy.is_path_excluded("src/app.py"))
        self.assertFalse(self.policy.is_path_excluded("tests/test_calc.py"))

    def test_sanitize_output(self):
        raw = "Error with token gho_123456789012345678901234 and password: mysecretpassword123"
        sanitized = SecurityPolicy.sanitize_output(raw)
        self.assertNotIn("gho_123456789012345678901234", sanitized)
        self.assertIn("[REDACTED_GH_TOKEN]", sanitized)
        self.assertNotIn("mysecretpassword123", sanitized)

if __name__ == "__main__":
    unittest.main()
