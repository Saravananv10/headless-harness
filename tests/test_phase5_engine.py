"""Step 5.3 — validate execution engine with in-memory harness."""

from __future__ import annotations

from interface import ConnectionConfig
from interface.events import HarnessEventType
from interface.reference.in_memory_harness import InMemoryHarness

from engine import ExecutionEngine, StartConversationRequest
from engine.exceptions import InterventionRequiredError
from engine.types import EngineNotificationKind
from phase5_common import journal_entry, scan_engine_isolation


def main() -> int:
    notifications: list[EngineNotificationKind] = []

    def observer(notification) -> None:
        notifications.append(notification.kind)

    harness = InMemoryHarness()
    harness.connect(ConnectionConfig(endpoint="memory://test"))
    engine = ExecutionEngine(harness, observer=observer)

    state = engine.start_conversation(
        StartConversationRequest(working_directory="/tmp", metadata={"test": True})
    )

    # Intervention path
    try:
        engine.execute_turn(state.conversation_id, "tool_flow", intervention_handler=None)
        intervention_raises = False
    except InterventionRequiredError:
        intervention_raises = True

    def auto_approve(event, _state):
        return "yes"

    result = engine.execute_turn(
        state.conversation_id,
        "tool_flow",
        intervention_handler=auto_approve,
    )

    # Multi-turn
    engine.execute_turn(state.conversation_id, "remember alpha", intervention_handler=auto_approve)
    second = engine.execute_turn(
        state.conversation_id,
        "recall prior",
        intervention_handler=auto_approve,
    )

    snapshot = engine.reconstruct(state.conversation_id)
    engine.close_conversation(state.conversation_id)
    harness.disconnect()

    leaks = scan_engine_isolation()
    ok = (
        not leaks
        and intervention_raises
        and result.final_text == "tool flow complete"
        and "prior turns: 1" in second.final_text
        and EngineNotificationKind.TURN_COMPLETED in notifications
        and len(snapshot["turns"]) >= 3
        and snapshot["history"]
    )

    journal_entry(
        milestone="Step 5.3 — Execution Engine",
        design_decisions=[
            "ExecutionEngine delegates all backend I/O to Harness only.",
            "InterventionHandler supplies external decisions (controller hook for Phase 6).",
            "EngineObserver emits lifecycle notifications for future controller integration.",
        ],
        implementation=["engine/execution_engine.py", "engine/types.py"],
        validation="PASS" if ok else f"FAIL leaks={leaks}",
        issues=leaks or ["None"],
        observations=[f"Notifications: {[n.value for n in notifications]}"],
        conclusions=["Engine executes full conversations with external intervention policy."],
        next_steps=["Run full engine validation suite."],
    )
    print("Step 5.3 PASS" if ok else "Step 5.3 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
