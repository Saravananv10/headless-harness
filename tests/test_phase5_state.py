"""Step 5.1 — validate conversation state model and reconstruction."""

from __future__ import annotations

from interface.events import HarnessEventType
from interface.models.session import HarnessSession

from engine.state import (
    ConversationState,
    ConversationStatus,
    EventRecord,
    HistoryEntry,
    HistoryRole,
    TurnState,
    TurnStatus,
    apply_session_snapshot,
    new_turn_id,
)
from phase5_common import journal_entry


def main() -> int:
    session = HarnessSession(session_id="sess-1", working_directory="/tmp")
    state = ConversationState(
        conversation_id="conv-1",
        harness_session=session,
        status=ConversationStatus.ACTIVE,
    )
    turn = TurnState(turn_id=new_turn_id(), user_message="hello")
    turn.streamed_text = "Echo: hello"
    turn.status = TurnStatus.COMPLETED
    turn.events.append(
        EventRecord(
            event_type=HarnessEventType.TEXT_DELTA,
            payload={"text": "Echo: "},
        )
    )
    state.turns.append(turn)
    state.history = [
        HistoryEntry(role=HistoryRole.USER, content="hello", turn_id=turn.turn_id),
        HistoryEntry(role=HistoryRole.ASSISTANT, content="Echo: hello", turn_id=turn.turn_id),
    ]

    snapshot = state.snapshot()
    rebuilt_session = HarnessSession(session_id=session.session_id)
    apply_session_snapshot(
        rebuilt_session,
        {
            "working_directory": snapshot["working_directory"],
            "session_turn_count": snapshot["session_turn_count"],
            "session_state": snapshot["session_state"],
        },
    )
    rebuilt = ConversationState.from_snapshot(snapshot, rebuilt_session)

    ok = (
        rebuilt.conversation_id == state.conversation_id
        and rebuilt.status == state.status
        and len(rebuilt.history) == len(state.history)
        and len(rebuilt.turns) == len(state.turns)
        and rebuilt.turns[0].streamed_text == turn.streamed_text
        and rebuilt.turns[0].user_message == turn.user_message
    )

    journal_entry(
        milestone="Step 5.1 — Conversation State",
        design_decisions=[
            "ConversationState tracks history, turns, active turn, and harness session.",
            "snapshot()/from_snapshot() enable reconstruction at any point.",
        ],
        implementation=["engine/state.py"],
        validation="PASS" if ok else "FAIL",
        issues=[],
        observations=[f"Snapshot keys: {list(snapshot.keys())}"],
        conclusions=["Conversation state is reconstructable from snapshots."],
        next_steps=["Implement event dispatcher."],
    )
    print("Step 5.1 PASS" if ok else "Step 5.1 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
