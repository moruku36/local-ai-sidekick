"""Observe execution separately from verification without running commands."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from sidekick.runner import SidekickRunner


class VerificationReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runner = SidekickRunner(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_empty_suite_is_unverified(self):
        passed, commands, summaries, error, observations = self.runner._run_verification_suite([], Mock())
        self.assertFalse(passed)
        self.assertEqual(observations, [])
        self.assertIn("No verification", error)

    def test_zero_tests_and_timeout_are_not_passes(self):
        for response, expected in [
            ((0, "", "Ran 0 tests"), "UNVERIFIED"),
            ((124, "", ""), "UNVERIFIED"),
        ]:
            workspace = Mock()
            workspace.run_command.return_value = response
            passed, _, _, _, observations = self.runner._run_verification_suite(["python -m unittest"], workspace)
            self.assertFalse(passed)
            self.assertEqual(observations[0]["verification"], expected)

    def test_later_failure_overrides_earlier_pass(self):
        workspace = Mock()
        workspace.run_command.side_effect = [(0, "Ran 1 test", ""), (1, "", "failed")]
        passed, _, summaries, _, observations = self.runner._run_verification_suite(["first", "second"], workspace)
        self.assertFalse(passed)
        self.assertEqual([o["verification"] for o in observations], ["PASSED", "FAILED"])
        self.assertNotIn("failed", str(summaries))


if __name__ == "__main__":
    unittest.main()
