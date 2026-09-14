"""CLI entrypoint for Sidekick (Phase 1, Phase 2, and Watcher)."""
import argparse
import sys
from pathlib import Path
from .config import SidekickConfig
from .runner import SidekickRunner
from .watcher import TaskWatcher

def main():
    parser = argparse.ArgumentParser(description="Local AI Sidekick Runner")
    parser.add_argument("--repo-root", type=str, default=".", help="Root directory of target repository")
    parser.add_argument("--model", type=str, default=None, help="Ollama model name (overrides config)")
    parser.add_argument("--env-file", type=str, default=None, help="Path to .env configuration file")
    parser.add_argument("--auto-git", action="store_true", help="Enable Phase 2 Git branch/commit/push automation")
    parser.add_argument("--watch", action="store_true", help="Run in continuous Phase 2 TASK.md watcher mode")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    env_file = Path(args.env_file).resolve() if args.env_file else None

    config = SidekickConfig.load(repo_root, env_file)
    if args.model:
        config.model = args.model
    if args.auto_git:
        config.auto_git = True

    if args.watch:
        config.auto_git = True
        watcher = TaskWatcher(repo_root=repo_root, config=config)
        watcher.start_loop()
        sys.exit(0)

    runner = SidekickRunner(repo_root=repo_root, config=config)
    result = runner.execute()

    status = result.get("automation_status") if config.auto_git else result.get("status")

    if status in ["SUCCESS", "READY_FOR_REVIEW"]:
        sys.exit(0)
    elif status and "BLOCKED" in status:
        sys.exit(2)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
