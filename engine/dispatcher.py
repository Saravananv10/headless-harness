"""Event dispatcher — routes harness events into conversation state."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from interface.events import (
    HarnessEvent,
    HarnessEventType,
    InterventionRequiredEvent,
    TextDeltaEvent,
    TurnCompletedEvent,
    TurnFailedEvent,
    is_terminal_event,
)

from engine.state import (
    ConversationState,
    ConversationStatus,
    EventRecord,
    HistoryEntry,
    HistoryRole,
    TurnState,
    TurnStatus,
    event_to_record,
)

logger = logging.getLogger(__name__)


@dataclass
class DispatchResult:
    """Outcome of dispatching one harness event."""

    event: HarnessEvent
    record: EventRecord
    is_terminal: bool
    requires_intervention: bool = False


class EventDispatcher:
    """Consumes harness events and updates conversation state."""

    def dispatch(self, state: ConversationState, event: HarnessEvent) -> DispatchResult:
        turn = state.active_turn
        if turn is None:
            raise RuntimeError("Cannot dispatch event without an active turn")

        record = event_to_record(event)
        turn.append_event_record(record)
        state.touch()

        if isinstance(event, TextDeltaEvent) and event.text:
            turn.streamed_text += event.text

        if isinstance(event, InterventionRequiredEvent):
            turn.status = TurnStatus.AWAITING_INTERVENTION
            turn.pending_intervention = event
            state.status = ConversationStatus.AWAITING_INTERVENTION
            logger.debug("Intervention required: %s", event.prompt)
            return DispatchResult(
                event=event,
                record=record,
                is_terminal=False,
                requires_intervention=True,
            )

        if isinstance(event, TurnCompletedEvent):
            self._complete_turn(state, turn, event.final_text or turn.streamed_text)
            return DispatchResult(event=event, record=record, is_terminal=True)

        if isinstance(event, TurnFailedEvent):
            self._fail_turn(state, turn, event.message, event.code)
            return DispatchResult(event=event, record=record, is_terminal=True)

        if is_terminal_event(event):
            return DispatchResult(event=event, record=record, is_terminal=True)

        # Non-terminal progress events (tool started/completed, etc.)
        if state.status == ConversationStatus.TURN_IN_PROGRESS:
            pass
        return DispatchResult(event=event, record=record, is_terminal=False)

    def mark_intervention_resolved(self, state: ConversationState) -> None:
        turn = state.active_turn
        if turn is None:
            return
        turn.pending_intervention = None
        if turn.status == TurnStatus.AWAITING_INTERVENTION:
            turn.status = TurnStatus.IN_PROGRESS
        if state.status == ConversationStatus.AWAITING_INTERVENTION:
            state.status = ConversationStatus.TURN_IN_PROGRESS
        state.touch()

    def _complete_turn(
        self,
        state: ConversationState,
        turn: TurnState,
        final_text: str,
    ) -> None:
        turn.status = TurnStatus.COMPLETED
        turn.ended_at = state.updated_at
        state.status = ConversationStatus.ACTIVE
        state.active_turn = None
        state.history.append(
            HistoryEntry(
                role=HistoryRole.ASSISTANT,
                content=final_text,
                turn_id=turn.turn_id,
            )
        )
        logger.debug("Turn %s completed (%d chars)", turn.turn_id, len(final_text))

    def _fail_turn(
        self,
        state: ConversationState,
        turn: TurnState,
        message: str,
        code: str,
    ) -> None:
        turn.status = TurnStatus.FAILED
        turn.ended_at = state.updated_at
        state.status = ConversationStatus.FAILED
        state.active_turn = None
        state.history.append(
            HistoryEntry(
                role=HistoryRole.SYSTEM,
                content=f"Turn failed [{code}]: {message}",
                turn_id=turn.turn_id,
            )
        )
        logger.error("Turn %s failed: %s", turn.turn_id, message)

    def event_count_for_type(self, state: ConversationState, event_type: HarnessEventType) -> int:
        if state.active_turn:
            turns = [state.active_turn]
        else:
            turns = state.turns
        count = 0
        for turn in turns:
            count += sum(1 for record in turn.events if record.event_type == event_type)
        return count
