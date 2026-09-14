"""Delegation engine and TASK.md generator for Astra / Antigravity Lead AI."""
import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Keywords or patterns strongly indicating Lead AI execution is required
LEAD_PATTERNS = [
    r"\b(architect|architecture|system\s+design|threat\s+model)\b",
    r"\b(cloud\s+design|trade-off|tradeoff|cross-system)\b",
    r"\b(terraform\s+apply|production\s+deploy|deploy\s+to\s+prod)\b",
    r"\b(aws|azure|gcp)\s+(write|create|delete|destroy|apply)\b",
    r"\b(iam\s+role|iam\s+policy|iam\s+permission|root\s+account|management\s+account)\b",
    r"\b(credential\s+design|secret\s+management|vault\s+design)\b",
    r"\b(final\s+review|human\s+review)\b",
]

# Keywords or patterns indicating high-risk operations that must be BLOCKED unless strictly audited
DESTRUCTIVE_OR_BLOCKED_PATTERNS = [
    r"\b(rm\s+-rf|format\s+disk|mkfs|drop\s+database|truncate\s+table)\b",
    r"\b(git\s+reset\s+--hard|git\s+push\s+.*--force)\b",
    r"\b(aws|azure|gcloud)\b.*(delete|destroy|terminate)",
]

# Keywords indicating typical Local Sidekick tasks
LOCAL_PATTERNS = [
    r"\b(fix|bug|issue|error|fail|failing|exception|broken)\b",
    r"\b(test|unittest|pytest|testcase|add\s+test|coverage)\b",
    r"\b(refactor|refactoring|clean\s*up|dead\s*code|optimize)\b",
    r"\b(format|formatter|lint|linter|flake8|black|mypy|typing|types)\b",
    r"\b(doc|docs|readme|comment|documentation)\b",
    r"\b(boilerplate|scaffold|helper|utility|script)\b",
    r"\b(search|find|explore|structure|investigate|survey)\b",
    r"\b(import|imports|config|configuration|settings)\b",
]

@dataclass
class DelegationDecision:
    decision: str  # "LOCAL", "LEAD", "BLOCKED"
    reason: str
    confidence: float
    task_type: str = "general"
    risk: str = "low"
    requires_human_approval: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "confidence": round(self.confidence, 2),
            "task_type": self.task_type,
            "risk": self.risk,
            "requires_human_approval": self.requires_human_approval,
        }

    def to_yaml(self) -> str:
        lines = [
            f"decision: {self.decision}",
            f"reason: \"{self.reason}\"",
            f"confidence: {round(self.confidence, 2)}",
            f"task_type: {self.task_type}",
            f"risk: {self.risk}",
            f"requires_human_approval: {str(self.requires_human_approval).lower()}",
        ]
        return "\n".join(lines)


class DelegationRouter:
    """Evaluates task requests and routes them to LOCAL, LEAD, or BLOCKED."""

    @staticmethod
    def evaluate(
        prompt: str,
        allowed_files: Optional[List[str]] = None,
        context: Optional[str] = None
    ) -> DelegationDecision:
        combined_text = f"{prompt} {context or ''}".lower()

        # 1. Check for destructive or inherently blocked actions
        for pat in DESTRUCTIVE_OR_BLOCKED_PATTERNS:
            if re.search(pat, combined_text, re.IGNORECASE):
                return DelegationDecision(
                    decision="BLOCKED",
                    reason=f"Dangerous/destructive operation pattern detected matching '{pat}'.",
                    confidence=0.98,
                    task_type="destructive",
                    risk="critical",
                    requires_human_approval=True
                )

        # 2. Check for Lead-exclusive domains
        for pat in LEAD_PATTERNS:
            if re.search(pat, combined_text, re.IGNORECASE):
                return DelegationDecision(
                    decision="LEAD",
                    reason=f"High-level design, cloud/infra write, or architecture domain matched '{pat}'. Must be handled by Lead AI.",
                    confidence=0.95,
                    task_type="architecture_or_cloud",
                    risk="high",
                    requires_human_approval=False
                )

        # 3. Check for ambiguity or undefined scope
        if allowed_files is not None and len(allowed_files) == 0:
            return DelegationDecision(
                decision="BLOCKED",
                reason="No Allowed Files specified or scope is completely undefined.",
                confidence=0.90,
                task_type="undefined_scope",
                risk="medium",
                requires_human_approval=True
            )

        # 4. Check for Local Sidekick patterns
        local_matched = False
        matched_category = "code_modification"
        for pat in LOCAL_PATTERNS:
            if re.search(pat, combined_text, re.IGNORECASE):
                local_matched = True
                matched_category = pat.strip(r"\b()")
                break

        if local_matched:
            return DelegationDecision(
                decision="LOCAL",
                reason="Task involves implementation, exploration, test, or maintenance with bounded scope suitable for Local Sidekick.",
                confidence=0.92,
                task_type=matched_category,
                risk="low",
                requires_human_approval=False
            )

        # 5. Default fallback for general requests
        # If requirements seem general but Allowed Files is provided, allow LOCAL with moderate confidence
        if allowed_files and len(allowed_files) > 0:
            return DelegationDecision(
                decision="LOCAL",
                reason="Concrete bounded target files provided. Suitable for Local Sidekick.",
                confidence=0.85,
                task_type="targeted_edit",
                risk="low",
                requires_human_approval=False
            )

        # If completely ambiguous and no target files
        return DelegationDecision(
            decision="BLOCKED",
            reason="Ambiguous request without explicit scope or target files. Needs Lead AI clarification or user input.",
            confidence=0.80,
            task_type="ambiguous",
            risk="medium",
            requires_human_approval=True
        )


