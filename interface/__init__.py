"""Backend-independent harness contract (Phase 3)."""

from interface.capabilities import HarnessCapabilities, HarnessCapability
from interface.events import (
    EventContext,
    HarnessEvent,
    HarnessEventType,
    InterventionKind,
    InterventionRequiredEvent,
    TextDeltaEvent,
    ToolCompletedEvent,
    ToolStartedEvent,
    TurnCompletedEvent,
    TurnFailedEvent,
    event_type_of,
    is_terminal_event,
)
from interface.exceptions import (
    HarnessConnectionError,
    HarnessError,
    HarnessNotConnectedError,
    HarnessSessionError,
    HarnessTurnError,
    HarnessUnsupportedError,
)
from interface.harness import Harness, TurnStream
from interface.models.requests import (
    ConnectionConfig,
    CreateSessionRequest,
    InterruptRequest,
    InterventionResponse,
    ResumeSessionRequest,
    SendMessageRequest,
)
from interface.models.responses import (
    ConnectionInfo,
    SessionCloseResult,
    SessionStatus,
    TurnResult,
    UsageStats,
)
from interface.models.session import HarnessSession, SessionState

__all__ = [
    "ConnectionConfig",
    "ConnectionInfo",
    "CreateSessionRequest",
    "Harness",
    "HarnessCapabilities",
    "HarnessCapability",
    "HarnessConnectionError",
    "HarnessError",
    "EventContext",
    "HarnessEvent",
    "HarnessEventType",
    "event_type_of",
    "is_terminal_event",
    "HarnessNotConnectedError",
    "HarnessSession",
    "HarnessSessionError",
    "HarnessTurnError",
    "HarnessUnsupportedError",
    "InterruptRequest",
    "InterventionKind",
    "InterventionRequiredEvent",
    "InterventionResponse",
    "ResumeSessionRequest",
    "SendMessageRequest",
    "SessionCloseResult",
    "SessionState",
    "SessionStatus",
    "TextDeltaEvent",
    "ToolCompletedEvent",
    "ToolStartedEvent",
    "TurnCompletedEvent",
    "TurnFailedEvent",
    "TurnResult",
    "TurnStream",
    "UsageStats",
]
