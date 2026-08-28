"""Track tool denials for adaptive recovery."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

DEFAULT_DENIAL_LOOP_THRESHOLD = 3


@dataclass
class DenialTracker:
    """Session-scoped denial counters keyed by tool + target + reason."""

    loop_threshold: int = DEFAULT_DENIAL_LOOP_THRESHOLD
    total_denials: int = 0
    by_reason: Counter[str] = field(default_factory=Counter)
    # (tool, target, reason) -> count
    groups: dict[tuple[str, str, str], int] = field(default_factory=dict)
    last_denied_tool: str | None = None
    last_denied_target: str | None = None
    last_denied_reason: str | None = None
    out_of_repo_denials: int = 0

    def record(
        self,
        *,
        tool_name: str,
        reason: str,
        target: str = "",
        approved: bool = False,
    ) -> None:
        if approved:
            return
        reason_l = (reason or "").strip()
        response_hint = reason_l.lower()
        if not (
            response_hint.startswith("deny")
            or response_hint.startswith("no")
            or "deny " in response_hint
        ):
            # Still count unapproved if caller says approved=False with empty reason
            if not reason_l:
                reason_l = "denied"
        self.total_denials += 1
        tool = (tool_name or "unknown").strip() or "unknown"
        tgt = (target or "").strip()
        bucket = reason_l[:120] if reason_l else "denied"
        self.by_reason[bucket] += 1
        key = (tool, tgt or "(unknown)", bucket)
        self.groups[key] = self.groups.get(key, 0) + 1
        self.last_denied_tool = tool
        self.last_denied_target = tgt
        self.last_denied_reason = bucket
        if "outside repository" in bucket.lower() or "outside repo" in bucket.lower():
            self.out_of_repo_denials += 1

    def clear_out_of_repo_groups(self) -> int:
        """Remove out-of-repo denial groups and recount. Returns groups cleared."""
        removed = 0
        new_groups: dict[tuple[str, str, str], int] = {}
        for key, count in self.groups.items():
            _tool, _tgt, reason = key
            if "outside repository" in reason.lower() or "outside repo" in reason.lower():
                removed += 1
                continue
            new_groups[key] = count
        self.groups = new_groups
        # Rebuild aggregates from remaining groups
        self.by_reason = Counter()
        self.total_denials = 0
        self.out_of_repo_denials = 0
        for (_tool, _tgt, reason), count in self.groups.items():
            self.by_reason[reason] += count
            self.total_denials += count
        return removed

    @property
    def top_group_count(self) -> int:
        return max(self.groups.values()) if self.groups else 0

    @property
    def top_group(self) -> tuple[str, str, str, int] | None:
        if not self.groups:
            return None
        (tool, tgt, reason), count = max(self.groups.items(), key=lambda kv: kv[1])
        return tool, tgt, reason, count

    @property
    def has_denial_loop(self) -> bool:
        return self.top_group_count >= max(1, self.loop_threshold)

    @property
    def out_of_repo_dominates(self) -> bool:
        if self.total_denials < 3:
            return False
        return self.out_of_repo_denials >= max(2, self.total_denials // 2)

    def snapshot(self) -> dict[str, Any]:
        top = self.top_group
        return {
            "total_denials": self.total_denials,
            "by_reason": dict(self.by_reason),
            "top_group_count": self.top_group_count,
            "top_group": (
                {
                    "tool": top[0],
                    "target": top[1],
                    "reason": top[2],
                    "count": top[3],
                }
                if top
                else None
            ),
            "has_denial_loop": self.has_denial_loop,
            "out_of_repo_denials": self.out_of_repo_denials,
        }
