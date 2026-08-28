"""Step 5.4 — full execution engine validation on real LLM backend."""

from __future__ import annotations

from adapter.chakra import ChakraHarness
from engine import ExecutionEngine, StartConversationRequest
from engine.state import ConversationStatus, HistoryRole
from interface import ConnectionConfig
from interface.events import HarnessEventType
from phase5_common import journal_entry, scan_engine_isolation
from scripts.real_backend import (
    SESSION_PROMPT_A,
    SESSION_PROMPT_B,
    SIMPLE_PROMPT,
    TOOL_PROMPT,
    connection_config,
    load_project_env,
    turn_timeout,
    working_directory,
)


def main() -> int:
    load_project_env()
    leaks = scan_engine_isolation()

    harness = ChakraHarness(default_timeout_seconds=turn_timeout())
    harness.connect(connection_config())
    engine = ExecutionEngine(harness)

    state = engine.start_conversation(
        StartConversationRequest(working_directory=working_directory("phase5_engine"))
    )

    def auto_approve(_event, _state):
        return "yes"

    # Single turn
    single = engine.execute_turn(
        state.conversation_id,
        SIMPLE_PROMPT,
        intervention_handler=auto_approve,
    )

    # Tool turn
    engine.execute_turn(
        state.conversation_id,
        TOOL_PROMPT,
        intervention_handler=auto_approve,
    )

    # Multi-turn recall
    engine.execute_turn(
        state.conversation_id,
        SESSION_PROMPT_A,
        intervention_handler=auto_approve,
    )
    recalled = engine.execute_turn(
        state.conversation_id,
        SESSION_PROMPT_B,
        intervention_handler=auto_approve,
    )

    conv = engine.get_conversation(state.conversation_id)
    snapshot = engine.reconstruct(state.conversation_id)
    engine.close_conversation(state.conversation_id)
    harness.disconnect()

    user_messages = [e.content for e in conv.history if e.role == HistoryRole.USER]
    assistant_messages = [e.content for e in conv.history if e.role == HistoryRole.ASSISTANT]

    ok = (
        not leaks
        and conv.status == ConversationStatus.CLOSED
        and single.final_text
        and len(user_messages) >= 4
        and len(assistant_messages) >= 4
        and "orchid" in recalled.final_text.lower()
        and len(snapshot["turns"]) >= 4
    )

    journal_entry(
        milestone="Step 5.4 — Engine Validation",
        design_decisions=[
            "Real LLM validation uses ChakraHarness injected into ExecutionEngine.",
            "Engine remains backend-agnostic — only Harness interface is used by engine/.",
        ],
        implementation=[
            "tests/test_phase5_engine.py",
            "tests/test_phase5_engine_real.py",
        ],
        validation="PASS" if ok else "FAIL",
        issues=leaks or ["None"],
        observations=[
            f"User turns: {len(user_messages)}",
            f"Assistant turns: {len(assistant_messages)}",
            f"Recall response: {recalled.final_text[:120]}",
        ],
        conclusions=["Conversation engine manages full lifecycle on real backend."],
        next_steps=["Implement controller (Phase 6) to supply decisions via InterventionHandler."],
    )
    print("Step 5.4 PASS" if ok else "Step 5.4 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
