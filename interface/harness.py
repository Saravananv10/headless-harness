"""Abstract harness interface implemented by all backend adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from interface.capabilities import HarnessCapabilities
from interface.events import HarnessEvent
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
)
from interface.models.session import HarnessSession


class TurnStream(ABC):
    """
    Active turn stream.

    Yields harness events until a terminal event is reached.
    Allows mid-turn intervention responses and cancellation.
    """

    @abstractmethod
    def __iter__(self) -> Iterator[HarnessEvent]:
        """Iterate events for this turn until terminal."""

    @abstractmethod
    def respond(self, response: InterventionResponse) -> None:
        """Reply to an intervention_required event."""

    @abstractmethod
    def cancel(self, request: InterruptRequest | None = None) -> None:
        """Interrupt the active turn."""

    @abstractmethod
    def result(self) -> TurnResult:
        """Return the final turn result after iteration completes."""


class Harness(ABC):
    """
    Backend-independent harness contract.

    Higher layers (execution engine, controller) depend only on this API.
    Concrete adapters translate these operations to backend-specific protocols.
    """

    @abstractmethod
    def connect(self, config: ConnectionConfig | None = None) -> ConnectionInfo:
        """Establish a connection to the harness backend."""

    @abstractmethod
    def disconnect(self) -> None:
        """Release connection resources."""

    @abstractmethod
    def connection_info(self) -> ConnectionInfo:
        """Return current connection state."""

    @abstractmethod
    def capabilities(self) -> HarnessCapabilities:
        """Advertise supported harness capabilities."""

    @abstractmethod
    def create_session(
        self, request: CreateSessionRequest | None = None
    ) -> HarnessSession:
        """Create a new conversation session."""

    @abstractmethod
    def resume_session(self, request: ResumeSessionRequest) -> HarnessSession:
        """Resume an existing session by identifier."""

    @abstractmethod
    def send_turn(
        self, session: HarnessSession, request: SendMessageRequest
    ) -> TurnStream:
        """Start a user turn and return a stream of harness events."""

    @abstractmethod
    def get_session_status(self, session: HarnessSession) -> SessionStatus:
        """Query session metadata and state."""

    @abstractmethod
    def close_session(self, session: HarnessSession) -> SessionCloseResult:
        """Close a session from the controller side."""
