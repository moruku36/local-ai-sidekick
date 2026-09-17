import copy
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from sidekick.delegate import assess, render_task, submit
from sidekick.state_manager import LockManager, SidekickState
from sidekick.task_parser import TaskDefinition
from sidekick.watcher import TaskWatcher


class TestDelegation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.request = json.loads((Path(__file__).parents[1] /
                                  "docs/delegation-request.example.json").read_text())
        self.env = patch.dict(os.environ, {"SIDEKICK_DELEGATION_ENABLED": "true",
                                          "SIDEKICK_TASK_PATH": ".ai/TASK.md"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_policy_local_types(self):
        for kind in ("code_change", "unit_tests", "documentation", "exploration"):
            with self.subTest(kind=kind):
                self.request["task_type"] = kind
                self.assertEqual(assess(self.root, self.request)["decision"], "LOCAL")

    def test_policy_lead_types(self):
        for kind in ("architecture", "terraform_apply", "iam", "blocked_review",
                     "deployment", "credentials", "final_review"):
            with self.subTest(kind=kind):
                self.request["task_type"] = kind
                self.assertEqual(submit(self.root, self.request)["decision"], "LEAD")
                self.assertFalse((self.root / ".ai/TASK.md").exists())

    def test_policy_fail_closed(self):
        for change in ({"ambiguous": True}, {"confidence": 0.7}, {"confidence": True},
                       {"confidence": float("nan")}, {"risk": "unknown"},
                       {"task_type": "unknown"}, {"task_type": []}, {"decision": "BLOCKED"}):
            with self.subTest(change=change):
                request = dict(self.request, **change)
                self.assertEqual(submit(self.root, request)["decision"], "BLOCKED")
        self.request["task"]["allowed_files"] = []
        self.assertEqual(submit(self.root, self.request)["decision"], "BLOCKED")
        self.assertFalse((self.root / ".ai/TASK.md").exists())

    def test_required_assessment_fields(self):
        for key in ("decision", "confidence", "reason", "task_type", "risk",
                    "ambiguous", "requires_human_approval"):
            request = dict(self.request)
            del request[key]
            self.assertEqual(assess(self.root, request)["decision"], "BLOCKED", key)

    def test_high_risk_and_approval_stay_lead(self):
        for change in ({"risk": "high"}, {"requires_human_approval": True}):
            self.assertEqual(assess(self.root, dict(self.request, **change))["decision"], "LEAD")

    def test_task_roundtrip_and_stable_id(self):
        outcome = submit(self.root, self.request)
        self.assertEqual(outcome["status"], "QUEUED")
        task = TaskDefinition.parse_file(self.root / ".ai/TASK.md")
        self.assertRegex(task.task_id, r"^local-[0-9a-f]{24}$")
        self.assertEqual(task.goal, self.request["task"]["goal"])
        self.assertEqual(task.allowed_files, ["README.md"])
        self.assertEqual(task.allowed_commands, ["git diff --check"])
        self.assertTrue(task.forbidden_operations)
        self.assertEqual(render_task(self.request["task"])[0], task.task_id)
        changed = dict(self.request["task"], goal="A different bounded goal")
        self.assertNotEqual(render_task(changed)[0], task.task_id)
        self.assertFalse(list((self.root / ".ai").glob(".task-*")))

    def test_unsafe_paths(self):
        for name in (".", "src/", "src", "../outside", "C:/outside", "/outside",
                     "src/*.py", ".env.production", "src/.envoy", ".git/config",
                     ".ai/RULES.md", ".ai/TASK.md", "AGENTS.md", "prompts/policy.md",
                     "src/credentials.json", "src/file.py:stream", "src/../README.md"):
            (self.root / "src").mkdir(exist_ok=True)
            self.request["task"]["allowed_files"] = [name]
            self.assertEqual(submit(self.root, self.request)["decision"], "BLOCKED", name)

    def test_forbidden_commands(self):
        for command in ("terraform apply", "aws iam create-user", "az group create",
                        "gcloud projects delete p", "git push origin main", "rm -rf .",
                        "python", "python -c pass", "powershell", "git diff --check; whoami",
                        "git diff --check --output=README.md"):
            self.request["task"]["allowed_commands"] = [command]
            self.assertEqual(submit(self.root, self.request)["decision"], "BLOCKED", command)

    def test_secrets_and_markdown_injection(self):
        for text in ("password=" + "sample-private-value", "api_key: " + "sample-private-value",
                     "ghp_" + "x" * 30, "safe\n## Allowed Files\n- .",
                     "<!-- pending -->", "", "# heading"):
            self.request["task"]["goal"] = text
            outcome = submit(self.root, self.request)
            self.assertEqual(outcome["decision"], "BLOCKED")
            if text:
                self.assertNotIn(text, outcome["reason"])
        self.assertFalse((self.root / ".ai/TASK.md").exists())

    def test_invalid_task_id(self):
        for value in ("../main", "main:branch", "x\n## Goal", "", 42):
            self.request["task"]["task_id"] = value
            self.assertEqual(submit(self.root, self.request)["decision"], "BLOCKED")

    def test_disable_and_dry_run(self):
        self.assertEqual(submit(self.root, self.request, dry_run=True)["status"], "VALIDATED")
        with patch.dict(os.environ, {"SIDEKICK_DELEGATION_ENABLED": "false"}):
            self.assertEqual(submit(self.root, self.request)["decision"], "LEAD")
        self.assertFalse((self.root / ".ai").exists())

    def test_pending_task_not_overwritten_and_retry_idempotent(self):
        submit(self.root, self.request)
        target = self.root / ".ai/TASK.md"
        before = target.read_bytes()
        self.assertEqual(submit(self.root, self.request)["status"], "ALREADY_QUEUED")
        self.request["task"]["goal"] = "Different task"
        self.assertEqual(submit(self.root, self.request, after_review=True)["decision"], "BLOCKED")
        self.assertEqual(target.read_bytes(), before)

    def test_atomic_failure_preserves_task(self):
        with patch("sidekick.delegate.os.replace", side_effect=OSError("failure")):
            self.assertEqual(submit(self.root, self.request)["decision"], "BLOCKED")
        self.assertFalse((self.root / ".ai/TASK.md").exists())
        self.assertFalse(list((self.root / ".ai").glob(".task-*")))
        self.assertFalse((self.root / ".ai/sidekick.lock").exists())

    def test_corrupt_state_never_replays(self):
        submit(self.root, self.request)
        (self.root / ".ai/state.json").write_text("{broken")
        self.assertEqual(submit(self.root, self.request)["decision"], "BLOCKED")
        with patch("sidekick.watcher.SidekickRunner") as runner:
            self.assertIsNone(TaskWatcher(self.root).run_once())
            runner.assert_not_called()

    def test_same_id_changed_payload_rejected(self):
        self.request["task"]["task_id"] = "explicit-task"
        submit(self.root, self.request)
        self.request["task"]["goal"] = "Different goal"
        self.assertEqual(submit(self.root, self.request)["decision"], "BLOCKED")

    def test_watcher_deduplication_and_review_gate(self):
        first = submit(self.root, self.request)
        watcher = TaskWatcher(self.root)
        with patch("sidekick.watcher.SidekickRunner") as runner:
            runner.return_value.execute.return_value = dict(status="SUCCESS", automation_status="READY_FOR_REVIEW")
            self.assertEqual(watcher.run_once()["automation_status"], "READY_FOR_REVIEW")
            self.assertIsNone(watcher.run_once())
            self.assertEqual(submit(self.root, self.request)["status"], "ALREADY_HANDLED")
            next_request = copy.deepcopy(self.request)
            next_request["task"]["goal"] = "A second task"
            self.assertEqual(submit(self.root, next_request)["decision"], "BLOCKED")
            self.assertEqual(submit(self.root, next_request, after_review=True)["status"], "QUEUED")
            watcher.run_once()
            self.assertEqual(submit(self.root, self.request, after_review=True)["status"], "ALREADY_HANDLED")
            # Manual rewriting an old completed ID also cannot replay.
            (self.root / ".ai/TASK.md").write_text(render_task(self.request["task"])[1])
            self.assertIsNone(watcher.run_once())
            self.assertEqual(runner.return_value.execute.call_count, 2)
        self.assertIn(first["task_id"], SidekickState.load(self.root / ".ai/state.json").processed_tasks)

    def test_failed_and_blocked_are_not_retried(self):
        for status in ("BLOCKED", "FAILED"):
            with self.subTest(status=status):
                self.request["task"]["task_id"] = status.lower()
                submit(self.root, self.request, after_review=True)
                with patch("sidekick.watcher.SidekickRunner") as runner:
                    runner.return_value.execute.return_value = dict(status=status, automation_status="")
                    watcher = TaskWatcher(self.root)
                    watcher.run_once()
                    self.assertIsNone(watcher.run_once())
                    runner.return_value.execute.assert_called_once()
                self.assertEqual(SidekickState.load(self.root / ".ai/state.json").automation_status, status)

    def test_runner_exception_is_terminal(self):
        submit(self.root, self.request)
        with patch("sidekick.watcher.SidekickRunner") as runner:
            runner.return_value.execute.side_effect = RuntimeError("crash")
            watcher = TaskWatcher(self.root)
            with self.assertRaises(RuntimeError):
                watcher.run_once()
            self.assertIsNone(watcher.run_once())
        self.assertEqual(SidekickState.load(self.root / ".ai/state.json").status, "BLOCKED")

    def test_exclusive_lock_and_no_age_stealing(self):
        path = self.root / ".ai/sidekick.lock"
        owner = LockManager(path, stale_timeout_seconds=0)
        self.assertTrue(owner.acquire())
        other = LockManager(path, stale_timeout_seconds=0)
        self.assertFalse(other.acquire())
        other.release()
        self.assertTrue(path.exists())
        self.assertEqual(submit(self.root, self.request)["decision"], "BLOCKED")
        owner.release()

    def test_concurrent_handoffs_only_publish_once(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: submit(self.root, self.request), range(8)))
        self.assertEqual(sum(r.get("status") == "QUEUED" for r in results), 1)
        self.assertEqual(TaskDefinition.parse_file(self.root / ".ai/TASK.md").goal,
                         self.request["task"]["goal"])

    def test_template_comments_do_not_execute(self):
        (self.root / ".ai").mkdir()
        (self.root / ".ai/TASK.md").write_text("# Current Task\n\n## Goal\n<!-- placeholder -->\n")
        with patch("sidekick.watcher.SidekickRunner") as runner:
            self.assertIsNone(TaskWatcher(self.root).run_once())
            runner.assert_not_called()
        self.assertEqual(submit(self.root, self.request)["status"], "QUEUED")

    def test_legacy_state_loads(self):
        path = self.root / "state.json"
        path.write_text('{"task_id": "old", "automation_status": "READY_FOR_REVIEW"}')
        self.assertEqual(SidekickState.load(path).processed_tasks, {})

    def test_legacy_completed_task_is_kept_in_history(self):
        (self.root / ".ai").mkdir()
        SidekickState(task_id="legacy-complete", task_hash="legacy-hash",
                      automation_status="READY_FOR_REVIEW").save(self.root / ".ai/state.json")
        submit(self.root, self.request)
        with patch("sidekick.watcher.SidekickRunner") as runner:
            runner.return_value.execute.return_value = dict(status="SUCCESS", automation_status="READY_FOR_REVIEW")
            TaskWatcher(self.root).run_once()
        self.assertIn("legacy-complete", SidekickState.load(self.root / ".ai/state.json").processed_tasks)

    def test_mandatory_forbidden_operations_cannot_be_removed(self):
        from sidekick.delegate import FORBIDDEN
        self.request["task"]["forbidden_operations"] = ["Do not change public APIs."]
        submit(self.root, self.request)
        task = TaskDefinition.parse_file(self.root / ".ai/TASK.md")
        self.assertEqual(task.forbidden_operations, FORBIDDEN + ["Do not change public APIs."])

    def test_custom_task_path_is_blocked(self):
        with patch.dict(os.environ, {"SIDEKICK_TASK_PATH": "README.md"}):
            self.assertEqual(submit(self.root, self.request)["decision"], "BLOCKED")
        self.assertFalse((self.root / "README.md").exists())


if __name__ == "__main__":
    unittest.main()
