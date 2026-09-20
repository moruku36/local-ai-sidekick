# Security Policy

## Overview

Local AI Sidekick is an automated local worker designed to execute bounded coding tasks using local Ollama models, under strict Git automation guards and Lead AI / human review.

Because Local AI Sidekick operates directly on local codebases and performs automated Git branching and command execution, security boundaries and operational assumptions must be clearly defined.

---

## Threat Model & Security Boundaries

### What Local AI Sidekick Protects (In-Scope Guards)

1. **Direct Main Branch Protection**:
   - The worker is architecturally forbidden from directly committing or pushing to `main` (or default branches).
   - All automated changes are strictly isolated to dedicated task branches (`ai/<task-id>`).
   - Push operations require explicit opt-in (`SIDEKICK_AUTO_PUSH=true`), defaulting to `false` (fail-closed local-only operation).

2. **Diff Guard & Allowed Files Enforcement**:
   - Every file modified by the worker is validated against the task's explicit `Allowed Files` list before staging.
   - Any attempt to modify out-of-scope files aborts execution with `DIFF_GUARD_VIOLATION`.

3. **Protected Paths & Traversal Defense**:
   - Critical repository metadata and security files are permanently excluded from worker access:
     - `.git/` and version control internals
     - `.env`, `.env.*`, and credential files
     - `.ai/DECISIONS.md` (Architecture Decision Records)
     - `AGENTS.md` and `CLAUDE.md` (Lead instructions)
   - Path traversal (`../`) and absolute path escapes outside the repository root are blocked.

4. **Pre-Commit Secret Scanning**:
   - Modified contents are inspected by regex-based pattern matching before any git commit is generated.
   - Known token formats (AWS keys, GitHub PATs, private keys, generic API secrets) trigger immediate execution abort.

5. **Command Interception & Denylist**:
   - Destructive commands (`rm -rf`, `git reset --hard`, `git push --force`, cloud write operations like `terraform apply`, `aws`, `az`, `gcloud`) are intercepted and denied.
   - Verification commands are strictly limited to safe test and build runners.

6. **Fail-Closed Delegation Boundary**:
   - The delegation router rejects ambiguous scopes, non-low risk tasks, high-consequence requirements, or missing human approval flags with `BLOCKED`.

---

### What Local AI Sidekick Does NOT Protect (Out-of-Scope & Limitations)

1. **LLM Output is Untrusted**:
   - Local LLMs (e.g. `qwen2.5:14b`) may hallucinate, introduce subtle logic bugs, generate insecure patterns (such as SQL injections or missing input sanitization), or misinterpret specifications.
   - **Local AI Sidekick is an implementation worker, not a security verification oracle.**
   - All code produced by Sidekick MUST undergo human review and automated CI/security scanning before merging into production branches.

2. **Shared GitHub Credentials & Identity Separation**:
   - If the worker process shares the same personal access token (PAT) or SSH key as a human developer, the Git hosting platform (e.g. GitHub) cannot distinguish between human actions and autonomous worker actions.
   - **GitHub Ruleset Boundary Nuance**: While repository branch rulesets (such as `main-guardrails`) enforce Pull Request workflows and CI gate passage, solo-maintainer configurations use `required_approving_review_count: 0`. Under this setting, GitHub enforces PR structure and CI status, but does not cryptographically require a distinct second GitHub account to approve before merge. In team environments or high-assurance workflows, configure non-zero approving reviews with CODEOWNERS or verify human approval via independent signed evidence ledgers (e.g., AI Engineering Factory).
   - **Recommendation**: Deploy separate bot accounts or read-only/branch-scoped deploy keys, and enforce branch rulesets requiring independent human approval.

3. **Host OS Compromise & Sandboxing**:
   - Local AI Sidekick runs directly in the host user's environment unless wrapped in a container.
   - If tests or verification commands execute untrusted third-party code or malicious dependencies, Sidekick's policy rules cannot defend against host-level exploits.
   - When working on untrusted repositories or dependencies, execute Local AI Sidekick inside an isolated container or virtual machine.

---

## Supported Versions

Only the latest minor release branch receives security patches and vulnerability remediations.

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| < 0.2.0 | :x:                |

---

## Reporting a Vulnerability

If you discover a security vulnerability or guardrail bypass in Local AI Sidekick:

1. **Do NOT open a public issue.**
2. Report the vulnerability privately via [GitHub Security Advisories](https://github.com/moruku36/local-ai-sidekick/security/advisories/new) or contact the project maintainers directly.
3. Include:
   - Description of the vulnerability and attack vector / bypass mechanism.
   - Reproducible example, including `TASK.md` or configuration payload.
   - Affected versions and host environment details (OS, Python version, Ollama version).

We aim to acknowledge reports within 48 hours and provide a remediation timeline or patch promptly.
