"""Step 4.3 — turn execution on real backend."""

from __future__ import annotations

from adapter.chakra import ChakraHarness
from interface import CreateSessionRequest, Harness, SendMessageRequest
from interface.events import HarnessEventType
from phase4_common import journal_entry
from scripts.real_backend import (
    SIMPLE_PROMPT,
    connection_config,
    consume_harness_stream,
    load_project_env,
    turn_timeout,
    working_directory,
)


def main() -> int:
    load_project_env()
    harness: Harness = ChakraHarness(default_timeout_seconds=turn_timeout())
    harness.connect(connection_config())
    session = harness.create_session(CreateSessionRequest(working_directory=working_directory("phase4_turn")))
    stream = harness.send_turn(session, SendMessageRequest(message=SIMPLE_PROMPT))
    events, result = consume_harness_stream(stream, print_text=True)
    harness.disconnect()

    types = [e.type for e in events]
    ok = HarnessEventType.TEXT_DELTA in types and HarnessEventType.TURN_COMPLETED in types and result.final_text

    journal_entry(
        milestone="Step 4.3 — Turn Execution Adapter",
        design_decisions=["ChakraTurnStream owns one bidi stream per harness turn."],
        implementation=["adapter/chakra/stream.py"],
        validation="PASS" if ok else "FAIL",
        issues=[],
        observations=[f"Event types: {[t.value for t in types]}"],
        conclusions=["Full turn executes through harness adapter on real LLM."],
        next_steps=["Validate event translation."],
    )
    print("Step 4.3 PASS" if ok else "Step 4.3 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
