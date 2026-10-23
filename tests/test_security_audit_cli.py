"""Synthetic-only tests for the local audit entrypoint; no live service calls."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sidekick import security_audit


FIXTURE = Path(__file__).parent / "fixtures" / "security_audit" / "synthetic-auth.txt"


class SecurityAuditCliTests(unittest.TestCase):
    def test_offline_fixture_reports_evidence_and_no_actions(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = security_audit.main(["--input", str(FIXTURE), "--source", "sshd", "--bsd-year", "2026", "--synthetic-or-public"])
        report = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(report["llm_status"], "NOT_REQUESTED")
        self.assertFalse(report["actions_executed"])
        self.assertEqual(report["total_findings"], 2)
        self.assertTrue(all(f["evidence_refs"] for f in report["findings"]))

    def test_llm_is_opt_in_and_offline_failure_is_explicit(self):
        output = io.StringIO()
        with patch.object(security_audit, "invoke_local_ollama", side_effect=ConnectionRefusedError):
            with contextlib.redirect_stdout(output):
                status = security_audit.main([
                    "--input", str(FIXTURE), "--source", "sshd", "--bsd-year", "2026", "--synthetic-or-public",
                    "--ollama", "--model", "already-installed:test",
                ])
        report = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertIn("DEFERRED_LLM", report["llm_status"])
        self.assertEqual(report["total_findings"], 2)

    def test_input_bounds_reject_before_inference(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "too-many.log"
            path.write_text("synthetic\n" * 2001, encoding="utf-8")
            with self.assertRaises(ValueError):
                security_audit.read_bounded_input(path)
            path.write_text("x" * (security_audit.MAX_INPUT_BYTES + 1), encoding="utf-8")
            with self.assertRaises(ValueError):
                security_audit.read_bounded_input(path)

    def test_unknown_timestamp_is_rejected_before_reporting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "synthetic.txt"
            path.write_text("untimed synthetic event\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                security_audit.read_bounded_input(path)

    def test_bsd_timestamp_requires_explicit_year(self):
        with self.assertRaises(ValueError):
            security_audit.read_bounded_input(FIXTURE)

    def test_explicit_bsd_year_and_space_timestamp_are_preserved(self):
        from sidekick.security_log_pipeline import parse_and_preprocess_logs

        entries = parse_and_preprocess_logs(
            ["Oct 19 02:00:00 sample-host event", "2025-10-19 03:00:00 sample-host event"],
            default_year=2024,
        )
        self.assertEqual(entries[0]["timestamp"], "2024-10-19T02:00:00Z")
        self.assertEqual(entries[1]["timestamp"], "2025-10-19T03:00:00Z")

    def test_local_endpoint_and_redacted_payload(self):
        class FakeResponse:
            status = 200

            def read(self, limit):
                return json.dumps({"message": {"content": '{"findings": []}'}}).encode()

        class FakeConnection:
            def __init__(self, host, port, timeout):
                self.address = (host, port)
                self.request_body = None

            def request(self, method, path, body, headers):
                self.request_body = body
                self.request_path = path

            def getresponse(self):
                return FakeResponse()

            def close(self):
                pass

        with patch.object(security_audit.http.client, "HTTPConnection", FakeConnection):
            entries = [{"line_no": 1, "raw_hash": "a" * 8, "content": "[REDACTED_SECRET]"}]
            self.assertEqual(security_audit.invoke_local_ollama(entries, "installed:test"), [])
        self.assertEqual((security_audit.OLLAMA_HOST, security_audit.OLLAMA_PORT), ("127.0.0.1", 11434))


if __name__ == "__main__":
    unittest.main()
