"""Unit tests for context budget: intervention caps and lean resume nudges."""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.completion import CompletionMode
from controller.context_builder import (
    ARG_PREVIEW_LIMIT,
    INTERVENTION_HISTORY_CAP,
    TOOL_EVENTS_CAP,
    build_intervention_context,
)
from controller.orchestration_state import OrchestrationState
from controller.trace_normalize import normalize_harness_event
from controller.workflow_common import lean_verifier_report_block
from engine.state import (
    ConversationState,
    ConversationStatus,
    EventRecord,
    HistoryEntry,
    HistoryRole,
    TurnState,
    TurnStatus,
)
from engine.types import EngineNotification, EngineNotificationKind
from interface.events import (
    HarnessEventType,
    ToolCompletedEvent,
    ToolStartedEvent,
    TurnCompletedEvent,
)
from interface.models.session import HarnessSession


def _state_with_tools(n_tools: int, *, history_lines: int = 5) -> ConversationState:
    session = HarnessSession(
        session_id="s1",
        working_directory="/tmp/repo",
    )
    state = ConversationState(
        conversation_id="c1",
        harness_session=session,
        status=ConversationStatus.ACTIVE,
    )
    turn = TurnState(turn_id="t1", user_message="go", status=TurnStatus.IN_PROGRESS)
    for i in range(n_tools):
        turn.events.append(
            EventRecord(
                event_type=HarnessEventType.TOOL_STARTED,
                payload={
                    "tool_name": "Write" if i % 2 == 0 else "Bash",
                    "arguments": {
                        "content": "X" * 5000 if i % 2 == 0 else "echo hi",
                        "command": "echo hi",
                        "file_path": f"/tmp/repo/f{i}.py",
                    },
                    "invocation_id": f"inv{i}",
                },
                timestamp=datetime.now(timezone.utc),
            )
        )
    state.turns.append(turn)
    state.active_turn = turn
    for i in range(history_lines):
        role = HistoryRole.USER if i % 2 == 0 else HistoryRole.ASSISTANT
        state.history.append(
            HistoryEntry(
                role=role,
                content=f"message {i} " + ("body " * 50),
                turn_id="t1",
            )
        )
    return state


def test_intervention_context_caps_tool_events_and_history() -> None:
    state = _state_with_tools(80, history_lines=10)
    payload = build_intervention_context(
        state,
        objective="",
        intervention_id="i1",
        prompt="Approve Write?",
        kind="confirm_action",
    )
    assert len(payload["tool_events"]) <= TOOL_EVENTS_CAP
    assert len(payload["history"]) <= INTERVENTION_HISTORY_CAP
    found_truncated = False
    for event in payload["tool_events"]:
        args = (event.get("payload") or {}).get("arguments") or {}
        content = args.get("content")
        if isinstance(content, str) and content.endswith("..."):
            assert len(content) <= ARG_PREVIEW_LIMIT
            found_truncated = True
    assert found_truncated


def test_lean_verifier_report_persists_and_stays_short() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        huge = "FAIL DETAIL\n" + ("line of failure evidence\n" * 400) + "VERDICT: FAIL\n"
        block = lean_verifier_report_block(huge, repo_path=str(repo))
        path = repo / "repair_artifacts" / "last_fail_report.md"
        assert path.is_file()
        assert "Full verifier report" in block
        assert str(path.resolve()) in block
        assert len(block) < len(huge)
        assert len(block) < 2500
        assert path.read_text(encoding="utf-8").strip().endswith("VERDICT: FAIL")


def test_resume_nudge_repair_uses_lean_report() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "plan.md").write_text("# Plan\nDo work.\n", encoding="utf-8")
        orch = OrchestrationState(
            completion_mode=CompletionMode.VERDICT_PASS,
            repo_path=str(repo),
            user_objective="Build arcade",
            log_root=str(repo / "logs"),
        )
        orch.lifecycle.repo_path = str(repo)
        orch.lifecycle.plan_agent_seen = True
        orch.lifecycle.env_ready_seen = True
        orch.lifecycle.implementation_gp_seen = True
        orch.lifecycle.implementation_complete_seen = True

        def _notify(kind, event=None):
            return EngineNotification(
                kind=kind,
                conversation_id="c1",
                state=ConversationState(
                    conversation_id="c1",
                    harness_session=HarnessSession(session_id="s1"),
                    status=ConversationStatus.ACTIVE,
                ),
                event=event,
                detail={},
            )

        orch.apply_notification(
            _notify(
                EngineNotificationKind.EVENT_RECEIVED,
                ToolStartedEvent(
                    tool_name="Agent",
                    invocation_id="v1",
                    arguments={"subagent_type": "verification"},
                ),
            )
        )
        huge = "missing runtime\n" + ("x" * 8000) + "\nVERDICT: FAIL\n"
        orch.apply_notification(
            _notify(
                EngineNotificationKind.EVENT_RECEIVED,
                ToolCompletedEvent(
                    tool_name="Agent",
                    invocation_id="v1",
                    output=huge,
                    is_error=False,
                ),
            )
        )
        nudge = orch.resume_nudge(repo_path=str(repo), default="Continue.")
        assert nudge.kind == "repair_planning"
        assert "Full verifier report" in nudge.message
        assert "repair_artifacts/last_fail_report.md" in nudge.message
        assert nudge.message.count("x") < 2000


def test_token_usage_and_compact_drop_in_normalize() -> None:
    first = TurnCompletedEvent(
        final_text="done",
        usage={"prompt_tokens": 10000, "completion_tokens": 50},
    )
    rows = normalize_harness_event(first)
    types = [r["normalized_type"] for r in rows]
    assert "token_usage" in types
    usage = next(r for r in rows if r["normalized_type"] == "token_usage")
    assert usage["prompt_tokens"] == 10000

    second = TurnCompletedEvent(
        final_text="after compact",
        usage={"prompt_tokens": 4000, "completion_tokens": 20},
    )
    rows2 = normalize_harness_event(second, previous_prompt_tokens=10000)
    types2 = [r["normalized_type"] for r in rows2]
    assert "context_compacted" in types2
    compact = next(r for r in rows2 if r["normalized_type"] == "context_compacted")
    assert compact["kind"] == "token_drop"
    assert compact["prompt_tokens_before"] == 10000
    assert compact["prompt_tokens_after"] == 4000


def test_start_chakra_exports_autocompact_override() -> None:
    script = (REPO_ROOT / "scripts" / "start_chakra.sh").read_text(encoding="utf-8")
    assert "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE" in script
    assert "${CLAUDE_AUTOCOMPACT_PCT_OVERRIDE:-55}" in script


def main() -> int:
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
    if failed:
        print(f"\n{failed} test(s) failed")
        return 1
    print(f"\nAll {len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
