"""Minimal gRPC client for the Chakra AgentService.Chat bidirectional stream."""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import grpc

from client.config import ChakraConfig, load_config
from client.generated import chakra_pb2, chakra_pb2_grpc

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    TEXT_CHUNK = "text_chunk"
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"
    ACTION_REQUIRED = "action_required"
    DONE = "done"
    ERROR = "error"
    STREAM_END = "stream_end"


@dataclass
class ServerEvent:
    """Normalized server event from the Chakra gRPC stream."""

    type: EventType
    text: str | None = None
    tool_name: str | None = None
    arguments_json: str | None = None
    tool_use_id: str | None = None
    output: str | None = None
    is_error: bool | None = None
    prompt_id: str | None = None
    question: str | None = None
    action_type: str | None = None
    full_text: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    error_message: str | None = None
    error_code: str | None = None
    raw: Any = field(default=None, repr=False)

    @classmethod
    def from_server_message(cls, msg: chakra_pb2.ServerMessage) -> ServerEvent:
        which = msg.WhichOneof("event")
        if which == "text_chunk":
            return cls(type=EventType.TEXT_CHUNK, text=msg.text_chunk.text, raw=msg)
        if which == "tool_start":
            t = msg.tool_start
            return cls(
                type=EventType.TOOL_START,
                tool_name=t.tool_name,
                arguments_json=t.arguments_json,
                tool_use_id=t.tool_use_id,
                raw=msg,
            )
        if which == "tool_result":
            t = msg.tool_result
            return cls(
                type=EventType.TOOL_RESULT,
                tool_name=t.tool_name,
                output=t.output,
                is_error=t.is_error,
                tool_use_id=t.tool_use_id,
                raw=msg,
            )
        if which == "action_required":
            a = msg.action_required
            return cls(
                type=EventType.ACTION_REQUIRED,
                prompt_id=a.prompt_id,
                question=a.question,
                action_type=chakra_pb2.ActionRequired.ActionType.Name(a.type),
                raw=msg,
            )
        if which == "done":
            d = msg.done
            return cls(
                type=EventType.DONE,
                full_text=d.full_text,
                prompt_tokens=d.prompt_tokens,
                completion_tokens=d.completion_tokens,
                raw=msg,
            )
        if which == "error":
            e = msg.error
            return cls(
                type=EventType.ERROR,
                error_message=e.message,
                error_code=e.code,
                raw=msg,
            )
        return cls(type=EventType.STREAM_END, raw=msg)


ActionHandler = Callable[[ServerEvent], str | None]


