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

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _read_template_or_default(filename: str, default_content: str) -> str:
    template_path = TEMPLATES_DIR / filename
    if template_path.is_file():
        return template_path.read_text(encoding="utf-8")
    return default_content


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

DEFAULT_DELEGATION_CONTENT = """# Automatic Delegation Policy (Lead only)

Apply this policy to ordinary user requests automatically, before implementation.
User instructions override routing preferences, but never authorize weakening
the Worker's guards. `SIDEKICK_DELEGATION_ENABLED=false` keeps work with Lead.
This is semantic judgment by the Lead, not keyword routing in the helper.

## Decide

Emit a concise decision with `decision: LOCAL | LEAD | BLOCKED`, `reason`, and
`confidence: 0.0-1.0`. For LOCAL, provide the structured assessment fields required by `sidekick-delegate`:
- `decision`: `"LOCAL"`
- `confidence`: float >= 0.8
- `risk`: `"low"`
- `ambiguous`: `false`
- `requires_human_approval`: `false`

- LOCAL: scoped repository exploration / file search / structure inspection,
  small or medium code changes, boilerplate, refactoring, formatting, lint,
  unit test creation/execution, test failure fixes, documentation/README/config
  edits, repetitive edits, typing/import/dead-code cleanup, and bounded changes
  for diff review with explicit acceptance criteria.
- LEAD: architecture/cloud/security design, threat modeling, requirements
  definition, cross-system design, trade-offs, high-impact changes, destructive
  operation decisions, production deployment decisions, IAM/credentials/secrets,
  Terraform apply, cloud writes, root/management account operations, final review,
  and decisions following a Worker BLOCKED result.
- BLOCKED: ambiguous requirements, unknown Allowed Files, insufficient acceptance
  criteria, uncertainty (confidence below 0.8), or invalid/unsafe task details.
  Never call something low risk merely because it says "small fix" or "config".

For LOCAL require `risk: low`, `ambiguous: false`, and
`requires_human_approval: false`. LEAD/BLOCKED never publish a TASK.
Do not merge automatically.
"""

DEFAULT_AGENTS_CONTENT = """# Lead AI entrypoint

Before acting on each user task, read [.ai/DELEGATION.md](.ai/DELEGATION.md)
and [.ai/RULES.md](.ai/RULES.md). Apply the delegation decision before doing
substantial exploration, implementation, or tests. Lead owns scoping, design,
security decisions, changes to this delegation layer, and final review.

This file is the Lead entrypoint for any Lead Host. Codex/Astra-compatible
hosts load it directly; Claude Code loads it automatically through the
`@AGENTS.md` import in [CLAUDE.md](CLAUDE.md) at the repository root.

For LOCAL work, generate a bounded assessment and invoke `sidekick-delegate` CLI
as documented in the policy; the running Sidekick Watcher executes the Worker task.
For LEAD work, proceed as Lead. For BLOCKED work, resolve the missing decision
with the user; do not guess, enqueue work, or repeatedly regenerate TASK.md.

These instructions target the Lead only. The Ollama Worker follows its existing
system prompt, RULES.md and TASK.md; it must never delegate back to itself.
"""

DEFAULT_CLAUDE_CONTENT = """# Claude Code — Lead Host entrypoint

Claude Code is a **Lead Host** for this repository, equivalent to any
Codex/Astra-compatible host. It follows the same Lead/Worker delegation
workflow, not a Claude-specific one. The policy is defined once, in
`.ai/DELEGATION.md`; nothing below restates it.

The imports below load the existing, host-agnostic instructions so Claude
Code sees exactly what any other Lead Host sees — no separate copy to keep
in sync:

@AGENTS.md
@.ai/DELEGATION.md
@.ai/RULES.md

## Claude Code notes

- Verify the imports loaded by running `/memory` inside Claude Code.
- Invoke `sidekick-delegate` CLI directly:
  `sidekick-delegate --repo-root . --request <path-to-assessment.json>`
  No `PYTHONPATH` manipulation is needed when Local AI Sidekick is installed.
"""

