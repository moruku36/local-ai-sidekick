"""State and lock management for Phase 2 Watcher and Runner."""
import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, Any

@dataclass
class SidekickState:
    task_id: str = ""
    task_hash: str = ""
    branch: str = ""
    status: str = "IDLE"
    commit_hash: str = ""
    push_status: str = ""
    automation_status: str = "IDLE"
    updated_at: str = ""

    def save(self, state_file: Path) -> None:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, state_file: Path) -> "SidekickState":
        if not state_file.exists():
            return cls()
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            return cls(**data)
        except Exception:
            return cls()

class LockManager:
    def __init__(self, lock_file: Path, stale_timeout_seconds: int = 600):
        self.lock_file = lock_file
        self.stale_timeout_seconds = stale_timeout_seconds

    def acquire(self) -> bool:
        """Attempts to acquire file lock, checking for stale locks."""
        now = time.time()
        if self.lock_file.exists():
            try:
                mtime = self.lock_file.stat().st_mtime
                if now - mtime > self.stale_timeout_seconds:
                    # Stale lock, overwrite
                    pass
                else:
                    return False
            except Exception:
                return False

        try:
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)
            self.lock_file.write_text(f"pid={os.getpid()}\ntime={now}\n", encoding="utf-8")
            return True
        except Exception:
            return False

    def release(self) -> None:
        if self.lock_file.exists():
            try:
                self.lock_file.unlink()
            except Exception:
                pass
