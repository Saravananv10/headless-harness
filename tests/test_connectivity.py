"""Milestone 1.2 — verify gRPC connectivity to real Chakra backend."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from scripts.real_backend import load_project_env, require_chakra

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Chakra gRPC connectivity")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    log = logging.getLogger("test_connectivity")
    load_project_env()

    client = require_chakra(connect_timeout=args.timeout)
    result: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "milestone": "1.2",
        "address": client.config.address,
        "service_inspection": client.inspect_service(),
        "connected": True,
        "error": None,
    }

    try:
        log.info("Successfully connected to %s", client.config.address)
        log.info("Service metadata: %s", json.dumps(result["service_inspection"], indent=2))
    finally:
        client.disconnect()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = LOG_DIR / f"connectivity_{ts}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    log.info("Wrote log to %s", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
