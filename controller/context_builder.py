"""Assemble controller context from execution engine state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.state import ConversationState, HistoryRole, TurnState

# Caps for intervention / safety-guard snapshots (avoid unbounded history dumps).
TOOL_EVENTS_CAP = 40
INTERVENTION_HISTORY_CAP = 2
ARG_PREVIEW_LIMIT = 500
_LARGE_ARG_KEYS = frozenset(
    {"content", "prompt", "new_string", "old_string", "file_text", "notebook_source"}
)


@dataclass(frozen=True)
class ControllerContext:
    """Backend-neutral snapshot presented to the controller before each decision."""

    objective: str
    conversation_id: str
    conversation_status: str
    session_id: str
    session_state: str
    working_directory: str | None
    turn_count: int
    history: list[dict[str, Any]] = field(default_factory=list)
    recent_events: list[dict[str, Any]] = field(default_factory=list)
    tool_events: list[dict[str, Any]] = field(default_factory=list)
    last_assistant_message: str | None = None
    last_user_message: str | None = None
    active_turn_status: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "conversation_id": self.conversation_id,
            "conversation_status": self.conversation_status,
            "session_id": self.session_id,
            "session_state": self.session_state,
            "working_directory": self.working_directory,
            "turn_count": self.turn_count,
            "history": list(self.history),
            "recent_events": list(self.recent_events),
            "tool_events": list(self.tool_events),
            "last_assistant_message": self.last_assistant_message,
            "last_user_message": self.last_user_message,
            "active_turn_status": self.active_turn_status,
            "metadata": dict(self.metadata),
        }


def _truncate_preview(value: Any, *, limit: int = ARG_PREVIEW_LIMIT) -> Any:
    if isinstance(value, str) and len(value) > limit:
        return value[: limit - 3] + "..."
    if isinstance(value, dict):
        return {
            key: (
                _truncate_preview(val, limit=limit)
                if key in _LARGE_ARG_KEYS or isinstance(val, (str, dict, list))
                else val
            )
            for key, val in value.items()
        }
    if isinstance(value, list):
        # Keep structure but truncate string elements / nested dicts.
        return [_truncate_preview(item, limit=limit) for item in value[:50]]
    return value


def _slim_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    slim = dict(payload)
    args = slim.get("arguments")
    if isinstance(args, dict):
        slim["arguments"] = _truncate_preview(args)
    output = slim.get("output")
    if isinstance(output, str) and len(output) > ARG_PREVIEW_LIMIT:
        slim["output"] = output[: ARG_PREVIEW_LIMIT - 3] + "..."
    return slim


def _all_tool_events_from_state(
    state: ConversationState,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Collect tool_started/tool_completed events from every turn (optionally capped)."""
    events: list[dict[str, Any]] = []
    for turn in state.turns:
        for record in turn.events:
            if record.event_type.value not in ("tool_started", "tool_completed"):
                continue
            events.append(
                {
                    "event_type": record.event_type.value,
                    "payload": _slim_event_payload(dict(record.payload)),
                    "timestamp": record.timestamp.isoformat(),
                    "turn_id": turn.turn_id,
                }
            )
    if limit is not None and limit >= 0:
        return events[-limit:]
    return events


def _recent_events_from_turn(turn: TurnState | None, *, limit: int = 12) -> list[dict[str, Any]]:
    if turn is None:
        return []
    records = turn.events[-limit:]
    return [
        {
            "event_type": record.event_type.value,
            "payload": _slim_event_payload(dict(record.payload)),
            "timestamp": record.timestamp.isoformat(),
        }
        for record in records
    ]


def _last_message(state: ConversationState, role: HistoryRole) -> str | None:
    for entry in reversed(state.history):
        if entry.role == role:
            return entry.content
    return None


def _history_entries(
    state: ConversationState,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    history = [
        {
            "role": entry.role.value,
            "content": entry.content,
            "turn_id": entry.turn_id,
            "timestamp": entry.timestamp.isoformat(),
        }
        for entry in state.history
    ]
    if limit is not None and limit >= 0:
        return history[-limit:]
    return history


def build_context(
    state: ConversationState,
    *,
    objective: str,
    recent_event_limit: int = 12,
    tool_event_limit: int | None = TOOL_EVENTS_CAP,
    history_limit: int | None = None,
    metadata_extra: dict[str, Any] | None = None,
) -> ControllerContext:
    """Gather conversation, session, history, and recent events for controller reasoning."""
    active_turn = state.active_turn
    if active_turn is None and state.turns:
        active_turn = state.turns[-1]

    metadata = dict(state.metadata)
    if metadata_extra:
        metadata.update(metadata_extra)

    return ControllerContext(
        objective=objective,
        conversation_id=state.conversation_id,
        conversation_status=state.status.value,
        session_id=state.session_id,
        session_state=state.harness_session.state.value,
        working_directory=state.harness_session.working_directory,
        turn_count=len(state.turns),
        history=_history_entries(state, limit=history_limit),
        recent_events=_recent_events_from_turn(active_turn, limit=recent_event_limit),
        tool_events=_all_tool_events_from_state(state, limit=tool_event_limit),
        last_assistant_message=_last_message(state, HistoryRole.ASSISTANT),
        last_user_message=_last_message(state, HistoryRole.USER),
        active_turn_status=state.active_turn.status.value if state.active_turn else None,
        metadata=metadata,
    )


def build_intervention_context(
    state: ConversationState,
    *,
    objective: str,
    intervention_id: str,
    prompt: str,
    kind: str,
) -> dict[str, Any]:
    """Context for resolving a harness intervention during an active turn.

    Intentionally lean: last few history entries, capped tool events, truncated
    argument previews — enough for safety/echo detection without dumping the
    full conversation into the intervention snapshot.
    """
    base = build_context(
        state,
        objective=objective,
        recent_event_limit=20,
        tool_event_limit=TOOL_EVENTS_CAP,
        history_limit=INTERVENTION_HISTORY_CAP,
    )
    payload = base.to_dict()
    payload["intervention"] = {
        "intervention_id": intervention_id,
        "prompt": prompt,
        "kind": kind,
    }
    return payload
