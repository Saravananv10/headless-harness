"""Step 6.4 — validate controller runtime with in-memory harness."""

from __future__ import annotations

import json

from controller import Controller, ControllerConfig, DeterministicLLMClient
from engine import ExecutionEngine, StartConversationRequest
from interface import ConnectionConfig
from interface.reference.in_memory_harness import InMemoryHarness
from phase6_common import journal_entry, scan_controller_isolation


def main() -> int:
    harness = InMemoryHarness()
    harness.connect(ConnectionConfig(endpoint="memory://controller"))
    engine = ExecutionEngine(harness)

    llm = DeterministicLLMClient(
        [
            json.dumps(
                {
                    "reasoning": "Greet backend",
                    "action": "send_message",
                    "message": "hello",
                }
            ),
            json.dumps(
                {
                    "reasoning": "Objective satisfied",
                    "action": "complete",
                    "summary": "Received echo response",
                }
            ),
        ]
    )
    controller = Controller(
        engine,
        llm,
        config=ControllerConfig(working_directory="/tmp", max_turns=5, max_decisions=5),
    )

    result = controller.run("Echo greeting test")
    harness.disconnect()
    leaks = scan_controller_isolation()

    ok = (
        not leaks
        and result.completed
        and result.turn_count == 1
        and len(result.actions) == 2
        and result.actions[0].action.value == "send_message"
        and result.actions[1].action.value == "complete"
        and result.final_state_snapshot is not None
    )

    journal_entry(
        milestone="Step 6.4 — Controller Runtime",
        design_decisions=[
            "Controller loop: build context → decide → execute_turn or complete.",
            "InterventionHandler delegates to DecisionPolicy during active turns.",
        ],
        implementation=["controller/controller.py"],
        validation="PASS" if ok else f"FAIL leaks={leaks}",
        issues=leaks or ["None"],
        observations=[
            f"Actions: {[a.action.value for a in result.actions]}",
            f"Summary: {result.summary}",
        ],
        conclusions=["Controller autonomously guides conversations via ExecutionEngine."],
        next_steps=["Run end-to-end validation on real backend."],
    )
    print("Step 6.4 PASS" if ok else "Step 6.4 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
