# Automatic Delegation Policy (Lead only)

Apply this policy to ordinary user requests automatically, before implementation.
User instructions override routing preferences, but never authorize weakening
the Worker's guards. `SIDEKICK_DELEGATION_ENABLED=false` keeps work with Lead.
This is semantic judgment by the Lead, not keyword routing in the helper.

## Decide

Emit a concise decision with `decision: LOCAL | LEAD | BLOCKED`, `reason`, and
`confidence: 0.0-1.0`. For LOCAL, also provide the structured fields in the
[example](../docs/delegation-request.example.json).

- LOCAL: scoped repository exploration / file search / structure inspection,
  small or medium code changes, boilerplate, refactoring, formatting, lint,
  unit test creation/execution, test failure fixes, documentation/README/config
  edits, repetitive edits, typing/import/dead-code cleanup, and bounded changes
  for diff review with explicit acceptance criteria.
- LEAD: architecture/cloud/security design, threat modeling, requirements
  definition, cross-system design, trade-offs, high-impact changes, destructive
  operation decisions, production deployment decisions, IAM/credentials/secrets,
  Terraform apply, cloud writes, root/management account operations, final review,
  and decisions following a Worker BLOCKED result. Mixed tasks containing such
  decisions stay with Lead until a separate low-risk implementation is scoped.
- BLOCKED: ambiguous requirements, unknown Allowed Files, insufficient acceptance
  criteria, uncertainty (confidence below 0.8), or invalid/unsafe task details.
  Never call something low risk merely because it says "small fix" or "config".

Use task_type from `LOCAL_TYPES` / `LEAD_TYPES` in `src/sidekick/delegate.py`.
For LOCAL require `risk: low`, `ambiguous: false`, and
`requires_human_approval: false`. LEAD/BLOCKED never publish a TASK.

## Scope and hand off

1. Perform only the minimum read-only inspection needed to identify concrete
   files and acceptance criteria. Delegate further exploration to Worker inside
   that scope. If scope cannot be identified safely, report BLOCKED.
2. Supply goal, background, exact repository-relative Allowed Files, requirements,
   acceptance criteria, approved verification commands, and review points. Keep
   each text field/list item on one line. No secrets, unrestricted directories,
   glob patterns, shell snippets, or changes to workflow/instruction files.
   Forbidden Operations is optional: helper always includes mandatory prohibitions.
3. Write assessment JSON to a temporary path **outside the target repository**
   (UTF-8, not versioned). Never persist credentials, including in the assessment.
4. Run from the Sidekick installation repository:

   ```powershell
   $env:PYTHONPATH = "$PWD\src"
   python -m sidekick.delegate --repo-root <target-repository> --request <assessment.json>
   ```

   `--dry-run` validates without publishing. LOCAL with `status: QUEUED` means the
   atomic handoff succeeded. ALREADY_QUEUED/ALREADY_HANDLED means stop submitting.
   BLOCKED returns exit code 2; resolve the reason before retrying. Never bypass
   helper validation by writing TASK.md directly for automatically delegated work.
5. Ensure the user-authorized Watcher is running using the README instructions.
   Enqueuing does not start a daemon or override Git/remote/push configuration.
   Report pending work honestly; do not claim implementation finished at QUEUED.
6. Inspect `.ai/state.json` and `.ai/RESULT.md` when Worker finishes. Review
   `ai/<task-id>` diff, tests, commit and push status at READY_FOR_REVIEW.
   Do not merge automatically. A BLOCKED/FAILED/crashed task needs Lead judgment.

## Loop prevention and next task

Only a new user request or an explicit Lead recovery decision can enqueue work.
RESULT.md updates, polling, and completed review never generate another TASK.
The helper derives a stable `local-<96-bit-content-digest>` ID when none is given.
Identical submissions keep the same ID; do not invent a fresh ID on every poll.
Watcher records attempted IDs/hashes before running, including failures/crashes.
History remains in state.json across subsequent tasks; do not delete it to retry.

After reviewing a finished previous task, use `--after-review` to replace it.
For an intentional retry after correcting a BLOCKED cause, provide a **new**
safe task_id and explain the recovery in Background. Do not use this to retry
automatically. Review RUNNING after a crash and record a terminal BLOCKED status
only after confirming no Worker is active; never clear a live lock by age.

## Host integration boundary

Root AGENTS.md is the explicit repository-level Lead entrypoint. This repository
contains no verified Astra/Antigravity-specific instruction-loading contract.
For a host that does not load AGENTS.md, attach AGENTS.md and this policy as its
workspace/system instructions once. README references alone do not activate
automatic routing. No proprietary filenames or hidden model hooks are assumed.
