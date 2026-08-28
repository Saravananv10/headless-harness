"""Backend-independent execution engine (Phase 5)."""

from engine.execution_engine import ExecutionEngine, StartConversationRequest
from engine.dispatcher import DispatchResult, EventDispatcher
from engine.exceptions import (
    ExecutionEngineError,
    ConversationNotFoundError,
    ConversationStateError,
    InterventionRequiredError,
)
from engine.state import (
    ConversationState,
    ConversationStatus,
    EventRecord,
    HistoryEntry,
    HistoryRole,
    TurnState,
    TurnStatus,
    apply_session_snapshot,
    event_to_record,
    new_conversation_id,
    new_turn_id,
)
from engine.types import (
    EngineNotification,
    EngineNotificationKind,
    EngineObserver,
    InterventionHandler,
)

__all__ = [
    "ExecutionEngine",
    "ExecutionEngineError",
    "ConversationNotFoundError",
    "ConversationState",
    "ConversationStateError",
    "ConversationStatus",
    "DispatchResult",
    "EngineNotification",
    "EngineNotificationKind",
    "EngineObserver",
    "EventDispatcher",
    "EventRecord",
    "HistoryEntry",
    "HistoryRole",
    "InterventionHandler",
    "InterventionRequiredError",
    "StartConversationRequest",
    "TurnState",
    "TurnStatus",
    "apply_session_snapshot",
    "event_to_record",
    "new_conversation_id",
    "new_turn_id",
]
