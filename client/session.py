"""Session lifecycle helpers for multi-turn Chakra conversations."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from client.chakra_client import ChakraClient, EventType, ServerEvent

logger = logging.getLogger(__name__)


@dataclass
class TurnRecord:
    """Record of a single user message and assistant response."""

    user_message: str
    assistant_text: str = ""
    events: list[ServerEvent] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None


@dataclass
class ChakraSession:
    """
    Manages a persistent Chakra session across multiple Chat streams.

    Chakra persists conversation history server-side when the same session_id
    is supplied on subsequent ChatRequest messages (see server.ts session store).
    Each turn uses a new bidirectional stream; context is keyed by session_id.
    """

    client: ChakraClient
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    working_directory: str = ""
    model: str | None = None
    turns: list[TurnRecord] = field(default_factory=list)
    closed: bool = False

    def send_message(
        self,
        message: str,
        *,
        auto_approve_tools: bool = True,
        timeout_seconds: float = 600.0,
    ) -> str:
        """Send a user message and return the assistant's final text."""
        if self.closed:
            raise RuntimeError("Session is closed")
        record = TurnRecord(user_message=message)
        self.turns.append(record)

        logger.info("Session %s turn %d: sending message", self.session_id, len(self.turns))

        self.client.open_stream()
        try:
            self.client.send_chat_request(
                message,
                session_id=self.session_id,
                working_directory=self.working_directory,
                model=self.model,
            )
            streamed: list[str] = []
            final_text = ""
            for event in self.client.iter_events(timeout_seconds=timeout_seconds):
                record.events.append(event)
                if event.type == EventType.TEXT_CHUNK and event.text:
                    streamed.append(event.text)
                elif event.type == EventType.ACTION_REQUIRED:
                    if auto_approve_tools:
                        self.client.send_user_input(event.prompt_id or "", "yes")
                    else:
                        raise RuntimeError(
                            f"Action required: {event.question}"
                        )
                elif event.type == EventType.DONE:
                    final_text = event.full_text or "".join(streamed)
                elif event.type == EventType.ERROR:
                    raise RuntimeError(
                        f"Server error [{event.error_code}]: {event.error_message}"
                    )
            record.assistant_text = final_text
            record.ended_at = datetime.now(timezone.utc)
            logger.info(
                "Session %s turn %d complete (%d chars)",
                self.session_id,
                len(self.turns),
                len(final_text),
            )
            return final_text
        finally:
            self.client.close_stream()

    def close(self) -> None:
        """Mark the session closed (client disconnect is separate)."""
        self.closed = True
        logger.info("Session %s closed after %d turns", self.session_id, len(self.turns))

    def summary(self) -> dict:
        return {
            "session_id": self.session_id,
            "turn_count": len(self.turns),
            "closed": self.closed,
            "working_directory": self.working_directory,
            "model": self.model,
        }
