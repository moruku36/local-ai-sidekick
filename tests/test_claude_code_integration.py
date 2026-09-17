"""Tests for the Claude Code Lead Host integration.

Verifies CLAUDE.md defers to .ai/DELEGATION.md as the single source of truth
(via Claude Code's @import mechanism) instead of duplicating the policy, and
that this documentation-only integration does not change existing
delegation behavior or the Worker's protected-file guards.
"""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sidekick.delegate import assess, submit

ROOT = Path(__file__).parents[1]


class TestClaudeCodeIntegration(unittest.TestCase):
    def setUp(self):
        self.claude_md = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.agents_md = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.delegation_md = (ROOT / ".ai" / "DELEGATION.md").read_text(encoding="utf-8")
        self.request = json.loads((ROOT / "docs/delegation-request.example.json").read_text())
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.temp_root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"SIDEKICK_DELEGATION_ENABLED": "true",
                                          "SIDEKICK_TASK_PATH": ".ai/TASK.md"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_claude_md_imports_the_single_source_of_truth(self):
        for imported in ("@AGENTS.md", "@.ai/DELEGATION.md", "@.ai/RULES.md"):
            self.assertIn(imported, self.claude_md)

    def test_claude_md_does_not_duplicate_the_policy(self):
        # CLAUDE.md must defer to .ai/DELEGATION.md via import, not restate
        # the LOCAL/LEAD/BLOCKED decision rules itself.
        for marker in ("LOCAL:", "LEAD:", "BLOCKED:"):
            self.assertNotIn(marker, self.claude_md)

    def test_agents_md_references_claude_md_entrypoint(self):
        self.assertIn("CLAUDE.md", self.agents_md)

    def test_delegation_policy_body_stays_host_agnostic(self):
        # Only the "Host integration boundary" section may name specific
        # Lead Hosts; the decision rules above it must remain provider-neutral.
        policy_body = self.delegation_md.split("## Host integration boundary")[0]
        for name in ("Codex", "Claude Code", "Astra"):
            self.assertNotIn(name, policy_body)

    def test_delegation_assessment_unaffected_by_doc_changes(self):
        # Regression guard: documentation/provider-neutral wording edits
        # must not change delegate.py's LOCAL/LEAD/BLOCKED classification.
        outcome = assess(self.temp_root, self.request)
        self.assertEqual(outcome["decision"], "LOCAL")

        lead_request = dict(self.request, task_type="architecture")
        self.assertEqual(assess(self.temp_root, lead_request)["decision"], "LEAD")

    def test_claude_md_and_agents_md_are_protected_from_worker_edits(self):
        for protected in ("CLAUDE.md", "AGENTS.md", ".ai/DELEGATION.md"):
            with self.subTest(protected=protected):
                request = copy.deepcopy(self.request)
                request["task"]["allowed_files"] = [protected]
                self.assertEqual(submit(self.temp_root, request)["decision"], "BLOCKED")
        self.assertFalse((self.temp_root / ".ai/TASK.md").exists())


if __name__ == "__main__":
    unittest.main()
