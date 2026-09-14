"""CLI entrypoint for Sidekick."""
import argparse
import sys
from pathlib import Path
from .config import SidekickConfig
from .runner import SidekickRunner

def main():
    parser = argparse.ArgumentParser(description="Local AI Sidekick Runner")
    parser.add_argument("--repo-root", type=str, default=".", help="Root directory of target repository")
    parser.add_argument("--model", type=str, default=None, help="Ollama model name (overrides config)")
    parser.add_argument("--env-file", type=str, default=None, help="Path to .env configuration file")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    env_file = Path(args.env_file).resolve() if args.env_file else None

    config = SidekickConfig.load(repo_root, env_file)
    if args.model:
        config.model = args.model

    runner = SidekickRunner(repo_root=repo_root, config=config)
    result = runner.execute()

    if result.get("status") == "SUCCESS":
        sys.exit(0)
    elif result.get("status") == "BLOCKED":
        sys.exit(2)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
