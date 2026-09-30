# Local AI Sidekick

[English](README.md) | [日本語](README.ja.md)

An Ollama-based local coding worker with explicit Lead/Worker delegation, scoped file access, guarded commands, safe Git automation, and human review. Lead handles design, scoping, security decisions, and final review.

## Lead and Worker

Lead owns architecture, scope, security decisions, and final review. The Ollama Worker implements bounded tasks within declared files and allowed commands. Automatic delegation is defined in [AGENTS.md](AGENTS.md) and [.ai/DELEGATION.md](.ai/DELEGATION.md).

## Setup

```bash
pip install -e ".[dev]"
```

Configure Ollama and the model using the Japanese setup guide. Validate a delegation request before publishing it:

```bash
sidekick-delegate --repo-root <target-repository> --request <assessment.json> --dry-run
```

The existing Watcher processes queued work. Review result state, changed files, verification evidence, and Git status before integration; queued work is not completed work.

## Boundaries

The framework enforces allowed-file and diff guards, command restrictions, secret redaction/scanning, immutable paths, and managed Git operations. It blocks direct pushes to main and leaves merging to human review. Local command execution interacts with the host and is not a complete sandbox for untrusted tasks. [Security model](SECURITY.md) · [Factory integration](docs/factory-integration.md) · [Inspiration: Local Fusion](https://cognition.com/blog/local-fusion).


## Contents

- [SECURITY.md](SECURITY.md)
- [config/](config)
- [docs/](docs)
- [prompts/](prompts)
- [scripts/](scripts)
- [src/](src)
- [templates/](templates)
- [tests/](tests)

## Detailed documentation

The [Japanese guide](README.ja.md) retains the complete original setup instructions, configuration, examples, project status, and limitations. Supporting documents keep their existing language.
