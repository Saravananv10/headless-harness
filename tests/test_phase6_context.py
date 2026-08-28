"""Step 6.1 — validate controller context construction."""

from __future__ import annotations

from interface.models.session import HarnessSession

from controller import build_context
from engine.state import ConversationState, ConversationStatus, HistoryEntry, HistoryRole
from phase6_common import journal_entry, scan_controller_isolation


def main() -> int:
    session = HarnessSession(session_id="sess-ctx", working_directory="/tmp/project")
    state = ConversationState(
        conversation_id="conv-ctx",
        harness_session=session,
        status=ConversationStatus.ACTIVE,
    )
    state.history = [
        HistoryEntry(role=HistoryRole.USER, content="build hello.py", turn_id="t1"),
        HistoryEntry(role=HistoryRole.ASSISTANT, content="Created hello.py", turn_id="t1"),
    ]

    context = build_context(state, objective="Create hello.py in the working directory")
    payload = context.to_dict()
    required_keys = {
        "objective",
        "conversation_id",
        "conversation_status",
        "session_id",
        "session_state",
        "working_directory",
        "turn_count",
        "history",
        "recent_events",
    }
    leaks = scan_controller_isolation()
    ok = (
        not leaks
        and required_keys.issubset(payload.keys())
        and payload["working_directory"] == "/tmp/project"
        and len(payload["history"]) == 2
        and payload["last_assistant_message"] == "Created hello.py"
        and "grpc" not in str(payload).lower()
        and "chakra" not in str(payload).lower()
    )

    journal_entry(
        milestone="Step 6.1 — Controller Context",
        design_decisions=[
            "ControllerContext is built only from ExecutionEngine ConversationState.",
            "Context includes objective, session, history, and recent harness events.",
        ],
        implementation=["controller/context_builder.py"],
        validation="PASS" if ok else "FAIL",
        issues=leaks or ["None"],
        observations=[f"Context keys: {sorted(payload.keys())}"],
        conclusions=["Controller receives backend-neutral state for every decision."],
        next_steps=["Finalize prompting strategy."],
    )
    print("Step 6.1 PASS" if ok else "Step 6.1 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
