"""Shared types for controller integration (Phase 6)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from interface.events import HarnessEvent, InterventionRequiredEvent
from interface.models.requests import InterventionResponse

from engine.state import ConversationState


class EngineNotificationKind(str, Enum):
    """Notifications emitted to observers during execution."""

    CONVERSATION_STARTED = "conversation_started"
    TURN_STARTED = "turn_started"
    EVENT_RECEIVED = "event_received"
    INTERVENTION_REQUIRED = "intervention_required"
    INTERVENTION_RESOLVED = "intervention_resolved"
    TURN_COMPLETED = "turn_completed"
    TURN_FAILED = "turn_failed"
    CONVERSATION_CLOSED = "conversation_closed"


@dataclass(frozen=True)
class EngineNotification:
    """Observer payload for engine lifecycle events."""

    kind: EngineNotificationKind
    conversation_id: str
    state: ConversationState
    event: HarnessEvent | None = None
    detail: dict[str, Any] = field(default_factory=dict)


InterventionHandler = Callable[
    [InterventionRequiredEvent, ConversationState],
    str | InterventionResponse,
]

EngineObserver = Callable[[EngineNotification], None]
