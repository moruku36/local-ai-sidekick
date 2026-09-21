# AI Engineering Factory Integration

Local AI Sidekick and [AI Engineering Factory](https://github.com/moruku36/ai-engineering-factory) solve different problems and are intended to be composed rather than merged into one runtime.

## Responsibility split

| Component | Responsibility |
| --- | --- |
| Lead Host | Requirements, architecture, risk decisions, final review |
| Local AI Sidekick | Bounded local implementation, tests, self-fix, task branch creation |
| AI Engineering Factory | Independent verification, phase contracts, evidence, approval boundary |
| Human Operator | Final review and merge decision |

The Sidekick is a **Worker**. The Factory is a **governance and verification layer**. A successful Sidekick RESULT is not, by itself, Factory-grade evidence.

## Recommended flow

~~~text
User / Lead
    ↓
LOCAL task decision
    ↓
Local AI Sidekick
    ↓
ai/<task-id> branch + tests + RESULT
    ↓
AI Engineering Factory
IndependentVerifier / phase_contract / quality gate
    ↓
Pull Request
    ↓
Human review
    ↓
Human merge
~~~

## Global session bootstrap

`ai-dev-bootstrap` (see [Global Integration](../README.md#global-integration-optional))
reports Factory as `AVAILABLE`/`CONFIGURED`/`UNAVAILABLE` at SessionStart by
checking for local markers only (an `AI_ENGINEERING_FACTORY_HOME`
environment variable, a `factory.yaml`/`.factory` manifest in the repository,
or a Factory executable on `PATH`). This is presence detection, nothing more:
the bootstrap never runs Factory verification, never treats a Sidekick
RESULT as Factory-grade evidence, and never invokes the Factory automatically
at any point. Whether and when to actually run the Factory against a
candidate is still the Lead's decision, made using the flow below.

## Important boundary

The Factory does not currently invoke Local AI Sidekick as a native worker runtime. There is no implicit adapter that turns a Sidekick run into trusted evidence.

Treat the handoff explicitly:

1. Sidekick implements a narrowly scoped task in a task branch or worktree.
2. Review the Sidekick diff and RESULT.
3. Define or update a Factory Task Manifest for the candidate.
4. Run the Factory's independent verification path against the actual candidate worktree/diff.
5. Bind approval to the reviewed PR HEAD.
6. Open/review the PR and let the Human Operator make the merge decision.

Do not treat the Factory `demo` / `ManualAdapter` path as evidence-grade isolation. Use the real isolation and `IndependentVerifier` path when the candidate is untrusted or when strong evidence is required.

## Phase contracts

Sidekick already constrains **where** a Worker can edit through Allowed Files and its diff guard. For multi-phase work, the Factory should additionally constrain **what state that phase may produce** with a machine-readable `phase_contract`.

Example:

~~~yaml
phase_contract:
  target_phase: 1
  preserves:
    - id: PRSV-01
      statement: "The Phase 1 baseline must remain observable"
      check_type: required_pattern
      patterns:
        - "BASELINE"
      applies_to:
        - "src/"
  prohibits:
    - id: PROH-01
      statement: "Phase 2 remediation must not be introduced early"
      target_phase: 2
      check_type: forbidden_pattern
      patterns:
        - "HARDENED"
      applies_to:
        - "src/"
~~~

This complements Sidekick's file-scope guard. It does not replace it.

## Git credentials

Sidekick defaults are deliberately conservative:

- `SIDEKICK_AUTO_GIT=false`
- `SIDEKICK_AUTO_PUSH=false`
- `SIDEKICK_CREATE_PR=false`
- runtime `.ai/TASK.md` and `.ai/RESULT.md` are not committed by default

For stronger separation, do not expose a Human merge-capable GitHub credential to the Worker process. A Worker credential should be limited to task-branch publication / PR creation where possible; Human merge authority should remain outside the Worker execution context.

## Related material

- [Local AI Sidekick README](../README.md)
- [Local AI Sidekick Architecture](architecture.md)
- [AI Engineering Factory Getting Started](https://github.com/moruku36/ai-engineering-factory/blob/main/docs/getting-started.md)
- [AI Engineering Factory Web Security Control Lab Case Study](https://github.com/moruku36/ai-engineering-factory/blob/main/docs/case-studies/web-security-control-lab.md)
