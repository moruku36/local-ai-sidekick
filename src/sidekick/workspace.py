"""Execution workspace and operations runner."""
import subprocess
import shutil
from pathlib import Path
from typing import List, Tuple, Dict
from .security import SecurityPolicy

class WorkspaceManager:
    def __init__(self, repo_root: Path, security_policy: SecurityPolicy):
        self.repo_root = repo_root.resolve()
        self.security_policy = security_policy

    def read_file(self, rel_path: str) -> str:
        allowed, reason = self.security_policy.is_path_allowed(rel_path)
        if not allowed:
            raise PermissionError(f"Security violation: {reason}")
        target = (self.repo_root / rel_path).resolve()
        if not target.exists():
            return ""
        return target.read_text(encoding="utf-8", errors="replace")

    def write_file(self, rel_path: str, content: str) -> None:
        allowed, reason = self.security_policy.is_path_allowed(rel_path)
        if not allowed:
            raise PermissionError(f"Security violation: {reason}")
        target = (self.repo_root / rel_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def run_command(self, command: str, timeout_seconds: int = 60) -> Tuple[int, str, str]:
        allowed, reason = self.security_policy.is_command_allowed(command)
        if not allowed:
            return 126, "", f"Command blocked by security policy: {reason}"

        try:
            res = subprocess.run(
                command,
                shell=True,
                cwd=str(self.repo_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds
            )
            stdout = self.security_policy.sanitize_output(res.stdout)
            stderr = self.security_policy.sanitize_output(res.stderr)
            return res.returncode, stdout, stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"Command timed out after {timeout_seconds} seconds"
        except Exception as e:
            return 1, "", f"Execution error: {str(e)}"

    def get_git_diff_summary(self) -> str:
        try:
            res = subprocess.run(
                ["git", "diff", "--stat"],
                cwd=str(self.repo_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10
            )
            diff_stat = res.stdout.strip()
            if not diff_stat:
                res_untracked = subprocess.run(
                    ["git", "status", "--short"],
                    cwd=str(self.repo_root),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=10
                )
                return res_untracked.stdout.strip() or "No changes detected."
            return diff_stat
        except Exception as e:
            return f"Failed to retrieve git diff: {str(e)}"
