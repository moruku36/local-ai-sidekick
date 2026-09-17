"""Validate a Lead assessment and atomically hand off a bounded task.

Semantic classification belongs to the Lead reading .ai/DELEGATION.md; this
module is a conservative gate, not a keyword-based replacement for that Lead.
"""
import argparse
import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path, PureWindowsPath

from .config import SidekickConfig
from .secret_scanner import SecretScanner
from .security import SecurityPolicy
from .state_manager import LockManager, SidekickState
from .task_parser import TaskDefinition

LOCAL_TYPES = {
    "exploration", "code_change", "boilerplate", "refactoring", "formatting",
    "lint", "unit_tests", "test_fix", "documentation", "config", "repetitive_edit",
    "typing", "imports", "dead_code",
}
LEAD_TYPES = {
    "architecture", "cloud_architecture", "security_architecture", "threat_modeling",
    "requirements", "cross_system_design", "trade_off", "high_impact_change",
    "destructive_operation", "deployment", "iam", "credentials", "terraform_apply",
    "cloud_write", "root_account", "final_review", "blocked_review",
}
# Deliberately small: do not accept arbitrary interpreters, shell snippets, or
# command prefixes from generated input. Lead can extend this reviewed list.
SAFE_COMMANDS = {
    "python -m unittest discover tests", "python -m pytest", "python -m pytest -q",
    "python -m compileall -q src", "python -m ruff check .",
    "python -m ruff format --check .", "git diff --check",
}
FORBIDDEN = [
    "Do not modify files outside Allowed Files or change architecture.",
    "Do not access credentials, .env*, .git, protected rules, or secret files.",
    "Do not delete files or perform destructive operations.",
    "Do not run terraform apply/destroy or aws/az/gcloud write operations.",
    "Do not deploy, change IAM, or operate root/management accounts.",
    "Do not push directly to main; only the existing Safe Commit/Push may publish.",
    "Do not execute commands outside Allowed Commands or weaken security guards.",
]
SECTIONS = {
    "goal": "Goal", "background": "Background", "allowed_files": "Allowed Files",
    "forbidden_operations": "Forbidden Operations", "requirements": "Requirements",
    "acceptance_criteria": "Acceptance Criteria", "allowed_commands": "Allowed Commands",
    "review_points": "Review Points",
}


def result(decision, reason, confidence=1.0, **extra):
    return dict(decision=decision, reason=reason, confidence=confidence, **extra)


def _text(value):
    # One line per field/item prevents injected Markdown sections or comments.
    return (isinstance(value, str) and bool(value.strip()) and
            not any(c in value for c in "\r\n\x00") and
            "<!--" not in value and not value.lstrip().startswith("#"))


def _validate_task(root, task):
    if not isinstance(task, dict) or set(task) - (set(SECTIONS) | {"task_id"}):
        raise ValueError("Task must contain only documented task fields.")
    for name in ("goal", "background"):
        if not _text(task.get(name)):
            raise ValueError(f"A concrete, single-line {name} is required.")
    for name in set(SECTIONS) - {"goal", "background"}:
        values = task.get(name, [] if name == "forbidden_operations" else None)
        if (not isinstance(values, list) or
                (not values and name != "forbidden_operations") or
                not all(_text(v) for v in values)):
            raise ValueError(f"A nonempty list of single-line {name} is required.")
    policy = SecurityPolicy(root, task["allowed_files"], task["allowed_commands"])
    for name in task["allowed_files"]:
        path = name.replace("\\", "/")
        parts = path.lower().split("/")
        resolved = (root / path).resolve()
        if not resolved.is_relative_to(root) or resolved != root / path:
            raise ValueError("Path escapes repository or aliases another path.")
        resolved_parts = resolved.relative_to(root).as_posix().lower().split("/")
        if (PureWindowsPath(path).is_absolute() or Path(path).is_absolute() or
                any(p in ("", ".", "..") or p.startswith((".git", ".env"))
                    or p.endswith((".", " ")) for p in parts) or
                any(c in path for c in ":*?[]") or
                parts[0] in {".ai", "prompts", ".agents", ".codex", ".agent"} or
                parts[-1] in {"agents.md", "gemini.md", "claude.md"} or
                resolved_parts[0] in {".ai", "prompts", ".agents", ".codex", ".agent"} or
                resolved_parts[-1] in {"agents.md", "gemini.md", "claude.md"} or
                (root / path).is_dir() or policy.is_path_excluded(path) or
                not policy.is_path_allowed(path)[0]):
            raise ValueError("Allowed Files must identify concrete, unprotected repository files.")
    for command in task["allowed_commands"]:
        if command not in SAFE_COMMANDS or not policy.is_command_allowed(command)[0]:
            raise ValueError("Allowed Commands contains an unapproved command.")
    if "task_id" in task and not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", task["task_id"]):
        raise ValueError("Task ID must be a safe branch-name component (max 80 characters).")
    plain = "\n".join(item for value in task.values()
                      for item in (value if isinstance(value, list) else [value]))
    if SecretScanner.scan_text(plain) or re.search(
            r"(?i)\b(password|secret|token|api_key|apikey|private_key)\s*[:=]\s*\S+", plain):
        raise ValueError("Potential credential detected; task was not written.")


