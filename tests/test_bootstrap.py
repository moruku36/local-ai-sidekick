"""Unit tests for ai-dev-bootstrap (sidekick.bootstrap)."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from sidekick.bootstrap import build_context


class TestBootstrapContext(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _init_git(self, path: Path):
        subprocess.run(["git", "init", "-q"], cwd=path, check=True)

    def test_non_git_directory(self):
        context = build_context(self.test_dir)
        self.assertIn("not a Git repository", context)
        self.assertIn("Local AI Sidekick:\nUNAVAILABLE", context)

    def test_normal_git_repository_not_initialized(self):
        self._init_git(self.test_dir)
        context = build_context(self.test_dir)
        self.assertIn(str(self.test_dir.resolve()), context)
        self.assertIn("NOT_INITIALIZED", context)
        self.assertIn("sidekick init .", context)

    def test_sidekick_initialized_repository(self):
        self._init_git(self.test_dir)
        ai_dir = self.test_dir / ".ai"
        ai_dir.mkdir()
        (ai_dir / "DELEGATION.md").write_text("policy", encoding="utf-8")
        (ai_dir / "RULES.md").write_text("rules", encoding="utf-8")
        context = build_context(self.test_dir)
        self.assertIn("Local AI Sidekick:\nREADY", context)
        self.assertIn("ENABLED", context)

    def test_worker_lock_detected(self):
        self._init_git(self.test_dir)
        ai_dir = self.test_dir / ".ai"
        ai_dir.mkdir()
        (ai_dir / "sidekick.lock").write_text("pid=1\n", encoding="utf-8")
        context = build_context(self.test_dir)
        self.assertIn("Worker:\nRUNNING", context)

    def test_factory_unavailable_by_default(self):
        self._init_git(self.test_dir)
        context = build_context(self.test_dir)
        self.assertIn("AI Engineering Factory:\nUNAVAILABLE", context)

    def test_factory_configured_via_manifest(self):
        self._init_git(self.test_dir)
        (self.test_dir / "factory.yaml").write_text("x: 1", encoding="utf-8")
        context = build_context(self.test_dir)
        self.assertIn("AI Engineering Factory:\nCONFIGURED", context)

    def test_output_contains_no_secret_like_strings(self):
        self._init_git(self.test_dir)
        context = build_context(self.test_dir)
        lowered = context.lower()
        for token in ("password", "api_key", "secret=", "token="):
            self.assertNotIn(token, lowered)

    def test_output_is_bounded(self):
        self._init_git(self.test_dir)
        context = build_context(self.test_dir)
        self.assertLess(len(context), 2200)

    def test_context_never_raises_on_bad_cwd(self):
        # A path that does not exist must degrade, not crash.
        context = build_context(self.test_dir / "does-not-exist")
        self.assertIn("AI DEVELOPMENT ENVIRONMENT", context)


class TestBootstrapMain(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q"], cwd=self.test_dir, check=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _run_bootstrap(self, stdin_payload, extra_args=None):
        cmd = ["python", "-m", "sidekick.bootstrap"] + (extra_args or [])
        return subprocess.run(
            cmd, input=stdin_payload, capture_output=True, text=True, check=False
        )

    def test_valid_session_start_json(self):
        payload = json.dumps({"cwd": str(self.test_dir)})
        result = self._run_bootstrap(payload)
        self.assertEqual(result.returncode, 0)
        self.assertIn("AI DEVELOPMENT ENVIRONMENT", result.stdout)

    def test_invalid_session_start_json_does_not_crash(self):
        result = self._run_bootstrap("{not valid json")
        self.assertEqual(result.returncode, 0)
        self.assertIn("AI DEVELOPMENT ENVIRONMENT", result.stdout)

    def test_missing_cwd_field_falls_back(self):
        result = self._run_bootstrap(json.dumps({"hook_event_name": "SessionStart"}))
        self.assertEqual(result.returncode, 0)
        self.assertIn("AI DEVELOPMENT ENVIRONMENT", result.stdout)

    def test_malicious_cwd_path_is_safely_resolved_or_ignored(self):
        payload = json.dumps({"cwd": "/nonexistent/../../etc/passwd\x00injected"})
        result = self._run_bootstrap(payload)
        self.assertEqual(result.returncode, 0)
        self.assertIn("AI DEVELOPMENT ENVIRONMENT", result.stdout)

    def test_json_output_mode_matches_claude_hook_contract(self):
        payload = json.dumps({"cwd": str(self.test_dir)})
        result = self._run_bootstrap(payload, extra_args=["--json"])
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("AI DEVELOPMENT ENVIRONMENT", data["hookSpecificOutput"]["additionalContext"])


if __name__ == "__main__":
    unittest.main()
