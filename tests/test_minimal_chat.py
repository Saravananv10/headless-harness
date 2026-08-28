"""Milestone 1.3 — send a chat request to the real Chakra + LLM backend."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from client.chakra_client import EventType
from scripts.real_backend import (
    SIMPLE_PROMPT,
    consume_client_stream,
    load_project_env,
    require_chakra,
    turn_timeout,
    working_directory,
)

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal Chakra chat test (real LLM)")
    parser.add_argument("--message", default=SIMPLE_PROMPT)
    parser.add_argument("--timeout", type=float, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    log = logging.getLogger("test_minimal_chat")
    load_project_env()

    timeout = args.timeout if args.timeout is not None else turn_timeout()
    client = require_chakra()
    events_log: list[dict] = []

    result: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "milestone": "1.3",
        "message": args.message,
        "address": client.config.address,
        "success": False,
        "final_text": "",
        "stream_chunk_count": 0,
        "event_types": [],
        "error": None,
    }

    try:
        client.open_stream()
        client.send_chat_request(
            args.message,
            working_directory=working_directory("phase1_chat"),
        )
        events, types = consume_client_stream(
            client,
            timeout_seconds=timeout,
            auto_approve=True,
            print_text=True,
        )
        for event in events:
            events_log.append({"type": event.type.value, "text": event.text})
        result["event_types"] = types
        result["stream_chunk_count"] = sum(1 for t in types if t == EventType.TEXT_CHUNK.value)

        done = next((e for e in events if e.type == EventType.DONE), None)
        if done:
            result["final_text"] = done.full_text or ""
            result["success"] = True
            log.info("Done. Tokens in/out: %s/%s", done.prompt_tokens, done.completion_tokens)
        else:
            error = next((e for e in events if e.type == EventType.ERROR), None)
            if error:
                raise RuntimeError(f"{error.error_code}: {error.error_message}")
    except Exception as exc:
        result["error"] = str(exc)
        log.error("Chat test failed: %s", exc)
    finally:
        client.close_stream()
        client.disconnect()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = LOG_DIR / f"minimal_chat_{ts}.json"
    out.write_text(json.dumps({**result, "events": events_log}, indent=2), encoding="utf-8")
    log.info("Wrote log to %s", out)
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
