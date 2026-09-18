"""Git automation and safety management for Phase 2."""
import re
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional
from .security import SecurityPolicy
from .secret_scanner import SecretScanner

class GitAutomationManager:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()

    def _run_git(self, args: List[str], timeout_seconds: int = 30) -> Tuple[int, str, str]:
        try:
            res = subprocess.run(
                ["git"] + args,
                shell=False,
                cwd=str(self.repo_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.TimeoutExpired:
            return 124, "", "Git command timed out"
        except Exception as e:
            return 1, "", str(e)

    def preflight_check(self, require_clean: bool = True) -> Tuple[bool, str]:
        """Validates git repo health, clean working tree, remote presence, and valid branch."""
        # 1. Check if git repo
        code, out, _ = self._run_git(["rev-parse", "--is-inside-work-tree"])
        if code != 0 or out != "true":
            return False, "Not inside a valid Git repository."

        # 2. Check remote origin
        code, out, _ = self._run_git(["remote"])
        if code != 0 or "origin" not in out.splitlines():
            return False, "No 'origin' remote configured in this repository."

        # 3. Check detached HEAD
        code, out, _ = self._run_git(["symbolic-ref", "-q", "HEAD"])
        if code != 0:
            return False, "Repository is in a detached HEAD state."

        # 4. Check rebase / merge / cherry-pick state
        git_dir_code, git_dir_out, _ = self._run_git(["rev-parse", "--git-path", "rebase-merge"])
        if git_dir_code == 0 and (self.repo_root / git_dir_out).exists():
            return False, "Repository is in the middle of a rebase."

        merge_head_code, merge_head_out, _ = self._run_git(["rev-parse", "--git-path", "MERGE_HEAD"])
        if merge_head_code == 0 and (self.repo_root / merge_head_out).exists():
            return False, "Repository is in the middle of a merge conflict."

        # 5. Check dirty working directory
        if require_clean:
            code, out, _ = self._run_git(["status", "--porcelain", "-uall"])
            if code == 0 and out.strip():
                # Allow TASK.md, RESULT.md, and state/lock files as normal task input/state
                allowed_preflight_dirty = {
                    ".ai/TASK.md", ".ai/RESULT.md", ".ai/task.md", ".ai/result.md",
                    ".ai/state.json", ".ai/sidekick.lock"
                }
                dirty_violations = []
                for line in out.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    p = line[2:].strip()
                    if " -> " in p:
                        p = p.split(" -> ")[1].strip()
                    norm_p = p.replace("\\", "/").rstrip("/")
                    if norm_p not in allowed_preflight_dirty and not norm_p.endswith((".pyc", ".pyo")) and "__pycache__" not in norm_p:
                        dirty_violations.append(p)

                if dirty_violations:
                    return False, f"Working tree is dirty. Stash or commit existing changes before starting Phase 2:\n" + "\n".join(dirty_violations[:10])

        return True, "Preflight check passed."

    def get_current_branch(self) -> str:
        code, out, _ = self._run_git(["branch", "--show-current"])
        return out if code == 0 else ""

    def ensure_task_branch(self, task_id: str) -> Tuple[bool, str, str]:
        """Creates or switches safely to ai/<task-id> branch without ever touching main directly."""
        safe_id = re.sub(r"[^a-zA-Z0-9_\-\.]", "-", task_id).strip("-")
        branch_name = f"ai/{safe_id}"

        curr_branch = self.get_current_branch()
        if curr_branch == branch_name:
            return True, branch_name, f"Already on task branch {branch_name}."

        # Check if branch exists
        code, out, _ = self._run_git(["branch", "--list", branch_name])
        if code == 0 and branch_name in out:
            # Switch to existing task branch
            sw_code, _, sw_err = self._run_git(["switch", branch_name])
            if sw_code != 0:
                return False, branch_name, f"Failed to switch to existing task branch: {sw_err}"
            return True, branch_name, f"Switched to existing task branch {branch_name}."

        # Create new branch from current base
        cb_code, _, cb_err = self._run_git(["checkout", "-b", branch_name])
        if cb_code != 0:
            return False, branch_name, f"Failed creating task branch {branch_name}: {cb_err}"

        return True, branch_name, f"Created and switched to task branch {branch_name}."

    def validate_diff_guard(self, allowed_files: List[str], extra_allowed: Optional[List[str]] = None) -> Tuple[bool, List[str], str]:
        """Verifies that only files matching allowed_files (plus .ai/TASK.md & .ai/RESULT.md) are modified."""
        code, out, err = self._run_git(["status", "--porcelain", "-uall"])
        if code != 0:
            return False, [], f"Failed to get git status: {err}"

        changed_paths = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            # Extract path (handles rename "R  old -> new")
            path_part = line[2:].strip()
            if " -> " in path_part:
                path_part = path_part.split(" -> ")[1].strip()
            changed_paths.append(path_part)

        permitted_rules = list(allowed_files)
        always_allowed = [
            ".ai/TASK.md", ".ai/RESULT.md", ".ai/task.md", ".ai/result.md",
            ".ai/state.json", ".ai/sidekick.lock"
        ]
        if extra_allowed:
            always_allowed.extend(extra_allowed)

        violations = []
        for rel in changed_paths:
            rel_norm = rel.replace("\\", "/").rstrip("/")
            if rel_norm in always_allowed:
                continue

            # Ignore transient Python cache / bytecode files if generated during tests
            if "__pycache__" in rel_norm or rel_norm.endswith((".pyc", ".pyo")):
                continue

            matched = False
            for pat in permitted_rules:
                pat_norm = pat.replace("\\", "/").rstrip("/")
                if rel_norm == pat_norm or rel_norm.startswith(pat_norm + "/"):
                    matched = True
                    break

            if not matched:
                violations.append(rel)

        if violations:
            return False, violations, f"Diff Guard violation: Files modified outside Allowed Files: {violations}"

        return True, changed_paths, "Diff Guard passed."

    def run_secret_scan_on_changed(self, changed_paths: List[str]) -> Tuple[bool, List[str]]:
        """Scans changed files for secrets."""
        findings = []
        for rel in changed_paths:
            p = self.repo_root / rel
            if p.exists() and p.is_file():
                results = SecretScanner.scan_file(p)
                for line_no, rule, fname in results:
                    findings.append(f"{rel}:{line_no} [{rule}]")

        if findings:
            return False, findings
        return True, []

    def commit_changes(self, task_id: str, commit_files: List[str], message_suffix: str = "") -> Tuple[bool, str, str]:
        """Stages only allowed changed files and creates a commit."""
        force_add_runtime = {
            ".ai/TASK.md", ".ai/RESULT.md", ".ai/task.md", ".ai/result.md"
        }
        for rel in commit_files:
            normalized = rel.replace("\\", "/")
            add_args = ["add"]
            if normalized in force_add_runtime:
                add_args.append("-f")
            add_args.append(rel)
            code, _, err = self._run_git(add_args)
            if code != 0:
                return False, "", f"Failed staging file {rel}: {err}"

        msg = f"sidekick({task_id}): implement requested changes"
        if message_suffix:
            msg += f" - {message_suffix}"

        c_code, c_out, c_err = self._run_git(["commit", "-m", msg])
        if c_code != 0:
            return False, "", f"Git commit failed: {c_err or c_out}"

        rev_code, rev_out, _ = self._run_git(["rev-parse", "--short", "HEAD"])
        commit_hash = rev_out if rev_code == 0 else "UNKNOWN"
        return True, commit_hash, "Committed successfully."

    def safe_push(self, branch_name: str) -> Tuple[bool, str]:
        """Pushes exclusively the ai/<task-id> branch to origin."""
        if not branch_name.startswith("ai/"):
            return False, f"Refusing to push non-task branch: {branch_name}"
        if branch_name in ["main", "master"]:
            return False, "CRITICAL: Attempted to push directly to main/master."

        code, out, err = self._run_git(["push", "-u", "origin", branch_name])
        if code != 0:
            return False, f"Git push failed: {err or out}"
        return True, "Pushed branch successfully to origin."
