"""Map Chakra backend events to common harness events."""

from __future__ import annotations

import json
import logging
from typing import Any

from client.chakra_client import EventType, ServerEvent

from interface.events import (
    EventContext,
    HarnessEvent,
    InterventionKind,
    InterventionRequiredEvent,
    TextDeltaEvent,
    ToolCompletedEvent,
    ToolStartedEvent,
    TurnCompletedEvent,
    TurnFailedEvent,
)

logger = logging.getLogger(__name__)

_INTERVENTION_KIND_MAP = {
    "CONFIRM_COMMAND": InterventionKind.CONFIRM_ACTION,
    "REQUEST_INFORMATION": InterventionKind.REQUEST_INFORMATION,
}


def serialize_server_event(event: ServerEvent) -> dict[str, Any]:
    """JSON-safe snapshot of a Chakra ServerEvent (excludes protobuf ``raw``)."""
    payload = {
        "type": event.type.value if hasattr(event.type, "value") else str(event.type),
        "text": event.text,
        "tool_name": event.tool_name,
        "arguments_json": event.arguments_json,
        "tool_use_id": event.tool_use_id,
        "output": event.output,
        "is_error": event.is_error,
        "prompt_id": event.prompt_id,
        "question": event.question,
        "action_type": event.action_type,
        "full_text": event.full_text,
        "prompt_tokens": event.prompt_tokens,
        "completion_tokens": event.completion_tokens,
        "error_message": event.error_message,
        "error_code": event.error_code,
    }
    return {key: value for key, value in payload.items() if value is not None}


def _context(
    *,
    session_id: str | None,
    turn_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> EventContext:
    return EventContext(
        session_id=session_id,
        turn_id=turn_id,
        metadata=dict(metadata or {}),
    )


def _parse_tool_arguments(arguments_json: str | None) -> dict[str, Any]:
    if not arguments_json:
        return {}
    try:
        parsed = json.loads(arguments_json)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        logger.debug("Failed to parse tool arguments JSON")
    return {"raw": arguments_json}


def translate_server_event(
    event: ServerEvent,
    *,
    session_id: str | None = None,
    turn_id: str | None = None,
) -> HarnessEvent | None:
    """Translate a Chakra ServerEvent into a harness event."""
    ctx = _context(
        session_id=session_id,
        turn_id=turn_id,
        metadata={"chakra_raw": serialize_server_event(event)},
    )

    if event.type == EventType.TEXT_CHUNK:
        return TextDeltaEvent(text=event.text or "", context=ctx)

    if event.type == EventType.TOOL_START:
        return ToolStartedEvent(
            tool_name=event.tool_name or "",
            arguments=_parse_tool_arguments(event.arguments_json),
            invocation_id=event.tool_use_id or "",
            context=ctx,
        )

    if event.type == EventType.TOOL_RESULT:
        return ToolCompletedEvent(
            tool_name=event.tool_name or "",
            invocation_id=event.tool_use_id or "",
            output=event.output or "",
            is_error=bool(event.is_error),
            context=ctx,
        )

    if event.type == EventType.ACTION_REQUIRED:
        kind = _INTERVENTION_KIND_MAP.get(
            event.action_type or "",
            InterventionKind.UNKNOWN,
        )
        return InterventionRequiredEvent(
            intervention_id=event.prompt_id or "",
            prompt=event.question or "",
            kind=kind,
            context=ctx,
        )

    if event.type == EventType.DONE:
        return TurnCompletedEvent(
            final_text=event.full_text or "",
            usage={
                "prompt_tokens": event.prompt_tokens or 0,
                "completion_tokens": event.completion_tokens or 0,
            },
            context=ctx,
        )

    if event.type == EventType.ERROR:
        return TurnFailedEvent(
            message=event.error_message or "Unknown backend error",
            code=event.error_code or "UNKNOWN",
            context=ctx,
        )

    if event.type == EventType.STREAM_END:
        return None

    logger.warning("Unhandled Chakra event type: %s", event.type)
    return None
