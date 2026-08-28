"""Execution engine — backend-independent conversation execution framework."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from engine.dispatcher import EventDispatcher
from engine.exceptions import (
    ConversationNotFoundError,
    ConversationStateError,
    InterventionRequiredError,
)
from engine.state import (
    ConversationState,
    ConversationStatus,
    HistoryEntry,
    HistoryRole,
    TurnState,
    TurnStatus,
    new_conversation_id,
    new_turn_id,
)
from engine.types import (
    EngineNotification,
    EngineNotificationKind,
    EngineObserver,
    InterventionHandler,
)
from interface.events import InterventionRequiredEvent, TurnFailedEvent
from interface.harness import Harness, TurnStream
from interface.models.requests import (
    CreateSessionRequest,
    InterruptRequest,
    InterventionResponse,
    SendMessageRequest,
)
from interface.models.responses import SessionCloseResult, TurnResult

logger = logging.getLogger(__name__)


@dataclass
class StartConversationRequest:
    """Parameters for starting a new conversation."""

    working_directory: str | None = None
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    conversation_id: str | None = None


class ExecutionEngine:
    """
    Backend-independent execution framework over the harness interface.

    Coordinates harness operations and maintains conversation state.
    Decision-making is supplied externally via handlers — the controller
    drives this engine in Phase 6.
    """

    def __init__(
        self,
        harness: Harness,
        *,
        observer: EngineObserver | None = None,
    ) -> None:
        self._harness = harness
        self._dispatcher = EventDispatcher()
        self._observer = observer
        self._conversations: dict[str, ConversationState] = {}
        self._active_streams: dict[str, TurnStream] = {}

    @property
    def harness(self) -> Harness:
        return self._harness

    def set_observer(self, observer: EngineObserver | None) -> EngineObserver | None:
        """Replace the engine observer; returns the previous observer."""
        previous = self._observer
        self._observer = observer
        return previous

    def start_conversation(
        self, request: StartConversationRequest | None = None
    ) -> ConversationState:
        req = request or StartConversationRequest()
        session = self._harness.create_session(
            CreateSessionRequest(
                working_directory=req.working_directory,
                model=req.model,
                metadata=dict(req.metadata),
            )
        )
        conversation_id = req.conversation_id or new_conversation_id()
        state = ConversationState(
            conversation_id=conversation_id,
            harness_session=session,
            status=ConversationStatus.ACTIVE,
            metadata=dict(req.metadata),
        )
        self._conversations[conversation_id] = state
        self._notify(
            EngineNotificationKind.CONVERSATION_STARTED,
            state,
            detail={"session_id": session.session_id},
        )
        logger.info("Started conversation %s (session %s)", conversation_id, session.session_id)
        return state

    def get_conversation(self, conversation_id: str) -> ConversationState:
        try:
            return self._conversations[conversation_id]
        except KeyError as exc:
            raise ConversationNotFoundError(conversation_id) from exc

    def execute_turn(
        self,
        conversation_id: str,
        message: str,
        *,
        intervention_handler: InterventionHandler | None = None,
        model: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> TurnResult:
        """
        Execute one user turn using externally supplied intervention decisions.

        The optional ``intervention_handler`` is called when the harness requests
        operator input. If omitted, ``InterventionRequiredError`` is raised.
        """
        state = self.get_conversation(conversation_id)
        self._ensure_can_start_turn(state)

        turn = TurnState(turn_id=new_turn_id(), user_message=message)
        state.active_turn = turn
        state.turns.append(turn)
        state.status = ConversationStatus.TURN_IN_PROGRESS
        state.history.append(
            HistoryEntry(role=HistoryRole.USER, content=message, turn_id=turn.turn_id)
        )
        state.touch()
        self._notify(
            EngineNotificationKind.TURN_STARTED,
            state,
            detail={"turn_id": turn.turn_id, "message": message},
        )

        stream = self._harness.send_turn(
            state.harness_session,
            SendMessageRequest(message=message, model=model, options=dict(options or {})),
        )
        self._active_streams[conversation_id] = stream

        try:
            self._process_stream(state, stream, intervention_handler)
            result = stream.result()
            turn.result = result
            return result
        except InterventionRequiredError:
            self._abort_active_turn(state)
            raise
        finally:
            self._active_streams.pop(conversation_id, None)

    def cancel_active_turn(
        self,
        conversation_id: str,
        *,
        reason: str = "engine_cancel",
    ) -> None:
        state = self.get_conversation(conversation_id)
        if state.active_turn is None:
            raise ConversationStateError("No active turn to cancel")
        stream = self._active_streams.get(conversation_id)
        if stream is not None:
            stream.cancel(InterruptRequest(reason=reason))
        state.active_turn.status = TurnStatus.CANCELLED
        state.active_turn.ended_at = state.updated_at
        state.active_turn = None
        state.status = ConversationStatus.ACTIVE
        state.touch()
        logger.info("Cancelled turn on conversation %s (%s)", conversation_id, reason)

    def close_conversation(self, conversation_id: str) -> SessionCloseResult:
        state = self.get_conversation(conversation_id)
        if state.active_turn is not None:
            raise ConversationStateError("Cannot close conversation during active turn")
        result = self._harness.close_session(state.harness_session)
        state.status = ConversationStatus.CLOSED
        state.touch()
        self._notify(
            EngineNotificationKind.CONVERSATION_CLOSED,
            state,
            detail={"turn_count": result.turn_count},
        )
        del self._conversations[conversation_id]
        logger.info("Closed conversation %s", conversation_id)
        return result

    def reconstruct(self, conversation_id: str) -> dict[str, Any]:
        """Return a full serializable snapshot for validation and controller context."""
        state = self.get_conversation(conversation_id)
        return state.snapshot()

    def _process_stream(
        self,
        state: ConversationState,
        stream: TurnStream,
        intervention_handler: InterventionHandler | None,
    ) -> None:
        turn = state.active_turn
        assert turn is not None

        for event in stream:
            result = self._dispatcher.dispatch(state, event)
            self._notify(
                EngineNotificationKind.EVENT_RECEIVED,
                state,
                event=event,
                detail={"turn_id": turn.turn_id},
            )

            if result.requires_intervention:
                assert isinstance(event, InterventionRequiredEvent)
                self._notify(
                    EngineNotificationKind.INTERVENTION_REQUIRED,
                    state,
                    event=event,
                    detail={"intervention_id": event.intervention_id},
                )
                response = self._resolve_intervention(
                    event, state, intervention_handler
                )
                stream.respond(response)
                self._dispatcher.mark_intervention_resolved(state)
                self._notify(
                    EngineNotificationKind.INTERVENTION_RESOLVED,
                    state,
                    event=event,
                    detail={"response": response.response},
                )

            if result.is_terminal:
                if isinstance(event, TurnFailedEvent):
                    self._notify(
                        EngineNotificationKind.TURN_FAILED,
                        state,
                        event=event,
                        detail={"code": event.code, "message": event.message},
                    )
                    raise ConversationStateError(f"{event.code}: {event.message}")
                self._notify(
                    EngineNotificationKind.TURN_COMPLETED,
                    state,
                    event=event,
                    detail={"turn_id": turn.turn_id},
                )
                return

    def _resolve_intervention(
        self,
        event: InterventionRequiredEvent,
        state: ConversationState,
        handler: InterventionHandler | None,
    ) -> InterventionResponse:
        if handler is None:
            raise InterventionRequiredError(event.intervention_id, event.prompt)
        outcome = handler(event, state)
        if isinstance(outcome, InterventionResponse):
            return outcome
        return InterventionResponse(
            intervention_id=event.intervention_id,
            response=str(outcome),
        )

    def _abort_active_turn(self, state: ConversationState) -> None:
        if state.active_turn is None:
            return
        state.active_turn.status = TurnStatus.FAILED
        state.active_turn.ended_at = state.updated_at
        state.active_turn = None
        if state.status in (
            ConversationStatus.TURN_IN_PROGRESS,
            ConversationStatus.AWAITING_INTERVENTION,
        ):
            state.status = ConversationStatus.ACTIVE
        state.touch()

    def _ensure_can_start_turn(self, state: ConversationState) -> None:
        if state.status == ConversationStatus.CLOSED:
            raise ConversationStateError("Conversation is closed")
        if state.status == ConversationStatus.FAILED:
            raise ConversationStateError("Conversation is in failed state")
        if state.active_turn is not None:
            raise ConversationStateError("A turn is already in progress")

    def _notify(
        self,
        kind: EngineNotificationKind,
        state: ConversationState,
        *,
        event=None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        if self._observer is None:
            return
        self._observer(
            EngineNotification(
                kind=kind,
                conversation_id=state.conversation_id,
                state=state,
                event=event,
                detail=dict(detail or {}),
            )
        )
