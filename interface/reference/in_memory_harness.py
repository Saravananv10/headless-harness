"""Reference in-memory harness for contract validation (not a production adapter)."""

from __future__ import annotations

import uuid
from collections import deque
from collections.abc import Iterator

from interface.capabilities import HarnessCapabilities, HarnessCapability
from interface.events import (
    HarnessEvent,
    InterventionKind,
    InterventionRequiredEvent,
    TextDeltaEvent,
    ToolCompletedEvent,
    ToolStartedEvent,
    TurnCompletedEvent,
    TurnFailedEvent,
    is_terminal_event,
)
from interface.exceptions import (
    HarnessNotConnectedError,
    HarnessSessionError,
    HarnessTurnError,
)
from interface.harness import Harness, TurnStream
from interface.models.requests import (
    ConnectionConfig,
    CreateSessionRequest,
    InterruptRequest,
    InterventionResponse,
    ResumeSessionRequest,
    SendMessageRequest,
)
from interface.models.responses import (
    ConnectionInfo,
    SessionCloseResult,
    SessionStatus,
    TurnResult,
    UsageStats,
)
from interface.models.session import HarnessSession


class _TurnIterator:
    def __init__(self, stream: "InMemoryTurnStream") -> None:
        self._stream = stream
        if not stream._primed:
            stream._prime()
            stream._primed = True

    def __iter__(self) -> "_TurnIterator":
        return self

    def __next__(self) -> HarnessEvent:
        if not self._stream._queue:
            raise StopIteration
        event = self._stream._queue.popleft()
        self._stream._events.append(event)
        if is_terminal_event(event):
            self._stream._finished = True
        return event


class InMemoryTurnStream(TurnStream):
    def __init__(
        self,
        session: HarnessSession,
        request: SendMessageRequest,
        history: list[str],
    ) -> None:
        self._session = session
        self._request = request
        self._history = history
        self._queue: deque[HarnessEvent] = deque()
        self._events: list[HarnessEvent] = []
        self._primed = False
        self._finished = False
        self._cancelled = False
        self._turn_id = str(uuid.uuid4())
        self._awaiting_intervention = False

    def _prime(self) -> None:
        message = self._request.message.strip()
        if message == "force_error":
            self._queue.append(TurnFailedEvent(message="simulated failure", code="SIMULATED"))
            return

        if message == "tool_flow":
            self._queue.append(
                ToolStartedEvent(
                    tool_name="shell",
                    arguments={"command": "echo test"},
                    invocation_id="inv-1",
                )
            )
            self._queue.append(
                InterventionRequiredEvent(
                    intervention_id="int-1",
                    prompt="Approve shell?",
                    kind=InterventionKind.CONFIRM_ACTION,
                )
            )
            self._awaiting_intervention = True
            return

        prior = f" (prior turns: {len(self._history)})" if self._history else ""
        text = f"Echo: {message}{prior}"
        for word in text.split():
            self._queue.append(TextDeltaEvent(text=word + " "))
        self._queue.append(
            TurnCompletedEvent(
                final_text=text,
                usage={"prompt_tokens": 1, "completion_tokens": len(text.split())},
            )
        )
        if message:
            self._history.append(message)

    def __iter__(self) -> Iterator[HarnessEvent]:
        return _TurnIterator(self)

    def respond(self, response: InterventionResponse) -> None:
        if not self._awaiting_intervention:
            raise HarnessTurnError("No pending intervention")
        approved = response.response.strip().lower() in {"y", "yes"}
        self._queue.append(
            ToolCompletedEvent(
                tool_name="shell",
                invocation_id="inv-1",
                output="ok" if approved else "denied",
                is_error=not approved,
            )
        )
        self._queue.append(TurnCompletedEvent(final_text="tool flow complete"))
        self._awaiting_intervention = False

    def cancel(self, request: InterruptRequest | None = None) -> None:
        self._cancelled = True
        self._queue.clear()
        self._finished = True

    def result(self) -> TurnResult:
        terminal = next((e for e in reversed(self._events) if is_terminal_event(e)), None)
        if terminal is None:
            raise HarnessTurnError("Turn has no terminal event")
        if isinstance(terminal, TurnFailedEvent):
            raise HarnessTurnError(terminal.message)
        usage = UsageStats()
        final_text = ""
        if isinstance(terminal, TurnCompletedEvent):
            final_text = terminal.final_text
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


class InMemoryHarness(Harness):
    """Minimal harness used to validate the abstract contract."""

    def __init__(self) -> None:
        self._connected = False
        self._sessions: dict[str, list[str]] = {}

    def connect(self, config: ConnectionConfig | None = None) -> ConnectionInfo:
        self._connected = True
        endpoint = config.endpoint if config else "memory://harness"
        return ConnectionInfo(connected=True, endpoint=endpoint, adapter_name="in_memory")

    def disconnect(self) -> None:
        self._connected = False

    def connection_info(self) -> ConnectionInfo:
        return ConnectionInfo(connected=self._connected, adapter_name="in_memory")

    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities(
            supported=frozenset(
                {
                    HarnessCapability.CONNECT,
                    HarnessCapability.DISCONNECT,
                    HarnessCapability.STREAMING,
                    HarnessCapability.SESSIONS,
                    HarnessCapability.SESSION_RESUME,
                    HarnessCapability.TOOL_EXECUTION,
                    HarnessCapability.INTERACTIVE_APPROVAL,
                    HarnessCapability.CANCELLATION,
                }
            )
        )

    def create_session(
        self, request: CreateSessionRequest | None = None
    ) -> HarnessSession:
        self._require_connected()
        session_id = str(uuid.uuid4())
        session = HarnessSession(
            session_id=session_id,
            working_directory=request.working_directory if request else None,
        )
        self._sessions[session_id] = []
        return session

    def resume_session(self, request: ResumeSessionRequest) -> HarnessSession:
        self._require_connected()
        self._sessions.setdefault(request.session_id, [])
        return HarnessSession(
            session_id=request.session_id,
            working_directory=request.working_directory,
        )

    def send_turn(
        self, session: HarnessSession, request: SendMessageRequest
    ) -> TurnStream:
        self._require_connected()
        if not session.is_active():
            raise HarnessSessionError("Session is closed")
        history = self._sessions.setdefault(session.session_id, [])
        session.turn_count += 1
        return InMemoryTurnStream(session, request, history)

    def get_session_status(self, session: HarnessSession) -> SessionStatus:
        return SessionStatus(
            session_id=session.session_id,
            state=session.state,
            turn_count=session.turn_count,
            working_directory=session.working_directory,
            metadata=dict(session.metadata),
        )

    def close_session(self, session: HarnessSession) -> SessionCloseResult:
        session.mark_closed()
        return SessionCloseResult(
            session_id=session.session_id,
            turn_count=session.turn_count,
        )

    def _require_connected(self) -> None:
        if not self._connected:
            raise HarnessNotConnectedError("Harness is not connected")
