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

The lead decides the scope and allowed commands. The worker follows [the permanent rules](.ai/RULES.md), operates on a task branch, and reports blocked or failed work for review. Cloud writes, destructive operations, and merging remain outside the worker's autonomous scope. See the [security policy](SECURITY.md) and [AI Governance Control integration](docs/factory-integration.md) for the trust boundary and independent verification model.

## License

[MIT](LICENSE).

---

## Future Research — runtime reliability and profiling (2026-10-13)

**Status: proposed; not implemented or reproduced.** Priorities below are an investigation order, not release dates.

### Sources and reading scope

- [OpenClaw and Ollama in Agentic AI: Toward Fully Autonomous and Scalable AI Agent Systems](https://arxiv.org/abs/2607.28629v1) — K. I. Roumeliotis and R. Sapkota. Sections 2–4 of the accessible [paper full text](https://www.researchgate.net/publication/411138539_OpenClaw_and_Ollama_in_Agentic_AI_Toward_Fully_Autonomous_and_Scalable_AI_Agent_Systems) separate inference, runtime, execution, memory and governance. The prototype compares inference alone, stateless tools and persistent memory. Its host-mode deployment does not validate container isolation.
- [Author code and evaluation artifacts](https://github.com/Applied-AI-Research-Lab/OpenClaw-and-Ollama-in-Agentic-AI): the current repository includes enriched-input controls and leak correction beyond the accessible manuscript's smaller experiment. Treat these as distinct artifacts; pin their commit before reproduction.
- [Accelerating Post-Quantum Cryptography via LLM-Driven Hardware-Software Co-Design](https://arxiv.org/html/2602.09410v1) — Y. Liao, T. Adegbija and R. Lysecky. Use its profiling workflow as design input; it did not evaluate Ollama workers.

The following are **our adaptations**, not reproduced paper results. No per-turn JSON “Memory Anchor” method was located in the reviewed manuscript; that design below is our proposal. Runtime integration does not establish model-size independence, production safety or an expected coding-success uplift.

### Proposed improvements and acceptance criteria

| Priority | Improvement | Evidence required before adoption |
|---|---|---|
| P1 | Clarify the existing runtime boundaries instead of replacing the worker: Ollama proposes typed actions; a trusted controller owns state, authorization, deadlines and command execution. Invalid model output cannot invoke tools. | A model-generated command, path or permission change is rejected outside the approved task scope; every executed action maps to a registered operation and actual result. |
| P1 | Add a versioned task checkpoint (“state anchor”) containing task/requirement version, goal, candidate digest, TDD stage where applicable, last independently observed test result, next permitted operation IDs and remaining budget. Store it outside model authority. | Restart with stale/corrupt checkpoints, changed candidates or another task cannot reuse evidence or widen permissions. Resume reconciles uncertain effects before retry; restart does not reset budgets. No fabricated RED evidence for documentation-only work. |
| P2 | Evaluate memory with provenance: task-local working state first; any cross-task memory is separately scoped, attributable, expirable and treated as untrusted input. | Tests cover goal continuity, stale requirements, poisoned notes and cross-task contamination. Retrieved text cannot alter policy, approval or accepted tests. |
| P2 | Compare identical model/input/budget runs: current worker; runtime without persistence; runtime with persistence; optionally structured checkpoints. Keep isolation and acceptance oracle identical. | Report independent task success, actual tool effects, recovery, scope violations, latency, retries and token/resource cost, including all failures. Tool claims and worker RESULT alone are insufficient. |
| P3 | Pilot local source/profile-log summarization for performance investigations, with function references and evidence links; compare source-only hypotheses with measured hotspots. | Hold out profiling results when evaluating source-only predictions; record compiler/build/workload conditions and ranking agreement. Unmeasured latency remains unknown; no automatic FPGA or cloud recommendation. |

### Integration boundary

Build on [the existing Factory handoff](docs/factory-integration.md): Lead scopes work, Sidekick proposes a candidate, AI Governance Control independently verifies it, and a human reviews the PR. A native adapter or OpenClaw dependency is a separate future decision. OpenClaw is an architectural reference here, not an installed runtime or a new protocol guarantee.

**Next research milestone:** define the checkpoint contract and a small fixed offline coding/recovery task set, then record a reproducible baseline before choosing a runtime change.

## Planned Worker roles (2026-10-15)

**Proposed; not implemented.** See the [Worker role roadmap](docs/worker-role-roadmap.md) for command-runner, code-explore and spec-coder contracts, staged adoption, current-code observations and evaluation criteria. The existing Lead/Worker safety boundary and independent verification remain in place. An English summary is included in the plan.
