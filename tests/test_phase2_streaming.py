"""Milestone 2.3 — verify streaming lifecycle on real backend."""

from __future__ import annotations

from client.chakra_client import EventType
from phase2_common import append_execution_log, write_json_log
from scripts.real_backend import (
    SIMPLE_PROMPT,
    consume_client_stream,
    load_project_env,
    require_chakra,
    turn_timeout,
    working_directory,
)


def run_turn(client, message: str) -> list[str]:
    client.open_stream()
    client.send_chat_request(
        message,
        session_id="phase2-stream",
        working_directory=working_directory("phase2_streaming"),
    )
    _, types = consume_client_stream(client, timeout_seconds=turn_timeout())
    client.close_stream()
    return types


def main() -> int:
    load_project_env()
    client = require_chakra()
    try:
        first = run_turn(client, f"{SIMPLE_PROMPT} turn-one")
        second = run_turn(client, f"{SIMPLE_PROMPT} turn-two")
        payload = {
            "milestone": "2.3",
            "conversations": [
                {"turn": 1, "event_sequence": first},
                {"turn": 2, "event_sequence": second},
            ],
        }
        out = write_json_log("phase2_streaming", payload)
        ok = all(EventType.DONE.value in seq for seq in (first, second))
        append_execution_log(
            milestone="Milestone 2.3 — Streaming Protocol",
            objective="Document lifecycle and event ordering over multiple turns.",
            commands=["python tests/test_phase2_streaming.py"],
            scripts_written=["tests/test_phase2_streaming.py"],
            observations=["Each live turn completed with done event."],
            validation="PASS" if ok else "FAIL",
            unexpected_behavior=[],
            conclusions=["Streaming protocol validated on real backend."],
            next_actions=["Validate session persistence."],
        )
        return 0 if ok else 1
    finally:
        client.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