class TaskGenerator:
    """Generates structured .ai/TASK.md documents for Local Sidekick."""

    @staticmethod
    def generate_task_id(short_desc: str = "task") -> str:
        now = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        clean_desc = re.sub(r"[^a-zA-Z0-9_-]", "-", short_desc).strip("-")[:25]
        return f"{now}-{clean_desc or 'task'}"

    @staticmethod
    def build_task_markdown(
        task_id: str,
        goal: str,
        background: str = "",
        allowed_files: Optional[List[str]] = None,
        forbidden_operations: Optional[List[str]] = None,
        requirements: Optional[List[str]] = None,
        acceptance_criteria: Optional[List[str]] = None,
        allowed_commands: Optional[List[str]] = None,
        review_points: Optional[List[str]] = None,
    ) -> str:
        files = allowed_files or []
        forbids = forbidden_operations or [
            "Do not modify files outside Allowed Files",
            "Do not commit .env or secrets",
            "Do not alter .ai/DECISIONS.md"
        ]
        reqs = requirements or [f"Implement: {goal}"]
        criteria = acceptance_criteria or ["All tests and verification commands pass."]
        cmds = allowed_commands or []
        reviews = review_points or ["Verify clean implementation and tests passing."]

        lines = [
            "# Current Task",
            "",
            "## Task ID",
            task_id,
            "",
            "## Goal",
            goal.strip(),
            "",
            "## Background",
            background.strip() or f"Automated delegation task for {goal.strip()}.",
            "",
            "## Allowed Files",
        ]
        lines.extend([f"- {f}" for f in files] if files else ["- (None specified)"])

        lines.extend([
            "",
            "## Forbidden Operations",
        ])
        lines.extend([f"- {f}" for f in forbids])

        lines.extend([
            "",
            "## Requirements",
        ])
        lines.extend([f"- {r}" for r in reqs])

        lines.extend([
            "",
            "## Acceptance Criteria",
        ])
        lines.extend([f"- {c}" for c in criteria])

        lines.extend([
            "",
            "## Allowed Commands",
        ])
        lines.extend([f"- {c}" for c in cmds] if cmds else ["- python -m unittest discover tests"])

        lines.extend([
            "",
            "## Review Points",
        ])
        lines.extend([f"- {r}" for r in reviews])
        lines.append("")

        return "\n".join(lines)

    @classmethod
    def write_task_file(
        cls,
        repo_root: Path,
        goal: str,
        short_desc: str = "task",
        task_id: Optional[str] = None,
        background: str = "",
        allowed_files: Optional[List[str]] = None,
        forbidden_operations: Optional[List[str]] = None,
        requirements: Optional[List[str]] = None,
        acceptance_criteria: Optional[List[str]] = None,
        allowed_commands: Optional[List[str]] = None,
        review_points: Optional[List[str]] = None,
    ) -> Tuple[str, Path]:
        actual_id = task_id or cls.generate_task_id(short_desc)
        content = cls.build_task_markdown(
            task_id=actual_id,
            goal=goal,
            background=background,
            allowed_files=allowed_files,
            forbidden_operations=forbidden_operations,
            requirements=requirements,
            acceptance_criteria=acceptance_criteria,
            allowed_commands=allowed_commands,
            review_points=review_points
        )
        task_path = repo_root / ".ai" / "TASK.md"
        task_path.parent.mkdir(parents=True, exist_ok=True)
        task_path.write_text(content, encoding="utf-8")
        return actual_id, task_path
