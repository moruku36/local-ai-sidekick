"""State and lock management for Phase 2 Watcher and Runner."""
import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict


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
    processed_tasks: Dict[str, str] = field(default_factory=dict)

    def save(self, state_file: Path) -> None:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                             dir=state_file.parent, delete=False) as handle:
                temp_path = Path(handle.name)
                json.dump(data, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, state_file)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

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
        self._owned = False

    def acquire(self) -> bool:
        """Atomically acquire the shared handoff/worker lock.

        Never steal a lock by age: a live Ollama run may exceed the timeout.
        After a crash the Lead must verify the owner is stopped before removal.
        The timeout argument remains accepted for backwards compatibility.
        """
        now = time.time()
        try:
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)
            with self.lock_file.open("x", encoding="utf-8") as handle:
                handle.write(f"pid={os.getpid()}\ntime={now}\n")
            self._owned = True
            return True
        except Exception:
            return False

    def release(self) -> None:
        if self._owned and self.lock_file.exists():
            try:
                self.lock_file.unlink()
            except Exception:
                pass
        self._owned = False
