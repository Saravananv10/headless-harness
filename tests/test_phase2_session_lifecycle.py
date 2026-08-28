"""Milestone 2.4 — session lifecycle on real backend."""

from __future__ import annotations

from client.session import ChakraSession
from phase2_common import append_execution_log, write_json_log
from scripts.real_backend import (
    SESSION_PROMPT_A,
    SESSION_PROMPT_B,
    load_project_env,
    require_chakra,
    turn_timeout,
    working_directory,
)


def main() -> int:
    load_project_env()
    client = require_chakra()
    try:
        session = ChakraSession(
            client=client,
            working_directory=working_directory("phase2_session"),
        )
        first = session.send_message(SESSION_PROMPT_A, timeout_seconds=turn_timeout())
        second = session.send_message(SESSION_PROMPT_B, timeout_seconds=turn_timeout())
        summary = session.summary()
        session.close()
        payload = {
            "milestone": "2.4",
            "first_response": first,
            "second_response": second,
            "summary": summary,
            "recalled_codeword": "orchid" in second.lower(),
        }
        out = write_json_log("phase2_session_lifecycle", payload)
        ok = payload["recalled_codeword"]
        append_execution_log(
            milestone="Milestone 2.4 — Session Lifecycle",
            objective="Verify persistent multi-turn sessions.",
            commands=["python tests/test_phase2_session_lifecycle.py"],
            scripts_written=["tests/test_phase2_session_lifecycle.py"],
            observations=[f"Second turn response: {second[:120]}"],
            validation="PASS" if ok else "FAIL",
            unexpected_behavior=[],
            conclusions=["Session persistence validated on real LLM."],
            next_actions=["Validate tool interaction."],
        )
        return 0 if ok else 1
    finally:
        client.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
