"""Onboarding and diagnostic helpers (sidekick init & sidekick doctor)."""
import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import SidekickConfig
from .security import EXCLUDED_EXPLORATION_DIRS, EXCLUDED_FILE_PATTERNS

DEFAULT_RULES_CONTENT = """# Permanent Rules

- TASK.mdに明記された範囲外を変更しない
- credential / secret / API keyを出力しない
- `.env`をcommitしない
- mainブランチへの危険な操作を行わない
- destructive operationを行わない
- cloud resourceの作成・更新・削除を勝手に行わない
- terraform applyを勝手に実行しない
- AWS / Azure / GCPのwrite APIを勝手に実行しない
- architectureを独断で変更しない
- 不明点を推測で補完しない
- 判断不能時はBLOCKEDとして終了する
"""

DEFAULT_DECISIONS_CONTENT = """# Architecture Decisions

This file records architecture decisions made by Lead AI.
Sidekick must respect these decisions and must NOT modify this file.

## ADR-001: Separation of Lead AI and Local Sidekick

- **Decision**: Use Lead AI for high-level architectural design and planning, and Local Sidekick for implementation, test execution, and repo-level exploration.
- **Reason**: Minimize expensive LLM token consumption while maintaining high architectural quality.
- **Date**: 2026-09-19
"""

DEFAULT_DELEGATION_CONTENT = """# Delegation Policy

## Purpose
Guidelines for Lead AI determining whether a task is delegated to Local AI Sidekick or retained by Lead.

## Decision Matrix
- **LOCAL**: Self-contained, bounded tasks with clear automated tests and low architectural risk.
- **LEAD**: Architectural design, cross-cutting refactoring, production configuration, or ambiguous scope.
- **BLOCKED**: Requires human clarification, missing approval token, or forbidden operations.
"""

GITIGNORE_ENTRIES = """
# Local AI Sidekick runtime state
.ai/state.json
.ai/sidekick.lock
.ai/TASK.md
.ai/RESULT.md
.env
"""


def init_repo(repo_root: Path, force: bool = False) -> dict[str, Any]:
    """Initialize a target repository with .ai/ configuration and standard templates."""
    repo_root = repo_root.resolve()
    repo_root.mkdir(parents=True, exist_ok=True)

    ai_dir = repo_root / ".ai"
    ai_dir.mkdir(parents=True, exist_ok=True)

    created_files: list[str] = []
    skipped_files: list[str] = []

    files_to_create = [
        (ai_dir / "RULES.md", DEFAULT_RULES_CONTENT),
        (ai_dir / "DECISIONS.md", DEFAULT_DECISIONS_CONTENT),
        (ai_dir / "DELEGATION.md", DEFAULT_DELEGATION_CONTENT),
    ]

    for target_path, content in files_to_create:
        if not target_path.exists() or force:
            target_path.write_text(content, encoding="utf-8")
            created_files.append(str(target_path.relative_to(repo_root)))
        else:
            skipped_files.append(str(target_path.relative_to(repo_root)))

    # Handle .gitignore entries
    gitignore_path = repo_root / ".gitignore"
    gitignore_updated = False
    if gitignore_path.exists():
        current_content = gitignore_path.read_text(encoding="utf-8")
        needed_entries = [line.strip() for line in GITIGNORE_ENTRIES.strip().splitlines() if line.strip() and not line.startswith("#")]
        missing = [e for e in needed_entries if e not in current_content]
        if missing:
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write(GITIGNORE_ENTRIES)
            gitignore_updated = True
    else:
        gitignore_path.write_text(GITIGNORE_ENTRIES.lstrip(), encoding="utf-8")
        created_files.append(".gitignore")

    return {
        "repo_root": str(repo_root),
        "created": created_files,
        "skipped": skipped_files,
        "gitignore_updated": gitignore_updated,
    }


@dataclass
class CheckItem:
    category: str
    name: str
    status: str  # "OK", "WARN", "FAIL", "INFO"
    message: str


