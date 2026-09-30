# Local AI Sidekick

[English](README.md) | [日本語](README.ja.md)

A local AI coding worker powered by Ollama. It keeps planning and final review with a lead AI, while a bounded worker investigates a repository, implements changes, runs approved tests, and reports the result.

[![CI](https://github.com/moruku36/local-ai-sidekick/actions/workflows/ci.yml/badge.svg)](https://github.com/moruku36/local-ai-sidekick/actions/workflows/ci.yml)

## What it does

- **Lead AI:** defines the task, makes architecture and security decisions, and reviews the final diff.
- **Local Sidekick:** works within the allowed files and commands, tests its changes, and returns a structured result.
- **Delegation policy:** routes requests to `LOCAL`, `LEAD`, or `BLOCKED` before a task is queued.
- **Git workflow:** uses a task branch for reviewed changes. Automatic push is opt-in and disabled by default; automatic merge is unsupported.
- **Runtime files:** `.ai/TASK.md` carries the task and `.ai/RESULT.md` carries its outcome. These files are ignored by default; reusable examples live in `templates/`.

The [Japanese guide](README.ja.md) contains the full workflow, configuration, platform integrations, troubleshooting, verification steps, and operating precautions.

## Requirements

- Windows 10/11, macOS, or Linux
- Python 3.10+, Git 2.30+, and PowerShell or Bash
- Ollama running locally at `http://localhost:11434` with an installed model; the default is `qwen2.5:14b`

## Quick start

```bash
git clone https://github.com/moruku36/local-ai-sidekick.git
cd local-ai-sidekick
python -m pip install -e ".[dev]"
ollama pull qwen2.5:14b
sidekick init /path/to/repo
sidekick doctor /path/to/repo
```

Initialize the repository where the worker will run, then use the [task template](templates/TASK.example.md) for the manual workflow or the delegation helper for an automatically queued task. The [Japanese guide](README.ja.md#自動委譲) explains the assessment fields, watcher setup, and review process.

## Workflow and safety

```text
User → Lead AI → bounded TASK.md → Local Sidekick → RESULT.md → Lead review
```

The lead decides the scope and allowed commands. The worker follows [the permanent rules](.ai/RULES.md), operates on a task branch, and reports blocked or failed work for review. Cloud writes, destructive operations, and merging remain outside the worker's autonomous scope. See the [security policy](SECURITY.md) and [AI Engineering Factory integration](docs/factory-integration.md) for the trust boundary and independent verification model.

## License

[MIT](LICENSE).
