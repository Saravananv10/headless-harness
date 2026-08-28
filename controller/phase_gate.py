"""Lifecycle phase gate for tool approval (enforce Plan → Implement → Verify)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from controller.lifecycle import (
    LifecycleObserver,
    is_verification_subagent,
    normalize_subagent_type,
)
from controller.workflow_common import IMPLEMENTATION_COMPLETE_MARKER


@dataclass(frozen=True)
class PhaseGateResult:
    deny: bool
    response: str
    reasoning: str


def evaluate_phase_gate(
    *,
    tool_name: str,
    arguments: dict[str, Any] | None,
    lifecycle: LifecycleObserver | None,
) -> PhaseGateResult | None:
    """
    Return a denial when Agent spawn violates phase order; else None.

    Blocks verification/verify before IMPLEMENTATION_STATUS: COMPLETE.
    """
    if (tool_name or "").strip() != "Agent":
        return None
    if lifecycle is None:
        return None
    args = dict(arguments or {})
    sub = normalize_subagent_type(
        str(
            args.get("subagent_type")
            or args.get("agentType")
            or args.get("agent_type")
            or ""
        )
    )
    if not is_verification_subagent(sub):
        return None
    if (
        lifecycle.implementation_complete_seen
        or any(
            e.get("kind") in ("informal_status_marker", "implementation_complete")
            and (e.get("has_implementation", True))
            for e in lifecycle.events
        )
    ):
        return None
    return PhaseGateResult(
        deny=True,
        response="no",
        reasoning=(
            "deny Agent verification: IMPLEMENTATION_STATUS: COMPLETE required first; "
            f"spawn general-purpose, implement, emit {IMPLEMENTATION_COMPLETE_MARKER} "
            "before verification"
        ),
    )
