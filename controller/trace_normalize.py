"""Serialize harness / Chakra events for dual-channel tracing (Phase 5 / 6)."""

from __future__ import annotations

from typing import Any

from controller.completion import (
    CompletionDetector,
    CompletionMode,
    TerminalEventKind,
)
from engine.state import event_to_record
from interface.events import (
    HarnessEvent,
    TextDeltaEvent,
    ToolCompletedEvent,
    ToolStartedEvent,
    TurnCompletedEvent,
    TurnFailedEvent,
    InterventionRequiredEvent,
)
from verification.parser import parse_verdict

_COMPACT_TEXT_HINTS = (
    "compact_boundary",
    "iscompactsummary",
    "conversation summary",
    "summary of the conversation so far",
    "this session is being continued from a previous",
)


def serialize_harness_event(event: HarnessEvent) -> dict[str, Any]:
    """Faithful JSON-serializable snapshot of a harness event (raw channel)."""
    record = event_to_record(event)
    payload: dict[str, Any] = {
        "event_type": record.event_type.value,
        "payload": dict(record.payload),
        "event_timestamp": record.timestamp.isoformat(),
    }
    context = getattr(event, "context", None)
    if context is not None:
        payload["context"] = {
            "timestamp": context.timestamp.isoformat() if context.timestamp else None,
            "turn_id": context.turn_id,
            "session_id": context.session_id,
            "metadata": dict(context.metadata or {}),
        }
        chakra_raw = (context.metadata or {}).get("chakra_raw")
        if chakra_raw is not None:
            payload["chakra_raw"] = chakra_raw
    return payload


def _looks_like_compact_text(text: str) -> bool:
    lowered = (text or "").lower()
    if not lowered.strip():
        return False
    return any(hint in lowered for hint in _COMPACT_TEXT_HINTS)


def normalize_harness_event(
    event: HarnessEvent,
    *,
    completion_mode: CompletionMode | None = None,
    previous_prompt_tokens: int | None = None,
) -> list[dict[str, Any]]:
    """
    Map one harness event into zero or more normalized orchestration records.

    Completion markers (Phase 6) are emitted only for terminal event kinds.
    """
    out: list[dict[str, Any]] = []
    detector = CompletionDetector(completion_mode) if completion_mode else None

    if isinstance(event, TextDeltaEvent):
        if event.text:
            out.append(
                {
                    "normalized_type": "assistant_text_delta",
                    "text": event.text,
                }
            )
            if _looks_like_compact_text(event.text):
                out.append(
                    {
                        "normalized_type": "context_compacted",
                        "kind": "text_hint",
                        "preview": event.text[:200],
                    }
                )
        return out

    if isinstance(event, ToolStartedEvent):
        kind = "agent_spawn" if event.tool_name == "Agent" else "tool_request"
        record = {
            "normalized_type": kind,
            "tool_name": event.tool_name,
            "arguments": dict(event.arguments),
            "invocation_id": event.invocation_id,
        }
        if event.tool_name == "Agent":
            record["subagent_type"] = event.arguments.get("subagent_type")
        out.append(record)
        return out

    if isinstance(event, ToolCompletedEvent):
        kind = "agent_completed" if event.tool_name == "Agent" else "tool_response"
        record: dict[str, Any] = {
            "normalized_type": kind,
            "tool_name": event.tool_name,
            "invocation_id": event.invocation_id,
            "output": event.output,
            "is_error": event.is_error,
        }
        out.append(record)
        if event.output:
            verdict = parse_verdict(event.output)
            if verdict is not None:
                out.append(
                    {
                        "normalized_type": "verification_result",
                        "verdict": verdict.value,
                        "source_tool": event.tool_name,
                        "invocation_id": event.invocation_id,
                    }
                )
            if detector is not None:
                hit = detector.inspect(
                    event.output,
                    event_kind=TerminalEventKind.TOOL_COMPLETED,
                    source=f"tool_completed:{event.tool_name}",
                )
                if hit is not None:
                    out.append({"normalized_type": "completion_marker", **hit.to_dict()})
            if _looks_like_compact_text(event.output):
                out.append(
                    {
                        "normalized_type": "context_compacted",
                        "kind": "tool_output_hint",
                        "tool_name": event.tool_name,
                        "preview": event.output[:200],
                    }
                )
        return out

    if isinstance(event, InterventionRequiredEvent):
        out.append(
            {
                "normalized_type": "intervention_required",
                "intervention_id": event.intervention_id,
                "prompt": event.prompt,
                "kind": event.kind.value,
            }
        )
        return out

    if isinstance(event, TurnCompletedEvent):
        usage = dict(event.usage or {})
        prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        completion_tokens = int(
            usage.get("completion_tokens") or usage.get("output_tokens") or 0
        )
        out.append(
            {
                "normalized_type": "assistant_message",
                "text": event.final_text,
                "usage": usage,
            }
        )
        out.append(
            {
                "normalized_type": "token_usage",
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
            }
        )
        if (
            previous_prompt_tokens is not None
            and previous_prompt_tokens > 0
            and prompt_tokens > 0
            and prompt_tokens < int(previous_prompt_tokens * 0.7)
        ):
            out.append(
                {
                    "normalized_type": "context_compacted",
                    "kind": "token_drop",
                    "prompt_tokens_before": previous_prompt_tokens,
                    "prompt_tokens_after": prompt_tokens,
                }
            )
        if event.final_text and _looks_like_compact_text(event.final_text):
            out.append(
                {
                    "normalized_type": "context_compacted",
                    "kind": "text_hint",
                    "preview": event.final_text[:200],
                }
            )
        if event.final_text and detector is not None:
            hit = detector.inspect(
                event.final_text,
                event_kind=TerminalEventKind.TURN_COMPLETED,
                source="turn_completed",
            )
            if hit is not None:
                out.append({"normalized_type": "completion_marker", **hit.to_dict()})
        return out

    if isinstance(event, TurnFailedEvent):
        out.append(
            {
                "normalized_type": "error",
                "message": event.message,
                "code": event.code,
            }
        )
        return out

    return out
