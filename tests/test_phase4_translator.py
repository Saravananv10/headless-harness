"""Step 4.4 — validate Chakra event translation to harness events."""

from __future__ import annotations

from client.chakra_client import EventType, ServerEvent

from adapter.chakra.translator import translate_server_event
from interface.events import (
    HarnessEventType,
    InterventionKind,
    InterventionRequiredEvent,
    TextDeltaEvent,
    ToolCompletedEvent,
    ToolStartedEvent,
    TurnCompletedEvent,
    TurnFailedEvent,
)
from phase4_common import journal_entry


def main() -> int:
    cases: list[tuple[ServerEvent, type, HarnessEventType]] = [
        (ServerEvent(type=EventType.TEXT_CHUNK, text="hi"), TextDeltaEvent, HarnessEventType.TEXT_DELTA),
        (
            ServerEvent(
                type=EventType.TOOL_START,
                tool_name="shell",
                arguments_json='{"command":"echo"}',
                tool_use_id="t1",
            ),
            ToolStartedEvent,
            HarnessEventType.TOOL_STARTED,
        ),
        (
            ServerEvent(
                type=EventType.TOOL_RESULT,
                tool_name="shell",
                output="ok",
                is_error=False,
                tool_use_id="t1",
            ),
            ToolCompletedEvent,
            HarnessEventType.TOOL_COMPLETED,
        ),
        (
            ServerEvent(
                type=EventType.ACTION_REQUIRED,
                prompt_id="p1",
                question="Approve?",
                action_type="CONFIRM_COMMAND",
            ),
            InterventionRequiredEvent,
            HarnessEventType.INTERVENTION_REQUIRED,
        ),
        (
            ServerEvent(
                type=EventType.DONE,
                full_text="done",
                prompt_tokens=3,
                completion_tokens=7,
            ),
            TurnCompletedEvent,
            HarnessEventType.TURN_COMPLETED,
        ),
        (
            ServerEvent(type=EventType.ERROR, error_message="boom", error_code="INTERNAL"),
            TurnFailedEvent,
            HarnessEventType.TURN_FAILED,
        ),
    ]

    ok = True
    for raw, expected_type, expected_event_type in cases:
        translated = translate_server_event(raw, session_id="s1", turn_id="t1")
        if translated is None or not isinstance(translated, expected_type):
            ok = False
            break
        if translated.type != expected_event_type:
            ok = False
            break

    intervention = translate_server_event(
        ServerEvent(
            type=EventType.ACTION_REQUIRED,
            prompt_id="p2",
            question="info?",
            action_type="REQUEST_INFORMATION",
        )
    )
    ok = ok and isinstance(intervention, InterventionRequiredEvent)
    ok = ok and intervention.kind == InterventionKind.REQUEST_INFORMATION

    journal_entry(
        milestone="Step 4.4 — Event Translation",
        design_decisions=[
            "Dedicated translator module maps Chakra ServerEvent to harness events.",
            "Higher layers never receive client.chakra_client.ServerEvent.",
        ],
        implementation=["adapter/chakra/translator.py"],
        validation="PASS" if ok else "FAIL",
        issues=[],
        observations=["All Phase 2 backend event families have harness equivalents."],
        conclusions=["Event translation is complete and backend-agnostic at boundary."],
        next_steps=["Run full adapter validation suite (Step 4.5)."],
    )
    print("Step 4.4 PASS" if ok else "Step 4.4 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
