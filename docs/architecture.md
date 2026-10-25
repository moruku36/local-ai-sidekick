# Architecture: the existing coding Worker

[Documentation index](README.md) | [Current status](current-status.md)

This document describes the existing coding Worker design, with historical Phase 1/2 terminology. It is one candidate use of the local GPU, not the project-wide strategy. Current runtime capabilities and validation limits are recorded in the status and role guides.

## 1. Overview

The coding Worker separates Lead judgment from bounded local execution. Cloud-token reduction was an original motivation, not a measured or guaranteed outcome. The broader project now explores useful supporting jobs for an RTX 3070:

- **Lead AI**: Operates at the architectural level, producing tasks, defining boundaries, and performing final code reviews.
- **Local Sidekick**: Operates locally within the repository, performing local exploration, code modifications, testing, self-fixing, and structured result generation.

Communication between Lead AI and Local Sidekick is file-mediated via local Markdown runtime documents (`.ai/TASK.md` / `.ai/RESULT.md`). The framework versions reusable examples under `templates/`; runtime task/result files are not part of the framework's tracked baseline.

![Local AI Sidekick Technical Architecture](images/architecture.jpg)

```text
       Lead AI (Cloud / Frontier LLM)
                      │
           Writes .ai/TASK.md
                      ▼
               Local Repository
    ┌─────────────────────────────────────────┐
    │ .ai/                                    │
    │  ├── RULES.md         (Permanent rules) │
    │  ├── DECISIONS.md     (Immutable ADR)   │
    │  ├── DELEGATION.md    (Delegation policy)│
    │  └── (TASK.md/RESULT.md ephemeral data) │
    └─────────────────────────────────────────┘
                      ▲
               Reads & Updates
                      │
         Local AI Sidekick (Runner)
    ┌───────────────────────────────────┐
    │ 1. Health & Model check (Ollama)  │
    │ 2. Security validator             │
    │ 3. Workspace file inspector       │
    │ 4. Local LLM invocation           │
    │ 5. Test execution & Self-fix      │
    │ 6. RESULT.md & Git diff summary   │
    └───────────────────────────────────┘
```

## Automatic Delegation

```mermaid
flowchart TD
    U[User] --> L[Lead Host: AGENTS.md]
    L --> P[.ai/DELEGATION.md: semantic decision]
    P -->|LEAD| D[Lead design / judgment / review]
    P -->|BLOCKED| B[Clarify scope / resolve risk]
    P -->|LOCAL| H[sidekick.delegate: validate assessment]
    H -->|shared exclusive lock + atomic replace| T[.ai/TASK.md]
    T --> W[Existing Watcher]
    W --> O[Ollama: implementation / tests / self-fix]
    O --> G[Diff Guard / Secret Scan / Optional Git automation]
    G --> R[RESULT.md + ai/task-id + READY_FOR_REVIEW]
    R --> D
```

Root AGENTS.md is the repository entrypoint for Lead Hosts that load it,
including Codex/Astra-compatible hosts and Claude Code, which loads it (and
`.ai/DELEGATION.md` / `.ai/RULES.md`) automatically through the `@import`s in
[CLAUDE.md](../CLAUDE.md). There is no verified Astra/Antigravity proprietary
hook in this repository; other clients must attach AGENTS.md and the policy
as workspace instructions. Worker system prompts remain unchanged and never
invoke delegation.

The Lead makes the semantic decision and confidence assessment. The helper
fails closed on incomplete assessments, ambiguous scope, non-low risk, unknown
types, unsafe files/commands, or detected credentials. This is not a semantic
security classifier: falsely labeling a risky request low-risk must be avoided
by the Lead. Existing Worker security guards remain the execution boundary.

The helper's file scope is deliberately stricter than legacy tasks: concrete
files only, no workflow/instruction files, directories, globs or secret paths.
It appends mandatory Forbidden Operations and restricts verification commands
to a small reviewed list. Lead can extend the list through code review.

TASK publication and Watcher execution share an exclusive lock. The helper
flushes a same-directory temporary file then atomically replaces TASK.md;
it never modifies Worker status. Watcher reads after locking and persists
`processed_tasks: {task_id: task_hash}` before execution. Other state fields are
unchanged; legacy states load with empty history. Runner preserves this history.
Every attempted ID/hash is deduplicated, including BLOCKED, FAILED and crashes.
This provides at-most-once dispatch, not guaranteed completion after a crash.
History is local to this checkout and must be retained; removing it loses the
cross-task replay protection. Direct legacy runner invocation remains manual.

