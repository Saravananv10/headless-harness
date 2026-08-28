"""Shared helpers for integration tests against the real Chakra + LLM backend."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from client.chakra_client import ChakraClient, EventType, ServerEvent
from client.config import load_config
from interface.events import HarnessEvent, HarnessEventType, InterventionRequiredEvent
from interface.harness import TurnStream
from interface.models.requests import ConnectionConfig, InterventionResponse
from interface.models.responses import TurnResult

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = REPO_ROOT / ".env"
EXPERIMENTS_DIR = REPO_ROOT / "experiments"

# Prompts tuned for real LLM + tool use
SIMPLE_PROMPT = "Reply with exactly: harness integration ok"
SESSION_PROMPT_A = "Remember the codeword 'orchid'. Reply with exactly: stored"
SESSION_PROMPT_B = "What codeword did I ask you to remember? Reply with only the codeword."
TOOL_PROMPT = (
    "Use the available tools to list files in the working directory. "
    "Run a single directory listing command only. Do not create or modify files."
)
LONG_PROMPT = (
    "Write a detailed step-by-step plan for building a snake game. "
    "Include at least 20 numbered steps and do not use any tools."
)


def load_project_env(env_file: Path | None = None) -> None:
    """Load repo .env into os.environ (does not override existing vars)."""
    path = env_file or DEFAULT_ENV_FILE
    if not path.is_file():
        logger.warning("No .env file at %s", path)
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

    # Bridge gRPC vars used by Chakra server startup.
    if "GRPC_HOST" in os.environ:
        os.environ.setdefault("CHAKRA_GRPC_HOST", os.environ["GRPC_HOST"])
    if "GRPC_PORT" in os.environ:
        os.environ.setdefault("CHAKRA_GRPC_PORT", os.environ["GRPC_PORT"])


def connection_config(timeout_seconds: float = 10.0) -> ConnectionConfig:
    load_project_env()
    cfg = load_config()
    return ConnectionConfig(
        endpoint=cfg.address,
        options={"timeout_seconds": timeout_seconds},
    )


def working_directory(subpath: str = "") -> str:
    base = EXPERIMENTS_DIR
    base.mkdir(parents=True, exist_ok=True)
    if subpath:
        target = base / subpath
        target.mkdir(parents=True, exist_ok=True)
        return str(target)
    return str(base)


def turn_timeout(default: float = 300.0) -> float:
    """Max seconds without a gRPC event before a backend turn times out (idle-based)."""
    return float(os.environ.get("HARNESS_TURN_TIMEOUT", default))


def controller_llm_timeout(default: float = 300.0) -> float:
    """Max seconds for a single controller LLM HTTP request."""
    return float(os.environ.get("HARNESS_CONTROLLER_LLM_TIMEOUT", default))


def inactivity_timeout_minutes(default: float = 60.0) -> float:
    """Max minutes without any conversation activity before session health stops the run."""
    return float(os.environ.get("HARNESS_INACTIVITY_TIMEOUT_MINUTES", default))


def progress_timeout_minutes(default: float = 20.0) -> float:
    """Max minutes without forward progress before stagnation handling starts."""
    return float(os.environ.get("HARNESS_PROGRESS_TIMEOUT_MINUTES", default))


def require_chakra(
    *,
    connect_timeout: float = 10.0,
    hint: str | None = None,
) -> ChakraClient:
    """Connect to the running Chakra backend or exit with instructions."""
    load_project_env()
    config = load_config()
    client = ChakraClient(config)
    try:
        client.connect(timeout_seconds=connect_timeout)
    except Exception as exc:
        message = hint or (
            "Start Chakra in another terminal:\n"
            "  ./scripts/start_chakra.sh\n"
            "Ensure .env LLM credentials are configured."
        )
        print(f"ERROR: Could not connect to Chakra at {config.address}: {exc}", file=sys.stderr)
        print(message, file=sys.stderr)
        raise SystemExit(1) from exc
    return client


def consume_client_stream(
    client: ChakraClient,
    *,
    timeout_seconds: float | None = None,
    auto_approve: bool = True,
    print_text: bool = False,
) -> tuple[list[ServerEvent], list[str]]:
    """Consume a Chakra client stream with optional auto-approval."""
    events: list[ServerEvent] = []
    types: list[str] = []
    timeout = timeout_seconds if timeout_seconds is not None else turn_timeout()

    for event in client.iter_events(timeout_seconds=timeout):
        events.append(event)
        types.append(event.type.value)
        if event.type == EventType.TEXT_CHUNK and event.text and print_text:
            print(event.text, end="", flush=True)
        if event.type == EventType.ACTION_REQUIRED and auto_approve:
            client.send_user_input(event.prompt_id or "", "yes")
            logger.info("Auto-approved: %s", event.question)
        if event.type == EventType.TOOL_START:
            logger.info("Tool started: %s", event.tool_name)
        if event.type == EventType.TOOL_RESULT:
            logger.info("Tool result: %s (error=%s)", event.tool_name, event.is_error)
    if print_text:
        print()
    return events, types


def consume_harness_stream(
    stream: TurnStream,
    *,
    auto_approve: bool = True,
    print_text: bool = False,
    approve_reply: str = "yes",
) -> tuple[list[HarnessEvent], TurnResult]:
    """Consume a harness TurnStream, auto-approving interventions when requested."""
    events: list[HarnessEvent] = []
    for event in stream:
        events.append(event)
        if print_text and event.type == HarnessEventType.TEXT_DELTA:
            print(event.text, end="", flush=True)
        if isinstance(event, InterventionRequiredEvent):
            logger.info("Intervention required: %s", event.prompt)
            if auto_approve:
                stream.respond(
                    InterventionResponse(
                        intervention_id=event.intervention_id,
                        response=approve_reply,
                    )
                )
        if event.type == HarnessEventType.TOOL_STARTED:
            logger.info("Tool started: %s", event.tool_name)
        if event.type == HarnessEventType.TOOL_COMPLETED:
            logger.info("Tool completed: %s (error=%s)", event.tool_name, event.is_error)
    if print_text:
        print()
    return events, stream.result()


def event_types(events: list[Any]) -> list[str]:
    if not events:
        return []
    if isinstance(events[0], ServerEvent):
        return [e.type.value for e in events]
    return [e.type.value for e in events]
