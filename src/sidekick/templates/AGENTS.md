# Lead AI entrypoint

Before acting on each user task, read [.ai/DELEGATION.md](.ai/DELEGATION.md)
and [.ai/RULES.md](.ai/RULES.md). Apply the delegation decision before doing
substantial exploration, implementation, or tests. Lead owns scoping, design,
security decisions, changes to this delegation layer, and final review.

This file is the Lead entrypoint for any Lead Host. Codex/Astra-compatible
hosts load it directly; Claude Code loads it automatically through the
`@AGENTS.md` import in [CLAUDE.md](CLAUDE.md) at the repository root.

For LOCAL work, generate a bounded assessment and invoke `sidekick.delegate`
as documented in the policy; the existing Watcher executes the Worker task.
For LEAD work, proceed as Lead. For BLOCKED work, resolve the missing decision
with the user; do not guess, enqueue work, or repeatedly regenerate TASK.md.

These instructions target the Lead only. The Ollama Worker follows its existing
system prompt, RULES.md and TASK.md; it must never delegate back to itself.
