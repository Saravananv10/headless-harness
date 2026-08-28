"""Milestone 3.3 — validate common event model covers Phase 2 observations."""

from __future__ import annotations

from interface.events import HarnessEventType, InterventionRequiredEvent, is_terminal_event
from interface.models.requests import InterventionResponse, SendMessageRequest
from interface.reference.in_memory_harness import InMemoryHarness
from interface.validation.event_mapping import PHASE2_BACKEND_EVENT_TO_HARNESS_EVENT
from phase3_common import journal_entry


def main() -> int:
    harness = InMemoryHarness()
    harness.connect()
    session = harness.create_session()

    # Happy path streaming
    stream = harness.send_turn(session, SendMessageRequest(message="event probe"))
    stream_events = [event.type for event in stream]

    # Tool + intervention path
    tool_stream = harness.send_turn(session, SendMessageRequest(message="tool_flow"))
    tool_events = []
    for event in tool_stream:
        tool_events.append(event.type)
        if isinstance(event, InterventionRequiredEvent):
            tool_stream.respond(
                InterventionResponse(intervention_id=event.intervention_id, response="yes")
            )
            for follow_up in tool_stream:
                tool_events.append(follow_up.type)

    # Error path
    err_stream = harness.send_turn(session, SendMessageRequest(message="force_error"))
    err_events = [event.type for event in err_stream]

    harness.disconnect()

    mapped_targets = set(PHASE2_BACKEND_EVENT_TO_HARNESS_EVENT.values())
    contract_events = {item.value for item in HarnessEventType}
    mapping_ok = mapped_targets.issubset(contract_events)
    lifecycle_ok = (
        HarnessEventType.TEXT_DELTA in stream_events
        and HarnessEventType.TURN_COMPLETED in stream_events
        and HarnessEventType.TOOL_STARTED in tool_events
        and HarnessEventType.INTERVENTION_REQUIRED in tool_events
        and HarnessEventType.TOOL_COMPLETED in tool_events
        and HarnessEventType.TURN_FAILED in err_events
    )
    ok = mapping_ok and lifecycle_ok

    journal_entry(
        milestone="Milestone 3.3 — Common Event System",
        objective="Provide consistent streamed event representation across harnesses.",
        design_decisions=[
            "Discriminated event union with explicit HarnessEventType values.",
            "Terminal events: turn_completed and turn_failed.",
            "Phase 2 backend events mapped in interface/validation/event_mapping.py.",
        ],
        implementation=[
            "interface/events.py",
            "interface/validation/event_mapping.py",
        ],
        validation="PASS" if ok else "FAIL",
        observations=[
            f"Phase 2 mapping targets: {sorted(mapped_targets)}",
            f"Stream events observed: {stream_events}",
            f"Tool events observed: {tool_events}",
            f"Error events observed: {err_events}",
        ],
        conclusions=[
            "Every Phase 2 backend event maps to a harness contract event.",
            "Event lifecycle supports streaming, intervention, and failure paths.",
        ],
        next_steps=["Run full contract validation review (Milestone 3.4)."],
    )
    print("Milestone 3.3 PASS" if ok else "Milestone 3.3 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
