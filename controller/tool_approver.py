"""Stateless automatic tool approval (Phase 4).

Transparent supervisor: approve tool requests without workflow/stage logic
and without blocking on an LLM. Safety boundaries (repo confinement,
destructive patterns) may still deny a request; everything else is approved
immediately so the conversation stream continues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from controller.intervention_guard import (
    evaluate_intervention_guard,
    extract_pending_tool,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ToolApproval:
    """One automatic intervention resolution with traceable metadata."""

    intervention_id: str
    prompt: str
    kind: str
    response: str
    reasoning: str
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    approved: bool = True
    source: str = "stateless_auto_approver"
    timestamp: str = field(default_factory=_utc_now_iso)

    def to_trace_dict(self) -> dict[str, Any]:
        return {
            "intervention_id": self.intervention_id,
            "prompt": self.prompt,
            "kind": self.kind,
            "tool_name": self.tool_name,
            "arguments": dict(self.arguments),
            "response": self.response,
            "reasoning": self.reasoning,
            "approved": self.approved,
            "source": self.source,
            "timestamp": self.timestamp,
        }


class StatelessAutoApprover:
    """
    Approve harness interventions without stage- or workflow-dependent policy.

    - Never calls an LLM (does not block the stream).
    - Never inspects planning / implementation / verification / repair stage.
    - Never uses the user objective to choose yes/no.
    - Uses deterministic safety checks only; if those are silent, approves.
    """

    SOURCE = "stateless_auto_approver"

    def approve(
        self,
        *,
        intervention_id: str,
        prompt: str,
        kind: str,
        working_directory: str | None,
        recent_events: list[dict[str, Any]],
        tool_events: list[dict[str, Any]] | None = None,
    ) -> ToolApproval:
        pending = extract_pending_tool(recent_events)
        tool_name = pending[0] if pending else ""
        arguments = dict(pending[1]) if pending else {}

        # Safety-only context — intentionally omits objective and workflow stage.
        safety_context: dict[str, Any] = {
            "working_directory": working_directory,
            "recent_events": recent_events,
            "tool_events": tool_events or [],
        }
        guard = evaluate_intervention_guard(safety_context)
        if guard is not None:
            approved = not guard.response.strip().lower().startswith("no")
            return ToolApproval(
                intervention_id=intervention_id,
                prompt=prompt,
                kind=kind,
                response=guard.response,
                reasoning=guard.reasoning,
                tool_name=tool_name,
                arguments=arguments,
                approved=approved,
                source=f"{self.SOURCE}+safety_guard",
            )

        # No safety denial — approve immediately (never defer to LLM / stage policy).
        if kind == "request_information" and not tool_name:
            return ToolApproval(
                intervention_id=intervention_id,
                prompt=prompt,
                kind=kind,
                response="continue",
                reasoning="stateless auto-reply for information request; no workflow decision",
                tool_name=tool_name,
                arguments=arguments,
                approved=True,
                source=self.SOURCE,
            )

        return ToolApproval(
            intervention_id=intervention_id,
            prompt=prompt,
            kind=kind,
            response="yes",
            reasoning="stateless auto-approve; independent of workflow stage",
            tool_name=tool_name,
            arguments=arguments,
            approved=True,
            source=self.SOURCE,
        )
