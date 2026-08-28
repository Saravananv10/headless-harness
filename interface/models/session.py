"""Session abstraction for multi-turn harness conversations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SessionState(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"


@dataclass
class HarnessSession:
    """
    Backend-independent session handle.

    Adapters map this to backend-specific identifiers (e.g. opaque session keys).
    """

    session_id: str
    state: SessionState = SessionState.ACTIVE
    working_directory: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    turn_count: int = 0

    def mark_closed(self) -> None:
        self.state = SessionState.CLOSED

    def is_active(self) -> bool:
        return self.state == SessionState.ACTIVE