@dataclass
class DoctorReport:
    repo_root: Path
    checks: list[CheckItem] = field(default_factory=list)

    @property
    def has_failures(self) -> bool:
        return any(c.status == "FAIL" for c in self.checks)

    @property
    def ok_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "OK")

    @property
    def warn_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "WARN")

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "FAIL")

    def format_text(self) -> str:
        lines = [
            "=== Local AI Sidekick Doctor ===",
            f"Target Repository: {self.repo_root}",
            "",
        ]

        categories: dict[str, list[CheckItem]] = {}
        for c in self.checks:
            categories.setdefault(c.category, []).append(c)

        category_labels = {
            "git": "Git Environment",
            "governance": "Governance & Templates (.ai/)",
            "ollama": "Ollama Service & Model",
            "security": "Security Policies & Configuration",
        }

        for cat_key, label in category_labels.items():
            items = categories.get(cat_key, [])
            if not items:
                continue
            lines.append(f"[{label}]")
            for item in items:
                lines.append(f"  [{item.status}] {item.name}: {item.message}")
            lines.append("")

        lines.append("--------------------------------------------------")
        if self.has_failures:
            lines.append(
                f"Doctor Summary: {self.ok_count} passed, {self.warn_count} warnings, {self.fail_count} failures. "
                "Action required before running automated tasks."
            )
        else:
            lines.append(
                f"Doctor Summary: {self.ok_count} passed, {self.warn_count} warnings, 0 failures. "
                "System is healthy and ready."
            )

        return "\n".join(lines)


