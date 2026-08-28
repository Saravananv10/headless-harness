#!/usr/bin/env python3
"""Run a manual query through the harness stack (non-automated interactive use)."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from adapter.chakra import ChakraHarness
from interface import CreateSessionRequest, Harness, SendMessageRequest
from interface.events import HarnessEventType, InterventionRequiredEvent
from interface.models.requests import InterventionResponse
from scripts.real_backend import (
    connection_config,
    load_project_env,
    turn_timeout,
    working_directory,
)

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def _prompt_approval(question: str) -> str:
    print(f"\n[ACTION REQUIRED] {question}")
    reply = input("Approve? (yes/no) [yes]: ").strip().lower()
    return reply or "yes"


def run_query(
    message: str,
    *,
    workdir: str,
    auto_approve: bool,
    timeout: float,
    backend: str,
) -> int:
    load_project_env()

    if backend == "harness":
        harness: Harness = ChakraHarness(default_timeout_seconds=timeout)
        harness.connect(connection_config())
        session = harness.create_session(
            CreateSessionRequest(working_directory=workdir)
        )
        print(f"Session: {session.session_id}")
        print(f"Working directory: {workdir}")
        print(f"Query: {message}\n")

        stream = harness.send_turn(
            session,
            SendMessageRequest(message=message, options={"timeout_seconds": timeout}),
        )
        streamed: list[str] = []
        for event in stream:
            if event.type == HarnessEventType.TEXT_DELTA:
                streamed.append(event.text)
                print(event.text, end="", flush=True)
            elif event.type == HarnessEventType.TOOL_STARTED:
                print(f"\n[tool] {event.tool_name} {event.arguments}", flush=True)
            elif isinstance(event, InterventionRequiredEvent):
                reply = "yes" if auto_approve else _prompt_approval(event.prompt)
                stream.respond(
                    InterventionResponse(
                        intervention_id=event.intervention_id,
                        response=reply,
                    )
                )
            elif event.type == HarnessEventType.TOOL_COMPLETED:
                print(f"\n[tool result] {event.tool_name}: {event.output[:500]}", flush=True)
            elif event.type == HarnessEventType.TURN_FAILED:
                print(f"\n[error] {event.code}: {event.message}", flush=True)
                harness.close_session(session)
                harness.disconnect()
                return 1

        print()
        result = stream.result()
        harness.close_session(session)
        harness.disconnect()

        log_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "backend": backend,
            "message": message,
            "workdir": workdir,
            "session_id": session.session_id,
            "final_text": result.final_text,
            "usage": {
                "prompt_tokens": result.usage.prompt_tokens,
                "completion_tokens": result.usage.completion_tokens,
            },
        }
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        log_path = LOG_DIR / f"manual_query_{ts}.json"
        import json

        log_path.write_text(json.dumps(log_payload, indent=2), encoding="utf-8")
        print(f"\n--- Done ({result.usage.prompt_tokens}/{result.usage.completion_tokens} tokens) ---")
        print(f"Log: {log_path}")
        return 0

    if backend == "client":
        from scripts.real_backend import consume_client_stream, require_chakra

        client = require_chakra()
        try:
            client.open_stream()
            client.send_chat_request(message, working_directory=workdir)
            events, _ = consume_client_stream(
                client,
                timeout_seconds=timeout,
                auto_approve=auto_approve,
                print_text=True,
            )
            done = next((e for e in events if e.type.value == "done"), None)
            if done:
                print(f"\n--- Done ({done.prompt_tokens}/{done.completion_tokens} tokens) ---")
            return 0
        finally:
            client.close_stream()
            client.disconnect()

    print(f"Unknown backend: {backend}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a manual query against the real Chakra backend"
    )
    parser.add_argument(
        "message",
        nargs="?",
        default="Create a simple snake game in Python with pygame. Save all files in the working directory.",
        help="User query to send",
    )
    parser.add_argument(
        "--workdir",
        default="",
        help="Subdirectory under runs/ (default: auto-generated timestamp folder)",
    )
    parser.add_argument(
        "--backend",
        choices=["harness", "client"],
        default="harness",
        help="harness = Phase 4 adapter (recommended), client = Phase 1 low-level client",
    )
    parser.add_argument(
        "--approve",
        choices=["auto", "manual"],
        default="auto",
        help="Tool approval mode",
    )
    parser.add_argument("--timeout", type=float, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    subpath = args.workdir
    if not subpath:
        subpath = datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")
    workdir = working_directory(subpath)
    timeout = args.timeout if args.timeout is not None else turn_timeout()

    return run_query(
        args.message,
        workdir=workdir,
        auto_approve=args.approve == "auto",
        timeout=timeout,
        backend=args.backend,
    )


if __name__ == "__main__":
    raise SystemExit(main())
