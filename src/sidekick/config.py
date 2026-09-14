"""Configuration manager for Local AI Sidekick."""
import os
from dataclasses import dataclass
from pathlib import Path

@dataclass
class SidekickConfig:
    ollama_base_url: str
    model: str
    max_retries: int
    timeout_seconds: int
    max_files: int
    max_file_bytes: int
    max_context_bytes: int
    rules_path: str
    task_path: str
    result_path: str
    decisions_path: str
    system_prompt_path: str

    @classmethod
    def load(cls, repo_root: Path, env_file: Path | None = None) -> "SidekickConfig":
        env_vars = {}
        target_env = env_file or (repo_root / ".env")
        if target_env.exists():
            for line in target_env.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    env_vars[key.strip()] = val.strip().strip("\"'")

        def get_val(key: str, default: str) -> str:
            return os.environ.get(key, env_vars.get(key, default))

        return cls(
            ollama_base_url=get_val("SIDEKICK_OLLAMA_BASE_URL", "http://localhost:11434"),
            model=get_val("SIDEKICK_MODEL", "qwen2.5:14b"),
            max_retries=int(get_val("SIDEKICK_MAX_RETRIES", "2")),
            timeout_seconds=int(get_val("SIDEKICK_TIMEOUT_SECONDS", "180")),
            max_files=int(get_val("SIDEKICK_MAX_FILES", "40")),
            max_file_bytes=int(get_val("SIDEKICK_MAX_FILE_BYTES", "50000")),
            max_context_bytes=int(get_val("SIDEKICK_MAX_CONTEXT_BYTES", "300000")),
            rules_path=get_val("SIDEKICK_RULES_PATH", ".ai/RULES.md"),
            task_path=get_val("SIDEKICK_TASK_PATH", ".ai/TASK.md"),
            result_path=get_val("SIDEKICK_RESULT_PATH", ".ai/RESULT.md"),
            decisions_path=get_val("SIDEKICK_DECISIONS_PATH", ".ai/DECISIONS.md"),
            system_prompt_path=get_val("SIDEKICK_SYSTEM_PROMPT_PATH", "prompts/sidekick-system.md"),
        )
