"""Request models exchanged through the harness interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConnectionConfig:
    """Optional connection parameters. Adapters interpret fields as needed."""

    endpoint: str | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CreateSessionRequest:
    """Create a new harness session."""

    working_directory: str | None = None
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResumeSessionRequest:
    """Resume an existing harness session."""

    session_id: str
    working_directory: str | None = None
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SendMessageRequest:
    """Submit a user turn within a session."""

    message: str
    model: str | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InterventionResponse:
    """Reply to an intervention_required event during a turn."""

    intervention_id: str
    response: str


@dataclass(frozen=True)
class InterruptRequest:
    """Request interruption of the active turn."""

    reason: str = "client_interrupt"