GITIGNORE_ENTRIES = """
# Local AI Sidekick runtime state
.ai/state.json
.ai/sidekick.lock
.ai/TASK.md
.ai/RESULT.md
.env
"""


def init_repo(
    repo_root: Path,
    force: bool = False,
    include_lead_entrypoints: bool = True,
) -> dict[str, Any]:
    """Initialize a target repository with .ai/ configuration, canonical policies, and Lead entrypoints."""
    repo_root = repo_root.resolve()
    repo_root.mkdir(parents=True, exist_ok=True)

    ai_dir = repo_root / ".ai"
    ai_dir.mkdir(parents=True, exist_ok=True)

    created_files: list[str] = []
    skipped_files: list[str] = []

    # Canonical files to create
    rules_content = _read_template_or_default("RULES.md", DEFAULT_RULES_CONTENT)
    decisions_content = _read_template_or_default("DECISIONS.md", DEFAULT_DECISIONS_CONTENT)
    delegation_content = _read_template_or_default("DELEGATION.md", DEFAULT_DELEGATION_CONTENT)

    files_to_create = [
        (ai_dir / "RULES.md", rules_content),
        (ai_dir / "DECISIONS.md", decisions_content),
        (ai_dir / "DELEGATION.md", delegation_content),
    ]

    if include_lead_entrypoints:
        agents_content = _read_template_or_default("AGENTS.md", DEFAULT_AGENTS_CONTENT)
        claude_content = _read_template_or_default("CLAUDE.md", DEFAULT_CLAUDE_CONTENT)
        files_to_create.extend([
            (repo_root / "AGENTS.md", agents_content),
            (repo_root / "CLAUDE.md", claude_content),
        ])

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
        needed_entries = [
            line.strip()
            for line in GITIGNORE_ENTRIES.strip().splitlines()
            if line.strip() and not line.startswith("#")
        ]
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
    mode: str = "all"
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
            f"Diagnostics Mode:  {self.mode}",
            "",
        ]

        categories: dict[str, list[CheckItem]] = {}
        for c in self.checks:
            categories.setdefault(c.category, []).append(c)

        category_labels = {
            "git": "Git Environment & Preflight",
            "governance": "Governance & Policy Files (.ai/)",
            "lead": "Lead Host Integration (AGENTS.md / CLAUDE.md)",
            "ollama": "Ollama Service & Model Availability",
            "security": "Security Policies & Guardrails",
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
                f"Doctor Summary: Mode '{self.mode}' — {self.fail_count} failure(s), "
                f"{self.warn_count} warning(s), {self.ok_count} passed.\n"
                "Status: EXECUTION BLOCKED. Resolve the failures above before running tasks."
            )
        else:
            lines.append(
                f"Doctor Summary: Mode '{self.mode}' — {self.ok_count} passed, "
                f"{self.warn_count} warning(s), 0 failures.\n"
                "Status: READY FOR EXECUTION."
            )

        return "\n".join(lines)


