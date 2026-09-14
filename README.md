# Local AI Sidekick (Fusion Lite Phase 1)

> Local AI coding sidekick using Ollama and a lightweight Lead/Worker workflow.

## Purpose

To significantly reduce expensive frontier AI token consumption by establishing a clear division of labor:

- **Lead AI**: Architecture design, strategic decisions, task scoping, and final code reviews.
- **Local Sidekick**: Local repository exploration, implementation, testing, self-fixing, and structured result generation.

In Phase 1, communication between Lead AI and Sidekick is file-mediated via Markdown (`.ai/TASK.md` and `.ai/RESULT.md`).

---

## Architecture

```text
Lead AI
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
  │   └── architecture.md
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

Install recommended coding models (e.g., `qwen2.5-coder:7b` or `gpt-oss:20b`):

```powershell
ollama pull qwen2.5-coder:7b
```

Any installed model can be specified through the environment variable `SIDEKICK_MODEL` or via the CLI flag `--model`.

---

## Installation & Configuration

1. Clone or navigate to the repository:
   ```powershell
   git clone https://github.com/moruku36/local-ai-sidekick.git
   cd local-ai-sidekick
   ```

2. (Optional) Create local configuration from example:
   ```powershell
   Copy-Item config\sidekick.example.env .env
   ```

Configuration parameters:
- `SIDEKICK_OLLAMA_BASE_URL`: Ollama endpoint (default: `http://localhost:11434`)
- `SIDEKICK_MODEL`: Default model (default: `qwen2.5-coder:7b`)
- `SIDEKICK_MAX_RETRIES`: Number of self-fix attempts upon test failure (default: `2`)
- `SIDEKICK_TIMEOUT_SECONDS`: Request timeout in seconds (default: `180`)

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

Run using the PowerShell wrapper (Windows first-class support):

```powershell
.\scripts\run-sidekick.ps1
```

Options:
- `-RepoRoot <path>`: Target repository directory (default: `.`)
- `-Model <model_name>`: Model override (e.g., `-Model "qwen2.5-coder:7b"`)
- `-EnvFile <path>`: Path to custom `.env` file

On Linux / macOS:

```bash
./scripts/run-sidekick --repo-root . --model qwen2.5-coder:7b
```

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

## Git Workflow & Safety

- **No automatic merge or push in Phase 1**: Sidekick only modifies local files and runs permitted checks.
- When working on target projects, recommended branching convention:
  ```text
  main
    │
    └── ai/<task-id>
  ```
- Push to remote `main` by Sidekick is strictly forbidden.

---

## Security Model

- **Permanent Rules**: Stored in `.ai/RULES.md`.
- **Allowed Files List**: Path traversal and access to undeclared files are blocked.
- **Immutable Files**: `.ai/DECISIONS.md`, `.git/`, and `.env*` cannot be altered.
- **Destructive Command Blocking**: Commands matching `rm -rf`, `git reset --hard`, `terraform apply`, `aws/az/gcloud` write operations are intercepted and denied.
- **Secret Redaction**: Detected GitHub tokens and passwords are automatically masked before writing logs or summaries.

---

## Limitations (Phase 1)

- Single-turn execution per runner invocation (plus self-fix retries).
- File-based handoff (no live bidirectional streaming/IPC).
- Local models must fit available GPU/CPU VRAM (recommended: 7B to 14B models for 8GB-16GB VRAM).

---

## Phase 2 Roadmap

The following items are planned for future phases:

- [ ] File system watcher on `.ai/TASK.md` for automatic background triggering
- [ ] Automated safe task branch creation (`ai/<task-id>`)
- [ ] Direct Lead AI API integration (e.g., Gemini API / Anthropic API / OpenAI API)
- [ ] Astra API integration
- [ ] Multi-agent collaborative conversation protocol
- [ ] Interactive terminal tool calling / live workspace sandboxing
