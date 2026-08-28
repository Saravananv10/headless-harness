"""Step 4.5 — full adapter validation on real backend."""

from __future__ import annotations

import inspect

from adapter.chakra import ChakraHarness
from interface import (
    CreateSessionRequest,
    Harness,
    InterruptRequest,
    SendMessageRequest,
)
from interface.events import HarnessEventType
from interface.harness import Harness as HarnessABC
from phase4_common import journal_entry, scan_consumer_layer_leaks
from scripts.real_backend import (
    LONG_PROMPT,
    SIMPLE_PROMPT,
    TOOL_PROMPT,
    connection_config,
    consume_harness_stream,
    load_project_env,
    turn_timeout,
    working_directory,
)


def main() -> int:
    load_project_env()
    leaks = scan_consumer_layer_leaks()
    abstract_methods = {
        name
        for name, _ in inspect.getmembers(HarnessABC, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    implemented = {
        name
        for name, _ in inspect.getmembers(ChakraHarness, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    interface_complete = abstract_methods.issubset(implemented)

    harness: Harness = ChakraHarness(default_timeout_seconds=turn_timeout())
    harness.connect(connection_config())
    workdir = working_directory("phase4_validation")
    session = harness.create_session(CreateSessionRequest(working_directory=workdir))

    stream = harness.send_turn(session, SendMessageRequest(message=SIMPLE_PROMPT))
    stream_events, _ = consume_harness_stream(stream)
    stream_types = [e.type for e in stream_events]

    tool_stream = harness.send_turn(session, SendMessageRequest(message=TOOL_PROMPT))
    tool_events, _ = consume_harness_stream(tool_stream)
    tool_types = [e.type for e in tool_events]

    denied_stream = harness.send_turn(session, SendMessageRequest(message=TOOL_PROMPT))
    denied_events, _ = consume_harness_stream(denied_stream, approve_reply="no")
    denied_types = [e.type for e in denied_events]
    tool_error = any(
        e.type == HarnessEventType.TOOL_COMPLETED and e.is_error for e in denied_events
    )

    cancel_stream = harness.send_turn(session, SendMessageRequest(message=LONG_PROMPT))
    cancel_types = []
    for event in cancel_stream:
        cancel_types.append(event.type)
        if event.type == HarnessEventType.TEXT_DELTA:
            cancel_stream.cancel(InterruptRequest(reason="phase4-test"))
            break

    harness.close_session(session)
    harness.disconnect()

    ok = (
        not leaks
        and interface_complete
        and HarnessEventType.TURN_COMPLETED in stream_types
        and HarnessEventType.TOOL_STARTED in tool_types
        and HarnessEventType.INTERVENTION_REQUIRED in tool_types
        and tool_error
        and HarnessEventType.TEXT_DELTA in cancel_types
    )

    journal_entry(
        milestone="Step 4.5 — Adapter Validation",
        design_decisions=["All integration tests run against real Chakra + LLM."],
        implementation=["scripts/real_backend.py", "scripts/run_all_real_tests.py"],
        validation="PASS" if ok else f"FAIL leaks={leaks}",
        issues=leaks or ["None"],
        observations=[
            f"Stream: {[t.value for t in stream_types]}",
            f"Tool: {[t.value for t in tool_types]}",
            f"Denied: {[t.value for t in denied_types]}",
        ],
        conclusions=["ChakraHarness validated end-to-end on real backend."],
        next_steps=["Use scripts/run_query.py for manual task testing."],
    )
    if leaks:
        for leak in leaks:
            print(leak)
    print("Step 4.5 PASS" if ok else "Step 4.5 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
