#!/usr/bin/env python3
"""Smoke test: verify Chakra gRPC exposes built-in subagents (Phase 1).

Requires a running Chakra gRPC server started after built-in agent registration
was enabled (restart ./scripts/start_chakra.sh after pulling changes).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from client.chakra_client import ChakraClient, EventType
from scripts.real_backend import consume_client_stream, load_project_env, require_chakra, working_directory

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SMOKE_PROMPT = """You must use the Agent tool exactly once with these arguments:
- subagent_type: "Explore"
- description: "find markdown files"
- prompt: "List every .md filename in the repository (quick thoroughness). Reply with filenames only."

Do not use Bash, Read, Glob, or Grep yourself — only the Explore subagent.
After the Explore agent returns, summarize its findings in one sentence."""

AGENT_TOOL_NAMES = frozenset({"agent", "task"})


def _is_agent_tool(name: str | None) -> bool:
    return (name or "").strip().lower() in AGENT_TOOL_NAMES


def main() -> int:
    load_project_env()
    workdir = working_directory("subagent_smoke")
    readme = Path(workdir) / "README.md"
    readme.write_text("# Subagent smoke test\n", encoding="utf-8")
    notes = Path(workdir) / "NOTES.md"
    notes.write_text("# Notes\n", encoding="utf-8")

    client = require_chakra()
    try:
        client.open_stream()
        client.send_chat_request(SMOKE_PROMPT, working_directory=workdir)
        events, types = consume_client_stream(client, auto_approve=True, print_text=True)
    finally:
        client.disconnect()

    agent_starts = [
        event
        for event in events
        if event.type == EventType.TOOL_START and _is_agent_tool(event.tool_name)
    ]
    agent_results = [
        event
        for event in events
        if event.type == EventType.TOOL_RESULT and _is_agent_tool(event.tool_name)
    ]
    unregistered = [
        event
        for event in agent_results
        if event.output
        and "not found" in event.output.lower()
        and "available agents" in event.output.lower()
    ]

    print("\n--- Subagent smoke summary ---")
    print(f"Workdir: {workdir}")
    print(f"Event types: {types}")
    print(f"Agent tool invocations: {len(agent_starts)}")

    if unregistered:
        print("FAIL: subagent_type is not registered on the gRPC server.")
        print(unregistered[0].output[:800])
        print("\nRestart Chakra after updating harness/chakra/src/grpc/server.ts:")
        print("  ./scripts/start_chakra.sh")
        return 1

    if not agent_starts:
        print("FAIL: backend did not invoke the Agent tool.")
        print("Check LLM credentials in .env and retry.")
        return 1

    agent_errors = [event for event in agent_results if event.is_error]
    if agent_errors:
        print("FAIL: Agent tool returned an error.")
        print((agent_errors[0].output or "")[:800])
        return 1

    print("PASS: built-in subagents are enabled on Chakra gRPC.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