def assess(root, request):
    """Fail closed on incomplete assessment; never infer low risk from keywords."""
    if not isinstance(request, dict):
        return result("BLOCKED", "Expected a Lead assessment object.")
    if SecretScanner.scan_text(str(request)):
        return result("BLOCKED", "Potential credential detected in assessment.")
    if os.environ.get("SIDEKICK_DELEGATION_ENABLED", "true").lower() in {"0", "false", "no"}:
        return result("LEAD", "Automatic delegation is disabled.")
    confidence = request.get("confidence")
    if (type(confidence) not in (int, float) or not math.isfinite(confidence) or
            not 0 <= confidence <= 1 or not _text(request.get("reason"))):
        return result("BLOCKED", "A reason and confidence in [0, 1] are required.")
    kind = request.get("task_type")
    if not isinstance(kind, str):
        return result("BLOCKED", "A documented task_type is required.")
    if (kind in LEAD_TYPES or request.get("risk") == "high" or
            request.get("requires_human_approval") is True or request.get("decision") == "LEAD"):
        return result("LEAD", "Design, high-risk operations, approvals and review stay with Lead.", confidence)
    if (request.get("decision") != "LOCAL" or kind not in LOCAL_TYPES or
            request.get("risk") != "low" or request.get("ambiguous") is not False or
            request.get("requires_human_approval") is not False or confidence < 0.8):
        return result("BLOCKED", "Resolve ambiguity, scope or uncertainty with Lead first.", confidence)
    try:
        _validate_task(root.resolve(), request.get("task"))
    except (ValueError, TypeError, OSError):
        # Never reflect untrusted task text or secrets in diagnostics.
        return result("BLOCKED", "Invalid task: check fields, file scope, commands and credentials.", confidence)
    return result("LOCAL", request["reason"], confidence)


def render_task(task):
    canonical = json.dumps(task, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    # Content-derived IDs make retries idempotent, including after other tasks.
    task_id = task.get("task_id") or "local-" + hashlib.sha256(canonical.encode()).hexdigest()[:24]
    values = dict(task, forbidden_operations=FORBIDDEN + task.get("forbidden_operations", []))
    blocks = ["# Current Task", f"## Task ID\n\n{task_id}"]
    for name, title in SECTIONS.items():
        value = values[name]
        body = "\n".join("- " + item for item in value) if isinstance(value, list) else value
        blocks.append(f"## {title}\n\n{body}")
    return task_id, "\n\n".join(blocks) + "\n"


def submit(root, request, *, after_review=False, dry_run=False):
    root = root.resolve()
    decision = assess(root, request)
    if decision["decision"] != "LOCAL":
        return decision
    task_id, content = render_task(request["task"])
    if dry_run:
        return dict(decision, task_id=task_id, status="VALIDATED")
    config = SidekickConfig.load(root)
    target = root / config.task_path
    # The handoff may never escape into a symlink, custom protected file or .git.
    if (config.task_path.replace("\\", "/") != ".ai/TASK.md" or
            (root / ".ai").is_symlink() or not target.resolve().is_relative_to(root)):
        return result("BLOCKED", "Delegation requires a local .ai/TASK.md path.")
    for path in (target, root / ".ai/state.json", root / ".ai/sidekick.lock"):
        if path.resolve() != path or not path.resolve().is_relative_to(root):
            return result("BLOCKED", "Unsafe workflow path.")
    lock = LockManager(root / ".ai/sidekick.lock")
    if not lock.acquire():
        return result("BLOCKED", "Worker or another delegation is active; retry after completion.")
    temp_path = None
    try:
        state_file = root / ".ai/state.json"
        # A corrupt state must not be interpreted as an empty task history.
        if state_file.exists():
            data = json.loads(state_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Invalid state")
            SidekickState(**data)
        state = SidekickState.load(state_file)
        if not isinstance(state.processed_tasks, dict):
            raise ValueError("Invalid history")
        if task_id in state.processed_tasks or task_id == state.task_id:
            return dict(decision, task_id=task_id, status="ALREADY_HANDLED")
        if target.exists():
            current = target.read_text(encoding="utf-8")
            previous = TaskDefinition.parse(current)
            if previous.task_id == task_id:
                if current != content:
                    return result("BLOCKED", "Task ID already exists with different content.")
                return dict(decision, task_id=task_id, status="ALREADY_QUEUED")
            real_goal = re.sub(r"<!--.*?-->", "", previous.goal, flags=re.DOTALL).strip()
            if real_goal and (not after_review or previous.task_id != state.task_id or
                              state.automation_status not in
                              {"READY_FOR_REVIEW", "SUCCESS", "BLOCKED", "FAILED"}):
                return result("BLOCKED", "Existing task must finish and be reviewed before replacement.")
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=target.parent, prefix=".task-", delete=False) as handle:
            temp_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
        return dict(decision, task_id=task_id, status="QUEUED")
    except (ValueError, TypeError, OSError):
        return result("BLOCKED", "Handoff failed; check state and filesystem before retrying.")
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        lock.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--request", type=Path, required=True, help="Lead assessment JSON (UTF-8)")
    parser.add_argument("--after-review", action="store_true", help="Lead reviewed the previous result")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        request = json.loads(args.request.read_text(encoding="utf-8-sig"))
        outcome = submit(args.repo_root, request, after_review=args.after_review, dry_run=args.dry_run)
    except (ValueError, OSError):
        outcome = result("BLOCKED", "Cannot read a valid assessment JSON.")
    print(json.dumps(outcome, ensure_ascii=False))
    return 2 if outcome["decision"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
