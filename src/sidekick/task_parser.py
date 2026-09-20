"""Task file parser and data structures."""
import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class TaskDefinition:
    task_id: str = ""
    goal: str = ""
    background: str = ""
    allowed_files: List[str] = field(default_factory=list)
    forbidden_operations: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    allowed_commands: List[str] = field(default_factory=list)
    review_points: List[str] = field(default_factory=list)
    raw_content: str = ""

    @classmethod
    def parse_file(cls, task_file: Path) -> "TaskDefinition":
        if not task_file.exists():
            raise FileNotFoundError(f"Task file not found: {task_file}")
        content = task_file.read_text(encoding="utf-8")
        return cls.parse(content)

    @classmethod
    def parse(cls, markdown_text: str) -> "TaskDefinition":
        def extract_section(title: str) -> str:
            pattern = rf"^##\s+{re.escape(title)}\s*\n(.*?)(?=^##\s+|\Z)"
            match = re.search(pattern, markdown_text, re.MULTILINE | re.DOTALL)
            return match.group(1).strip() if match else ""

        def extract_items(section_text: str) -> List[str]:
            items = []
            for line in section_text.splitlines():
                line = line.strip()
                # Remove markdown bullets -, *, 1.
                clean = re.sub(r"^[-*]\s+|\d+\.\s+", "", line).strip()
                # Exclude markdown comments
                if clean and not clean.startswith("<!--") and not clean.endswith("-->"):
                    items.append(clean)
            return items

        raw_task_id = extract_section("Task ID")
        # Remove any comments or bullets from task_id
        task_id = ""
        for line in raw_task_id.splitlines():
            clean = re.sub(r"^[-*]\s+", "", line).strip()
            if clean and not clean.startswith("<!--") and not clean.endswith("-->"):
                task_id = clean
                break

        if not task_id:
            task_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

        goal = extract_section("Goal")
        background = extract_section("Background")
        allowed_files = extract_items(extract_section("Allowed Files"))
        forbidden_operations = extract_items(extract_section("Forbidden Operations"))
        requirements = extract_items(extract_section("Requirements"))
        acceptance_criteria = extract_items(extract_section("Acceptance Criteria"))
        allowed_commands = extract_items(extract_section("Allowed Commands"))
        review_points = extract_items(extract_section("Review Points"))

        return cls(
            task_id=task_id,
            goal=goal,
            background=background,
            allowed_files=allowed_files,
            forbidden_operations=forbidden_operations,
            requirements=requirements,
            acceptance_criteria=acceptance_criteria,
            allowed_commands=allowed_commands,
            review_points=review_points,
            raw_content=markdown_text
        )
