# Antigravity & Astra Delegation Instructions

This repository operates under a **Lead / Worker** cooperative model:
- **Lead AI (Antigravity / Astra)**: System design, architecture planning, boundary enforcement, and final code review.
- **Worker (Local Sidekick / Ollama)**: Repository exploration, file modifications, test execution, linting, and self-fixing.

## 1. Automatic Delegation Policy

Whenever a user request arrives, Antigravity / Astra MUST evaluate the delegation policy before making direct code changes:

### Principle: Delegate to LOCAL wherever possible
The following tasks MUST be delegated to Local Sidekick:
- Code repairs, bug fixes, exception handling
- Unit test additions, test execution, test failure fixes
- Code refactoring, formatting, lint cleanup, type improvements, dead code removal
- Documentation updates (README, docs, docstrings)
- Boilerplate generation, configuration updates, helper scripts
- Repository exploration, file/symbol search, codebase structure survey

### Retain for LEAD (Antigravity / Astra)
The following tasks MUST NOT be delegated to Local Sidekick:
- System & architecture design, threat modeling, security architecture
- Architectural trade-off decisions, cross-system design
- Cloud resource writes, Terraform apply, production deployments
- IAM permissions, credential/secret management, cloud management operations
- Final code review of READY_FOR_REVIEW branches
- Resolving ambiguous requirements or unblocking BLOCKED states

### Mark as BLOCKED
- Requests where Allowed Files cannot be safely bounded
- Ambiguous user requirements that could lead to destructive actions
- Dangerous shell execution attempts (m -rf, format disk, git force push)

---

## 2. Delegation Execution Workflow

When a request is classified as **LOCAL**:
1. Lead AI crafts .ai/TASK.md following the standard schema (or runs python -m sidekick.cli --generate-task "<goal>" --allowed-files <files...>).
2. The active background Watcher (scripts/watch-sidekick.ps1) automatically detects the task SHA-256 update.
3. Local Sidekick executes locally using Ollama (qwen2.5:14b), tests the changes, and self-fixes if needed.
4. Diff Guard and Secret Scanner validate the changes.
5. Local Sidekick commits to i/<task-id> branch, pushes, and marks READY_FOR_REVIEW.
6. Lead AI (Antigravity / Astra) reviews .ai/RESULT.md and the remote branch diff before final merge.

---

## 3. Loop Prevention & Idempotency
- Never re-generate the same TASK.md content with identical Task ID if state.json is already READY_FOR_REVIEW.
- If Local Sidekick reports BLOCKED or FAILED, Lead AI must inspect .ai/RESULT.md and consult the user rather than blindly looping.