class ChakraClient:
    """Thin Python client over chakra.v1.AgentService/Chat."""

    def __init__(self, config: ChakraConfig | None = None) -> None:
        self.config = config or load_config()
        self._channel: grpc.Channel | None = None
        self._stub: chakra_pb2_grpc.AgentServiceStub | None = None
        self._request_queue: queue.Queue[chakra_pb2.ClientMessage | None] | None = None
        self._responses: Any = None
        self._reader_thread: threading.Thread | None = None
        self._events: list[ServerEvent] = []
        self._event_lock = threading.Lock()
        self._stream_error: Exception | None = None
        self._stream_closed = threading.Event()

    def connect(self, timeout_seconds: float = 50.0) -> None:
        """Open an insecure gRPC channel and verify the server is reachable."""
        address = self.config.address
        logger.info("Connecting to Chakra gRPC at %s", address)
        self._channel = grpc.insecure_channel(address)
        grpc.channel_ready_future(self._channel).result(timeout=timeout_seconds)
        self._stub = chakra_pb2_grpc.AgentServiceStub(self._channel)
        logger.info("Connected to Chakra gRPC at %s", address)

    def disconnect(self) -> None:
        """Close the active stream and channel."""
        self.close_stream()
        if self._channel is not None:
            self._channel.close()
            self._channel = None
            self._stub = None
            logger.info("Disconnected from Chakra gRPC")

    def is_connected(self) -> bool:
        return self._channel is not None and self._stub is not None

    def open_stream(self) -> None:
        """Open a bidirectional Chat stream."""
        if not self._stub:
            raise RuntimeError("Not connected — call connect() first")
        if self._request_queue is not None:
            raise RuntimeError("Stream already open on this client")
        self._events.clear()
        self._stream_error = None
        self._stream_closed.clear()
        self._request_queue = queue.Queue()

        def request_iterator():
            assert self._request_queue is not None
            while True:
                msg = self._request_queue.get()
                if msg is None:
                    return
                yield msg

        self._responses = self._stub.Chat(request_iterator())
        self._reader_thread = threading.Thread(
            target=self._read_loop, name="chakra-grpc-reader", daemon=True
        )
        self._reader_thread.start()
        logger.info("Opened Chat stream")

    def close_stream(self) -> None:
        """End the current Chat stream."""
        if self._request_queue is not None:
            self._request_queue.put(None)
            self._request_queue = None
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=5.0)
            self._reader_thread = None
        self._responses = None
        self._stream_closed.set()
        logger.info("Closed Chat stream")

    def _write(self, envelope: chakra_pb2.ClientMessage) -> None:
        if self._request_queue is None:
            raise RuntimeError("No open stream — call open_stream() first")
        self._request_queue.put(envelope)

    def send_chat_request(
        self,
        message: str,
        *,
        session_id: str = "",
        working_directory: str = "",
        model: str | None = None,
    ) -> None:
        """Send the initial ChatRequest on the open stream."""
        if self._request_queue is None:
            raise RuntimeError("No open stream — call open_stream() first")
        req = chakra_pb2.ChatRequest(
            message=message,
            working_directory=working_directory,
            session_id=session_id,
        )
        if model:
            req.model = model
        envelope = chakra_pb2.ClientMessage(request=req)
        self._write(envelope)
        logger.info(
            "Sent ChatRequest session_id=%r message_len=%d",
            session_id or "(new)",
            len(message),
        )

    def send_user_input(self, prompt_id: str, reply: str) -> None:
        """Reply to an action_required prompt."""
        if self._request_queue is None:
            raise RuntimeError("No open stream")
        self._write(
            chakra_pb2.ClientMessage(
                input=chakra_pb2.UserInput(prompt_id=prompt_id, reply=reply)
            )
        )
        logger.info("Sent UserInput prompt_id=%s reply=%r", prompt_id, reply)

    def send_cancel(self, reason: str = "client_cancel") -> None:
        """Interrupt the current generation."""
        if self._request_queue is None:
            raise RuntimeError("No open stream")
        self._write(
            chakra_pb2.ClientMessage(
                cancel=chakra_pb2.CancelSignal(reason=reason)
            )
        )
        logger.info("Sent CancelSignal reason=%r", reason)

    def iter_events(self, timeout_seconds: float | None = None) -> Iterator[ServerEvent]:
        """Yield server events until done, error, or stream end.

        When ``timeout_seconds`` is set, raises ``TimeoutError`` only after that
        many seconds without receiving a new event (idle-based; reset per event).
        """
        last_event_at = time.monotonic()
        index = 0
        while True:
            with self._event_lock:
                if index < len(self._events):
                    event = self._events[index]
                    index += 1
                elif self._stream_error is not None:
                    raise self._stream_error
                elif self._stream_closed.is_set() and index >= len(self._events):
                    return
                else:
                    event = None
            if event is not None:
                last_event_at = time.monotonic()
                yield event
                if event.type in (EventType.DONE, EventType.ERROR):
                    return
                continue
            if timeout_seconds and (time.monotonic() - last_event_at) > timeout_seconds:
                raise TimeoutError("Timed out waiting for server events")
            time.sleep(0.05)

    def chat(
        self,
        message: str,
        *,
        session_id: str = "",
        working_directory: str = "",
        model: str | None = None,
        on_action_required: ActionHandler | None = None,
        auto_approve_tools: bool = False,
        timeout_seconds: float =600.0,
    ) -> str:
        """
        Send one chat turn on a fresh stream and return the final text.

        Opens a stream, sends the request, consumes events until done/error,
        then closes the stream.
        """
        self.open_stream()
        try:
            self.send_chat_request(
                message,
                session_id=session_id,
                working_directory=working_directory,
                model=model,
            )
            streamed_text: list[str] = []
            final_text = ""
            for event in self.iter_events(timeout_seconds=timeout_seconds):
                logger.debug("Event: %s", event.type.value)
                if event.type == EventType.TEXT_CHUNK and event.text:
                    streamed_text.append(event.text)
                elif event.type == EventType.ACTION_REQUIRED:
                    reply = None
                    if on_action_required:
                        reply = on_action_required(event)
                    elif auto_approve_tools:
                        reply = "yes"
                    if reply is None:
                        raise RuntimeError(
                            f"Action required but no handler: {event.question}"
                        )
                    self.send_user_input(event.prompt_id or "", reply)
                elif event.type == EventType.DONE:
                    final_text = event.full_text or "".join(streamed_text)
                elif event.type == EventType.ERROR:
                    raise RuntimeError(
                        f"Server error [{event.error_code}]: {event.error_message}"
                    )
            return final_text
        finally:
            self.close_stream()

    def _read_loop(self) -> None:
        assert self._responses is not None
        try:
            for msg in self._responses:
                event = ServerEvent.from_server_message(msg)
                with self._event_lock:
                    self._events.append(event)
                if event.type in (EventType.DONE, EventType.ERROR):
                    break
        except grpc.RpcError as exc:
            self._stream_error = exc
            logger.error("gRPC stream error: %s", exc)
        finally:
            self._stream_closed.set()

    def inspect_service(self) -> dict[str, Any]:
        """Return static metadata about the configured gRPC service."""
        return {
            "address": self.config.address,
            "service": self.config.service_name,
            "method": self.config.method_name,
            "proto": str(self.config.proto_path),
            "transport": "gRPC bidirectional streaming (insecure)",
            "client_messages": ["ChatRequest", "UserInput", "CancelSignal"],
            "server_events": [
                "text_chunk",
                "tool_start",
                "tool_result",
                "action_required",
                "done",
                "error",
            ],
        }
