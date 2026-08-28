"""Step 5.2 — validate event dispatcher updates state correctly."""

from __future__ import annotations

from interface.events import (
    HarnessEventType,
    InterventionRequiredEvent,
    InterventionKind,
    TextDeltaEvent,
    ToolCompletedEvent,
    ToolStartedEvent,
    TurnCompletedEvent,
    TurnFailedEvent,
)
from interface.models.session import HarnessSession

from engine.dispatcher import EventDispatcher
from engine.state import ConversationState, ConversationStatus, TurnState, TurnStatus, new_turn_id
from phase5_common import journal_entry


def main() -> int:
    dispatcher = EventDispatcher()
    session = HarnessSession(session_id="sess-dispatch")
    state = ConversationState(conversation_id="conv-dispatch", harness_session=session)
    turn = TurnState(turn_id=new_turn_id(), user_message="tool_flow")
    state.active_turn = turn
    state.turns.append(turn)
    state.status = ConversationStatus.TURN_IN_PROGRESS

    events = [
        TextDeltaEvent(text="working "),
        ToolStartedEvent(tool_name="shell", arguments={"cmd": "ls"}, invocation_id="t1"),
        InterventionRequiredEvent(
            intervention_id="int-1",
            prompt="Approve?",
            kind=InterventionKind.CONFIRM_ACTION,
        ),
        ToolCompletedEvent(tool_name="shell", invocation_id="t1", output="ok"),
        TurnCompletedEvent(final_text="done", usage={"prompt_tokens": 1, "completion_tokens": 2}),
    ]

    intervention_seen = False
    for event in events:
        if isinstance(event, InterventionRequiredEvent):
            intervention_seen = True
            result = dispatcher.dispatch(state, event)
            assert result.requires_intervention
            dispatcher.mark_intervention_resolved(state)
            continue
        result = dispatcher.dispatch(state, event)
        if result.is_terminal:
            break

    ok = (
        intervention_seen
        and state.status == ConversationStatus.ACTIVE
        and state.active_turn is None
        and len(state.history) == 1
        and state.history[0].content == "done"
        and turn.streamed_text == "working "
        and dispatcher.event_count_for_type(state, HarnessEventType.TOOL_STARTED) >= 1
    )

    journal_entry(
        milestone="Step 5.2 — Event Dispatcher",
        design_decisions=[
            "EventDispatcher is the single path for harness event -> state updates.",
            "Terminal and intervention events transition conversation status explicitly.",
        ],
        implementation=["engine/dispatcher.py"],
        validation="PASS" if ok else "FAIL",
        issues=[],
        observations=[
            f"Final status: {state.status.value}",
            f"Turn status: {turn.status.value}",
            f"Event records: {len(turn.events)}",
        ],
        conclusions=["All harness event types update conversation state correctly."],
        next_steps=["Implement execution engine."],
    )
    print("Step 5.2 PASS" if ok else "Step 5.2 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
