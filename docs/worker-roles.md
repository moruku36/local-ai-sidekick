# Explicit Worker roles (candidate)

[Documentation index](README.md) | [Current status](current-status.md)

The Lead first applies `.ai/DELEGATION.md` and fixes the scope. Add `## Worker Role` to `.ai/TASK.md` (or `worker_role` to a delegated task request). Accepted values are `command-runner`, `code-explore`, and `spec-coder`; an omitted role uses the previous worker path. All explicit roles require a safe task ID, a concrete goal/background and exact, unprotected `Allowed Files` paths. `spec-coder` also requires requirements, acceptance criteria and review points. The delegation gate accepts only its small reviewed command set.

| Role | Runtime capability | Report |
| --- | --- | --- |
| `code-explore` | Reads existing exact files within byte/context limits and calls the configured Ollama model. Requires an empty `Allowed Commands` list. Never enters the editor, command runner or Git automation. | Cited facts, separately labeled inferences, searched scope, unsearched portions and review points. Citations establish a source line, not the truth of an interpretation. |
| `spec-coder` | Proposes edits only for exact allowed files. The complete structured proposal is checked before the first write; ambiguity, deviations, invalid fields, credentials and scope expansion block it. Only preapproved verification commands run. | Implementation status, independently observed verification status, unverified claims, changed files and review points. Existing Git options still apply; review them before running. |
| `command-runner` | Runs the preapproved commands without a model or Git automation. Commands can have host side effects. | Per-command task/candidate/run IDs, CWD, timing, execution status, exit code and verification status. Candidate changes during verification are unverified. |

Example read-only task body (complete other Lead fields as usual):

```markdown
## Task ID

synthetic-explore-1

## Worker Role

code-explore

## Goal

Find the synthetic helper.

## Background

Only the public synthetic example is in scope.

## Allowed Files

- examples/synthetic_helper.py

## Allowed Commands

```

The runner writes `.ai/RESULT.md` for review. Model roles require a loopback Ollama endpoint. Source text and model output are untrusted. `code-explore` skips possible sensitive content; do not supply real logs, personal data or private source. The Lead checks citations, the final diff and test evidence independently. No role makes an automatic merge decision.

The command observation contains no detailed output log (`log_ref: null`, `output_retained: false`). Local retention, expiry and access policy remain to be designed before claiming the full planned command-runner contract. The two opt-in real Ollama tests and GPU operation have not been run for this candidate.
