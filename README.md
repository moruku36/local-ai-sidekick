# Local AI Sidekick

[English](README.md) | [日本語](README.ja.md)

**Cloud AI does the main work; this project explores where the local GPU genuinely helps as a sidekick.** Combinations with Claude, Gemini and ChatGPT are being tried, and the jobs worth offloading are still being sorted out.

[![CI](https://github.com/moruku36/local-ai-sidekick/actions/workflows/ci.yml/badge.svg)](https://github.com/moruku36/local-ai-sidekick/actions/workflows/ci.yml)

## At a glance

| Item | Status |
| --- | --- |
| Local host (until 2026-11-17) | NVIDIA RTX 3070 (8GB) — see the [2026-11-06 architecture snapshot](docs/architecture-2026-11-06.md) |
| Local host (from 2026-11-18) | New PC with RTX 5070 Ti (16GB) and 64GB RAM — see the [2026-11-18 architecture](docs/architecture-2026-11-18.md) (planned; installation and measurements follow delivery) |
| Active local model | None confirmed. Qwen is retired; its successor on the current host is not established |
| In this repository | A Python CLI, a bounded file-based delegation protocol (Lead AI → local Worker), Worker roles, and an offline security-log audit candidate |
| Evidence rule | Code and synthetic tests show what exists in source — not what has run on the real machine |

## Try it (no GPU, no model)

With Python 3.10+, run from this checkout:

```bash
PYTHONPATH=src python -m sidekick.cli --help
PYTHONPATH=src python -m sidekick.security_audit --input tests/fixtures/security_audit/synthetic-auth.txt --source sshd --bsd-year 2026 --synthetic-or-public
```

No model or package installation is needed. The audit example uses a synthetic fixture only and applies no remediation. PowerShell syntax and the optional model-backed setup are in the [usage guide](docs/usage.md) / [detailed Japanese guide](docs/usage.ja.md).

## How it works

```text
User + Lead AI -> bounded task -> local Worker -> result + diff -> Lead / human review
```

The Lead owns requirements, architecture, security decisions and final review. The Worker runs with file/command guards, but host command execution is not a complete sandbox. Defaults are `auto_git=false` and `auto_push=false`; Watcher mode enables Git automation, so review its settings before starting it. Push is opt-in; automatic merge is not supported. See [SECURITY.md](SECURITY.md).

```mermaid
flowchart TD
    U["User / human approval"] --> L["Lead AI host: scope, design, review"]
    L --> D["Delegation assessment: LOCAL / LEAD / BLOCKED"]
    D -->|LOCAL only| H["sidekick.delegate: validate and publish TASK"]
    subgraph Local["Local development host / RTX 3070 context"]
        H --> T[".ai/TASK.md + rules"]
        T --> W["Watcher or manual runner"]
        W --> C["command-runner: approved commands, no LLM"]
        W --> M["code-explore / spec-coder / legacy coding path"]
        M --> O["Local Ollama: explicitly selected installed model"]
        O --> M
        C --> R["RESULT + state + observed verification"]
        M --> G["Scope / diff / secret guards; optional Git"]
        G --> R
    end
    R --> L
    D -->|LEAD or BLOCKED| L
    L -. "future experiments, not deployed" .-> P["Gemma adoption / Modal GPU / Kaggle"]
```

| Component | What exists in this repository |
| --- | --- |
| Lead entrypoints | `AGENTS.md`, `CLAUDE.md`, delegation policy, optional host setup/bootstrap |
| Delegation | `LOCAL / LEAD / BLOCKED` assessment; `sidekick.delegate` publishes bounded `.ai/TASK.md` requests |
| CLI and execution | `init`, `doctor`, `run`, `integrate`, plus `--watch` mode; manual run or a separately started Watcher |
| Model-free role | `command-runner` executes approved commands without an LLM or Git automation |
| Model-backed roles | Read-only `code-explore`, bounded `spec-coder`, and the legacy coding path, using the configured local Ollama |
| Review evidence | `.ai/RESULT.md`, state, observed verification, optional guarded Git changes; no automatic merge |
| Claude Code assets | 8 agent definitions and 3 skills, plus imports/hook — instruction files, not 8 deployed services |
| Security-log audit candidate | Offline rules over synthetic/public inputs, with optional local Ollama assistance; no remediation |

Details: [role contracts](docs/worker-roles.md) and [current status / integration limits](docs/current-status.md). `QUEUED` means a request file was written, not that a Worker ran. The delegation helper does not start the Watcher. The diagram shows the implemented paths on the current host; the hardware change on 2026-11-18 is documented in the [2026-11-18 architecture](docs/architecture-2026-11-18.md).

## Model status

| Item | Status |
| --- | --- |
| Qwen | Retired, per the owner's correction. `qwen2.5:14b` remains the source/example default and the `Modelfile` is an earlier Qwen experiment; leaving the model unspecified still selects the legacy default in current code |
| Successor (current host) | Not established by this repository. Before model-backed work, set `SIDEKICK_MODEL` or pass `--model` with the actually installed model |
| Gemma 4 E4B plan (recorded 2026-11-03) | Planned, not installed. Requested `gemma4:e4b` + `Q5_K_M` (5-bit); an official E4B `Q5_K_M` tag was not confirmed. This plan is not confirmation that Gemma replaced Qwen |
| From 2026-11-18 | Local LLM platform moves to Strata on the new PC: Qwen3.8-Flash-Next IQ3_S for daily use, DeepSeek V4.1-Flash for heavy jobs, one at a time. Plan only until measured — see [architecture 2026-11-18](docs/architecture-2026-11-18.md) |

Gemma sources checked on 2026-11-03: [Google's Gemma 4 overview](https://ai.google.dev/gemma/docs/core) confirms E4B; the [official Ollama tag list](https://ollama.com/library/gemma4/tags) lists `gemma4:e4b`. Select the exact distribution before installation; VRAM fit and performance remain unverified.

## Documents

| Looking for | Read |
| --- | --- |
| What exists, what is verified, and integration limits | [Current status](docs/current-status.md) |
| RTX 3070 options, sources and next experiments | [Future directions / 今後の展開案](docs/future-directions.md) |
| Episodic cloud GPU tests, cost guards and Kaggle boundaries | [Modal GPU experiments](docs/modal-gpu-experiments.md) |
| A GPU-free first look, then optional Worker setup | [Usage](docs/usage.md) / [詳細な日本語ガイド](docs/usage.ja.md) |
| Architecture snapshots (2026-11-06 / 2026-11-18), all documents and the folder map | [Documentation index](docs/README.md) |

## Boundaries worth knowing

- **Delegation:** [AGENTS.md](AGENTS.md) and [.ai/DELEGATION.md](.ai/DELEGATION.md) define `LOCAL / LEAD / BLOCKED`; see the [operating guide](docs/usage.ja.md#自動委譲). Queueing a task does not mean it finished.
- **Global integration (optional):** Codex / Claude Code setup code and instruction files exist; see the [setup guide](docs/usage.ja.md#グローバル連携任意) and [integration evidence limits](docs/current-status.md#cloud-ai-integration-boundaries) before changing host settings. Gemini / ChatGPT product connections are exploration ideas — the generic file protocol does not establish a working connector.
- **Separate systems:** HomeLab / OpenClaw are not part of this repository. Windows Defender state collection belongs to that workflow; Sidekick's synthetic-log audit is a different, unverified deployment candidate.

## Why local at all

The original motive was saving cloud AI tokens. In the current workflow, cloud AI often lets the owner keep building without watching token use, so the local role is being reconsidered: short classification/extraction, local search assistance and transcription are candidates to compare against simpler alternatives, and coding offload remains one experiment rather than the main strategy. This is a personal workflow observation, not a claim that cloud AI is always cheaper or faster.

## License

[MIT](LICENSE).
