"""Step 6.2 — validate prompting strategy consistency."""

from __future__ import annotations

import json

from controller import (
    DeterministicLLMClient,
    build_context,
    build_decision_messages,
    parse_controller_action,
)
from interface.models.session import HarnessSession

from engine.state import ConversationState, ConversationStatus
from phase6_common import journal_entry


def main() -> int:
    session = HarnessSession(session_id="sess-prompt", working_directory="/tmp")
    state = ConversationState(
        conversation_id="conv-prompt",
        harness_session=session,
        status=ConversationStatus.ACTIVE,
    )
    context = build_context(state, objective="Write hello.py")

    messages_a = build_decision_messages(context)
    messages_b = build_decision_messages(context)
    consistent = messages_a == messages_b

    valid_response = json.dumps(
        {
            "reasoning": "Start implementation",
            "action": "send_message",
            "message": "Create hello.py that prints Hello World",
        }
    )
    llm = DeterministicLLMClient([valid_response, valid_response])
    parsed_a = parse_controller_action(llm.complete(messages_a))
    parsed_b = parse_controller_action(llm.complete(messages_b))

    ok = (
        consistent
        and parsed_a.action == parsed_b.action
        and parsed_a.message == parsed_b.message
        and "send_message" in messages_a[0]["content"]
        and "complete" in messages_a[0]["content"]
    )

    journal_entry(
        milestone="Step 6.2 — Prompting Strategy",
        design_decisions=[
            "System prompt defines role, actions, JSON schema, and constraints.",
            "Decision prompts are deterministic for identical ControllerContext input.",
        ],
        implementation=["controller/prompt_builder.py"],
        validation="PASS" if ok else "FAIL",
        issues=["None"],
        observations=[f"Prompt message count: {len(messages_a)}"],
        conclusions=["Identical contexts produce identical prompts and valid actions."],
        next_steps=["Implement action generation and validation."],
    )
    print("Step 6.2 PASS" if ok else "Step 6.2 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
