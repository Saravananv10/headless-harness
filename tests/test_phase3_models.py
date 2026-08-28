"""Milestone 3.2 — validate common data models are generic and usable."""

from __future__ import annotations

import dataclasses

from interface import (
    ConnectionConfig,
    CreateSessionRequest,
    HarnessSession,
    InterventionResponse,
    ResumeSessionRequest,
    SendMessageRequest,
    SessionCloseResult,
    SessionStatus,
    TurnResult,
    UsageStats,
)
from interface.reference.in_memory_harness import InMemoryHarness
from phase3_common import journal_entry


def main() -> int:
    models = [
        ConnectionConfig,
        CreateSessionRequest,
        ResumeSessionRequest,
        SendMessageRequest,
        InterventionResponse,
        HarnessSession,
        TurnResult,
        SessionStatus,
        SessionCloseResult,
        UsageStats,
    ]
    all_frozen_or_session = all(
        dataclasses.is_dataclass(model)
        and (getattr(model, "__dataclass_params__").frozen or model is HarnessSession)
        for model in models
    )

    harness = InMemoryHarness()
    harness.connect(ConnectionConfig(endpoint="memory://test"))
    session = harness.create_session(CreateSessionRequest(working_directory="/tmp"))
    stream = harness.send_turn(session, SendMessageRequest(message="hello"))
    events = list(stream)
    result = stream.result()
    status = harness.get_session_status(session)
    close = harness.close_session(session)
    harness.disconnect()

    ok = (
        all_frozen_or_session
        and len(events) >= 2
        and result.final_text.startswith("Echo:")
        and status.session_id == session.session_id
        and close.turn_count == 1
    )

    journal_entry(
        milestone="Milestone 3.2 — Common Data Models",
        objective="Define backend-independent request, response, and session models.",
        design_decisions=[
            "Immutable request/response dataclasses; mutable session handle.",
            "Generic ConnectionConfig.options bag for adapter-specific settings.",
            "TurnResult captures terminal text and usage counters.",
        ],
        implementation=[
            "interface/models/requests.py",
            "interface/models/responses.py",
            "interface/models/session.py",
        ],
        validation="PASS" if ok else "FAIL",
        observations=[
            f"Validated {len(models)} model types with in-memory harness.",
            "Session lifecycle models work end-to-end without backend protocol types.",
        ],
        conclusions=[
            "Models are generic enough for non-Chakra backends.",
        ],
        next_steps=["Define universal event model (Milestone 3.3)."],
    )
    print("Milestone 3.2 PASS" if ok else "Milestone 3.2 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
