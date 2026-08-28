"""Milestone 1.4 — multi-turn session lifecycle test (real LLM)."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from client.session import ChakraSession
from scripts.real_backend import (
    SESSION_PROMPT_A,
    SESSION_PROMPT_B,
    load_project_env,
    require_chakra,
    turn_timeout,
    working_directory,
)

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def main() -> int:
    parser = argparse.ArgumentParser(description="Chakra session lifecycle test (real LLM)")
    parser.add_argument(
        "--turns",
        nargs="+",
        default=[SESSION_PROMPT_A, SESSION_PROMPT_B],
    )
    parser.add_argument("--timeout", type=float, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    log = logging.getLogger("test_session")
    load_project_env()

    timeout = args.timeout if args.timeout is not None else turn_timeout()
    client = require_chakra()
    result: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "milestone": "1.4",
        "address": client.config.address,
        "success": False,
        "session": None,
        "turns": [],
        "error": None,
    }

    try:
        session = ChakraSession(
            client=client,
            working_directory=working_directory("phase1_session"),
        )
        log.info("Created session %s", session.session_id)

        for i, message in enumerate(args.turns, start=1):
            log.info("Turn %d: %r", i, message)
            reply = session.send_message(message, timeout_seconds=timeout)
            result["turns"].append(
                {
                    "turn": i,
                    "user": message,
                    "assistant": reply,
                    "event_count": len(session.turns[-1].events),
                }
            )
            log.info("Turn %d reply: %s", i, reply[:200])

        session.close()
        result["session"] = session.summary()
        # Second turn should recall the codeword on a real LLM.
        recalled = "orchid" in result["turns"][-1]["assistant"].lower()
        result["success"] = len(result["turns"]) == len(args.turns) and recalled
        if not recalled:
            log.warning("Session recall check failed; response was: %s", result["turns"][-1]["assistant"])
    except Exception as exc:
        result["error"] = str(exc)
        log.error("Session test failed: %s", exc)
    finally:
        if client.is_connected():
            client.disconnect()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = LOG_DIR / f"session_{ts}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    log.info("Wrote log to %s", out)
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
