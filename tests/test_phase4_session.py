"""Step 4.2 — session adapter on real backend."""

from __future__ import annotations

from adapter.chakra import ChakraHarness
from interface import (
    CreateSessionRequest,
    Harness,
    ResumeSessionRequest,
    SendMessageRequest,
)
from interface.events import HarnessEventType
from phase4_common import journal_entry
from scripts.real_backend import (
    SESSION_PROMPT_A,
    SESSION_PROMPT_B,
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
    workdir = working_directory("phase4_session")

    session = harness.create_session(CreateSessionRequest(working_directory=workdir))
    first_stream = harness.send_turn(session, SendMessageRequest(message=SESSION_PROMPT_A))
    _, first_result = consume_harness_stream(first_stream)

    resumed = harness.resume_session(
        ResumeSessionRequest(session_id=session.session_id, working_directory=workdir)
    )
    second_stream = harness.send_turn(resumed, SendMessageRequest(message=SESSION_PROMPT_B))
    second_events, _ = consume_harness_stream(second_stream)
    second_text = next(
        (e.final_text for e in second_events if e.type == HarnessEventType.TURN_COMPLETED),
        "",
    )

    status = harness.get_session_status(resumed)
    close = harness.close_session(resumed)
    harness.disconnect()

    ok = "orchid" in second_text.lower() and status.turn_count == 2 and close.turn_count == 2

    journal_entry(
        milestone="Step 4.2 — Session Adapter",
        design_decisions=["HarnessSession.session_id maps to Chakra ChatRequest.session_id."],
        implementation=["adapter/chakra/session.py", "adapter/chakra/harness.py"],
        validation="PASS" if ok else "FAIL",
        issues=[],
        observations=[f"Second turn text: {second_text[:120]}", f"First turn: {first_result.final_text[:80]}"],
        conclusions=["Multi-turn session works through harness adapter on real LLM."],
        next_steps=["Validate turn execution."],
    )
    print("Step 4.2 PASS" if ok else "Step 4.2 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
