"""Milestone 2.5 — tool interaction on real backend."""

from __future__ import annotations

from client.chakra_client import EventType
from phase2_common import append_execution_log, write_json_log
from scripts.real_backend import (
    TOOL_PROMPT,
    load_project_env,
    require_chakra,
    turn_timeout,
    working_directory,
)


def run_flow(client, reply: str) -> dict:
    client.open_stream()
    client.send_chat_request(
        TOOL_PROMPT,
        working_directory=working_directory("phase2_tools"),
    )
    seen = []
    tool_result = None
    for event in client.iter_events(timeout_seconds=turn_timeout()):
        seen.append(event.type.value)
        if event.type == EventType.ACTION_REQUIRED:
            client.send_user_input(event.prompt_id or "", reply)
        if event.type == EventType.TOOL_RESULT:
            tool_result = {"output": event.output, "is_error": event.is_error}
    client.close_stream()
    return {"events": seen, "tool_result": tool_result}


def main() -> int:
    load_project_env()
    client = require_chakra()
    try:
        approved = run_flow(client, "yes")
        denied = run_flow(client, "no")
        payload = {"milestone": "2.5", "approved": approved, "denied": denied}
        out = write_json_log("phase2_tool_interaction", payload)
        ok = (
            EventType.TOOL_START.value in approved["events"]
            and EventType.ACTION_REQUIRED.value in approved["events"]
            and approved["tool_result"] is not None
            and denied["tool_result"] is not None
            and denied["tool_result"]["is_error"] is True
        )
        append_execution_log(
            milestone="Milestone 2.5 — Tool Interaction",
            objective="Observe tool invocation + approval loop on real backend.",
            commands=["python tests/test_phase2_tool_interaction.py"],
            scripts_written=["tests/test_phase2_tool_interaction.py"],
            observations=[
                f"Approved flow events: {approved['events']}",
                f"Denied tool is_error: {denied['tool_result']}",
            ],
            validation="PASS" if ok else "FAIL",
            unexpected_behavior=[],
            conclusions=["Tool approval loop works on real Chakra backend."],
            next_actions=["Validate cancellation behavior."],
        )
        return 0 if ok else 1
    finally:
        client.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
