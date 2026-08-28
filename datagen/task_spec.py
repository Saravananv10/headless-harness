"""task_spec.py — the task record used throughout this package, sourced
from the local task bank (datagen.bank_ingest).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskSpec:
    id: str
    title: str
    description: str
    category: str
    origin: str
    sheet: str
    row_num: int
    process_steps: str = ""
    decision_tree: str = ""
    standards: str = ""
    source: str = ""
    subcategory: str = ""
    variant: str = ""
    task_num: str = ""
    global_index: int = 0
    platform_prompt: str = ""
    dimensions_hint: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def narrative(self) -> str:
        """Assemble the task's own narrative fields into readable prose."""
        parts = [f"Title: {self.title}", f"Description: {self.description}"]
        if self.process_steps:
            parts.append(f"Step-by-Step Process:\n{self.process_steps}")
        if self.decision_tree:
            parts.append(f"Decision Tree / Scenarios:\n{self.decision_tree}")
        if self.standards:
            parts.append(f"Industry Standard / Framework: {self.standards}")
        if self.variant:
            parts.append(f"Variant: {self.variant}")
        return "\n\n".join(parts)
