"""Runtime gates for explicit Worker roles, including manually written TASK files."""

from __future__ import annotations

from pathlib import Path, PureWindowsPath
from ipaddress import ip_address
import re
from typing import Any
from urllib.parse import urlsplit

from .config import SidekickConfig
from .delegate import SAFE_COMMANDS
from .secret_scanner import SecretScanner
from .security import SecurityPolicy
from .task_parser import TaskDefinition

ROLES = {"command-runner", "code-explore", "spec-coder"}
PROTECTED_ROOTS = {".ai", ".git", ".claude", ".agents", ".codex", ".agent", "prompts"}
PROTECTED_NAMES = {"agents.md", "claude.md", "gemini.md"}
PLAN_FIELDS = {
    "status", "summary", "files_to_write", "verification_command",
    "decisions_required", "review_points", "spec_deviations",
    "unfinished_items", "unverified_claims",
}


def _safe_file(root: Path, name: str, policy: SecurityPolicy) -> bool:
    if not isinstance(name, str) or not name or name != name.strip():
        return False
    normalized = name.replace("\\", "/")
    parts = normalized.split("/")
    if (
        Path(name).is_absolute() or PureWindowsPath(name).is_absolute()
        or any(p in {"", ".", ".."} or p.endswith((".", " ")) for p in parts)
        or any(c in normalized for c in ":*?[]<>|\r\n\x00")
        or parts[0].lower() in PROTECTED_ROOTS
        or parts[-1].lower() in PROTECTED_NAMES
        or any(p.startswith((".git", ".env")) for p in parts)
        or policy.is_path_excluded(normalized)
    ):
        return False
    target = root / normalized
    resolved = target.resolve()
    return (
        resolved == target and resolved.is_relative_to(root)
        and not target.is_dir() and policy.is_path_allowed(normalized)[0]
    )


def validate_role_task(root: Path, task: TaskDefinition, config: SidekickConfig) -> str:
    """Return a generic reason when an explicit role's scope is unsafe."""
    if task.worker_role not in ROLES:
        return "Unsupported Worker role."
    if task.worker_role in {"code-explore", "spec-coder"}:
        try:
            endpoint = urlsplit(config.ollama_base_url)
            host = endpoint.hostname or ""
            local = host == "localhost" or ip_address(host).is_loopback
            if (endpoint.scheme != "http" or not local or endpoint.username
                    or endpoint.password or endpoint.path not in ("", "/")
                    or endpoint.query or endpoint.fragment or endpoint.port is None):
                return "Role model endpoint must be a local Ollama address."
        except ValueError:
            return "Role model endpoint must be a local Ollama address."
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", task.task_id):
        return "Role task needs a safe Task ID."
    if not task.goal.strip() or not task.background.strip():
        return "Role task needs a concrete goal and background."
    if len(task.raw_content) > config.max_context_bytes:
        return "Role task exceeds context bounds."
    if not task.allowed_files or len(task.allowed_files) > config.max_files:
        return "Role task needs bounded, exact Allowed Files."
    policy = SecurityPolicy(root, task.allowed_files, task.allowed_commands)
    if len(set(task.allowed_files)) != len(task.allowed_files) or any(
        not _safe_file(root, name, policy) for name in task.allowed_files
    ):
        return "Role task contains an unsafe Allowed Files path."
    if task.worker_role == "code-explore":
        if task.allowed_commands:
            return "code-explore cannot execute commands."
        if any(not (root / name).is_file() for name in task.allowed_files):
            return "code-explore requires existing files."
    else:
        if not task.allowed_commands or any(
            command not in SAFE_COMMANDS or not policy.is_command_allowed(command)[0]
            for command in task.allowed_commands
        ):
            return "Role task needs approved verification commands."
    if task.worker_role == "spec-coder" and (
        not task.requirements or not task.acceptance_criteria or not task.review_points
    ):
        return "spec-coder needs settled requirements, acceptance criteria and review points."
    if SecretScanner.scan_text(task.raw_content):
        return "Role task contains possible credentials."
    return ""


def validate_spec_plan(
    root: Path, task: TaskDefinition, config: SidekickConfig, plan: Any
) -> str:
    """Reject the entire proposed edit batch before the first write."""
    if not isinstance(plan, dict) or set(plan) - PLAN_FIELDS:
        return "Invalid spec-coder response fields."
    if plan.get("status") != "SUCCESS":
        return "spec-coder did not return a successful proposal."
    if plan.get("decisions_required") or plan.get("spec_deviations") or plan.get("unfinished_items"):
        return "Specification ambiguity or deviation requires Lead review."
    if (not isinstance(plan.get("decisions_required", ""), str)
            or plan.get("spec_deviations", []) != []
            or plan.get("unfinished_items", []) != []
            or plan.get("verification_command") not in (None, *task.allowed_commands)):
        return "Invalid spec-coder proposal metadata."
    if (not isinstance(plan.get("summary"), str) or len(plan["summary"]) > 500
            or SecretScanner.scan_text(plan["summary"])):
        return "Invalid spec-coder summary."
    if (not isinstance(plan.get("review_points", ""), str)
            or len(plan.get("review_points", "")) > 500
            or SecretScanner.scan_text(plan.get("review_points", ""))):
        return "Invalid spec-coder review points."
    claims = plan.get("unverified_claims", [])
    if not isinstance(claims, list) or len(claims) > 10 or any(
        not isinstance(item, str) or len(item) > 200 or SecretScanner.scan_text(item)
        for item in claims
    ):
        return "Invalid unverified-claims list."
    edits = plan.get("files_to_write")
    if not isinstance(edits, list) or not edits or len(edits) > config.max_files:
        return "spec-coder must propose a bounded, nonempty edit batch."
    policy = SecurityPolicy(root, task.allowed_files, task.allowed_commands)
    seen: set[str] = set()
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {"path", "content"}:
            return "Invalid spec-coder edit object."
        name, content = edit["path"], edit["content"]
        if (
            not isinstance(name, str) or name not in task.allowed_files or name in seen
            or not _safe_file(root, name, policy)
            or not isinstance(content, str)
            or len(content.encode("utf-8")) > config.max_file_bytes
            or SecretScanner.scan_text(content)
        ):
            return "Spec-coder edit exceeds scope, size or secret guard."
        seen.add(name)
    return ""
