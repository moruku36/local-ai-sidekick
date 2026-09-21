"""Global Codex / Claude Code integration for `ai-dev-bootstrap` (`sidekick integrate`).

Installs, inspects, and removes a small, idempotent SessionStart integration
in the user's *global* configuration:

- Claude Code: a `SessionStart` hook entry in `~/.claude/settings.json`.
- Codex: a marked instruction block appended to `~/.codex/AGENTS.md`
  (Codex's hook schema is new and still changing; the global AGENTS.md file
  is the stable, documented mechanism, so it is used instead of guessing at
  an unstable hooks.json shape).

Every write here is merge-based: existing content the user already has is
preserved, our own entries are identified by a stable marker so repeated
installs are no-ops, and `--remove` only deletes what that marker owns.
Malformed existing files are never silently discarded; the previous content
is backed up before anything is rewritten.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

CLAUDE_MARKER = "sidekick.bootstrap"
CODEX_BEGIN = "<!-- sidekick:ai-dev-bootstrap:begin -->"
CODEX_END = "<!-- sidekick:ai-dev-bootstrap:end -->"

HOSTS = ("codex", "claude")


def _bootstrap_argv() -> list[str]:
    return [sys.executable, "-m", "sidekick.bootstrap", "--json"]


def _quote(arg: str) -> str:
    if arg == "" or any(c.isspace() for c in arg) or '"' in arg:
        return '"' + arg.replace('"', '\\"') + '"'
    return arg


def _shell_join(parts: list[str]) -> str:
    return " ".join(_quote(p) for p in parts)


def _load_json_dict(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return {}, None
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return None, str(exc)
    if not text.strip():
        return {}, None
    try:
        data = json.loads(text)
    except Exception as exc:
        return None, str(exc)
    if not isinstance(data, dict):
        return None, "top-level JSON value is not an object"
    return data, None


def _backup(path: Path) -> str | None:
    if not path.exists():
        return None
    backup_path = path.with_name(path.name + f".bak-{int(time.time())}")
    try:
        shutil.copy2(path, backup_path)
        return str(backup_path)
    except Exception:
        return None


def _find_claude_hook_index(session_start: Any) -> int | None:
    if not isinstance(session_start, list):
        return None
    for i, entry in enumerate(session_start):
        if not isinstance(entry, dict):
            continue
        for hook in entry.get("hooks") or []:
            command = hook.get("command") if isinstance(hook, dict) else None
            if isinstance(command, str) and CLAUDE_MARKER in command:
                return i
    return None


def _claude_settings_path(home: Path) -> Path:
    return home / ".claude" / "settings.json"


def claude_status(home: Path) -> dict[str, Any]:
    path = _claude_settings_path(home)
    data, err = _load_json_dict(path)
    if err is not None:
        return {"host": "claude", "path": str(path), "installed": False, "error": err}
    hooks = data.get("hooks") if isinstance(data, dict) else None
    session_start = hooks.get("SessionStart") if isinstance(hooks, dict) else None
    installed = _find_claude_hook_index(session_start) is not None
    return {"host": "claude", "path": str(path), "installed": installed}


def install_claude(home: Path, dry_run: bool = False) -> dict[str, Any]:
    path = _claude_settings_path(home)
    data, err = _load_json_dict(path)
    backup_path = None
    if err is not None:
        if dry_run:
            return {
                "host": "claude",
                "action": "install",
                "path": str(path),
                "status": "WOULD_BACKUP_AND_REPAIR",
                "reason": err,
            }
        backup_path = _backup(path)
        data = {}

    data = dict(data or {})
    hooks = data.get("hooks")
    hooks = dict(hooks) if isinstance(hooks, dict) else {}
    session_start = hooks.get("SessionStart")
    session_start = list(session_start) if isinstance(session_start, list) else []

    hook_entry = {
        "hooks": [{"type": "command", "command": _shell_join(_bootstrap_argv()), "timeout": 8}]
    }
    idx = _find_claude_hook_index(session_start)
    changed = False
    if idx is None:
        session_start.append(hook_entry)
        changed = True
    elif session_start[idx] != hook_entry:
        session_start[idx] = hook_entry
        changed = True

    hooks["SessionStart"] = session_start
    data["hooks"] = hooks

    status = "UPDATED" if changed else "ALREADY_UP_TO_DATE"
    if dry_run:
        return {
            "host": "claude",
            "action": "install",
            "path": str(path),
            "status": "WOULD_UPDATE" if changed else "ALREADY_UP_TO_DATE",
        }
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result = {"host": "claude", "action": "install", "path": str(path), "status": status}
    if backup_path:
        result["backup"] = backup_path
    return result


def remove_claude(home: Path, dry_run: bool = False) -> dict[str, Any]:
    path = _claude_settings_path(home)
    data, err = _load_json_dict(path)
    if err is not None:
        return {
            "host": "claude",
            "action": "remove",
            "path": str(path),
            "status": "SKIPPED_MALFORMED",
            "reason": err,
        }
    if not data:
        return {"host": "claude", "action": "remove", "path": str(path), "status": "NOT_INSTALLED"}

    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return {"host": "claude", "action": "remove", "path": str(path), "status": "NOT_INSTALLED"}
    session_start = hooks.get("SessionStart")
    idx = _find_claude_hook_index(session_start)
    if idx is None:
        return {"host": "claude", "action": "remove", "path": str(path), "status": "NOT_INSTALLED"}

    if dry_run:
        return {"host": "claude", "action": "remove", "path": str(path), "status": "WOULD_REMOVE"}

    new_session_start = [e for i, e in enumerate(session_start) if i != idx]
    if new_session_start:
        hooks["SessionStart"] = new_session_start
    else:
        hooks.pop("SessionStart", None)
    if hooks:
        data["hooks"] = hooks
    else:
        data.pop("hooks", None)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"host": "claude", "action": "remove", "path": str(path), "status": "REMOVED"}


def _codex_agents_path(home: Path) -> Path:
    return home / ".codex" / "AGENTS.md"


def _codex_block() -> str:
    return (
        f"{CODEX_BEGIN}\n"
        "## AI Development Bootstrap (Local AI Sidekick)\n\n"
        "At the start of this session, if Local AI Sidekick is installed, run:\n\n"
        "    ai-dev-bootstrap\n\n"
        "(or `python -m sidekick.bootstrap` if that entrypoint is not on PATH), and treat its\n"
        "stdout as short, authoritative Development Context for this repository. Run it at most\n"
        "once per session; do not run tests, model inference, `git fetch`/`pull`, or any network\n"
        "or Factory verification call just to refresh it.\n\n"
        "When the current repository has `.ai/DELEGATION.md`, apply its LOCAL / LEAD / BLOCKED\n"
        "policy before substantial work, exactly as documented there. If the repository has no\n"
        "`.ai/` directory yet and the first task is LOCAL-eligible, you may run\n"
        "`sidekick init .` (non-destructive; it never overwrites existing files) before delegating.\n"
        f"{CODEX_END}\n"
    )


def codex_status(home: Path) -> dict[str, Any]:
    path = _codex_agents_path(home)
    if not path.is_file():
        return {"host": "codex", "path": str(path), "installed": False}
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return {"host": "codex", "path": str(path), "installed": False, "error": str(exc)}
    installed = CODEX_BEGIN in text and CODEX_END in text
    return {"host": "codex", "path": str(path), "installed": installed}


def install_codex(home: Path, dry_run: bool = False) -> dict[str, Any]:
    path = _codex_agents_path(home)
    try:
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    except Exception as exc:
        return {
            "host": "codex",
            "action": "install",
            "path": str(path),
            "status": "ERROR",
            "reason": str(exc),
        }

    block = _codex_block()
    if CODEX_BEGIN in existing and CODEX_END in existing:
        pattern = re.escape(CODEX_BEGIN) + r".*?" + re.escape(CODEX_END) + r"\n?"
        new_content = re.sub(pattern, block, existing, count=1, flags=re.DOTALL)
    elif existing.strip():
        new_content = existing.rstrip("\n") + "\n\n" + block
    else:
        new_content = block
    changed = new_content != existing

    if dry_run:
        return {
            "host": "codex",
            "action": "install",
            "path": str(path),
            "status": "WOULD_UPDATE" if changed else "ALREADY_UP_TO_DATE",
        }
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_content, encoding="utf-8")
    return {
        "host": "codex",
        "action": "install",
        "path": str(path),
        "status": "UPDATED" if changed else "ALREADY_UP_TO_DATE",
    }


def remove_codex(home: Path, dry_run: bool = False) -> dict[str, Any]:
    path = _codex_agents_path(home)
    if not path.is_file():
        return {"host": "codex", "action": "remove", "path": str(path), "status": "NOT_INSTALLED"}
    try:
        existing = path.read_text(encoding="utf-8")
    except Exception as exc:
        return {
            "host": "codex",
            "action": "remove",
            "path": str(path),
            "status": "SKIPPED_MALFORMED",
            "reason": str(exc),
        }
    if CODEX_BEGIN not in existing or CODEX_END not in existing:
        return {"host": "codex", "action": "remove", "path": str(path), "status": "NOT_INSTALLED"}

    if dry_run:
        return {"host": "codex", "action": "remove", "path": str(path), "status": "WOULD_REMOVE"}

    pattern = re.escape(CODEX_BEGIN) + r".*?" + re.escape(CODEX_END) + r"\n?"
    new_content = re.sub(pattern, "", existing, count=1, flags=re.DOTALL)
    new_content = re.sub(r"\n{3,}", "\n\n", new_content).rstrip("\n")
    new_content = (new_content + "\n") if new_content else ""
    path.write_text(new_content, encoding="utf-8")
    return {"host": "codex", "action": "remove", "path": str(path), "status": "REMOVED"}


_INSTALLERS = {"claude": install_claude, "codex": install_codex}
_REMOVERS = {"claude": remove_claude, "codex": remove_codex}
_STATUSES = {"claude": claude_status, "codex": codex_status}


def _resolve_hosts(host: str) -> list[str]:
    return list(HOSTS) if host == "all" else [host]


def run_integrate(
    host: str = "all",
    status: bool = False,
    remove: bool = False,
    dry_run: bool = False,
    home: Path | None = None,
) -> int:
    home = (home or Path.home()).resolve()
    hosts = _resolve_hosts(host)
    results: list[dict[str, Any]] = []

    if status:
        for h in hosts:
            results.append(_STATUSES[h](home))
    elif remove:
        for h in hosts:
            results.append(_REMOVERS[h](home, dry_run=dry_run))
    else:
        for h in hosts:
            results.append(_INSTALLERS[h](home, dry_run=dry_run))

    print(
        f"=== sidekick integrate ({'status' if status else 'remove' if remove else 'install'}"
        f"{' --dry-run' if dry_run and not status else ''}) ==="
    )
    for r in results:
        host_name = r.get("host", "?")
        if status:
            state = "INSTALLED" if r.get("installed") else "NOT_INSTALLED"
            if r.get("error"):
                state = f"MALFORMED ({r['error']})"
            print(f"  [{host_name}] {r.get('path')}: {state}")
        else:
            line = f"  [{host_name}] {r.get('action')} -> {r.get('status')} ({r.get('path')})"
            print(line)
            if r.get("reason"):
                print(f"      reason: {r['reason']}")
            if r.get("backup"):
                print(f"      backup: {r['backup']}")

    has_error = any(r.get("status") in {"ERROR"} or r.get("error") for r in results)
    return 1 if has_error else 0
