"""Synthetic tests for the explorer's read and evidence boundary."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sidekick.code_explore import run_code_explore
from sidekick.config import SidekickConfig
from sidekick.task_parser import TaskDefinition

WORKSPACE = Path(__file__).resolve().parents[2]


class CodeExploreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=WORKSPACE)
        self.root = Path(self.temp.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "sample.py").write_text(
            "def synthetic_function():\n    return 42\n", encoding="utf-8"
        )
        self.task = TaskDefinition(
            task_id="synthetic-explore", goal="Find the synthetic function.",
            allowed_files=["src/sample.py"], review_points=["Check the result against the source."],
        )
        self.config = SidekickConfig.load(self.root)
        self.model = Mock()
        self.model.chat_complete.return_value = json.dumps({
            "status": "SUCCESS",
            "facts": [{"claim": "The function is defined.", "path": "src/sample.py",
                       "line": 1, "excerpt": "def synthetic_function():"}],
            "inferences": [{"claim": "It may be a small helper.", "fact_refs": [1]}],
        })

    def tearDown(self):
        self.temp.cleanup()

    def run_role(self):
        with patch("subprocess.run", side_effect=AssertionError("no command or Git calls")):
            with patch.object(Path, "write_text", side_effect=AssertionError("no filesystem writes")):
                return run_code_explore(self.root, self.task, self.config, self.model)

    def test_valid_citation_and_inference_are_distinct(self):
        before = (self.root / "src" / "sample.py").read_bytes()
        self.config.auto_git = True
        self.config.auto_push = True
        result = self.run_role()
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["facts"][0]["citation"], "src/sample.py:1")
        self.assertEqual(result["inferences"][0]["fact_refs"], [1])
        self.assertEqual(result["search_scope"], [
            {"path": "src/sample.py", "lines_read": 2, "complete": True}
        ])
        self.assertEqual((self.root / "src" / "sample.py").read_bytes(), before)
        self.assertFalse((self.root / ".ai").exists())
        sent = json.loads(self.model.chat_complete.call_args.args[1][1]["content"])
        self.assertEqual(sent["source"][0]["lines"][0]["text"], "def synthetic_function():")

    def test_fabricated_line_or_excerpt_is_blocked(self):
        original = self.model.chat_complete.return_value
        for line, excerpt in [(99, "return 42"), (1, "unseen text")]:
            with self.subTest(line=line):
                response = json.loads(original)
                response["facts"][0].update({"line": line, "excerpt": excerpt})
                self.model.chat_complete.return_value = json.dumps(response)
                self.assertEqual(self.run_role()["status"], "BLOCKED")

    def test_action_fields_and_uncited_inferences_are_blocked(self):
        response = json.loads(self.model.chat_complete.return_value)
        response["files_to_write"] = [{"path": "src/sample.py", "content": "bad"}]
        self.model.chat_complete.return_value = json.dumps(response)
        self.assertEqual(self.run_role()["status"], "BLOCKED")
        response.pop("files_to_write")
        response["inferences"][0]["fact_refs"] = [2]
        self.model.chat_complete.return_value = json.dumps(response)
        self.assertEqual(self.run_role()["status"], "BLOCKED")

    def test_unsafe_or_nonexact_scope_is_blocked_before_model(self):
        for allowed in [[], ["src"], ["../outside.py"], [".ai/RESULT.md"],
                        [".env"], ["src/*.py"], ["src/sample.py", "src/sample.py"]]:
            with self.subTest(allowed=allowed):
                self.task.allowed_files = allowed
                self.assertEqual(self.run_role()["status"], "BLOCKED")
        self.model.chat_complete.assert_not_called()

    def test_commands_in_task_are_blocked(self):
        self.task.allowed_commands = ["python -m unittest"]
        self.assertEqual(self.run_role()["status"], "BLOCKED")
        self.model.chat_complete.assert_not_called()

    def test_truncated_lines_cannot_be_cited(self):
        self.config.max_file_bytes = len("def synthetic_function():\n".encode()) + 5
        response = json.loads(self.model.chat_complete.return_value)
        response["facts"][0].update({"line": 2, "excerpt": "return"})
        self.model.chat_complete.return_value = json.dumps(response)
        result = self.run_role()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["search_scope"][0]["complete"])
        self.assertEqual(result["unsearched"][0]["reason"], "remainder beyond read limit")

    def test_missing_file_is_reported_as_unsearched(self):
        self.task.allowed_files.append("src/missing.py")
        result = self.run_role()
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["unsearched"], [
            {"path": "src/missing.py", "reason": "file does not exist"}
        ])

    def test_all_files_missing_never_calls_model(self):
        self.task.allowed_files = ["src/missing.py"]
        result = self.run_role()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["unsearched"][0]["reason"], "file does not exist")
        self.model.chat_complete.assert_not_called()

    def test_possible_secret_is_never_sent_to_model(self):
        (self.root / "src" / "sample.py").write_text(
            "password='synthetic-placeholder-value'\n", encoding="utf-8"
        )
        result = self.run_role()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["unsearched"][0]["reason"], "possible sensitive content")
        self.model.chat_complete.assert_not_called()

    def test_model_unavailable_and_oversized_response_are_blocked(self):
        self.model.chat_complete.side_effect = ConnectionRefusedError("offline")
        self.assertEqual(self.run_role()["status"], "BLOCKED")
        self.model.chat_complete.side_effect = None
        self.model.chat_complete.return_value = "x" * 64_001
        self.assertEqual(self.run_role()["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
