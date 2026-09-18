# Local AI Sidekick

> Local AI coding worker using Ollama, bounded Lead/Worker delegation, safe Git automation, and human review.

[![CI](https://github.com/moruku36/local-ai-sidekick/actions/workflows/ci.yml/badge.svg)](https://github.com/moruku36/local-ai-sidekick/actions/workflows/ci.yml)

## Purpose

To significantly reduce expensive frontier AI token consumption by establishing a clear division of labor:

- **Lead AI**: Architecture design, strategic decisions, task scoping, and final code reviews.
- **Local Sidekick**: Local repository exploration, implementation, testing, self-fixing, and structured result generation.

Communication between Lead AI and Sidekick is file-mediated via local Markdown runtime files (`.ai/TASK.md` and `.ai/RESULT.md`). These runtime files are no longer tracked by the framework repository; reusable examples live under `templates/`.

### Current scope

| Capability | Status |
| --- | --- |
| Phase 1 manual local worker | Implemented |
| Phase 2 safe branch / commit automation | Implemented |
| Automatic LOCAL / LEAD / BLOCKED delegation | Implemented |
| Claude Code Lead integration | Implemented |
| Automatic push | **Opt-in only; default OFF** |
| Automatic merge | Not supported |

For independent verification and human approval boundaries, see [AI Engineering Factory Integration](docs/factory-integration.md).

---

## Automatic Delegation

```text
User -> Lead Host (Codex/Astra-compatible, Claude Code, ...) -> Delegation Policy -> LOCAL / LEAD / BLOCKED
                                            |
                                      LOCAL only
                                            v
TASK.md -> Existing Watcher -> Local Sidekick -> RESULT.md -> Lead Review
                                  implementation / test / self-fix
                                  ai/<task-id> -> READY_FOR_REVIEW
```

[AGENTS.md](AGENTS.md) instructs the Lead to apply
[.ai/DELEGATION.md](.ai/DELEGATION.md) before each ordinary user request.
The Lead classifies semantically; the standard-library helper validates the
assessment and publishes TASK.md atomically. This is an instruction-driven
delegation layer, not an independent natural-language classifier or a new daemon.
`.ai/DELEGATION.md` is the single source of truth for this policy regardless of
Lead Host: [CLAUDE.md](CLAUDE.md) imports it (and AGENTS.md/RULES.md) for
Claude Code rather than duplicating it. See
[Supported Lead Hosts](#supported-lead-hosts) below. For Astra/Antigravity or
other hosts that do not load AGENTS.md, attach it and the policy to workspace
instructions once; host-specific auto-loading beyond Claude Code is not
verified here.

- **LOCAL**: bounded exploration, small/medium implementation, refactoring,
  tests, fixes, formatting, lint, README/docs/config, and repetitive edits.
- **LEAD**: design, security/IAM, cloud/destructive/deployment decisions, final
  review and Worker BLOCKED recovery.
- **BLOCKED**: ambiguous requirements, unknown file scope, missing acceptance
  criteria, low confidence or unsafe task data. No TASK is written.

Prepare JSON following [the example](docs/delegation-request.example.json),
stored outside the target repository so it cannot enter a Worker commit.
Use concrete file paths, single-line fields, and commands from `SAFE_COMMANDS`
in `src/sidekick/delegate.py`. Arbitrary shell/interpreter commands are rejected.

```powershell
# After installing this repository with pip install -e .
sidekick-delegate --repo-root <target-repository> --request <assessment.json> --dry-run
sidekick-delegate --repo-root <target-repository> --request <assessment.json>
# In another terminal, after reviewing target repo/remote and push settings:
.\scripts\watch-sidekick.ps1 -RepoRoot <target-repository>
```

On macOS/Linux use `sidekick-delegate ...` and `sidekick --repo-root <target-repository> --watch`.
Existing Phase 2/Ollama setup, RULES.md and decisions are still required in the
target repository. The helper does not start the Watcher or alter push settings.

Disable new automatic delegation with `$env:SIDEKICK_DELEGATION_ENABLED = "false"`
(POSIX: `export SIDEKICK_DELEGATION_ENABLED=false`). Stop the Watcher with Ctrl+C
to stop consuming already queued tasks; disabling delegation does not cancel them.

**Troubleshooting:** QUEUED means submitted, not completed. If nothing runs,
check the Watcher terminal, target path, Ollama/model availability and Git preflight.
ALREADY_QUEUED/ALREADY_HANDLED is intentional deduplication. Review RESULT.md and
state.json; use `--after-review` only after reviewing the previous terminal result.
A corrected retry needs a new explicit task_id. BLOCKED/FAILED and interrupted
runs do not restart on polling. Inspect a stale lock's owner and stop any live
Worker before removing it; age alone is insufficient. Repair corrupt state from
a trusted copy rather than deleting history. Delegation currently requires the
default `.ai/TASK.md` path, even though the legacy CLI supports custom paths.

## Supported Lead Hosts

`AGENTS.md` and `.ai/DELEGATION.md` are host-agnostic; the following Lead
Hosts are supported today, and both delegate LOCAL work to the same
`sidekick.delegate` helper, the same Watcher, and the same Ollama Worker:

- **Codex / Astra-compatible host**: loads `AGENTS.md` directly, or has it
  attached to workspace/system instructions once if it does not auto-load
  the file (see the note above).
- **[Claude Code](https://claude.com/claude-code)**: loads `AGENTS.md`,
  `.ai/DELEGATION.md` and `.ai/RULES.md` automatically through the
  `@import`s in [CLAUDE.md](CLAUDE.md) at the repository root.

No Worker code path is specific to either host.

### Claude Code setup

1. Open this repository as the project root in Claude Code (run `claude`
   from this directory, or open the folder in the Claude desktop app).
2. Claude Code automatically loads `CLAUDE.md`, which imports `AGENTS.md`,
   `.ai/DELEGATION.md` and `.ai/RULES.md`. No extra configuration is needed.
3. Verify the imports loaded by running `/memory` inside Claude Code; it
   lists every file contributing to the active project instructions,
   including the three imported files above.
4. Give Claude Code an ordinary task. It applies the same LOCAL/LEAD/BLOCKED
   policy as any other Lead Host and, for LOCAL work, runs
   `sidekick.delegate` exactly as documented in
   [Automatic Delegation](#automatic-delegation).

## Existing Worker Architecture

![Local AI Sidekick Technical Architecture](docs/images/architecture.jpg)

```text
Lead Host (Codex/Astra-compatible, Claude Code, ...)
  │
  │ writes .ai/TASK.md
  ▼
Local Repository
  │
  ├── .ai/
  │   ├── RULES.md       (Permanent rules)
  │   ├── TASK.md        (Task specification)
  │   ├── RESULT.md      (Execution output)
  │   └── DECISIONS.md   (Architecture decisions)
  │
  ├── prompts/
  │   └── sidekick-system.md
  │
  ├── scripts/
  │   ├── run-sidekick.ps1 (Windows runner)
  │   └── run-sidekick     (Bash runner)
  │
  ├── config/
  │   └── sidekick.example.env
  │
  ├── docs/
  │   ├── architecture.md
  │   └── factory-integration.md
  │
  ├── templates/
  │   ├── TASK.example.md
  │   └── RESULT.example.md
  │
  └── README.md
        │
        ▼
Local Sidekick (Ollama Runner)
        │
        ├── repository exploration (Allowed Files only)
        ├── implementation
        ├── lint / format / validation
        ├── unit test execution
        ├── self-fix loop
        └── RESULT.md & git diff generation
```

See [docs/architecture.md](docs/architecture.md) for detailed technical specifications.

---

## Requirements

- **OS**: Windows 10/11, macOS, or Linux
- **Python**: 3.10+ (Standard library only; no external pip dependencies required)
- **PowerShell**: 7+ (or Windows PowerShell) / Bash
- **Git**: 2.30+
- **Ollama**: Installed and running at `http://localhost:11434`

---

## Ollama & Model Setup

Ensure Ollama is running:

```powershell
ollama list
```

Install the standard model (`qwen2.5:14b`):

```powershell
ollama pull qwen2.5:14b
```

### GPU Offload Layer Limit (Video Playback & Desktop Safety)

To prevent Ollama from 100% monopolizing VRAM (allowing concurrent video playback, window manager fluidness, or other GPU workloads), a `Modelfile` is provided:

```dockerfile
FROM qwen2.5:14b
PARAMETER num_gpu 25
```

Apply this layer limit:

```powershell
ollama create qwen2.5:14b -f Modelfile
```

Any installed model can also be specified through the environment variable `SIDEKICK_MODEL` or via the CLI flag `--model`.

---

## Installation & Configuration

1. Clone and install the package:
   ```powershell
   git clone https://github.com/moruku36/local-ai-sidekick.git
   cd local-ai-sidekick
   python -m pip install -e .
   ```

2. (Optional) Create local configuration from example:
   ```powershell
   Copy-Item config\sidekick.example.env .env
   ```

3. For manual TASK.md workflow, copy the runtime templates. Automatic delegation creates `.ai/TASK.md` atomically, so this is not required for delegated tasks.
   ```powershell
   Copy-Item templates\TASK.example.md .ai\TASK.md
   Copy-Item templates\RESULT.example.md .ai\RESULT.md
   ```

   `.ai/TASK.md`, `.ai/RESULT.md`, `.ai/state.json`, and `.ai/sidekick.lock` are runtime files and are ignored by Git by default.

Configuration parameters:
- `SIDEKICK_OLLAMA_BASE_URL`: Ollama endpoint (default: `http://localhost:11434`)
- `SIDEKICK_MODEL`: Default model (default: `qwen2.5:14b`)
- `SIDEKICK_MAX_RETRIES`: Number of self-fix attempts upon test failure (default: `2`)
- `SIDEKICK_TIMEOUT_SECONDS`: Request timeout in seconds (default: `180`)
- `SIDEKICK_AUTO_PUSH`: Push task branches automatically (**default: `false`**)
- `SIDEKICK_COMMIT_TASK_FILE`: Commit runtime TASK.md (**default: `false`**)
- `SIDEKICK_COMMIT_RESULT_FILE`: Commit runtime RESULT.md (**default: `false`**)

---

## TASK.md Workflow

### 1. Lead AI creates `.ai/TASK.md`

Lead AI fills in `.ai/TASK.md` with bounded requirements:

```markdown
# Current Task

## Goal
Implement a string utility function to reverse text.

## Background
Need a string reverser in src/text_utils.py.

## Allowed Files
- src/text_utils.py
- tests/test_text_utils.py

## Forbidden Operations
- Do not modify any files outside Allowed Files

## Requirements
- Provide `reverse_string(text: str) -> str`

## Acceptance Criteria
- `python -m unittest discover tests` succeeds

## Allowed Commands
- python -m unittest discover tests

## Review Points
- Function docstring and type annotations
```

---

## Running Sidekick

After `pip install -e .`, the primary CLI is:

```powershell
sidekick --repo-root .
```

The existing PowerShell wrapper remains available for compatibility:

```powershell
.\scripts\run-sidekick.ps1
```

Options:
- `-RepoRoot <path>`: Target repository directory (default: `.`)
- `-Model <model_name>`: Model override (e.g., `-Model "qwen2.5-coder:7b"`)
- `-EnvFile <path>`: Path to custom `.env` file

On Linux / macOS:

```bash
sidekick --repo-root . --model qwen2.5:14b
```

The `./scripts/run-sidekick` wrapper remains available.

---

## RESULT.md Review

Upon completion, Sidekick generates `.ai/RESULT.md`:

- **Status**: `SUCCESS`, `PARTIAL`, `BLOCKED`, or `FAILED`
- **Summary**: Concise overview of changes made
- **Files Changed**: List of modified/created files
- **Commands Executed**: List of commands run and exit codes
- **Test Results**: Output from test runs
- **Errors**: Diagnostic errors if tests failed
- **Decisions Required**: Items requiring Lead AI decision
- **Git Diff Summary**: `git diff --stat` or untracked file summary

Lead AI inspects `.ai/RESULT.md`, verifies the diff, and accepts or iterates.

---

## Git Workflow & Safety (Phase 1 & Phase 2)

### Phase 1 Manual Workflow
- **No automatic merge or push**: Sidekick modifies local files and runs permitted checks. Run with `scripts/run-sidekick.ps1`.

### Phase 2 Autonomous Git Automation
- When running via `scripts/run-sidekick-phase2.ps1` or `scripts/watch-sidekick.ps1`:
  1. **Preflight Check**: Verifies clean git working tree and remote configuration.
  2. **Automated Branching**: Automatically switches to or creates `ai/<task-id>` from base branch. Direct execution or push to `main` is strictly forbidden.
  3. **Diff Guard**: Before commit, checks all modified files against `Allowed Files` (and `.ai/TASK.md` / `.ai/RESULT.md`). Any unauthorized modification immediately blocks commit and push (`status: BLOCKED`).
  4. **Secret Scan**: Inspects changed files for API keys, AWS tokens, private keys, and high-entropy secrets. Detects and halts if any secret is found (`status: BLOCKED_SECRET_DETECTED`).
  5. **Safe Commit & Push**: Commits source changes with message `ai(<task-id>): <summary>`. Push is **disabled by default** and, when explicitly enabled, is restricted to `origin ai/<task-id>`.
  6. **Final Status**: Marks `.ai/state.json` and `.ai/RESULT.md` as `READY_FOR_REVIEW` for Lead AI or human review.

---

## Phase 2 Watcher Mode (Autonomous Background Worker)

Run the Task Watcher to monitor `.ai/TASK.md` continuously:

```powershell
.\scripts\watch-sidekick.ps1 -Interval 5
```

- Calculates SHA256 hashes of `.ai/TASK.md` to prevent redundant runs.
- Manages concurrency via an exclusive `.ai/sidekick.lock` shared with delegation.
  Stale locks require Lead inspection; elapsed time never steals a live Worker lock.
- Logs execution state in `.ai/state.json`.

---

## Security Model & Operational Notice

> [!WARNING]
> **Local Execution & Untrusted Tasks Warning**:
> This tool executes code, builds, and test commands locally on your machine via subprocesses. While dangerous commands (`rm -rf`, destructive cloud writes, git hard resets) and undeclared file edits are guarded, command execution still interacts directly with your host environment. **Do not run untrusted or unreviewed tasks from unknown sources.**

- **Permanent Rules**: Stored in `.ai/RULES.md`.
- **Allowed Files List & Diff Guard**: Path traversal and access to undeclared files are blocked at execution and before Git commit.
- **Immutable Files**: `.ai/DECISIONS.md`, `.git/`, and `.env*` cannot be altered.
- **Destructive Command Blocking**: Commands matching `rm -rf`, `git reset --hard`, `terraform apply`, `aws/az/gcloud` write operations are intercepted and denied.
- **Secret Redaction & Pre-commit Scanning**: Detects and masks credentials in outputs; blocks commits containing raw secrets.
- **Git Protection**: Local LLM never executes raw git commands; all git operations are performed by hardened Python manager. Push to `main` is blocked.
- **Runtime Task Data**: `.ai/TASK.md` / `.ai/RESULT.md` are runtime files and are not tracked by default. Versioned examples live under `templates/`.
- **Task Data Isolation Recommendation**: This repository provides the sidekick framework. For actual proprietary projects, configure the sidekick in your target project repository rather than committing sensitive operational task/result data.
- **Independent Verification**: For stronger evidence, phase contracts, and merge approval boundaries, use the [AI Engineering Factory integration path](docs/factory-integration.md).

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## References & Acknowledgments

This project's architecture and Lead/Worker division of labor concept is inspired by Cognition's Local Fusion:
- [Cognition: Local Fusion](https://cognition.com/blog/local-fusion)

Related project:
- [AI Engineering Factory integration](docs/factory-integration.md) — independent verification, phase contracts, and human-approved merge boundaries

