# Local AI Sidekick

[English](README.md) | [日本語](README.ja.md)

A place to explore useful supporting jobs for my local **NVIDIA RTX 3070**, with powerful cloud AI doing the main work. I am trying combinations with Claude, Gemini and ChatGPT; I am still deciding where the local GPU actually helps.

- **Current model status:** Qwen is no longer in use. The repository still contains Qwen defaults and earlier experiment settings; they do not describe my current runtime. A replacement model's installed tag and live operation have not been verified for this update.
- **In this repository:** an Ollama coding Worker with bounded delegation, task/result files, Git controls, role-specific paths, and an offline synthetic security-log audit candidate. Code and synthetic tests are separate from real deployment evidence.
- **Next:** compare short classification/extraction, local search assistance and transcription against simpler alternatives. These are proposals, not implemented product integrations. Coding offload remains one experiment rather than the main strategy.

The motivation has shifted: in my current workflow, cloud AI often lets me keep building without worrying much about token use. This is a personal reason to reconsider local offload, not a claim that cloud AI is always cheaper or faster.

[![CI](https://github.com/moruku36/local-ai-sidekick/actions/workflows/ci.yml/badge.svg)](https://github.com/moruku36/local-ai-sidekick/actions/workflows/ci.yml)

## Current architecture — 2026-11-06

The current repository provides a Python CLI and a local file-based handoff between a Lead AI host and a bounded Worker. The diagram below describes implemented paths, not a live deployment check. Qwen is no longer the reported active model. Gemma adoption and Modal/Kaggle experiments remain unverified plans. HomeLab/OpenClaw are separate systems.

See the [dated architecture, network diagram and configuration evidence](docs/architecture-2026-11-06.md).

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
| Lead entrypoints | `AGENTS.md`, `CLAUDE.md`, delegation policy and optional host setup/bootstrap |
| Delegation | `LOCAL / LEAD / BLOCKED` assessment; `sidekick.delegate` publishes bounded `.ai/TASK.md` requests |
| CLI and execution | `init`, `doctor`, `run`, `integrate`, plus `--watch` mode; manual execution or a separately started Watcher |
| Model-free role | `command-runner` executes approved commands without calling an LLM or Git automation |
| Model-backed roles | Read-only `code-explore`, bounded `spec-coder`, and the legacy coding path use configured local Ollama |
| Review evidence | `.ai/RESULT.md`, state, observed verification and optional guarded Git changes; no automatic merge |
| Claude Code assets | 8 agent definitions and 3 skills, plus imports/hook; these are instruction files, not 8 deployed services |
| Security-log audit candidate | Offline rules over synthetic/public inputs, with optional local Ollama assistance; no remediation |

See the [role contracts](docs/worker-roles.md) and [integration evidence limits](docs/current-status.md#cloud-ai-integration-boundaries). `QUEUED` means a request was written, not that a Worker completed it. The helper does not start the Watcher.

## Model status

| Item | Current evidence |
| --- | --- |
| Local GPU context | NVIDIA RTX 3070 |
| Qwen use | No longer in use, per the owner's latest correction |
| Remaining Qwen configuration | `qwen2.5:14b` remains the source/example default; `Modelfile` is an earlier Qwen experiment setting |
| Active replacement model | Not established by the repository or this documentation check |
| Model selection | Set `SIDEKICK_MODEL` or pass `--model` to select the actual installed model before model-backed work |

This update changes documentation only. It does not replace runtime defaults, install a model or claim a successful GPU run. Leaving the model unspecified still selects the legacy Qwen default in the current code.

### Gemma adoption plan recorded on 2026-11-03

| Item | Plan / status |
| --- | --- |
| Local GPU | NVIDIA RTX 3070 |
| Selected model | Gemma 4 E4B |
| Requested quantization | `gemma4:e4b` + `Q5_K_M` (5-bit); this is the requested configuration, not a confirmed runnable tag |
| Adoption status | Planned; this documentation update does not install, download or benchmark the model |
| Still to confirm | Exact E4B Q5_K_M distribution file / Ollama tag, VRAM fit, inference speed and quality compared with alternatives |

This is the previously recorded adoption plan, not confirmation that Gemma is now installed or active. Qwen's discontinuation does not establish which model replaced it. Performance on the RTX 3070 remains unverified.

Sources checked on **2026-11-03**: [Google's Gemma 4 overview](https://ai.google.dev/gemma/docs/core) confirms E4B, and the [official Ollama tag list](https://ollama.com/library/gemma4/tags) lists `gemma4:e4b`. An official E4B `Q5_K_M` tag was not confirmed there. Select the exact distribution before installation; full GPU residency and performance remain unverified.

## Start here

For a GPU-free first look with Python 3.10+, run from this checkout:

```bash
PYTHONPATH=src python -m sidekick.cli --help
PYTHONPATH=src python -m sidekick.security_audit --input tests/fixtures/security_audit/synthetic-auth.txt --source sshd --bsd-year 2026 --synthetic-or-public
```

These commands need no model or package installation. The audit uses a synthetic fixture and applies no remediation. See the usage guide below for PowerShell syntax and optional model-backed setup.

| Looking for | Read |
| --- | --- |
| What exists, what is verified, and integration limits | [Current status](docs/current-status.md) |
| RTX 3070 options, sources and next experiments | [Future directions / 今後の展開案](docs/future-directions.md) |
| Episodic cloud GPU tests, cost guards and Kaggle boundaries | [Modal GPU experiments](docs/modal-gpu-experiments.md) |
| A GPU-free first look, then optional Worker setup | [Usage](docs/usage.md) / [詳細な日本語ガイド](docs/usage.ja.md) |
| All documents and the folder map | [Documentation index](docs/README.md) |

## How the existing Worker fits

```text
User + Lead AI -> bounded task -> local Worker -> result + diff -> Lead / human review
```

The Lead owns requirements, architecture, security decisions and final review. The Worker has file/command guards; local command execution still interacts with the host and is not a complete sandbox. Configuration defaults are `auto_git=false` and `auto_push=false`; Watcher mode enables Git automation, so review its settings before starting it. Push remains opt-in and automatic merge is unsupported. See [SECURITY.md](SECURITY.md).

Windows Defender state collection does not need a GPU. It belongs to the separate HomeLab operations workflow; Sidekick's synthetic-log audit is a different, unverified deployment candidate.

## Automatic Delegation

For existing instruction links: [AGENTS.md](AGENTS.md) and [.ai/DELEGATION.md](.ai/DELEGATION.md) define `LOCAL / LEAD / BLOCKED`. See the [operating guide](docs/usage.ja.md#自動委譲) for the helper, Watcher and review steps. Queueing a task does not mean it finished.

## Global Integration (Optional)

Codex / Claude Code setup code and instruction files exist. See the [optional setup guide](docs/usage.ja.md#グローバル連携任意) and [integration evidence limits](docs/current-status.md#cloud-ai-integration-boundaries) before changing host settings. Gemini / ChatGPT product connections are exploration ideas; the generic file protocol does not establish a working connector.

## License

[MIT](LICENSE).
