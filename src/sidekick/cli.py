"""CLI entrypoint for Sidekick (Phase 1, Phase 2, and Watcher)."""
import argparse
import sys
from pathlib import Path
from .config import SidekickConfig
from .runner import SidekickRunner
from .watcher import TaskWatcher
from .delegation import DelegationRouter, TaskGenerator

def main():
    parser = argparse.ArgumentParser(description="Local AI Sidekick Runner")
    parser.add_argument("--repo-root", type=str, default=".", help="Root directory of target repository")
    parser.add_argument("--model", type=str, default=None, help="Ollama model name (overrides config)")
    parser.add_argument("--env-file", type=str, default=None, help="Path to .env configuration file")
    parser.add_argument("--auto-git", action="store_true", help="Enable Phase 2 Git branch/commit/push automation")
    parser.add_argument("--watch", action="store_true", help="Run in continuous Phase 2 TASK.md watcher mode")
    parser.add_argument("--delegate", type=str, default=None, help="Evaluate a task prompt and output delegation decision")
    parser.add_argument("--generate-task", type=str, default=None, help="Generate .ai/TASK.md for a given task goal")
    parser.add_argument("--allowed-files", nargs="*", default=None, help="Allowed files for delegation/task generation")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    env_file = Path(args.env_file).resolve() if args.env_file else None

    # Delegation check command
    if args.delegate:
        decision = DelegationRouter.evaluate(args.delegate, allowed_files=args.allowed_files)
        print(decision.to_yaml())
        sys.exit(0 if decision.decision == "LOCAL" else (2 if decision.decision == "BLOCKED" else 1))

    # Task generation command
    if args.generate_task:
        task_id, path = TaskGenerator.write_task_file(
            repo_root=repo_root,
            goal=args.generate_task,
            allowed_files=args.allowed_files
        )
        print(f"Generated task '{task_id}' at {path}")
        sys.exit(0)

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
