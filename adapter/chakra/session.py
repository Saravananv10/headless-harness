"""Session mapping between HarnessSession and Chakra session identifiers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from interface.models.requests import CreateSessionRequest, ResumeSessionRequest
from interface.models.responses import SessionCloseResult, SessionStatus
from interface.models.session import HarnessSession, SessionState


def create_harness_session(request: CreateSessionRequest | None = None) -> HarnessSession:
    """Create a new harness session backed by a Chakra session_id."""
    session_id = str(uuid.uuid4())
    working_directory = request.working_directory if request else None
    metadata: dict = {}
    if request and request.model:
        metadata["model"] = request.model
    if request and request.metadata:
        metadata.update(request.metadata)
    return HarnessSession(
        session_id=session_id,
        working_directory=working_directory,
        metadata=metadata,
    )


def resume_harness_session(request: ResumeSessionRequest) -> HarnessSession:
    """Resume an existing Chakra session through the harness abstraction."""
    metadata: dict = {}
    if request.model:
        metadata["model"] = request.model
    if request.metadata:
        metadata.update(request.metadata)
    return HarnessSession(
        session_id=request.session_id,
        working_directory=request.working_directory,
        metadata=metadata,
    )


def to_session_status(session: HarnessSession) -> SessionStatus:
    return SessionStatus(
        session_id=session.session_id,
        state=session.state,
        turn_count=session.turn_count,
        working_directory=session.working_directory,
        metadata=dict(session.metadata),
        updated_at=datetime.now(timezone.utc),
    )


def close_harness_session(session: HarnessSession) -> SessionCloseResult:
    session.mark_closed()
    return SessionCloseResult(
        session_id=session.session_id,
        turn_count=session.turn_count,
        closed_at=datetime.now(timezone.utc),
    )