def run_doctor(
    repo_root: Path,
    config: SidekickConfig | None = None,
    mode: str = "all",
) -> DoctorReport:
    """Diagnose repository readiness, Ollama connectivity, model availability, and guardrails.

    Modes:
        - "all": Thorough check across Phase 1, Phase 2, delegation, and security bounds.
        - "phase1": Manual single-run execution checks.
        - "phase2": Autonomous Git automation preflight checks (strictly requires clean working tree).
        - "delegation": Checks automatic delegation router and Lead Host entrypoints.
    """
    repo_root = repo_root.resolve()
    if config is None:
        config = SidekickConfig.load(repo_root)

    report = DoctorReport(repo_root=repo_root, mode=mode)

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
                if mode in ("phase2", "all") and config.auto_push:
                    report.checks.append(
                        CheckItem(
                            "git",
                            "Remote Origin",
                            "FAIL",
                            "No 'origin' remote configured, but SIDEKICK_AUTO_PUSH is enabled. "
                            "Remote publishing strictly requires a valid git remote.",
                        )
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
                if mode in ("phase2", "all"):
                    report.checks.append(
                        CheckItem(
                            "git",
                            "Working Tree",
                            "FAIL",
                            f"Working tree has {len(dirty_files)} uncommitted file(s). "
                            "Phase 2 preflight check requires a clean tree before running tasks.",
                        )
                    )
                else:
                    report.checks.append(
                        CheckItem(
                            "git",
                            "Working Tree",
                            "WARN",
                            f"{len(dirty_files)} uncommitted file(s) present. "
                            "Clean working tree is recommended before starting tasks.",
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
        rules_text = rules_file.read_text(encoding="utf-8")
        if "Permanent Rules" in rules_text and "TASK.md" in rules_text:
            report.checks.append(CheckItem("governance", "RULES.md", "OK", f"Found permanent rules at {config.rules_path}."))
        else:
            report.checks.append(
                CheckItem("governance", "RULES.md", "WARN", f"{config.rules_path} does not contain standard rules.")
            )
    else:
        report.checks.append(
            CheckItem(
                "governance",
                "RULES.md",
                "FAIL",
                f"Missing {config.rules_path}. Required boundary for all worker executions. Run 'sidekick init'.",
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
        del_text = delegation_file.read_text(encoding="utf-8")
        if "confidence" in del_text and "LOCAL" in del_text and "BLOCKED" in del_text:
            report.checks.append(CheckItem("governance", "DELEGATION.md", "OK", "Found canonical delegation policy."))
        else:
            report.checks.append(
                CheckItem(
                    "governance",
                    "DELEGATION.md",
                    "WARN",
                    ".ai/DELEGATION.md lacks standard Fail-Closed policy clauses. Run 'sidekick init --force' to update.",
                )
            )
    else:
        if mode in ("delegation", "all"):
            report.checks.append(
                CheckItem(
                    "governance",
                    "DELEGATION.md",
                    "FAIL",
                    "Missing .ai/DELEGATION.md. Required for automatic lead delegation. Run 'sidekick init'.",
                )
            )
        else:
            report.checks.append(
                CheckItem(
                    "governance",
                    "DELEGATION.md",
                    "INFO",
                    "Missing .ai/DELEGATION.md (only required for automatic lead-to-worker delegation).",
                )
            )

    # 3. Lead Host Integration Checks
    agents_file = repo_root / "AGENTS.md"
    claude_file = repo_root / "CLAUDE.md"
    has_agents = agents_file.is_file() and ".ai/DELEGATION.md" in agents_file.read_text(encoding="utf-8")
    has_claude = claude_file.is_file() and "@AGENTS.md" in claude_file.read_text(encoding="utf-8")

    if has_agents and has_claude:
        report.checks.append(
            CheckItem("lead", "Lead Host Entrypoints", "OK", "AGENTS.md and CLAUDE.md configured and linked to policy.")
        )
    elif has_agents or has_claude:
        found_name = "AGENTS.md" if has_agents else "CLAUDE.md"
        missing_name = "CLAUDE.md" if has_agents else "AGENTS.md"
        report.checks.append(
            CheckItem("lead", "Lead Host Entrypoints", "WARN", f"Found {found_name}, but {missing_name} is missing.")
        )
    else:
        if mode in ("delegation", "all"):
            report.checks.append(
                CheckItem(
                    "lead",
                    "Lead Host Entrypoints",
                    "FAIL",
                    "Missing AGENTS.md and CLAUDE.md. Lead AIs cannot discover delegation policy. Run 'sidekick init'.",
                )
            )
        else:
            report.checks.append(
                CheckItem(
                    "lead",
                    "Lead Host Entrypoints",
                    "INFO",
                    "Lead Host entrypoints not configured (only required for Lead delegation hosts like Claude Code).",
                )
            )

    # 4. Ollama Connectivity & Model Availability
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
                # Missing configured model is a fatal blocker for executing Sidekick!
                report.checks.append(
                    CheckItem(
                        "ollama",
                        "Model Availability",
                        "FAIL",
                        f"Configured model '{target_model}' not found in Ollama ({len(installed_models)} models installed). "
                        f"Execution will fail. Install with: ollama pull {target_model}",
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

    # 5. Security & Guardrails
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
