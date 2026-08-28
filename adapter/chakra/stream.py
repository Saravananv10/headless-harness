"""Streaming adapter bridging Chakra client streams to harness TurnStream."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Iterator
from typing import Any

from client.chakra_client import ChakraClient, EventType

from adapter.chakra.translator import serialize_server_event, translate_server_event
from interface.events import (
    HarnessEvent,
    InterventionRequiredEvent,
    TurnCompletedEvent,
    TurnFailedEvent,
    is_terminal_event,
)
from interface.exceptions import HarnessTurnError
from interface.harness import TurnStream
from interface.models.requests import InterruptRequest, InterventionResponse, SendMessageRequest
from interface.models.responses import TurnResult, UsageStats
from interface.models.session import HarnessSession

logger = logging.getLogger(__name__)

RawEventSink = Callable[[dict[str, Any]], None]


class ChakraTurnStream(TurnStream):
    """Adapter TurnStream over a single Chakra Chat bidi stream."""

    def __init__(
        self,
        client: ChakraClient,
        session: HarnessSession,
        request: SendMessageRequest,
        *,
        timeout_seconds: float = 600.0,
        on_raw_event: RawEventSink | None = None,
    ) -> None:
        self._client = client
        self._session = session
        self._request = request
        self._timeout_seconds = timeout_seconds
        self._turn_id = str(uuid.uuid4())
        self._events: list[HarnessEvent] = []
        self._started = False
        self._closed = False
        self._raw_iter: Iterator | None = None
        self._stream_text: list[str] = []
        self._on_raw_event = on_raw_event

    def _start(self) -> None:
        if self._started:
            return
        self._client.open_stream()
        model = self._request.model or self._session.metadata.get("model")
        working_directory = self._session.working_directory or ""
        self._client.send_chat_request(
            self._request.message,
            session_id=self._session.session_id,
            working_directory=working_directory,
            model=model,
        )
        self._raw_iter = self._client.iter_events(timeout_seconds=self._timeout_seconds)
        self._started = True
        logger.debug(
            "Started Chakra turn stream session=%s turn=%s",
            self._session.session_id,
            self._turn_id,
        )

    def _close_backend_stream(self) -> None:
        if self._started and not self._closed:
            self._client.close_stream()
            self._closed = True

    def __iter__(self) -> Iterator[HarnessEvent]:
        return self

    def __next__(self) -> HarnessEvent:
        if self._closed and not self._events:
            raise StopIteration
        self._start()
        assert self._raw_iter is not None

        while True:
            try:
                raw = next(self._raw_iter)
            except StopIteration:
                self._close_backend_stream()
                raise
            except Exception as exc:
                self._close_backend_stream()
                failed = TurnFailedEvent(message=str(exc), code="STREAM_ERROR")
                self._events.append(failed)
                raise HarnessTurnError(str(exc)) from exc

            if raw.type == EventType.TEXT_CHUNK and raw.text:
                self._stream_text.append(raw.text)

            translated = translate_server_event(
                raw,
                session_id=self._session.session_id,
                turn_id=self._turn_id,
            )
            if translated is None:
                # Preserve untranslated Chakra events (e.g. STREAM_END) when a sink is set.
                if self._on_raw_event is not None:
                    self._on_raw_event(serialize_server_event(raw))
                continue

            self._events.append(translated)
            if is_terminal_event(translated):
                self._close_backend_stream()
            return translated

    def respond(self, response: InterventionResponse) -> None:
        if not self._started:
            raise HarnessTurnError("Cannot respond before turn stream starts")
        self._client.send_user_input(response.intervention_id, response.response)
        logger.debug("Sent intervention response id=%s", response.intervention_id)

    def cancel(self, request: InterruptRequest | None = None) -> None:
        if not self._started:
            return
        reason = request.reason if request else "client_interrupt"
        self._client.send_cancel(reason)
        self._close_backend_stream()
        logger.debug("Cancelled Chakra turn stream reason=%s", reason)

    def result(self) -> TurnResult:
        terminal = next((e for e in reversed(self._events) if is_terminal_event(e)), None)
        if terminal is None:
            raise HarnessTurnError("Turn has no terminal harness event")

        if isinstance(terminal, TurnFailedEvent):
            raise HarnessTurnError(f"{terminal.code}: {terminal.message}")

        final_text = ""
        usage = UsageStats()
        if isinstance(terminal, TurnCompletedEvent):
            final_text = terminal.final_text or "".join(self._stream_text)
            usage = UsageStats(
                prompt_tokens=terminal.usage.get("prompt_tokens", 0),
                completion_tokens=terminal.usage.get("completion_tokens", 0),
            )

        return TurnResult(
            final_text=final_text,
            usage=usage,
            turn_id=self._turn_id,
            session_id=self._session.session_id,
            event_count=len(self._events),
        )
