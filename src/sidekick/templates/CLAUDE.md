# Claude Code — Lead Host entrypoint

Claude Code is a **Lead Host** for this repository, equivalent to any
Codex/Astra-compatible host. It follows the same Lead/Worker delegation
workflow, not a Claude-specific one. The policy is defined once, in
`.ai/DELEGATION.md`; nothing below restates it.

The imports below load the existing, host-agnostic instructions so Claude
Code sees exactly what any other Lead Host sees — no separate copy to keep
in sync:

@AGENTS.md
@.ai/DELEGATION.md
@.ai/RULES.md

## Claude Code notes

- Verify the imports loaded by running `/memory` inside Claude Code; it
  lists every file contributing to the active project instructions,
  including the three files imported above.
- Invoke `sidekick-delegate` CLI directly:
  `sidekick-delegate --repo-root . --request <path-to-assessment.json>`
  No `PYTHONPATH` manipulation is needed when Local AI Sidekick is installed.
- `sidekick-delegate` already refuses `Allowed Files` entries named
  `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, or anything under `.ai/`, `.agents/`,
  `.codex/` or `.agent/`, for every Lead Host, not only Claude Code. A LOCAL
  task can never target this file, `AGENTS.md`, or `.ai/DELEGATION.md`.
- The Ollama Worker itself has no Claude-specific code path and no
  Claude-specific system prompt; it is invoked identically regardless of
  which Lead Host queued the task.
