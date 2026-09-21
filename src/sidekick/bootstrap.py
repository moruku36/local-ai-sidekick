"""Lightweight SessionStart bootstrap for Codex / Claude Code (`ai-dev-bootstrap`).

Runs once per session start. It only inspects local, already-on-disk state
(cwd, `.git`, `.ai/`, lock/state files, a handful of well-known paths) and
prints a short Development Context block. It must stay fast and safe:

- No network access, no `git fetch`/`pull`, no GitHub API calls.
- No Ollama inference, no test suite, no Docker, no Factory verification run.
- No writes to the repository or to any global configuration.
- Never raises: any unexpected failure degrades to a minimal, honest report
  rather than crashing the host session.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

MAX_CONTEXT_CHARS = 2000
GIT_TIMEOUT_SECONDS = 2.0


def _read_session_input() -> dict[str, Any]:
    """Best-effort parse of the SessionStart JSON piped on stdin.

    Untrusted input: only a few string/scalar fields are ever read from it.
    """
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return {}
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_cwd(session_input: dict[str, Any]) -> Path:
    candidate = session_input.get("cwd") if isinstance(session_input, dict) else None
    if isinstance(candidate, str) and candidate.strip():
        try:
            path = Path(candidate).resolve()
            if path.exists():
                return path
        except Exception:
            pass
    try:
        return Path.cwd()
    except Exception:
        return Path(".")


def _git_root(cwd: Path) -> Path | None:
    git_bin = shutil.which("git")
    if not git_bin:
        return None
    try:
        proc = subprocess.run(
            [git_bin, "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    if not out:
        return None
    try:
        return Path(out).resolve()
    except Exception:
        return None


def _sidekick_status(repo_root: Path | None) -> str:
    if repo_root is None:
        return "UNAVAILABLE"
    ai_dir = repo_root / ".ai"
    delegation = ai_dir / "DELEGATION.md"
    rules = ai_dir / "RULES.md"
    if delegation.is_file() and rules.is_file():
        return "READY"
    if ai_dir.is_dir():
        return "PARTIAL"
    return "NOT_INITIALIZED"


def _worker_status(repo_root: Path | None) -> str:
    if repo_root is None:
        return "N/A"
    lock_file = repo_root / ".ai" / "sidekick.lock"
    if lock_file.is_file():
        try:
            age = time.time() - lock_file.stat().st_mtime
        except Exception:
            age = None
        if age is not None and age > 600:
            return "LOCK_STALE"
        return "RUNNING"
    return "IDLE"


def _factory_status(repo_root: Path | None) -> str:
    """Detect presence only; never invokes any Factory verification path."""
    if os.environ.get("AI_ENGINEERING_FACTORY_HOME"):
        return "CONFIGURED"
    if repo_root is not None:
        for name in (".factory", "factory.yaml", "factory.yml", "factory_manifest.yaml"):
            if (repo_root / name).exists():
                return "CONFIGURED"
        sibling = repo_root.parent / "ai-engineering-factory"
        if sibling.is_dir():
            return "AVAILABLE"
    for candidate in ("ai-engineering-factory", "factory"):
        if shutil.which(candidate):
            return "AVAILABLE"
    return "UNAVAILABLE"


def build_context(cwd: Path) -> str:
    try:
        repo_root = _git_root(cwd)
        repo_label = str(repo_root) if repo_root else f"{cwd} (not a Git repository)"
        sidekick_state = _sidekick_status(repo_root)
        worker_state = _worker_status(repo_root)
        factory_state = _factory_status(repo_root)

        lines = [
            "AI DEVELOPMENT ENVIRONMENT",
            "Repository:",
            repo_label,
            "Local AI Sidekick:",
            sidekick_state,
        ]
        if sidekick_state == "NOT_INITIALIZED":
            lines.append(
                "Before the first LOCAL task delegation, run non-destructive `sidekick init .` "
                "(it never overwrites existing files) to provision `.ai/`."
            )
        elif sidekick_state == "PARTIAL":
            lines.append(
                "`.ai/` exists but is incomplete; run `sidekick doctor` before delegating."
            )
        lines.append("Worker:")
        lines.append(worker_state)
        if worker_state == "LOCK_STALE":
            lines.append(
                "A stale worker lock was found; do not delete it automatically. "
                "Confirm no Worker/Watcher process is active, then let Lead resolve it."
            )
        lines.extend(
            [
                "Delegation:",
                "ENABLED" if sidekick_state != "UNAVAILABLE" else "N/A (not a git repository)",
                "Workflow:",
                "LOCAL   -> Local AI Sidekick",
                "LEAD    -> Current Lead Host",
                "BLOCKED -> Stop and resolve ambiguity",
                "AI Engineering Factory:",
                factory_state,
                "Factory policy:",
                "Use only at verification / governance boundaries.",
                "Never bypass Human Approval.",
                "Never auto-merge.",
                "Before substantial implementation:",
                "apply LOCAL / LEAD / BLOCKED classification per .ai/DELEGATION.md.",
                "Final review remains the responsibility of the Lead Host.",
            ]
        )
        context = "\n".join(lines)
    except Exception:
        context = (
            "AI DEVELOPMENT ENVIRONMENT\n"
            "Status: DEGRADED (bootstrap check failed; host session is unaffected)\n"
            "Apply LOCAL / LEAD / BLOCKED classification manually if `.ai/DELEGATION.md` exists."
        )
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS].rstrip() + "\n... (truncated)"
    return context


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    json_mode = "--json" in argv
    session_input = _read_session_input()
    cwd = _resolve_cwd(session_input)
    context = build_context(cwd)
    if json_mode:
        payload = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": context,
            }
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(context)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
