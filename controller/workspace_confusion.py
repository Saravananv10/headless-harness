"""Detect workspace confusion (../, absolute out-of-repo, harness self-paths)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_WORKSPACE_CONFUSION_THRESHOLD = 3

_HARNESS_PATH_MARKERS = (
    "headless_harness",
    "/controller/",
    "headless_harness_datagen",
    "/logs/",
)


@dataclass
class WorkspaceConfusionTracker:
    """Count denials/attempts that indicate the agent left the assigned repo."""

    threshold: int = DEFAULT_WORKSPACE_CONFUSION_THRESHOLD
    repo_path: str = ""
    confusion_count: int = 0
    last_target: str | None = None
    last_reason: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_confused(self) -> bool:
        return self.confusion_count >= max(1, self.threshold)

    def record_denial(
        self,
        *,
        tool_name: str,
        reason: str,
        target: str = "",
    ) -> bool:
        """
        Record a denial; return True if this event counts as workspace confusion.
        """
        if self._is_confusion(tool_name=tool_name, reason=reason, target=target):
            self.confusion_count += 1
            self.last_target = target
            self.last_reason = reason
            self.events.append(
                {
                    "tool": tool_name,
                    "target": target[:200],
                    "reason": reason[:200],
                    "count": self.confusion_count,
                }
            )
            return True
        return False

    def _is_confusion(self, *, tool_name: str, reason: str, target: str) -> bool:
        reason_l = (reason or "").lower()
        tgt = (target or "").strip()
        blob = f"{tgt} {reason_l}"

        repo = (self.repo_path or "").strip()
        if repo:
            try:
                repo_r = Path(repo).resolve()
                if tgt.startswith("/"):
                    cand = Path(tgt).expanduser().resolve()
                    if cand == repo_r or repo_r in cand.parents:
                        return False
            except (OSError, ValueError):
                pass

        if "outside repository" in reason_l or "outside repo" in reason_l:
            return True
        if ".." in tgt or re.search(r"(^|[\s=])\.\.(/|$)", tgt):
            return True
        if any(m in blob for m in _HARNESS_PATH_MARKERS):
            return True

        # Bash relative parent escapes mentioned in reason/target
        if tool_name == "Bash" and (
            "../" in tgt
            or "cd .." in tgt.lower()
            or re.search(r"\bcd\s+\.\.", tgt)
        ):
            return True

        return False

    def snapshot(self) -> dict[str, Any]:
        return {
            "threshold": self.threshold,
            "confusion_count": self.confusion_count,
            "is_confused": self.is_confused,
            "last_target": self.last_target,
            "last_reason": self.last_reason,
        }


def classify_bash_parent_escape(command: str) -> bool:
    """True if Bash command uses relative parent directory escapes."""
    c = command or ""
    if "../" in c or "/.." in c:
        return True
    if re.search(r"\bcd\s+\.\.(\s|$|/|;|&)", c, re.I):
        return True
    if re.search(r"(^|[\s;|&])\.\.(\s|$|/)", c):
        return True
    return False


def is_harness_path(path_str: str, *, repo_path: str = "") -> bool:
    p = (path_str or "").strip()
    if not p:
        return False
    lower = p.lower()
    if any(m in lower for m in _HARNESS_PATH_MARKERS):
        return True
    repo = (repo_path or "").strip()
    if repo:
        try:
            parent = str(Path(repo).resolve().parent)
            if p.startswith(parent) and "headless" in p.lower():
                return True
        except (OSError, ValueError):
            pass
    return False
