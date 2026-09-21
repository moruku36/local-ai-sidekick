"""CLI entrypoint for Sidekick (Phase 1, Phase 2, Watcher, init, and doctor)."""
import argparse
import sys
from pathlib import Path

from .config import SidekickConfig
from .onboarding import init_repo, run_doctor
from .runner import SidekickRunner
from .watcher import TaskWatcher


def main():
    parser = argparse.ArgumentParser(description="Local AI Sidekick Runner & Onboarding")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # init subcommand
    init_parser = subparsers.add_parser("init", help="Initialize target repository with .ai/ structure, canonical policies, and Lead entrypoints")
    init_parser.add_argument("path", nargs="?", default=".", help="Target repository directory (default: current directory)")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing template files")
    init_parser.add_argument("--no-lead", action="store_true", help="Do not create Lead Host entrypoints (AGENTS.md, CLAUDE.md)")

    # doctor subcommand
    doc_parser = subparsers.add_parser("doctor", help="Diagnose repository readiness, Ollama connection, and guardrails")
    doc_parser.add_argument("path", nargs="?", default=".", help="Target repository directory (default: current directory)")
    doc_parser.add_argument("--mode", type=str, choices=["all", "phase1", "phase2", "delegation"], default="all", help="Diagnostic mode (default: all)")
    doc_parser.add_argument("--model", type=str, default=None, help="Ollama model name (overrides config)")
    doc_parser.add_argument("--env-file", type=str, default=None, help="Path to .env configuration file")

    # integrate subcommand (global Codex / Claude Code SessionStart bootstrap)
    integrate_parser = subparsers.add_parser(
        "integrate",
        help="Install/inspect/remove the global ai-dev-bootstrap SessionStart integration for Codex/Claude Code",
    )
    integrate_parser.add_argument("--global", dest="global_", action="store_true", help="Apply to the user's global configuration (the only supported scope)")
    integrate_parser.add_argument("--host", choices=["codex", "claude", "all"], default="all", help="Target host (default: all)")
    integrate_parser.add_argument("--status", action="store_true", help="Report current integration status instead of installing")
    integrate_parser.add_argument("--remove", action="store_true", help="Remove a previously installed integration instead of installing")
    integrate_parser.add_argument("--dry-run", action="store_true", help="Show planned changes without writing any files")

    # run subcommand (explicit)
    run_parser = subparsers.add_parser("run", help="Run sidekick execution on target repository")
    run_parser.add_argument("--repo-root", type=str, default=".", help="Root directory of target repository")
    run_parser.add_argument("--model", type=str, default=None, help="Ollama model name (overrides config)")
    run_parser.add_argument("--env-file", type=str, default=None, help="Path to .env configuration file")
    run_parser.add_argument("--auto-git", action="store_true", help="Enable Phase 2 Git branch/commit/push automation")
    run_parser.add_argument("--watch", action="store_true", help="Run in continuous Phase 2 TASK.md watcher mode")

    # root options (for backward compatibility when invoked without subcommand, e.g. `sidekick --watch`)
    parser.add_argument("--repo-root", type=str, default=".", help="Root directory of target repository")
    parser.add_argument("--model", type=str, default=None, help="Ollama model name (overrides config)")
    parser.add_argument("--env-file", type=str, default=None, help="Path to .env configuration file")
    parser.add_argument("--auto-git", action="store_true", help="Enable Phase 2 Git branch/commit/push automation")
    parser.add_argument("--watch", action="store_true", help="Run in continuous Phase 2 TASK.md watcher mode")

    args = parser.parse_args()

    if args.command == "init":
        target = Path(args.path).resolve()
        res = init_repo(target, force=args.force, include_lead_entrypoints=not getattr(args, "no_lead", False))
        print(f"=== Initialized Local AI Sidekick in {res['repo_root']} ===")
        for f in res["created"]:
            print(f"  [+] Created {f}")
        for f in res["skipped"]:
            print(f"  [.] Skipped existing {f}")
        if res["gitignore_updated"]:
            print("  [+] Updated .gitignore with runtime exclusions")
        print("\nNext steps:")
        print("  1. Run 'sidekick doctor' to verify local environment readiness")
        print("  2. Compatible Lead Hosts can use the generated delegation entrypoints; host-specific instruction loading may require setup.")
        print("  3. For manual tasks, write .ai/TASK.md and run 'sidekick --watch' or 'sidekick --auto-git'")
        sys.exit(0)

    if args.command == "integrate":
        from .integrate import run_integrate

        if args.status and args.remove:
            print("Error: --status and --remove are mutually exclusive.", file=sys.stderr)
            sys.exit(2)
        sys.exit(run_integrate(host=args.host, status=args.status, remove=args.remove, dry_run=args.dry_run))

    if args.command == "doctor":
        target = Path(args.path).resolve()
        env_file = Path(args.env_file).resolve() if args.env_file else None
        config = SidekickConfig.load(target, env_file)
        if args.model:
            config.model = args.model
        report = run_doctor(target, config, mode=args.mode)
        print(report.format_text())
        sys.exit(1 if report.has_failures else 0)

    # Default / 'run' command execution
    repo_root = Path(getattr(args, "repo_root", ".")).resolve()
    env_file = Path(args.env_file).resolve() if getattr(args, "env_file", None) else None

    config = SidekickConfig.load(repo_root, env_file)
    if args.model:
        config.model = args.model
    if getattr(args, "auto_git", False):
        config.auto_git = True

    if getattr(args, "watch", False):
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
