"""Response models returned by harness operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from interface.models.session import SessionState


@dataclass(frozen=True)
class UsageStats:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(frozen=True)
class ConnectionInfo:
    connected: bool
    endpoint: str | None = None
    adapter_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TurnResult:
    """Final outcome of a completed turn."""

    final_text: str
    usage: UsageStats = field(default_factory=UsageStats)
    turn_id: str | None = None
    session_id: str | None = None
    event_count: int = 0


@dataclass(frozen=True)
class SessionStatus:
    session_id: str
    state: SessionState
    turn_count: int
    working_directory: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class SessionCloseResult:
    session_id: str
    turn_count: int
    closed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
