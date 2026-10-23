"""Synthetic integration checks for explicit role capability paths."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sidekick.config import SidekickConfig
from sidekick.runner import SidekickRunner
from sidekick.task_parser import TaskDefinition


WORKSPACE = Path(__file__).resolve().parents[2]
COMMAND = "python -m compileall -q src"


class WorkerRoleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=WORKSPACE)
        self.root = Path(self.temp.name)
        (self.root / ".ai").mkdir()
        (self.root / ".ai" / "RULES.md").write_text("Use only the task scope.", encoding="utf-8")
        (self.root / "src").mkdir()
        (self.root / "src" / "one.py").write_text("def one():\n    return 1\n", encoding="utf-8")
        (self.root / "src" / "two.py").write_text("def two():\n    return 2\n", encoding="utf-8")
        self.config = SidekickConfig.load(self.root)
        self.config.auto_git = True
        self.config.auto_push = True
        self.config.max_retries = 0
        self.runner = SidekickRunner(self.root, self.config)

    def tearDown(self):
        self.temp.cleanup()

    def task(self, role, files=None, commands=None):
        task = TaskDefinition(
            task_id="synthetic-role", worker_role=role, goal="Inspect or update the synthetic example.",
            background="Only public synthetic source is in scope.",
            requirements=["Keep the example small."], acceptance_criteria=["Verify the scoped result."],
            allowed_files=files or ["src/one.py"],
            allowed_commands=commands if commands is not None else [COMMAND],
            review_points=["Review the source and cited facts."],
        )
        body = ["# Current Task", "## Task ID", task.task_id, "## Worker Role", role,
                "## Goal", task.goal, "## Background", task.background]
        for title, values in [("Requirements", task.requirements), ("Acceptance Criteria", task.acceptance_criteria),
                              ("Allowed Files", task.allowed_files), ("Allowed Commands", task.allowed_commands),
                              ("Review Points", task.review_points)]:
            body.extend(["## " + title, *("- " + item for item in values)])
        (self.root / ".ai" / "TASK.md").write_text("\n\n".join(body), encoding="utf-8")

    def test_explore_dispatch_never_enters_git_or_command_path(self):
        self.task("code-explore", commands=[])
        self.runner.ollama.check_health = lambda: True
        self.runner.ollama.is_model_available = lambda _: True
        self.runner.ollama.chat_complete = lambda *args, **kwargs: json.dumps({
            "status": "SUCCESS", "facts": [{"claim": "one exists", "path": "src/one.py",
                                                 "line": 1, "excerpt": "def one():"}], "inferences": []
        })
        with patch.object(self.runner.git_manager, "preflight_check", side_effect=AssertionError("Git called")):
            with patch("sidekick.workspace.WorkspaceManager.run_command", side_effect=AssertionError("command called")):
                result = self.runner.execute()
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["role_report"]["facts"][0]["citation"], "src/one.py:1")
        self.assertEqual(result["files_changed"], [])
        self.assertEqual(result["verification_status"], "UNVERIFIED")

    def test_spec_batch_rejects_second_invalid_edit_before_first_write(self):
        self.task("spec-coder", files=["src/one.py", "src/two.py"])
        self.config.auto_git = False
        self.runner.ollama.check_health = lambda: True
        self.runner.ollama.is_model_available = lambda _: True
        self.runner.ollama.chat_complete = lambda *args, **kwargs: json.dumps({
            "status": "SUCCESS", "summary": "Synthetic edit", "files_to_write": [
                {"path": "src/one.py", "content": "changed\n"},
                {"path": "src/other.py", "content": "outside scope\n"}],
            "verification_command": COMMAND, "decisions_required": "", "review_points": "Check diff",
        })
        before = (self.root / "src" / "one.py").read_bytes()
        with patch.object(self.runner.git_manager, "get_current_branch", return_value="local"):
            result = self.runner.execute()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual((self.root / "src" / "one.py").read_bytes(), before)

    def test_spec_valid_batch_records_actual_verification(self):
        self.task("spec-coder")
        self.config.auto_git = False
        self.runner.ollama.check_health = lambda: True
        self.runner.ollama.is_model_available = lambda _: True
        self.runner.ollama.chat_complete = lambda *args, **kwargs: json.dumps({
            "status": "SUCCESS", "summary": "Update synthetic helper",
            "files_to_write": [{"path": "src/one.py", "content": "def one():\n    return 3\n"}],
            "verification_command": COMMAND, "decisions_required": "",
            "review_points": "Check diff", "unverified_claims": ["Runtime behavior needs review"],
        })
        with patch.object(self.runner.git_manager, "get_current_branch", return_value="local"):
            with patch("sidekick.workspace.WorkspaceManager.run_command", return_value=(0, "", "")):
                with patch("sidekick.workspace.WorkspaceManager.get_git_diff_summary", return_value="synthetic diff"):
                    result = self.runner.execute()
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["implementation_status"], "CHANGES_APPLIED")
        self.assertEqual(result["verification_status"], "PASSED")
        self.assertEqual(result["spec_unverified_claims"], ["Runtime behavior needs review"])
        self.assertIn("return 3", (self.root / "src" / "one.py").read_text(encoding="utf-8"))

    def test_nonlocal_model_endpoint_blocks_before_source_read(self):
        self.task("code-explore", commands=[])
        self.config.ollama_base_url = "https://example.invalid:11434"
        with patch.object(self.runner.ollama, "check_health", side_effect=AssertionError("model contacted")):
            result = self.runner.execute()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("local Ollama", result["errors"])

    def test_command_runner_records_observation_without_model_or_git(self):
        self.task("command-runner")
        with patch.object(self.runner.git_manager, "preflight_check", side_effect=AssertionError("Git called")):
            with patch.object(self.runner.ollama, "chat_complete", side_effect=AssertionError("model called")):
                with patch("sidekick.workspace.WorkspaceManager.run_command", return_value=(0, "", "")):
                    result = self.runner.execute()
        self.assertEqual(result["status"], "SUCCESS")
        observation = result["verification_observations"][0]
        self.assertEqual(observation["execution"], "RAN")
        self.assertEqual(observation["verification"], "PASSED")
        self.assertEqual(observation["candidate_digest"], result["role_report"]["candidate_digest_before"])
        self.assertFalse(observation["output_retained"])


if __name__ == "__main__":
    unittest.main()
