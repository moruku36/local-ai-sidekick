"""Security policy and validator for Sidekick commands and file paths."""
import re
import shlex
from pathlib import Path
from typing import List, Tuple

FORBIDDEN_COMMAND_PATTERNS = [
    r"\brm\s+-[rfRF]+",
    r"\bdel\s+/[fqFQ]+",
    r"\brmdir\s+/[sqSQ]+",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[fdxFDX]+",
    r"\bgit\s+push\b",
    r"\bgit\s+branch\s+-[dD]\b",
    r"\bterraform\s+apply\b",
    r"\bterraform\s+destroy\b",
    r"\baws\s+.*(create|delete|update|put|terminate)\b",
    r"\baz\s+.*(create|delete|update)\b",
    r"\bgcloud\s+.*(create|delete|update)\b",
    r"\bformat\s+[a-zA-Z]:",
    r"\bdrop\s+database\b",
    r"\bdrop\s+table\b",
    r"\bcurl\b.*\|\s*(sh|bash|pwsh|powershell)\b",
    r"\bwget\b.*\|\s*(sh|bash|pwsh|powershell)\b",
]

SECRET_KEYWORDS = [
    "password", "secret", "token", "api_key", "apikey", "private_key",
    "bearer", "ghp_", "gho_", "BEGIN RSA PRIVATE KEY", "BEGIN OPENSSH PRIVATE KEY"
]

class SecurityPolicy:
    def __init__(self, repo_root: Path, allowed_files: List[str], allowed_commands: List[str]):
        self.repo_root = repo_root.resolve()
        self.allowed_files = [f.strip() for f in allowed_files if f.strip()]
        self.allowed_commands = [c.strip() for c in allowed_commands if c.strip()]

    def is_path_allowed(self, target_path: Path | str) -> Tuple[bool, str]:
        resolved = (self.repo_root / target_path).resolve()
        try:
            rel = resolved.relative_to(self.repo_root).as_posix()
        except ValueError:
            return False, f"Path {target_path} is outside repository root."

        # Never allow touching .git, .env, or DECISIONS.md
        if rel.startswith(".git") or rel == ".git":
            return False, "Modifying .git directory is forbidden."
        if rel == ".env" or rel.startswith(".env."):
            return False, "Accessing or modifying .env files is forbidden."
        if rel == ".ai/DECISIONS.md":
            return False, ".ai/DECISIONS.md is immutable and cannot be modified."

        # Always allowed internal workflow result file
        if rel in [".ai/RESULT.md", ".ai/result.md"]:
            return True, "Result file is allowed."

        # If Allowed Files list is specified, check inclusion
        if self.allowed_files:
            for pattern in self.allowed_files:
                norm_pat = pattern.replace("\\", "/").rstrip("/")
                if rel == norm_pat or rel.startswith(norm_pat + "/"):
                    return True, f"Path matches allowed pattern: {pattern}"
            return False, f"Path '{rel}' is not in Allowed Files: {self.allowed_files}"

        return True, "Allowed"

    def is_command_allowed(self, cmd: str) -> Tuple[bool, str]:
        cmd_stripped = cmd.strip()
        if not cmd_stripped:
            return False, "Empty command."

        for pattern in FORBIDDEN_COMMAND_PATTERNS:
            if re.search(pattern, cmd_stripped, re.IGNORECASE):
                return False, f"Command contains forbidden destructive pattern: {pattern}"

        if self.allowed_commands:
            # Check if command matches or begins with allowed command base
            matched = False
            for allowed in self.allowed_commands:
                if cmd_stripped == allowed or cmd_stripped.startswith(allowed + " "):
                    matched = True
                    break
            if not matched:
                return False, f"Command '{cmd_stripped}' is not in Allowed Commands list: {self.allowed_commands}"

        return True, "Allowed"

    @staticmethod
    def sanitize_output(output: str) -> str:
        """Mask potential secrets in command outputs or logs."""
        sanitized = output
        # Mask github tokens
        sanitized = re.sub(r"gh[opusr]_[A-Za-z0-9_]{20,}", "[REDACTED_GH_TOKEN]", sanitized)
        # Mask standard Bearer tokens
        sanitized = re.sub(r"Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*", "Bearer [REDACTED_TOKEN]", sanitized, flags=re.IGNORECASE)
        # Mask generic secrets
        sanitized = re.sub(r"(?i)(password|secret|apikey|api_key)\s*[:=]\s*['\"]?([^\s'\"]+)", r"\1: [REDACTED]", sanitized)
        return sanitized
