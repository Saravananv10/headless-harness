"""Conversation and turn state models."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from interface.events import (
    HarnessEvent,
    HarnessEventType,
    InterventionRequiredEvent,
    TextDeltaEvent,
    ToolCompletedEvent,
    ToolStartedEvent,
    TurnCompletedEvent,
    TurnFailedEvent,
)
from interface.models.responses import TurnResult
from interface.models.session import HarnessSession, SessionState


class ConversationStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    TURN_IN_PROGRESS = "turn_in_progress"
    AWAITING_INTERVENTION = "awaiting_intervention"
    FAILED = "failed"
    CLOSED = "closed"


class TurnStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    AWAITING_INTERVENTION = "awaiting_intervention"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HistoryRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class HistoryEntry:
    role: HistoryRole
    content: str
    turn_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class EventRecord:
    event_type: HarnessEventType
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TurnState:
    turn_id: str
    user_message: str
    status: TurnStatus = TurnStatus.IN_PROGRESS
    streamed_text: str = ""
    events: list[EventRecord] = field(default_factory=list)
    pending_intervention: InterventionRequiredEvent | None = None
    result: TurnResult | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None

    def append_event_record(self, record: EventRecord) -> None:
        self.events.append(record)


@dataclass
class ConversationState:
    """Complete mutable state for one conversation."""

    conversation_id: str
    harness_session: HarnessSession
    status: ConversationStatus = ConversationStatus.CREATED
    history: list[HistoryEntry] = field(default_factory=list)
    turns: list[TurnState] = field(default_factory=list)
    active_turn: TurnState | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def session_id(self) -> str:
        return self.harness_session.session_id

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def snapshot(self) -> dict[str, Any]:
        """Return a serializable snapshot for reconstruction validation."""
        return {
            "conversation_id": self.conversation_id,
            "status": self.status.value,
            "session_id": self.session_id,
            "session_state": self.harness_session.state.value,
            "session_turn_count": self.harness_session.turn_count,
            "working_directory": self.harness_session.working_directory,
            "metadata": dict(self.metadata),
            "history": [
                {
                    "role": entry.role.value,
                    "content": entry.content,
                    "turn_id": entry.turn_id,
                    "timestamp": entry.timestamp.isoformat(),
                }
                for entry in self.history
            ],
            "turns": [
                {
                    "turn_id": turn.turn_id,
                    "user_message": turn.user_message,
                    "status": turn.status.value,
                    "streamed_text": turn.streamed_text,
                    "events": [
                        {
                            "event_type": record.event_type.value,
                            "payload": dict(record.payload),
                            "timestamp": record.timestamp.isoformat(),
                        }
                        for record in turn.events
                    ],
                    "pending_intervention_id": (
                        turn.pending_intervention.intervention_id
                        if turn.pending_intervention
                        else None
                    ),
                    "result": (
                        {
                            "final_text": turn.result.final_text,
                            "prompt_tokens": turn.result.usage.prompt_tokens,
                            "completion_tokens": turn.result.usage.completion_tokens,
                            "turn_id": turn.result.turn_id,
                            "session_id": turn.result.session_id,
                            "event_count": turn.result.event_count,
                        }
                        if turn.result
                        else None
                    ),
                    "started_at": turn.started_at.isoformat(),
                    "ended_at": turn.ended_at.isoformat() if turn.ended_at else None,
                }
                for turn in self.turns
            ],
            "active_turn_id": self.active_turn.turn_id if self.active_turn else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_snapshot(
        cls,
        data: dict[str, Any],
        harness_session: HarnessSession,
    ) -> ConversationState:
        """Rebuild conversation state from a snapshot dictionary."""
        state = cls(
            conversation_id=data["conversation_id"],
            harness_session=harness_session,
            status=ConversationStatus(data["status"]),
            metadata=dict(data.get("metadata", {})),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )
        for entry in data.get("history", []):
            state.history.append(
                HistoryEntry(
                    role=HistoryRole(entry["role"]),
                    content=entry["content"],
                    turn_id=entry.get("turn_id"),
                    timestamp=datetime.fromisoformat(entry["timestamp"]),
                )
            )
        turn_by_id: dict[str, TurnState] = {}
        for turn_data in data.get("turns", []):
            turn = TurnState(
                turn_id=turn_data["turn_id"],
                user_message=turn_data["user_message"],
                status=TurnStatus(turn_data["status"]),
                streamed_text=turn_data.get("streamed_text", ""),
                started_at=datetime.fromisoformat(turn_data["started_at"]),
                ended_at=(
                    datetime.fromisoformat(turn_data["ended_at"])
                    if turn_data.get("ended_at")
                    else None
                ),
            )
            for record_data in turn_data.get("events", []):
                turn.events.append(
                    EventRecord(
                        event_type=HarnessEventType(record_data["event_type"]),
                        payload=dict(record_data.get("payload", {})),
                        timestamp=datetime.fromisoformat(record_data["timestamp"]),
                    )
                )
            if turn_data.get("result"):
                from interface.models.responses import UsageStats

                r = turn_data["result"]
                turn.result = TurnResult(
                    final_text=r["final_text"],
                    usage=UsageStats(
                        prompt_tokens=r.get("prompt_tokens", 0),
                        completion_tokens=r.get("completion_tokens", 0),
                    ),
                    turn_id=r.get("turn_id"),
                    session_id=r.get("session_id"),
                    event_count=r.get("event_count", 0),
                )
            turn_by_id[turn.turn_id] = turn
            state.turns.append(turn)
        active_id = data.get("active_turn_id")
        if active_id:
            state.active_turn = turn_by_id.get(active_id)
        return state


def new_conversation_id() -> str:
    return str(uuid.uuid4())


def new_turn_id() -> str:
    return str(uuid.uuid4())


def event_to_record(event: HarnessEvent) -> EventRecord:
    """Convert a harness event into a storable EventRecord."""
    payload: dict[str, Any] = {}
    if isinstance(event, TextDeltaEvent):
        payload["text"] = event.text
    elif isinstance(event, ToolStartedEvent):
        payload.update(
            {
                "tool_name": event.tool_name,
                "arguments": dict(event.arguments),
                "invocation_id": event.invocation_id,
            }
        )
    elif isinstance(event, ToolCompletedEvent):
        payload.update(
            {
                "tool_name": event.tool_name,
                "invocation_id": event.invocation_id,
                "output": event.output,
                "is_error": event.is_error,
            }
        )
    elif isinstance(event, InterventionRequiredEvent):
        payload.update(
            {
                "intervention_id": event.intervention_id,
                "prompt": event.prompt,
                "kind": event.kind.value,
            }
        )
    elif isinstance(event, TurnCompletedEvent):
        payload.update(
            {"final_text": event.final_text, "usage": dict(event.usage)}
        )
    elif isinstance(event, TurnFailedEvent):
        payload.update({"message": event.message, "code": event.code})
    return EventRecord(event_type=event.type, payload=payload)


def apply_session_snapshot(harness_session: HarnessSession, data: dict[str, Any]) -> None:
    harness_session.working_directory = data.get("working_directory")
    harness_session.turn_count = int(data.get("session_turn_count", 0))
    harness_session.state = SessionState(data.get("session_state", SessionState.ACTIVE.value))
    harness_session.metadata.update(data.get("metadata", {}))