Stable content-derived IDs make identical helper submissions idempotent.
An unfinished task cannot be overwritten; a terminal task requires explicit
`--after-review` and a new ID for an intentional retry. RESULT changes never
trigger delegation. Stale locks are not stolen on timeout; recovery requires
verifying the owner stopped. State saves are atomic to avoid partial JSON.

See [the operating guide](usage.ja.md#自動委譲) for startup,
disable controls, host setup and troubleshooting. Queueing does not start a
Watcher, change Git settings, merge code or grant production/cloud permissions.

## 2. Directory Structure

The [documentation index](README.md#フォルダ構成) owns the current folder map. Runtime TASK / RESULT files are separate from reusable templates.

## 3. Workflow Protocol

### Phase 1 Manual Mode
1. **Lead AI specifies task**: Writes `.ai/TASK.md`.
2. **Developer runs**: `.\scripts\run-sidekick.ps1`.
3. **Execution Pipeline**: Ollama check -> Task parse -> Local LLM -> Verification -> Self-fix -> RESULT.md -> Exit.

### Phase 2 Optional Git Automation

This is the legacy/spec-coder edit workflow when Git automation is enabled.
Explicit `code-explore` and `command-runner` paths skip Git automation; see [Worker roles](worker-roles.md).
Push remains opt-in and defaults to disabled.

1. **Lead AI writes `.ai/TASK.md`** with `Task ID`.
2. **Watcher or Runner triggered**: `.\scripts\watch-sidekick.ps1` or `.\scripts\run-sidekick-phase2.ps1`.
3. **Git Preflight Check**: Confirms clean git working tree and remote configuration.
4. **Task Branch Creation**: Switches to or creates `ai/<task-id>`. Direct push to `main` is strictly forbidden.
5. **Implementation & Verification**: Local LLM edits allowed files, runs verification commands, and self-fixes if tests fail.
6. **Diff Guard**: Strictly validates modified files against `Allowed Files` before staging.
7. **Secret Scan**: Scans all modified files for tokens, keys, and credentials.
8. **Safe Commit & Optional Push**: Commits when configured; pushes only `origin ai/<task-id>` when explicitly enabled.
9. **Ready For Review**: Updates `.ai/state.json` and `.ai/RESULT.md` to `READY_FOR_REVIEW`.
10. **Lead AI Review**: Lead AI reviews the local candidate (or explicitly published branch) and `RESULT.md`.

## 4. Security & Safety Model

- **Worker Mindset**: Sidekick cannot make unilateral architectural changes. Ambiguities cause status `BLOCKED`.
- **Allowed Files Enforcement & Diff Guard**: Files outside `Allowed Files` cannot be edited or committed.
- **Protected Paths**: `.git`, `.env*`, and `.ai/DECISIONS.md` are strictly blocked.
- **Destructive Command Blocking**: Commands matching `rm -rf`, `git reset --hard`, `terraform apply`, `aws/gcloud/az write` are intercepted and denied.
- **Secret Redaction & Pre-commit Scanning**: Command outputs mask credentials, and git commits containing secrets are blocked.
- **Git Branch Protection**: Local LLM never executes raw git commands. Only trusted Python logic executes git operations. Direct commit or push to `main` is blocked.

## 5. Governance Integration

For independent verification, machine-readable phase boundaries, evidence generation, and Human merge approval, see [AI Governance Control Integration](factory-integration.md). Local AI Sidekick remains the Worker; the AI Governance Control remains the governance/verifier layer.

## 6. References

- [Cognition: Local Fusion](https://cognition.com/blog/local-fusion)


## 7. Proposed Worker role specialization (2026-10-15)

**Candidate paths implemented 2026-10-23.** See [Worker roles](worker-roles.md) for command-runner, code-explore and spec-coder. The [roadmap](worker-role-roadmap.md) retains the earlier proposal and remaining evaluation work. Detailed command-log retention and live Ollama/GPU validation remain open; role names are not evidence of production readiness.
