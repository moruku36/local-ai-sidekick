"""Orchestrator runner for Local AI Sidekick (supporting Phase 1 and Phase 2)."""
import json
import re
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .config import SidekickConfig
from .security import SecurityPolicy
from .task_parser import TaskDefinition
from .ollama_client import OllamaClient
from .workspace import WorkspaceManager
from .git_manager import GitAutomationManager
from .state_manager import SidekickState, LockManager

class SidekickRunner:
    def __init__(self, repo_root: Path, config: Optional[SidekickConfig] = None):
        self.repo_root = repo_root.resolve()
        self.config = config or SidekickConfig.load(self.repo_root)
        self.ollama = OllamaClient(
            base_url=self.config.ollama_base_url,
            timeout_seconds=self.config.timeout_seconds
        )
        self.git_manager = GitAutomationManager(self.repo_root)
        self.state_file = self.repo_root / ".ai" / "state.json"

    def _explore_repository(self, task: TaskDefinition, workspace: WorkspaceManager, security_policy: SecurityPolicy) -> Tuple[List[str], Dict[str, str]]:
        """Explores allowed files and directories within configured limits."""
        discovered_files: List[str] = []
        file_contents: Dict[str, str] = {}
        total_context_bytes = 0

        for pattern in task.allowed_files:
            pat_clean = pattern.replace("\\", "/").rstrip("/")
            target_path = self.repo_root / pat_clean

            if not target_path.exists():
                if pat_clean not in discovered_files:
                    discovered_files.append(pat_clean)
                file_contents[pat_clean] = "(File does not exist yet - new file)"
                continue

            if target_path.is_file():
                rel = pat_clean
                if not security_policy.is_path_excluded(rel) and rel not in discovered_files:
                    discovered_files.append(rel)
            elif target_path.is_dir():
                for p in sorted(target_path.rglob("*")):
                    if len(discovered_files) >= self.config.max_files:
                        break
                    if p.is_file():
                        try:
                            rel = p.relative_to(self.repo_root).as_posix()
                        except ValueError:
                            continue
                        if not security_policy.is_path_excluded(rel) and rel not in discovered_files:
                            discovered_files.append(rel)

        # Read contents within size and context byte limits
        for rel in discovered_files:
            if rel in file_contents:
                continue
            allowed, _ = security_policy.is_path_allowed(rel)
            if not allowed or security_policy.is_path_excluded(rel):
                continue

            file_path = self.repo_root / rel
            if not file_path.exists():
                file_contents[rel] = "(File does not exist yet)"
                continue

            file_size = file_path.stat().st_size
            if file_size > self.config.max_file_bytes:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(self.config.max_file_bytes) + "\n\n[TRUNCATED]"
            else:
                content = workspace.read_file(rel)

            content_bytes = len(content.encode("utf-8", errors="replace"))
            if total_context_bytes + content_bytes > self.config.max_context_bytes:
                remaining_bytes = max(0, self.config.max_context_bytes - total_context_bytes)
                if remaining_bytes > 200:
                    truncated = content[:remaining_bytes] + "\n\n[TRUNCATED: CONTEXT LIMIT REACHED]"
                    file_contents[rel] = truncated
                    total_context_bytes += len(truncated.encode("utf-8"))
                else:
                    file_contents[rel] = "[OMITTED: CONTEXT LIMIT REACHED]"
                break
            else:
                file_contents[rel] = content
                total_context_bytes += content_bytes

        return discovered_files, file_contents

    def _run_verification_suite(self, commands: List[str], workspace: WorkspaceManager) -> Tuple[bool, List[str], List[str], str]:
        """Runs candidate verification commands sequentially; returns (passed, commands_run, test_summaries, error_msg)."""
        commands_run = []
        test_summaries = []
        all_passed = True
        first_error = ""

        for cmd in commands:
            if not cmd or not cmd.strip():
                continue
            cmd_clean = cmd.strip()
            print(f"  -> Running: {cmd_clean}")
            code, stdout, stderr = workspace.run_command(cmd_clean)
            commands_run.append(f"`{cmd_clean}` (exit code {code})")
            test_summaries.append(f"Command: {cmd_clean}\nExit Code: {code}\nOutput: {stdout}\nErrors: {stderr}")
            if code != 0:
                all_passed = False
                first_error = f"Command failed: {cmd_clean}\n{stderr or stdout}"
                break

        return all_passed, commands_run, test_summaries, first_error

    def execute(self) -> Dict[str, Any]:
        result_data = {
            "status": "BLOCKED",
            "task_id": "",
            "branch": "",
            "commit_hash": "",
            "push_status": "",
            "automation_status": "IDLE",
            "summary": "",
            "files_changed": [],
            "commands_executed": [],
            "test_results": "",
            "errors": "",
            "remaining_issues": "",
            "decisions_required": "",
            "review_points": "",
            "git_diff_summary": "",
        }

        # Step 1: Health check
        print("[1/12] Verifying Ollama status...")
        if not self.ollama.check_health():
            result_data["status"] = "BLOCKED"
            result_data["errors"] = f"Ollama is not responding at {self.config.ollama_base_url}."
            result_data["summary"] = "Halted: Ollama instance unreachable."
            self._write_result(result_data)
            return result_data

        # Step 2: Model availability check
        print(f"[2/12] Checking model '{self.config.model}'...")
        if not self.ollama.is_model_available(self.config.model):
            available = self.ollama.list_models()
            result_data["status"] = "BLOCKED"
            result_data["errors"] = f"Model '{self.config.model}' is not available in Ollama. Available models: {available}"
            result_data["summary"] = "Halted: Required LLM model not found."
            self._write_result(result_data)
            return result_data

        # Step 3: Load RULES.md
        print("[3/12] Loading RULES.md...")
        rules_file = self.repo_root / self.config.rules_path
        if not rules_file.exists():
            result_data["status"] = "BLOCKED"
            result_data["errors"] = f"Rules file not found at {rules_file}."
            self._write_result(result_data)
            return result_data
        rules_content = rules_file.read_text(encoding="utf-8")

        # Step 4: Load TASK.md
        print("[4/12] Loading TASK.md...")
        task_file = self.repo_root / self.config.task_path
        if not task_file.exists():
            result_data["status"] = "BLOCKED"
            result_data["errors"] = f"Task file not found at {task_file}."
            self._write_result(result_data)
            return result_data
        task = TaskDefinition.parse_file(task_file)
        if not task.goal.strip():
            result_data["status"] = "BLOCKED"
            result_data["errors"] = "TASK.md has no Goal defined."
            self._write_result(result_data)
            return result_data

        result_data["task_id"] = task.task_id

        # Phase 2 Preflight & Branch creation
        if self.config.auto_git:
            print("[4.1/12] Performing Git Preflight Check (Phase 2)...")
            ok, reason = self.git_manager.preflight_check(require_clean=self.config.require_clean_git)
            if not ok:
                result_data["status"] = "BLOCKED"
                result_data["errors"] = f"Git Preflight Failed: {reason}"
                result_data["summary"] = "Halted: Git state is not clean or valid."
                self._write_result(result_data)
                return result_data

            if self.config.auto_branch:
                print(f"[4.2/12] Ensuring task branch for '{task.task_id}'...")
                b_ok, branch_name, b_msg = self.git_manager.ensure_task_branch(task.task_id)
                if not b_ok:
                    result_data["status"] = "BLOCKED"
                    result_data["errors"] = f"Branch creation failed: {b_msg}"
                    result_data["summary"] = "Halted: Failed to create task branch."
                    self._write_result(result_data)
                    return result_data
                result_data["branch"] = branch_name
                print(f"  -> {b_msg}")
        else:
            result_data["branch"] = self.git_manager.get_current_branch() or "local"

        # Check for Resume: if previous run already succeeded / committed on this task
        if self.state_file.exists() and self.config.auto_git:
            prev_state = SidekickState.load(self.state_file)
            if prev_state.task_id == task.task_id and prev_state.status == "SUCCESS":
                if prev_state.commit_hash:
                    result_data["commit_hash"] = prev_state.commit_hash
                    result_data["status"] = "SUCCESS"
                    print(f"  [Resume] Detected previously successful commit {prev_state.commit_hash} for task {task.task_id}.")
                    if self.config.auto_push:
                        print(f"  [Resume] Resuming push of branch {result_data['branch']} to origin...")
                        p_ok, p_msg = self.git_manager.safe_push(result_data["branch"])
                        if not p_ok:
                            result_data["push_status"] = "PUSH_FAILED"
                            result_data["automation_status"] = "PUSH_FAILED"
                            result_data["errors"] = p_msg
                            prev_state.push_status = "PUSH_FAILED"
                            prev_state.automation_status = "PUSH_FAILED"
                            prev_state.save(self.state_file)
                            self._write_result(result_data)
                            return result_data
                        result_data["push_status"] = "SUCCESS"
                        result_data["automation_status"] = "READY_FOR_REVIEW"
                        prev_state.push_status = "SUCCESS"
                        prev_state.automation_status = "READY_FOR_REVIEW"
                        prev_state.save(self.state_file)
                        self._write_result(result_data)
                        print(f"  [Resume] Successfully resumed and pushed branch {result_data['branch']}! READY_FOR_REVIEW.")
                        return result_data

        # Step 5: Load DECISIONS.md
        print("[5/12] Loading DECISIONS.md...")
        decisions_file = self.repo_root / self.config.decisions_path
        decisions_content = decisions_file.read_text(encoding="utf-8") if decisions_file.exists() else "No decisions recorded."

        # Setup Security and Workspace
        security_policy = SecurityPolicy(
            repo_root=self.repo_root,
            allowed_files=task.allowed_files,
            allowed_commands=task.allowed_commands
        )
        workspace = WorkspaceManager(self.repo_root, security_policy)

        # Step 6: Safe repository exploration & file inspection
        print("[6/12] Exploring repository within allowed scope...")
        discovered_files, file_contexts = self._explore_repository(task, workspace, security_policy)

        repo_structure_text = "\n".join(f"- {f}" for f in discovered_files) or "No matching files."
        formatted_file_sections = []
        for rel_path, content in file_contexts.items():
            formatted_file_sections.append(f"FILE: {rel_path}\n```\n{content}\n```")
        repo_files_text = "\n\n".join(formatted_file_sections)

        # Step 7: Build LLM context and prompt
        print("[7/12] Formulating prompt for Local LLM...")
        sys_prompt_file = self.repo_root / self.config.system_prompt_path
        system_instruction = sys_prompt_file.read_text(encoding="utf-8") if sys_prompt_file.exists() else "You are a local coding assistant."

        user_content = f"""
RULES:
{rules_content}

DECISIONS:
{decisions_content}

TASK:
Task ID: {task.task_id}
Goal: {task.goal}
Background: {task.background}
Requirements: {json.dumps(task.requirements, ensure_ascii=False)}
Acceptance Criteria: {json.dumps(task.acceptance_criteria, ensure_ascii=False)}
Allowed Files: {json.dumps(task.allowed_files, ensure_ascii=False)}
Allowed Commands: {json.dumps(task.allowed_commands, ensure_ascii=False)}
Forbidden Operations: {json.dumps(task.forbidden_operations, ensure_ascii=False)}

REPOSITORY STRUCTURE:
{repo_structure_text}

FILE CONTENTS:
{repo_files_text}

INSTRUCTION:
Produce a single strictly valid JSON response containing the implementation plan and file edits.
Do NOT include markdown formatting or conversational text outside the JSON.
Schema:
{{
  "status": "SUCCESS" | "BLOCKED",
  "summary": "Brief explanation of changes",
  "files_to_write": [
    {{
      "path": "relative/path/to/file",
      "content": "Full new content of the file"
    }}
  ],
  "verification_command": "Command to verify from Allowed Commands (or null)",
  "decisions_required": "Any architecture ambiguity (leave empty string if none)",
  "review_points": "Points for Lead AI to check"
}}
If you cannot safely proceed without violating rules or if design is ambiguous, set status to "BLOCKED" and specify "decisions_required".
"""

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content}
        ]

        # Step 8: Execute LLM completion
        print(f"[8/12] Invoking Local LLM ({self.config.model})...")
        try:
            llm_response = self.ollama.chat_complete(
                model=self.config.model,
                messages=messages,
                temperature=0.1
            )
        except Exception as e:
            result_data["status"] = "FAILED"
            result_data["errors"] = f"LLM execution failed: {str(e)}"
            self._write_result(result_data)
            return result_data

        plan = self._extract_json(llm_response)
        if not plan:
            result_data["status"] = "FAILED"
            result_data["errors"] = f"Failed to parse structured JSON from LLM response:\n{llm_response[:500]}"
            self._write_result(result_data)
            return result_data

        if plan.get("status") == "BLOCKED":
            result_data["status"] = "BLOCKED"
            result_data["summary"] = plan.get("summary", "Blocked by LLM evaluation.")
            result_data["decisions_required"] = plan.get("decisions_required", "Lead AI decision needed.")
            result_data["review_points"] = plan.get("review_points", "")
            self._write_result(result_data)
            return result_data

        # Apply file edits
        changed_files = []
        for file_entry in plan.get("files_to_write", []):
            rel = file_entry.get("path")
            content = self._normalize_content(file_entry.get("content", ""))
            if not rel:
                continue
            try:
                workspace.write_file(rel, content)
                changed_files.append(rel)
                print(f"  -> Modified {rel}")
            except Exception as e:
                result_data["status"] = "FAILED"
                result_data["errors"] = f"Failed writing file {rel}: {str(e)}"
                self._write_result(result_data)
                return result_data

        result_data["files_changed"] = changed_files
        result_data["summary"] = plan.get("summary", "Files updated.")
        result_data["review_points"] = plan.get("review_points", "\n".join(task.review_points))

        # Step 9: Lint / Test & Self-Fix Loop
        print("[9/12] Verifying implementation via allowed commands...")
        verification_suite = [c for c in task.allowed_commands if c.strip()]
        if not verification_suite and plan.get("verification_command"):
            verification_suite = [plan.get("verification_command")]

        suite_passed, commands_run, test_summaries, failure_err = self._run_verification_suite(
            verification_suite, workspace
        )

        result_data["commands_executed"] = commands_run
        result_data["test_results"] = "\n\n".join(test_summaries) if test_summaries else "No verification command was executed."
        if not suite_passed:
            result_data["errors"] = failure_err

        # Self-fix loop if verification failed
        if not suite_passed and self.config.max_retries > 0:
            print("[9.1/12] Self-fix iteration triggered...")
            for attempt in range(1, self.config.max_retries + 1):
                print(f"  Attempt {attempt} of {self.config.max_retries}...")
                fix_messages = list(messages)
                fix_messages.append({"role": "assistant", "content": json.dumps(plan)})
                fix_messages.append({
                    "role": "user",
                    "content": f"The verification failed with:\n{result_data['errors']}\nPlease analyze the failure and provide corrected files in the exact same JSON format."
                })
                try:
                    fix_resp = self.ollama.chat_complete(
                        model=self.config.model,
                        messages=fix_messages,
                        temperature=0.1
                    )
                    fix_plan = self._extract_json(fix_resp)
                    if not fix_plan:
                        break
                    for file_entry in fix_plan.get("files_to_write", []):
                        rel = file_entry.get("path")
                        content = self._normalize_content(file_entry.get("content", ""))
                        workspace.write_file(rel, content)
                        if rel not in changed_files:
                            changed_files.append(rel)

                    # Re-verify full test suite
                    print("  Re-running full verification suite...")
                    full_passed, re_cmds, re_summaries, re_err = self._run_verification_suite(
                        verification_suite, workspace
                    )
                    result_data["commands_executed"].extend(re_cmds)
                    result_data["test_results"] += f"\n\n[Self-fix Attempt {attempt} Results]\n" + "\n\n".join(re_summaries)

                    if full_passed:
                        suite_passed = True
                        result_data["errors"] = ""
                        print(f"  -> All verification commands passed on attempt {attempt}!")
                        break
                    else:
                        result_data["errors"] = re_err
                except Exception as ex:
                    result_data["errors"] += f"\nSelf-fix attempt error: {str(ex)}"
                    break

        result_data["status"] = "SUCCESS" if suite_passed else "FAILED"

        # Step 10: RESULT.md generation
        print("[10/12] Generating RESULT.md...")
        # Step 11: Git diff inspection
        print("[11/12] Generating git diff summary...")
        result_data["git_diff_summary"] = workspace.get_git_diff_summary()

        # Step 12: Phase 2 Diff Guard, Secret Scan, Commit, and Push
        if self.config.auto_git and result_data["status"] == "SUCCESS":
            print("[12/12] Phase 2 Git Automation Pipeline...")
            # 12.1 Diff Guard
            extra_allowed = []
            if self.config.commit_task_file:
                extra_allowed.append(self.config.task_path)
            if self.config.commit_result_file:
                extra_allowed.append(self.config.result_path)

            d_ok, actual_changed, d_msg = self.git_manager.validate_diff_guard(
                task.allowed_files, extra_allowed=extra_allowed
            )
            if not d_ok:
                result_data["status"] = "BLOCKED"
                result_data["errors"] = d_msg
                result_data["automation_status"] = "BLOCKED"
                self._write_result(result_data)
                return result_data

            # 12.2 Secret Scan
            print("  -> Performing secret scan on changed files...")
            s_ok, findings = self.git_manager.run_secret_scan_on_changed(actual_changed)
            if not s_ok:
                result_data["status"] = "BLOCKED_SECRET_DETECTED"
                result_data["errors"] = f"Secrets detected in modified files:\n" + "\n".join(f"  {f}" for f in findings)
                result_data["automation_status"] = "BLOCKED_SECRET_DETECTED"
                print(f"  ! {result_data['errors']}")
                self._write_result(result_data)
                return result_data

            # Write result file prior to commit if configured
            self._write_result(result_data)

            # 12.3 Safe Commit
            if self.config.auto_commit:
                print(f"  -> Creating commit for task {task.task_id}...")
                result_data["automation_status"] = "READY_FOR_REVIEW"
                result_data["push_status"] = "PENDING" if self.config.auto_push else "NONE"
                self._write_result(result_data)

                commit_files = [
                    f for f in actual_changed
                    if f.replace("\\", "/") not in [".ai/state.json", ".ai/sidekick.lock"]
                    and "__pycache__" not in f
                    and not f.endswith((".pyc", ".pyo"))
                ]
                if self.config.commit_result_file and self.config.result_path not in commit_files:
                    commit_files.append(self.config.result_path)

                c_ok, c_hash, c_msg = self.git_manager.commit_changes(
                    task.task_id, commit_files, message_suffix=result_data["summary"]
                )
                if not c_ok:
                    result_data["status"] = "FAILED"
                    result_data["errors"] = c_msg
                    result_data["automation_status"] = "FAILED"
                    self._save_state(task.task_id, result_data)
                    self._write_result(result_data)
                    return result_data
                result_data["commit_hash"] = c_hash
                print(f"  -> Committed commit {c_hash}: {c_msg}")

                # Save committed state immediately so resumption works even if push fails or crashes
                self._save_state(task.task_id, result_data)

            # 12.4 Safe Push
            if self.config.auto_push:
                print(f"  -> Pushing branch {result_data['branch']} to origin...")
                p_ok, p_msg = self.git_manager.safe_push(result_data["branch"])
                if not p_ok:
                    result_data["push_status"] = "PUSH_FAILED"
                    result_data["automation_status"] = "PUSH_FAILED"
                    result_data["errors"] = p_msg
                    self._save_state(task.task_id, result_data)
                    self._write_result(result_data)
                    return result_data
                result_data["push_status"] = "SUCCESS"
                result_data["automation_status"] = "READY_FOR_REVIEW"
                print("  -> Successfully pushed task branch!")

            # Update final state
            self._save_state(task.task_id, result_data)
            self._write_result(result_data)

            print(f"\n=======================================================")
            print(f"  *** READY_FOR_REVIEW ***")
            print(f"  Task ID : {result_data['task_id']}")
            print(f"  Branch  : {result_data['branch']}")
            print(f"  Commit  : {result_data['commit_hash']}")
            print(f"  Awaiting Lead AI / Human Review")
            print(f"=======================================================\n")
        else:
            self._write_result(result_data)
            print(f"[12/12] Done. Final status: {result_data['status']}. Awaiting human/Lead AI review.")

        return result_data

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        clean = text.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean)
        clean = clean.strip()

        try:
            return json.loads(clean)
        except Exception:
            match = re.search(r"(\{.*\})", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception:
                    pass
        return None

    def _normalize_content(self, content: str) -> str:
        """Handles potential escaped newlines from raw JSON string output."""
        if "\n" not in content and "\\n" in content:
            try:
                return bytes(content, "utf-8").decode("unicode_escape")
            except Exception:
                return content.replace("\\n", "\n").replace("\\t", "\t")
        return content

    def _write_result(self, res: Dict[str, Any]) -> None:
        target = self.repo_root / self.config.result_path
        files_str = "\n".join(f"- `{f}`" for f in res.get("files_changed", [])) or "None"
        cmds_str = "\n".join(f"- {c}" for c in res.get("commands_executed", [])) or "None"

        content = f"""# Result

## Status

{res.get("status", "FAILED")}

## Task ID

{res.get("task_id", "") or "None"}

## Branch

{res.get("branch", "") or "None"}

## Commit

{res.get("commit_hash", "") or "None"}

## Push Status

{res.get("push_status", "") or "None"}

## Automation Status

{res.get("automation_status", "") or "None"}

## Summary

{res.get("summary", "")}

## Files Changed

{files_str}

## Commands Executed

{cmds_str}

## Test Results

```text
{res.get("test_results", "None")}
```

## Errors

{res.get("errors", "None") or "None"}

## Remaining Issues

{res.get("remaining_issues", "None") or "None"}

## Decisions Required

{res.get("decisions_required", "None") or "None"}

## Review Points

{res.get("review_points", "None") or "None"}

## Git Diff Summary

```text
{res.get("git_diff_summary", "No changes")}
```
"""
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def _save_state(self, task_id: str, res: Dict[str, Any]) -> None:
        previous = SidekickState.load(self.state_file)
        state = SidekickState(
            task_id=task_id,
            task_hash=previous.task_hash if previous.task_id == task_id else "",
            processed_tasks=previous.processed_tasks,
            branch=res.get("branch", ""),
            status=res.get("status", "IDLE"),
            commit_hash=res.get("commit_hash", ""),
            push_status=res.get("push_status", ""),
            automation_status=res.get("automation_status", "IDLE"),
            updated_at=time.strftime("%Y-%m-%d %H:%M:%S")
        )
        state.save(self.state_file)

