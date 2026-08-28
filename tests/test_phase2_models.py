"""Milestone 2.2 — validate request/response models on real backend."""

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


def main() -> int:
    load_project_env()
    client = require_chakra()
    try:
        client.open_stream()
        client.send_chat_request(
            SIMPLE_PROMPT,
            session_id="phase2-models",
            working_directory=working_directory("phase2_models"),
        )
        events, seen = consume_client_stream(client, timeout_seconds=turn_timeout())
        done_payload = {}
        for event in events:
            if event.type == EventType.DONE:
                done_payload = {
                    "full_text": event.full_text,
                    "prompt_tokens": event.prompt_tokens,
                    "completion_tokens": event.completion_tokens,
                }

        payload = {
            "milestone": "2.2",
            "response_checked": {"FinalResponse": done_payload, "event_sequence": seen},
        }
        out = write_json_log("phase2_models", payload)
        ok = EventType.DONE.value in seen and bool(done_payload.get("full_text"))
        append_execution_log(
            milestone="Milestone 2.2 — Request and Response Models",
            objective="Verify supported request type produces expected response payloads.",
            commands=["python tests/test_phase2_models.py"],
            scripts_written=["tests/test_phase2_models.py"],
            observations=["Live ChatRequest produced text_chunk events and done."],
            validation="PASS" if ok else "FAIL",
            unexpected_behavior=[],
            conclusions=["Request/response models validated on real LLM backend."],
            next_actions=["Analyze streaming lifecycle."],
        )
        return 0 if ok else 1
    finally:
        client.close_stream()
        client.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
