"""Unit tests for sidekick init and sidekick doctor."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from sidekick.config import SidekickConfig
from sidekick.onboarding import init_repo, run_doctor


class TestOnboarding(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_init_repo_creates_expected_files(self):
        res = init_repo(self.test_dir)
        self.assertTrue((self.test_dir / ".ai" / "RULES.md").is_file())
        self.assertTrue((self.test_dir / ".ai" / "DECISIONS.md").is_file())
        self.assertTrue((self.test_dir / ".ai" / "DELEGATION.md").is_file())
        self.assertTrue((self.test_dir / "AGENTS.md").is_file())
        self.assertTrue((self.test_dir / "CLAUDE.md").is_file())
        self.assertTrue((self.test_dir / ".gitignore").is_file())

        delegation_text = (self.test_dir / ".ai" / "DELEGATION.md").read_text(encoding="utf-8")
        self.assertIn("confidence", delegation_text)
        self.assertIn("LOCAL", delegation_text)
        self.assertIn("BLOCKED", delegation_text)

        claude_text = (self.test_dir / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("@AGENTS.md", claude_text)
        self.assertIn("@.ai/DELEGATION.md", claude_text)

        gitignore_text = (self.test_dir / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".ai/state.json", gitignore_text)
        self.assertIn(".ai/sidekick.lock", gitignore_text)
        self.assertIn(".ai/TASK.md", gitignore_text)
        self.assertIn(".ai/RESULT.md", gitignore_text)

        # Confirm tracked created list (6 files total: 3 under .ai, AGENTS.md, CLAUDE.md, .gitignore)
        self.assertEqual(len(res["created"]), 6)
        self.assertEqual(len(res["skipped"]), 0)

    def test_init_repo_no_lead_option(self):
        res = init_repo(self.test_dir, include_lead_entrypoints=False)
        self.assertTrue((self.test_dir / ".ai" / "RULES.md").is_file())
        self.assertFalse((self.test_dir / "AGENTS.md").exists())
        self.assertFalse((self.test_dir / "CLAUDE.md").exists())
        self.assertEqual(len(res["created"]), 4)

    def test_init_repo_idempotent_and_force(self):
        init_repo(self.test_dir)
        (self.test_dir / ".ai" / "RULES.md").write_text("# Custom Rules", encoding="utf-8")

        # Second init without force skips existing
        res2 = init_repo(self.test_dir, force=False)
        self.assertEqual((self.test_dir / ".ai" / "RULES.md").read_text(encoding="utf-8"), "# Custom Rules")
        self.assertIn(os.path.join(".ai", "RULES.md"), [os.path.normpath(p) for p in res2["skipped"]])

        # Third init with force overwrites
        res3 = init_repo(self.test_dir, force=True)
        self.assertIn("Permanent Rules", (self.test_dir / ".ai" / "RULES.md").read_text(encoding="utf-8"))
        self.assertIn(os.path.join(".ai", "RULES.md"), [os.path.normpath(p) for p in res3["created"]])

    def test_init_repo_appends_to_existing_gitignore(self):
        (self.test_dir / ".gitignore").write_text("*.pyc\n__pycache__/\n", encoding="utf-8")
        res = init_repo(self.test_dir)
        self.assertTrue(res["gitignore_updated"])
        content = (self.test_dir / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("*.pyc", content)
        self.assertIn(".ai/state.json", content)

    def test_doctor_non_git_repo_fails(self):
        report = run_doctor(self.test_dir)
        self.assertTrue(report.has_failures)
        fail_checks = [c for c in report.checks if c.status == "FAIL"]
        self.assertTrue(any("Git Repository" in c.name for c in fail_checks))

    def test_doctor_missing_ai_dir_fails(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.test_dir, capture_output=True, check=False)
        report = run_doctor(self.test_dir)
        self.assertTrue(report.has_failures)
        fail_checks = [c for c in report.checks if c.status == "FAIL"]
        self.assertTrue(any(".ai Directory" in c.name for c in fail_checks))

    def test_doctor_missing_rules_fails(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.test_dir, capture_output=True, check=False)
        init_repo(self.test_dir)
        (self.test_dir / ".ai" / "RULES.md").unlink()
        report = run_doctor(self.test_dir)
        self.assertTrue(report.has_failures)
        rules_fail = [c for c in report.checks if c.name == "RULES.md" and c.status == "FAIL"]
        self.assertEqual(len(rules_fail), 1)

    def test_doctor_missing_model_fails_ready_check(self):
        """If configured model is missing in Ollama, doctor must FAIL (not just WARN) and block ready state."""
        subprocess.run(["git", "init", "-b", "main"], cwd=self.test_dir, capture_output=True, check=False)
        init_repo(self.test_dir)

        mock_tags_response = json.dumps({
            "models": [
                {"name": "llama3:8b", "size": 4000000000},
            ]
        }).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_tags_response
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            config = SidekickConfig.load(self.test_dir)
            config.model = "qwen2.5:14b"
            report = run_doctor(self.test_dir, config)
            self.assertTrue(report.has_failures)
            model_fail = [c for c in report.checks if c.name == "Model Availability" and c.status == "FAIL"]
            self.assertEqual(len(model_fail), 1)
            self.assertIn("qwen2.5:14b", model_fail[0].message)
            self.assertIn("EXECUTION BLOCKED", report.format_text())

    def test_doctor_mode_phase2_dirty_working_tree_fails(self):
        """In phase2 mode, uncommitted files must trigger FAIL because preflight requires a clean tree."""
        subprocess.run(["git", "init", "-b", "main"], cwd=self.test_dir, capture_output=True, check=False)
        init_repo(self.test_dir)
        # Create uncommitted dirty file
        (self.test_dir / "dirty_file.py").write_text("x = 1\n", encoding="utf-8")

        report = run_doctor(self.test_dir, mode="phase2")
        self.assertTrue(report.has_failures)
        tree_fail = [c for c in report.checks if c.name == "Working Tree" and c.status == "FAIL"]
        self.assertEqual(len(tree_fail), 1)

    def test_doctor_mode_phase1_dirty_working_tree_warns_only(self):
        """In phase1 mode, uncommitted files warn but do not fail execution readiness."""
        subprocess.run(["git", "init", "-b", "main"], cwd=self.test_dir, capture_output=True, check=False)
        init_repo(self.test_dir)
        (self.test_dir / "dirty_file.py").write_text("x = 1\n", encoding="utf-8")

        mock_tags = json.dumps({"models": [{"name": "qwen2.5:14b"}]}).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_tags
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            report = run_doctor(self.test_dir, mode="phase1")
            tree_checks = [c for c in report.checks if c.name == "Working Tree"]
            self.assertEqual(tree_checks[0].status, "WARN")
            self.assertFalse(report.has_failures)
            self.assertIn("READY FOR EXECUTION", report.format_text())

    def test_doctor_mode_delegation_missing_lead_entrypoints_fails(self):
        """In delegation mode, missing AGENTS.md / CLAUDE.md must FAIL."""
        subprocess.run(["git", "init", "-b", "main"], cwd=self.test_dir, capture_output=True, check=False)
        init_repo(self.test_dir, include_lead_entrypoints=False)

        report = run_doctor(self.test_dir, mode="delegation")
        self.assertTrue(report.has_failures)
        lead_fail = [c for c in report.checks if c.name == "Lead Host Entrypoints" and c.status == "FAIL"]
        self.assertEqual(len(lead_fail), 1)

    def test_doctor_healthy_repo_with_mocked_ollama(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.test_dir, capture_output=True, check=False)
        subprocess.run(["git", "config", "user.name", "Tester"], cwd=self.test_dir, capture_output=True, check=False)
        subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=self.test_dir, capture_output=True, check=False)
        init_repo(self.test_dir)
        subprocess.run(["git", "add", "."], cwd=self.test_dir, capture_output=True, check=False)
        subprocess.run(["git", "commit", "-m", "chore: initial"], cwd=self.test_dir, capture_output=True, check=False)

        mock_tags_response = json.dumps({
            "models": [
                {"name": "qwen2.5:14b", "size": 9000000000},
                {"name": "qwen2.5-coder:7b", "size": 4500000000},
            ]
        }).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_tags_response
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            config = SidekickConfig.load(self.test_dir)
            report = run_doctor(self.test_dir, config)
            self.assertFalse(report.has_failures)
            self.assertGreaterEqual(report.ok_count, 10)

            # Check formatted report text
            formatted = report.format_text()
            self.assertIn("Local AI Sidekick Doctor", formatted)
            self.assertIn("Model Availability", formatted)
            self.assertIn("READY FOR EXECUTION", formatted)

    def test_doctor_ollama_offline_fails(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.test_dir, capture_output=True, check=False)
        init_repo(self.test_dir)

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            report = run_doctor(self.test_dir)
            self.assertTrue(report.has_failures)
            ollama_fail = [c for c in report.checks if c.name == "Ollama Connection" and c.status == "FAIL"]
            self.assertEqual(len(ollama_fail), 1)
            self.assertIn("Connection refused", ollama_fail[0].message)


if __name__ == "__main__":
    unittest.main()
