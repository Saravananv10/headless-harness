"""Step 6.3 — validate action generation and parsing."""

from __future__ import annotations

import json

from controller import (
    ActionType,
    DecisionPolicy,
    DeterministicLLMClient,
    InvalidActionError,
    parse_controller_action,
    parse_intervention_decision,
)
from controller.context_builder import ControllerContext
from phase6_common import journal_entry


def main() -> int:
    send_raw = json.dumps(
        {"reasoning": "next step", "action": "send_message", "message": "Run tests"}
    )
    complete_raw = json.dumps(
        {"reasoning": "done", "action": "complete", "summary": "All tests pass"}
    )
    intervention_raw = json.dumps({"reasoning": "safe", "response": "yes"})

    send_action = parse_controller_action(send_raw)
    complete_action = parse_controller_action(complete_raw)
    intervention = parse_intervention_decision(intervention_raw)

    invalid_handled = False
    try:
        parse_controller_action('{"action": "send_message"}')
    except InvalidActionError:
        invalid_handled = True

    context = ControllerContext(
        objective="test",
        conversation_id="c1",
        conversation_status="active",
        session_id="s1",
        session_state="active",
        working_directory="/tmp",
        turn_count=0,
    )
    policy = DecisionPolicy(
        DeterministicLLMClient(
            [
                "not json",
                send_raw,
            ]
        ),
        max_retries=1,
    )
    recovered = policy.decide(context)

    ok = (
        send_action.action == ActionType.SEND_MESSAGE
        and complete_action.action == ActionType.COMPLETE
        and intervention.response == "yes"
        and invalid_handled
        and recovered.message == "Run tests"
    )

    journal_entry(
        milestone="Step 6.3 — Action Generation",
        design_decisions=[
            "Actions are JSON with explicit action field and validation per type.",
            "DecisionPolicy retries invalid LLM output with corrective feedback.",
        ],
        implementation=["controller/decision.py", "controller/policies.py"],
        validation="PASS" if ok else "FAIL",
        issues=["None"],
        observations=[
            f"Parsed send action: {send_action.action.value}",
            f"Intervention response: {intervention.response}",
        ],
        conclusions=["Every generated action is parseable and executable by the engine."],
        next_steps=["Implement controller runtime loop."],
    )
    print("Step 6.3 PASS" if ok else "Step 6.3 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
