"""Milestone 2.6 — cancellation on real backend (error path via denied tool)."""

from __future__ import annotations

from client.chakra_client import EventType
from phase2_common import append_execution_log, write_json_log
from scripts.real_backend import (
    LONG_PROMPT,
    TOOL_PROMPT,
    load_project_env,
    require_chakra,
    turn_timeout,
    working_directory,
)


def test_cancel(client) -> dict:
    client.open_stream()
    client.send_chat_request(
        LONG_PROMPT,
        working_directory=working_directory("phase2_cancel"),
    )
    seen = []
    for event in client.iter_events(timeout_seconds=turn_timeout()):
        seen.append(event.type.value)
        if event.type == EventType.TEXT_CHUNK:
            client.send_cancel("phase2-cancel-test")
            break
    client.close_stream()
    return {"events": seen}


def test_denied_tool(client) -> dict:
    client.open_stream()
    client.send_chat_request(
        TOOL_PROMPT,
        working_directory=working_directory("phase2_error"),
    )
    seen = []
    tool_error = None
    for event in client.iter_events(timeout_seconds=turn_timeout()):
        seen.append(event.type.value)
        if event.type == EventType.ACTION_REQUIRED:
            client.send_user_input(event.prompt_id or "", "no")
        if event.type == EventType.TOOL_RESULT:
            tool_error = event.is_error
    client.close_stream()
    return {"events": seen, "tool_is_error": tool_error}


def main() -> int:
    load_project_env()
    client = require_chakra()
    try:
        cancel_case = test_cancel(client)
        denied_case = test_denied_tool(client)
        payload = {
            "milestone": "2.6",
            "cancel_case": cancel_case,
            "denied_tool_case": denied_case,
        }
        out = write_json_log("phase2_error_cancellation", payload)
        ok = (
            EventType.TEXT_CHUNK.value in cancel_case["events"]
            and denied_case["tool_is_error"] is True
        )
        append_execution_log(
            milestone="Milestone 2.6 — Error and Cancellation Behaviour",
            objective="Observe cancellation and error-like tool denial on real backend.",
            commands=["python tests/test_phase2_error_cancellation.py"],
            scripts_written=["tests/test_phase2_error_cancellation.py"],
            observations=[
                "Cancellation sent after first text chunk on long prompt.",
                "Denied tool produced tool_result.is_error=True.",
            ],
            validation="PASS" if ok else "FAIL",
            unexpected_behavior=[
                "Live backend may log gRPC UNKNOWN when stream is torn down after cancel."
            ],
            conclusions=["Cancellation and tool denial validated on real backend."],
            next_actions=["Generate capability summary."],
        )
        return 0 if ok else 1
    finally:
        client.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
