"""JSONL conversation tracing — dual raw + normalized channels (Phase 5)."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from controller.completion import CompletionMode
from controller.trace_normalize import normalize_harness_event, serialize_harness_event
from engine.types import EngineNotification, EngineNotificationKind
from interface.events import HarnessEvent

DEFAULT_LOG_ROOT = Path("logs")


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{uuid.uuid4().hex[:8]}"


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    if is_dataclass(value):
        return asdict(value)
    # #region agent log
    try:
        import time as _time

        with open(
            "/Users/anuragupperwal/Documents/Coding/Internship_Soket/temp_harness_h/.cursor/debug-ec07a5.log",
            "a",
            encoding="utf-8",
        ) as _df:
            _df.write(
                json.dumps(
                    {
                        "sessionId": "ec07a5",
                        "runId": "post-fix",
                        "hypothesisId": "B",
                        "location": "trace.py:_json_default",
                        "message": "unhandled type in _json_default",
                        "data": {"type_name": type(value).__name__, "repr": repr(value)[:200]},
                        "timestamp": int(_time.time() * 1000),
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


class ConversationTrace:
    """
    Append-only dual-channel trace:

    - ``trace.jsonl`` — normalized orchestration records
    - ``raw_events.jsonl`` — faithful harness / Chakra event snapshots

    Both channels share one monotonic ``seq`` so a full replay can merge by order.
    """

    def __init__(
        self,
        run_id: str,
        log_root: Path | str = DEFAULT_LOG_ROOT,
        completion_mode: CompletionMode | None = None,
        session_id: str | None = None,
    ) -> None:

        self.run_id = run_id
        self.directory = Path(log_root) / run_id
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "trace.jsonl"
        self.raw_path = self.directory / "raw_events.jsonl"
        self.completion_mode = completion_mode
        self._sequence = 0
        self._last_prompt_tokens: int | None = None
        self.session_id = session_id or f"session_{run_id}"

        # Langfuse Observability Integration
        import os
        import logging
        for _logger in ["langfuse", "opentelemetry", "opentelemetry.sdk", "opentelemetry.sdk.trace", "opentelemetry.exporter"]:
            logging.getLogger(_logger).setLevel(logging.CRITICAL)
        os.environ["LANGFUSE_DEBUG"] = "False"
        os.environ["LANGFUSE_LOG_LEVEL"] = "ERROR"

        self._langfuse_client = None
        self._trace_context = None
        pub_key = (os.getenv("LANGFUSE_PUBLIC_KEY") or "").strip('"\' ')
        sec_key = (os.getenv("LANGFUSE_SECRET_KEY") or "").strip('"\' ')
        host = (os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com").strip('"\' ').rstrip('/')

        if pub_key and sec_key:
            try:
                from langfuse import Langfuse
                from langfuse.types import TraceContext
                client = Langfuse(
                    public_key=pub_key,
                    secret_key=sec_key,
                    host=host,
                )
                if client.auth_check():
                    self._langfuse_client = client
                    self._trace_id = client.create_trace_id()
                    self._trace_context = TraceContext(
                        trace_id=self._trace_id,
                        session_id=self.session_id,
                    )
            except Exception:
                self._langfuse_client = None

    def log(self, record_type: str, **fields: Any) -> None:
        """Append a normalized orchestration record."""
        self._append(self.path, record_type, channel="normalized", **fields)
        if self._langfuse_client:
            try:
                inp = fields.get("messages") or fields.get("message") or fields.get("action")
                out = fields.get("raw") or fields.get("response") or fields.get("detail") or fields.get("summary")
                self._langfuse_client.create_event(
                    name=f"task:{self.run_id}:{record_type}",
                    trace_context=self._trace_context,
                    input=inp,
                    output=out,
                    metadata={"run_id": self.run_id, "session_id": self.session_id, **fields},
                )
            except Exception:
                pass

    def log_raw(self, record_type: str, **fields: Any) -> None:
        """Append a raw-channel record (harness/Chakra event snapshot)."""
        self._append(self.raw_path, record_type, channel="raw", **fields)
        if self._langfuse_client:
            try:
                inp = fields.get("event") or fields.get("request") or fields.get("message")
                out = fields.get("detail") or fields.get("response") or fields.get("raw")
                self._langfuse_client.create_event(
                    name=f"raw:{self.run_id}:{record_type}",
                    trace_context=self._trace_context,
                    input=inp,
                    output=out,
                    metadata={"run_id": self.run_id, "session_id": self.session_id, **fields},
                )
            except Exception:
                pass



    def flush(self) -> None:
        """Flush pending Langfuse traces to cloud/server."""
        if self._langfuse_client:
            try:
                self._langfuse_client.flush()
            except Exception:
                pass


    def _append(self, path: Path, record_type: str, *, channel: str, **fields: Any) -> None:
        self._sequence += 1
        record = {
            "seq": self._sequence,
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "channel": channel,
            "type": record_type,
            **fields,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=_json_default, ensure_ascii=False) + "\n")

    def log_controller_llm_request(
        self,
        *,
        purpose: str,
        messages: list[dict[str, str]],
        temperature: float,
        attempt: int = 1,
    ) -> None:
        self.log(
            "controller_llm_request",
            purpose=purpose,
            attempt=attempt,
            temperature=temperature,
            messages=messages,
        )

    def log_controller_llm_response(
        self,
        *,
        purpose: str,
        raw: str,
        attempt: int = 1,
    ) -> None:
        self.log(
            "controller_llm_response",
            purpose=purpose,
            attempt=attempt,
            raw=raw,
        )

    def log_controller_action(self, action: dict[str, Any], *, purpose: str = "decision") -> None:
        self.log("controller_action", purpose=purpose, action=action)

    def log_backend_turn_start(self, *, message: str, turn_id: str | None = None) -> None:
        self.log("backend_turn_start", message=message, turn_id=turn_id)

    def log_backend_event(self, event: HarnessEvent, *, turn_id: str | None = None) -> None:
        """Legacy helper — prefer log_engine_notification (writes raw + normalized)."""
        self._write_harness_event(event, turn_id=turn_id, conversation_id=None)

    def log_backend_intervention_response(
        self,
        *,
        intervention_id: str,
        prompt: str,
        response: str,
        reasoning: str = "",
    ) -> None:
        self.log(
            "backend_intervention_response",
            intervention_id=intervention_id,
            prompt=prompt,
            response=response,
            reasoning=reasoning,
        )

    def log_tool_approval(self, approval: dict[str, Any]) -> None:
        """Record a Phase-4 automatic tool approval (request + response + metadata)."""
        self.log("tool_approval", **dict(approval))

    def log_chakra_raw_event(
        self,
        payload: dict[str, Any],
        *,
        turn_id: str | None = None,
        session_id: str | None = None,
        dropped: bool = False,
    ) -> None:
        """Persist a raw Chakra ServerEvent snapshot (including untranslated ones)."""
        self.log_raw(
            "chakra_server_event",
            turn_id=turn_id,
            session_id=session_id,
            dropped=dropped,
            chakra_raw=payload,
        )

    def log_engine_notification(self, notification: EngineNotification) -> None:
        """Write raw + normalized records for one engine notification (exact order)."""
        detail = dict(notification.detail)
        turn_id = detail.get("turn_id")
        conversation_id = notification.conversation_id

        if notification.kind == EngineNotificationKind.EVENT_RECEIVED and notification.event:
            self._write_harness_event(
                notification.event,
                turn_id=turn_id,
                conversation_id=conversation_id,
            )
            return

        if notification.kind == EngineNotificationKind.TURN_STARTED:
            self.log(
                "backend_turn_start",
                message=detail.get("message", ""),
                turn_id=turn_id,
                conversation_id=conversation_id,
            )
            return

        if notification.kind == EngineNotificationKind.INTERVENTION_REQUIRED and notification.event:
            # Raw + normalized already written on EVENT_RECEIVED for the same event.
            return

        if notification.kind == EngineNotificationKind.INTERVENTION_RESOLVED:
            self.log(
                "intervention_resolved",
                turn_id=turn_id,
                conversation_id=conversation_id,
                response=detail.get("response"),
            )
            return

        if notification.kind == EngineNotificationKind.TURN_COMPLETED:
            if notification.event:
                # TurnCompleted may already have been logged via EVENT_RECEIVED.
                # Emit a lightweight turn boundary marker only.
                self.log(
                    "backend_turn_completed",
                    turn_id=turn_id,
                    conversation_id=conversation_id,
                    detail=detail,
                )
            else:
                self.log(
                    "backend_turn_completed",
                    turn_id=turn_id,
                    conversation_id=conversation_id,
                    detail=detail,
                )
            return

        if notification.kind == EngineNotificationKind.TURN_FAILED:
            if notification.event:
                self.log(
                    "backend_turn_failed",
                    turn_id=turn_id,
                    conversation_id=conversation_id,
                    detail=detail,
                )
            else:
                self.log(
                    "error",
                    turn_id=turn_id,
                    conversation_id=conversation_id,
                    message=detail.get("message"),
                    code=detail.get("code"),
                    detail=detail,
                )
            return

        self.log(
            "engine_notification",
            kind=notification.kind.value,
            conversation_id=conversation_id,
            detail=detail,
        )

    def _write_harness_event(
        self,
        event: HarnessEvent,
        *,
        turn_id: str | None,
        conversation_id: str | None,
    ) -> None:
        # Raw channel first (preserve exact stream fidelity for replay/parsers).
        raw_payload = serialize_harness_event(event)
        self.log_raw(
            "harness_event",
            turn_id=turn_id,
            conversation_id=conversation_id,
            **raw_payload,
        )

        # Normalized orchestration records (assistant / tools / agents / markers).
        for normalized in normalize_harness_event(
            event,
            completion_mode=self.completion_mode,
            previous_prompt_tokens=self._last_prompt_tokens,
        ):
            ntype = str(normalized.pop("normalized_type"))
            if ntype == "token_usage":
                try:
                    self._last_prompt_tokens = int(
                        normalized.get("prompt_tokens")
                        or normalized.get("input_tokens")
                        or 0
                    ) or self._last_prompt_tokens
                except (TypeError, ValueError):
                    pass
            self.log(
                ntype,
                turn_id=turn_id,
                conversation_id=conversation_id,
                **normalized,
            )
