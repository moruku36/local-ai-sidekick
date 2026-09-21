"""Unit tests for global Codex / Claude Code integration (sidekick.integrate)."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from sidekick.integrate import (
    claude_status,
    codex_status,
    install_claude,
    install_codex,
    remove_claude,
    remove_codex,
    run_integrate,
)


class TestClaudeIntegration(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def test_install_on_empty_home(self):
        result = install_claude(self.home)
        self.assertEqual(result["status"], "UPDATED")
        data = json.loads((self.home / ".claude" / "settings.json").read_text(encoding="utf-8"))
        commands = data["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        self.assertIn("sidekick.bootstrap", commands)

    def test_dry_run_does_not_write(self):
        result = install_claude(self.home, dry_run=True)
        self.assertEqual(result["status"], "WOULD_UPDATE")
        self.assertFalse((self.home / ".claude" / "settings.json").exists())

    def test_idempotent_install(self):
        install_claude(self.home)
        second = install_claude(self.home)
        self.assertEqual(second["status"], "ALREADY_UP_TO_DATE")
        install_claude(self.home)
        install_claude(self.home)
        data = json.loads((self.home / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["hooks"]["SessionStart"]), 1)

    def test_preserves_existing_hooks_and_settings(self):
        settings_dir = self.home / ".claude"
        settings_dir.mkdir(parents=True)
        existing = {
            "hooks": {
                "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo hi"}]}],
                "SessionStart": [{"hooks": [{"type": "command", "command": "echo user-hook"}]}],
            },
            "otherSetting": True,
        }
        (settings_dir / "settings.json").write_text(json.dumps(existing), encoding="utf-8")
        install_claude(self.home)
        data = json.loads((settings_dir / "settings.json").read_text(encoding="utf-8"))
        self.assertTrue(data["otherSetting"])
        self.assertEqual(len(data["hooks"]["PreToolUse"]), 1)
        commands = [h["command"] for entry in data["hooks"]["SessionStart"] for h in entry["hooks"]]
        self.assertIn("echo user-hook", commands)
        self.assertTrue(any("sidekick.bootstrap" in c for c in commands))

    def test_malformed_settings_is_backed_up_not_destroyed(self):
        settings_dir = self.home / ".claude"
        settings_dir.mkdir(parents=True)
        settings_path = settings_dir / "settings.json"
        settings_path.write_text("{not valid json", encoding="utf-8")
        result = install_claude(self.home)
        self.assertIn("backup", result)
        self.assertTrue(Path(result["backup"]).is_file())
        self.assertEqual(Path(result["backup"]).read_text(encoding="utf-8"), "{not valid json")
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertIn("hooks", data)

    def test_status_reports_installed(self):
        self.assertFalse(claude_status(self.home)["installed"])
        install_claude(self.home)
        self.assertTrue(claude_status(self.home)["installed"])

    def test_remove_only_removes_own_entry(self):
        settings_dir = self.home / ".claude"
        settings_dir.mkdir(parents=True)
        existing = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo user-hook"}]}]}}
        (settings_dir / "settings.json").write_text(json.dumps(existing), encoding="utf-8")
        install_claude(self.home)
        result = remove_claude(self.home)
        self.assertEqual(result["status"], "REMOVED")
        data = json.loads((settings_dir / "settings.json").read_text(encoding="utf-8"))
        commands = [h["command"] for entry in data["hooks"]["SessionStart"] for h in entry["hooks"]]
        self.assertEqual(commands, ["echo user-hook"])

    def test_remove_when_not_installed(self):
        result = remove_claude(self.home)
        self.assertEqual(result["status"], "NOT_INSTALLED")


class TestCodexIntegration(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def test_install_on_empty_home(self):
        result = install_codex(self.home)
        self.assertEqual(result["status"], "UPDATED")
        text = (self.home / ".codex" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("ai-dev-bootstrap", text)

    def test_preserves_existing_agents_md(self):
        codex_dir = self.home / ".codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "AGENTS.md").write_text("# My rules\nDo the thing.\n", encoding="utf-8")
        install_codex(self.home)
        text = (codex_dir / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("# My rules", text)
        self.assertIn("Do the thing.", text)
        self.assertIn("ai-dev-bootstrap", text)

    def test_idempotent_install(self):
        install_codex(self.home)
        first_text = (self.home / ".codex" / "AGENTS.md").read_text(encoding="utf-8")
        install_codex(self.home)
        install_codex(self.home)
        second_text = (self.home / ".codex" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(first_text, second_text)
        self.assertEqual(second_text.count("sidekick:ai-dev-bootstrap:begin"), 1)

    def test_status_and_remove(self):
        self.assertFalse(codex_status(self.home)["installed"])
        install_codex(self.home)
        self.assertTrue(codex_status(self.home)["installed"])
        result = remove_codex(self.home)
        self.assertEqual(result["status"], "REMOVED")
        self.assertFalse(codex_status(self.home)["installed"])

    def test_remove_preserves_user_content(self):
        codex_dir = self.home / ".codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "AGENTS.md").write_text("# My rules\n", encoding="utf-8")
        install_codex(self.home)
        remove_codex(self.home)
        text = (codex_dir / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("# My rules", text)
        self.assertNotIn("ai-dev-bootstrap", text)


class TestRunIntegrateCLI(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def test_install_both_hosts(self):
        code = run_integrate(host="all", home=self.home)
        self.assertEqual(code, 0)
        self.assertTrue((self.home / ".claude" / "settings.json").exists())
        self.assertTrue((self.home / ".codex" / "AGENTS.md").exists())

    def test_dry_run_writes_nothing(self):
        code = run_integrate(host="all", dry_run=True, home=self.home)
        self.assertEqual(code, 0)
        self.assertFalse((self.home / ".claude").exists())
        self.assertFalse((self.home / ".codex").exists())

    def test_status_flag(self):
        run_integrate(host="all", home=self.home)
        code = run_integrate(host="all", status=True, home=self.home)
        self.assertEqual(code, 0)

    def test_remove_flag_all_hosts(self):
        run_integrate(host="all", home=self.home)
        code = run_integrate(host="all", remove=True, home=self.home)
        self.assertEqual(code, 0)
        self.assertFalse(claude_status(self.home)["installed"])
        self.assertFalse(codex_status(self.home)["installed"])

    def test_single_host_only_touches_that_host(self):
        run_integrate(host="claude", home=self.home)
        self.assertTrue((self.home / ".claude" / "settings.json").exists())
        self.assertFalse((self.home / ".codex").exists())

    def test_repeated_install_ten_times_is_stable(self):
        for _ in range(10):
            run_integrate(host="all", home=self.home)
        data = json.loads((self.home / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["hooks"]["SessionStart"]), 1)
        text = (self.home / ".codex" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("sidekick:ai-dev-bootstrap:begin"), 1)


if __name__ == "__main__":
    unittest.main()
