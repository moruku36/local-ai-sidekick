import unittest
import tempfile
import shutil
from pathlib import Path
from sidekick.delegation import DelegationRouter, TaskGenerator, DelegationDecision
from sidekick.task_parser import TaskDefinition

class TestDelegationPolicy(unittest.TestCase):
    def test_local_simple_code_fix(self):
        d = DelegationRouter.evaluate("fix the null check in parser.py", allowed_files=["src/parser.py"])
        self.assertEqual(d.decision, "LOCAL")
        self.assertFalse(d.requires_human_approval)

    def test_local_unit_test(self):
        d = DelegationRouter.evaluate("add unit test for math_utils", allowed_files=["tests/test_math.py"])
        self.assertEqual(d.decision, "LOCAL")

    def test_local_readme_update(self):
        d = DelegationRouter.evaluate("update README with quickstart guide", allowed_files=["README.md"])
        self.assertEqual(d.decision, "LOCAL")

    def test_local_refactoring(self):
        d = DelegationRouter.evaluate("refactor the helper function to clean up dead code", allowed_files=["src/utils.py"])
        self.assertEqual(d.decision, "LOCAL")

    def test_lead_architecture_design(self):
        d = DelegationRouter.evaluate("create the system architecture design for user auth")
        self.assertEqual(d.decision, "LEAD")

    def test_lead_terraform_apply(self):
        d = DelegationRouter.evaluate("run terraform apply on aws prod environment")
        self.assertEqual(d.decision, "LEAD")

    def test_lead_aws_iam_change(self):
        d = DelegationRouter.evaluate("create a new IAM role with admin permissions")
        self.assertEqual(d.decision, "LEAD")

    def test_lead_root_account_task(self):
        d = DelegationRouter.evaluate("configure root account security settings")
        self.assertEqual(d.decision, "LEAD")

    def test_blocked_allowed_files_unknown(self):
        d = DelegationRouter.evaluate("refactor something", allowed_files=[])
        self.assertEqual(d.decision, "BLOCKED")
        self.assertTrue(d.requires_human_approval)

    def test_blocked_ambiguous_requirement(self):
        d = DelegationRouter.evaluate("make it look better and do some stuff")
        self.assertEqual(d.decision, "BLOCKED")

    def test_blocked_destructive_command(self):
        d = DelegationRouter.evaluate("run rm -rf /var/data and reset database")
        self.assertEqual(d.decision, "BLOCKED")
        self.assertEqual(d.risk, "critical")

class TestTaskGeneration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_task_id(self):
        tid = TaskGenerator.generate_task_id("fix-test")
        self.assertIn("fix-test", tid)
        self.assertTrue(len(tid) > 10)

    def test_write_task_file_and_parse(self):
        task_id, path = TaskGenerator.write_task_file(
            repo_root=self.temp_dir,
            goal="Fix unit test failure",
            background="Test is failing on empty input",
            allowed_files=["src/app.py", "tests/test_app.py"],
            allowed_commands=["python -m unittest discover tests"]
        )
        self.assertTrue(path.exists())
        task_def = TaskDefinition.parse_file(path)
        self.assertEqual(task_def.task_id, task_id)
        self.assertEqual(task_def.goal, "Fix unit test failure")
        self.assertEqual(task_def.allowed_files, ["src/app.py", "tests/test_app.py"])
        self.assertIn("python -m unittest discover tests", task_def.allowed_commands)
        self.assertTrue(len(task_def.forbidden_operations) > 0)

class TestDelegationWatcherIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        (self.temp_dir / ".ai").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_watcher_detects_and_prevents_loop(self):
        from sidekick.watcher import TaskWatcher
        from sidekick.config import SidekickConfig
        from sidekick.state_manager import SidekickState

        # 1. Generate task
        task_id, path = TaskGenerator.write_task_file(
            repo_root=self.temp_dir,
            goal="Refactor utils",
            allowed_files=["src/utils.py"]
        )
        self.assertTrue(path.exists())

        # 2. Setup watcher
        config = SidekickConfig.load(self.temp_dir)
        watcher = TaskWatcher(repo_root=self.temp_dir, config=config)

        # 3. Simulate existing completed state with matching hash
        task_hash = watcher._compute_hash()
        state = SidekickState(
            task_id=task_id,
            task_hash=task_hash,
            status="SUCCESS",
            automation_status="READY_FOR_REVIEW"
        )
        state.save(self.temp_dir / ".ai" / "state.json")

        # 4. Watcher run_once should detect already processed and return None (no loop)
        result = watcher.run_once()
        self.assertIsNone(result, "Watcher must skip task when task_id and hash match READY_FOR_REVIEW state")

if __name__ == "__main__":
    unittest.main()

