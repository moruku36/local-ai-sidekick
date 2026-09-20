"""File watcher for .ai/TASK.md in Phase 2."""
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Optional

from .config import SidekickConfig
from .runner import SidekickRunner
from .state_manager import LockManager, SidekickState
from .task_parser import TaskDefinition


class TaskWatcher:
    def __init__(self, repo_root: Path, config: Optional[SidekickConfig] = None):
        self.repo_root = repo_root.resolve()
        self.config = config or SidekickConfig.load(self.repo_root)
        self.task_file = self.repo_root / self.config.task_path
        self.state_file = self.repo_root / ".ai" / "state.json"
        self.lock_file = self.repo_root / ".ai" / "sidekick.lock"
        self.lock_manager = LockManager(self.lock_file)

    def _compute_hash(self) -> str:
        if not self.task_file.exists():
            return ""
        content = self.task_file.read_bytes()
        return hashlib.sha256(content).hexdigest()

    def run_once(self) -> Optional[dict]:
        """Checks if TASK.md has a new unhandled task and executes Phase 2 runner if ready."""
        # Read task and state only after acquiring the same lock as the producer.
        if not self.lock_manager.acquire():
            return None
        try:
            return self._run_locked()
        finally:
            self.lock_manager.release()

    def _run_locked(self) -> Optional[dict]:
        if not self.task_file.exists():
            return None

        current_hash = self._compute_hash()
        try:
            state = (SidekickState(**json.loads(self.state_file.read_text(encoding="utf-8")))
                     if self.state_file.exists() else SidekickState())
            if not isinstance(state.processed_tasks, dict):
                return None
        except (ValueError, TypeError, OSError):
            return None  # Corrupt state needs Lead review, never replay tasks.

        try:
            task = TaskDefinition.parse_file(self.task_file)
        except Exception:
            return None

        if not re.sub(r"<!--.*?-->", "", task.goal, flags=re.DOTALL).strip():
            return None

        # Check if already processed
        if (task.task_id in state.processed_tasks or current_hash in state.processed_tasks.values() or
                (state.task_id == task.task_id and state.automation_status not in ["", "IDLE"])):
            return None

        try:
            # Persist before execution. A crash must require review, not rerun.
            if state.task_id and state.automation_status not in ["", "IDLE"]:
                state.processed_tasks.setdefault(state.task_id, state.task_hash)
            state.processed_tasks[task.task_id] = current_hash
            state.task_id = task.task_id
            state.task_hash = current_hash
            state.status = "RUNNING"
            state.automation_status = "RUNNING"
            state.save(self.state_file)
            print(f"\n[Watcher] Detected new or updated task '{task.task_id}'! Triggering Sidekick Phase 2...")
            # Set auto_git true for Phase 2 watcher
            self.config.auto_git = True
            runner = SidekickRunner(repo_root=self.repo_root, config=self.config)
            result = runner.execute()

            # Record state
            state.task_id = task.task_id
            state.task_hash = current_hash
            state.status = result.get("status", "FAILED")
            state.branch = result.get("branch", "")
            state.commit_hash = result.get("commit_hash", "")
            state.push_status = result.get("push_status", "")
            state.automation_status = result.get("automation_status") or state.status
            state.updated_at = time.strftime("%Y-%m-%d %H:%M:%S")
            state.save(self.state_file)
            return result
        except Exception:
            state.status = "BLOCKED"
            state.automation_status = "BLOCKED"
            state.save(self.state_file)
            raise

    def start_loop(self) -> None:
        """Runs the continuous watching loop."""
        print("==================================================")
        print("Local AI Sidekick (Phase 2 Task Watcher)")
        print(f"Watching: {self.task_file}")
        print(f"Poll Interval: {self.config.watch_interval}s")
        print("Press Ctrl+C to stop.")
        print("==================================================")

        try:
            while True:
                self.run_once()
                time.sleep(self.config.watch_interval)
        except KeyboardInterrupt:
            print("\n[Watcher] Stopped by user.")