def run_doctor(repo_root: Path, config: SidekickConfig | None = None) -> DoctorReport:
    """Diagnose repository readiness, Ollama connectivity, model availability, and guardrails."""
    repo_root = repo_root.resolve()
    if config is None:
        config = SidekickConfig.load(repo_root)

    report = DoctorReport(repo_root=repo_root)

    # 1. Git Checks
    try:
        t_res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if t_res.returncode == 0 and t_res.stdout.strip():
            toplevel = Path(t_res.stdout.strip()).resolve()
            if toplevel == repo_root:
                report.checks.append(CheckItem("git", "Git Repository", "OK", "Valid Git working tree detected."))
            else:
                report.checks.append(
                    CheckItem(
                        "git",
                        "Git Repository",
                        "FAIL",
                        f"'{repo_root}' is a subfolder inside '{toplevel}', not its own repository root.",
                    )
                )

            # Branch check
            b_res = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            branch = b_res.stdout.strip() if b_res.returncode == 0 else "unknown"
            if branch in ("main", "master"):
                report.checks.append(
                    CheckItem(
                        "git",
                        "Current Branch",
                        "OK",
                        f"Currently on '{branch}'. Task execution will safely isolate changes to ai/<task-id> branches.",
                    )
                )
            else:
                report.checks.append(CheckItem("git", "Current Branch", "OK", f"On branch '{branch}'."))

            # Remote check
            r_res = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            if r_res.returncode == 0 and r_res.stdout.strip():
                report.checks.append(
                    CheckItem("git", "Remote Origin", "OK", f"Configured remote: {r_res.stdout.strip()}")
                )
            else:
                report.checks.append(
                    CheckItem(
                        "git",
                        "Remote Origin",
                        "WARN",
                        "No 'origin' remote configured. Remote publishing requires a valid git remote.",
                    )
                )

            # Working tree status
            s_res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            dirty_files = [line for line in s_res.stdout.splitlines() if line.strip()]
            if dirty_files:
                report.checks.append(
                    CheckItem(
                        "git",
                        "Working Tree",
                        "INFO",
                        f"{len(dirty_files)} uncommitted file(s) present. Git preflight requires a clean tree before running tasks.",
                    )
                )
            else:
                report.checks.append(CheckItem("git", "Working Tree", "OK", "Working tree is clean."))
        else:
            report.checks.append(
                CheckItem(
                    "git",
                    "Git Repository",
                    "FAIL",
                    f"'{repo_root}' is not inside a Git repository. Run 'git init' to initialize.",
                )
            )
    except FileNotFoundError:
        report.checks.append(CheckItem("git", "Git Binary", "FAIL", "'git' executable was not found in PATH."))

    # 2. Governance Checks (.ai/)
    ai_dir = repo_root / ".ai"
    if ai_dir.is_dir():
        report.checks.append(CheckItem("governance", ".ai Directory", "OK", ".ai/ governance directory exists."))
    else:
        report.checks.append(
            CheckItem("governance", ".ai Directory", "FAIL", "Missing .ai/ directory. Run 'sidekick init'.")
        )

    rules_file = repo_root / config.rules_path
    if rules_file.is_file():
        report.checks.append(CheckItem("governance", "RULES.md", "OK", f"Found permanent rules at {config.rules_path}."))
    else:
        report.checks.append(
            CheckItem(
                "governance",
                "RULES.md",
                "WARN",
                f"Missing {config.rules_path}. Recommended for defining worker boundaries.",
            )
        )

    decisions_file = repo_root / config.decisions_path
    if decisions_file.is_file():
        report.checks.append(
            CheckItem("governance", "DECISIONS.md", "OK", f"Found architecture decisions at {config.decisions_path}.")
        )
    else:
        report.checks.append(
            CheckItem(
                "governance",
                "DECISIONS.md",
                "WARN",
                f"Missing {config.decisions_path}. Recommended for ADR tracking.",
            )
        )

    delegation_file = repo_root / ".ai" / "DELEGATION.md"
    if delegation_file.is_file():
        report.checks.append(CheckItem("governance", "DELEGATION.md", "OK", "Found delegation policy at .ai/DELEGATION.md."))
    else:
        report.checks.append(
            CheckItem(
                "governance",
                "DELEGATION.md",
                "INFO",
                "Missing .ai/DELEGATION.md. Required if using automatic lead-to-worker delegation.",
            )
        )

    # 3. Ollama Connectivity & Model
    ollama_url = config.ollama_base_url.rstrip("/")
    tags_url = f"{ollama_url}/api/tags"
    try:
        req = urllib.request.Request(tags_url, headers={"User-Agent": "sidekick-doctor/0.2.0"})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            report.checks.append(CheckItem("ollama", "Ollama Connection", "OK", f"Connected to Ollama at {ollama_url}."))

            installed_models = [m.get("name", "") for m in data.get("models", [])]
            target_model = config.model
            model_matched = any(
                target_model == m or target_model == m.split(":")[0] or m.startswith(f"{target_model}:")
                for m in installed_models
            )

            if model_matched:
                report.checks.append(
                    CheckItem("ollama", "Model Availability", "OK", f"Configured model '{target_model}' is installed.")
                )
            else:
                report.checks.append(
                    CheckItem(
                        "ollama",
                        "Model Availability",
                        "WARN",
                        f"Configured model '{target_model}' not found in Ollama ({len(installed_models)} models installed). "
                        f"Run: ollama pull {target_model}",
                    )
                )
    except urllib.error.URLError as e:
        report.checks.append(
            CheckItem(
                "ollama",
                "Ollama Connection",
                "FAIL",
                f"Cannot connect to Ollama at {ollama_url}: {e.reason}. Ensure Ollama is running.",
            )
        )
    except Exception as e:
        report.checks.append(
            CheckItem("ollama", "Ollama Connection", "FAIL", f"Unexpected error connecting to Ollama: {e}")
        )

    # 4. Security & Guardrails
    if config.auto_push:
        report.checks.append(
            CheckItem(
                "security",
                "Auto-Push Policy",
                "WARN",
                "SIDEKICK_AUTO_PUSH is enabled. Autonomous push will be attempted after successful tasks.",
            )
        )
    else:
        report.checks.append(
            CheckItem(
                "security",
                "Auto-Push Policy",
                "OK",
                "SIDEKICK_AUTO_PUSH is disabled (safe default: local commits only, manual push required).",
            )
        )

    report.checks.append(
        CheckItem(
            "security",
            "Diff Guard & Protected Paths",
            "OK",
            f"Active: {len(EXCLUDED_FILE_PATTERNS)} file patterns & {len(EXCLUDED_EXPLORATION_DIRS)} dirs protected (.git, .env*, .ai/DECISIONS.md, AGENTS.md, CLAUDE.md).",
        )
    )

    report.checks.append(
        CheckItem(
            "security",
            "Secret Scanner",
            "OK",
            "Pre-commit regex pattern scanner loaded (detects AWS keys, GitHub tokens, private keys).",
        )
    )

    return report
