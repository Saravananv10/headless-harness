"""Universal event model for harness streaming."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Union


class HarnessEventType(str, Enum):
    TEXT_DELTA = "text_delta"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    INTERVENTION_REQUIRED = "intervention_required"
    TURN_COMPLETED = "turn_completed"
    TURN_FAILED = "turn_failed"


class InterventionKind(str, Enum):
    """Categories of operator intervention requested by the harness."""

    CONFIRM_ACTION = "confirm_action"
    REQUEST_INFORMATION = "request_information"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EventContext:
    """Shared metadata attached to harness events."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    turn_id: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TextDeltaEvent:
    type: HarnessEventType = HarnessEventType.TEXT_DELTA
    text: str = ""
    context: EventContext = field(default_factory=EventContext)


@dataclass(frozen=True)
class ToolStartedEvent:
    type: HarnessEventType = HarnessEventType.TOOL_STARTED
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    invocation_id: str = ""
    context: EventContext = field(default_factory=EventContext)


@dataclass(frozen=True)
class ToolCompletedEvent:
    type: HarnessEventType = HarnessEventType.TOOL_COMPLETED
    tool_name: str = ""
    invocation_id: str = ""
    output: str = ""
    is_error: bool = False
    context: EventContext = field(default_factory=EventContext)


@dataclass(frozen=True)
class InterventionRequiredEvent:
    type: HarnessEventType = HarnessEventType.INTERVENTION_REQUIRED
    intervention_id: str = ""
    prompt: str = ""
    kind: InterventionKind = InterventionKind.UNKNOWN
    context: EventContext = field(default_factory=EventContext)


@dataclass(frozen=True)
class TurnCompletedEvent:
    type: HarnessEventType = HarnessEventType.TURN_COMPLETED
    final_text: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    context: EventContext = field(default_factory=EventContext)


@dataclass(frozen=True)
class TurnFailedEvent:
    type: HarnessEventType = HarnessEventType.TURN_FAILED
    message: str = ""
    code: str = ""
    context: EventContext = field(default_factory=EventContext)


HarnessEvent = Union[
    TextDeltaEvent,
    ToolStartedEvent,
    ToolCompletedEvent,
    InterventionRequiredEvent,
    TurnCompletedEvent,
    TurnFailedEvent,
]

TERMINAL_EVENT_TYPES = frozenset(
    {HarnessEventType.TURN_COMPLETED, HarnessEventType.TURN_FAILED}
)


def event_type_of(event: HarnessEvent) -> HarnessEventType:
    return event.type


def is_terminal_event(event: HarnessEvent) -> bool:
    return event_type_of(event) in TERMINAL_EVENT_TYPES
