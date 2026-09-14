"""File watcher for .ai/TASK.md in Phase 2."""
import hashlib
import time
from pathlib import Path
from typing import Optional

from .config import SidekickConfig
from .runner import SidekickRunner
from .task_parser import TaskDefinition
from .state_manager import SidekickState, LockManager

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
        if not self.task_file.exists():
            return None

        current_hash = self._compute_hash()
        state = SidekickState.load(self.state_file)

        try:
            task = TaskDefinition.parse_file(self.task_file)
        except Exception:
            return None

        if not task.goal.strip():
            return None

        # Check if already processed
        if state.task_id == task.task_id and state.task_hash == current_hash and state.automation_status in ["READY_FOR_REVIEW", "SUCCESS"]:
            return None

        # Attempt to acquire lock
        if not self.lock_manager.acquire():
            print(f"[Watcher] Another sidekick process is active (lock file exists at {self.lock_file}).")
            return None

        try:
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
            state.automation_status = result.get("automation_status", "")
            state.updated_at = time.strftime("%Y-%m-%d %H:%M:%S")
            state.save(self.state_file)
            return result
        finally:
            self.lock_manager.release()

    def start_loop(self) -> None:
        """Runs the continuous watching loop."""
        print(f"==================================================")
        print(f"Local AI Sidekick (Phase 2 Task Watcher)")
        print(f"Watching: {self.task_file}")
        print(f"Poll Interval: {self.config.watch_interval}s")
        print(f"Press Ctrl+C to stop.")
        print(f"==================================================")

        try:
            while True:
                self.run_once()
                time.sleep(self.config.watch_interval)
        except KeyboardInterrupt:
            print("\n[Watcher] Stopped by user.")
