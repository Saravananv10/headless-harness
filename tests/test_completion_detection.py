"""Unit tests for Phase 6 explicit completion detection."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.completion import (
    CompletionDetector,
    CompletionMode,
    TerminalEventKind,
    TerminalMarker,
    find_markers,
    text_has_completion,
)
from controller.orchestration_state import OrchestrationState
from engine.state import ConversationState, ConversationStatus
from engine.types import EngineNotification, EngineNotificationKind
from interface.events import (
    TextDeltaEvent,
    ToolCompletedEvent,
    ToolStartedEvent,
    TurnCompletedEvent,
)
from interface.models.session import HarnessSession


def _state() -> ConversationState:
    return ConversationState(
        conversation_id="c1",
        harness_session=HarnessSession(session_id="s1"),
        status=ConversationStatus.ACTIVE,
    )


def _notify(kind, event=None, detail=None) -> EngineNotification:
    return EngineNotification(
        kind=kind,
        conversation_id="c1",
        state=_state(),
        event=event,
        detail=detail or {},
    )


def test_find_markers_explicit_only() -> None:
    text = (
        "Implemented.\nIMPLEMENTATION_STATUS: COMPLETE\n"
        "Repaired.\nREPAIR_STATUS: COMPLETE\n"
        "VERDICT: PASS\n"
    )
    markers = find_markers(text)
    assert TerminalMarker.IMPLEMENTATION_COMPLETE in markers
    assert TerminalMarker.REPAIR_COMPLETE in markers
    assert TerminalMarker.VERDICT_PASS in markers
    assert find_markers("looks done to me") == []
    assert find_markers("VERDICT: FAIL") == []


def test_detector_requires_terminal_event_kind() -> None:
    detector = CompletionDetector(CompletionMode.VERDICT_PASS)
    # text_delta must never complete
    assert (
        detector.inspect(
            "VERDICT: PASS",
            event_kind="text_delta",
            source="delta",
        )
        is None
    )

    hit = detector.inspect(
        "All good\nVERDICT: PASS",
        event_kind=TerminalEventKind.TURN_COMPLETED,
        source="turn_completed",
    )
    assert hit is not None
    assert hit.marker == TerminalMarker.VERDICT_PASS


def test_mode_selects_required_marker() -> None:
    assert text_has_completion(
        "IMPLEMENTATION_STATUS: COMPLETE", CompletionMode.IMPLEMENTATION_COMPLETE
    )
    assert not text_has_completion(
        "IMPLEMENTATION_STATUS: COMPLETE", CompletionMode.VERDICT_PASS
    )
    assert text_has_completion("VERDICT: PASS", CompletionMode.VERDICT_PASS)
    assert text_has_completion(
        "REPAIR_STATUS: COMPLETE", CompletionMode.REPAIR_COMPLETE
    )
    assert not text_has_completion("REPAIR_STATUS: COMPLETE", CompletionMode.VERDICT_PASS)


def test_orchestration_ignores_text_delta_and_main_turn_verdict() -> None:
    orch = OrchestrationState(completion_mode=CompletionMode.VERDICT_PASS)
    orch.apply_notification(
        _notify(
            EngineNotificationKind.EVENT_RECEIVED,
            TextDeltaEvent(text="Almost done VERDICT: PASS"),
        )
    )
    assert not orch.completion_detected

    orch.apply_notification(
        _notify(
            EngineNotificationKind.EVENT_RECEIVED,
            TurnCompletedEvent(final_text="Done\nVERDICT: PASS"),
        )
    )
    # Main-assistant VERDICT: PASS is not authoritative — must not complete.
    assert not orch.completion_detected


def test_orchestration_completes_on_verification_agent_verdict() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "plan.md").write_text("# Plan\n", encoding="utf-8")
        orch = OrchestrationState(
            completion_mode=CompletionMode.VERDICT_PASS,
            repo_path=str(repo),
        )
        orch.apply_notification(
            _notify(
                EngineNotificationKind.EVENT_RECEIVED,
                ToolStartedEvent(
                    tool_name="Agent",
                    invocation_id="plan1",
                    arguments={"subagent_type": "Plan", "cwd": str(repo)},
                ),
            )
        )
        orch.apply_notification(
            _notify(
                EngineNotificationKind.EVENT_RECEIVED,
                ToolCompletedEvent(
                    tool_name="Agent",
                    invocation_id="plan1",
                    output="planned",
                    is_error=False,
                ),
            )
        )
        orch.apply_notification(
            _notify(
                EngineNotificationKind.EVENT_RECEIVED,
                ToolStartedEvent(
                    tool_name="Agent",
                    invocation_id="gp1",
                    arguments={"subagent_type": "general-purpose", "cwd": str(repo)},
                ),
            )
        )
        orch.apply_notification(
            _notify(
                EngineNotificationKind.EVENT_RECEIVED,
                ToolCompletedEvent(
                    tool_name="Agent",
                    invocation_id="gp1",
                    output="ENV_STATUS: READY\nIMPLEMENTATION_STATUS: COMPLETE",
                    is_error=False,
                ),
            )
        )
        orch.apply_notification(
            _notify(
                EngineNotificationKind.EVENT_RECEIVED,
                ToolStartedEvent(
                    tool_name="Agent",
                    invocation_id="v1",
                    arguments={"subagent_type": "verification", "cwd": str(repo)},
                ),
            )
        )
        orch.apply_notification(
            _notify(
                EngineNotificationKind.EVENT_RECEIVED,
                ToolCompletedEvent(
                    tool_name="Agent",
                    invocation_id="v1",
                    output=(
                        "**Command run:**\n  pytest\n"
                        "RUNTIME_CHECK: PASS\nVERDICT: PASS\n"
                        "<usage>tool_uses: 4</usage>\n"
                    ),
                    is_error=False,
                ),
            )
        )
        assert orch.completion_detected
        assert orch.completion_hit is not None
        assert orch.completion_hit.source.startswith("tool_completed")


def test_orchestration_rejects_zero_tool_pass() -> None:
    from verification.parser import (
        evaluation_rejects_pass,
        has_runtime_check_pass,
        has_verification_tool_evidence,
    )

    assert has_runtime_check_pass("RUNTIME_CHECK: PASS\nVERDICT: PASS")
    assert not has_verification_tool_evidence(
        "RUNTIME_CHECK: PASS\nVERDICT: PASS\n<usage>tool_uses: 0</usage>"
    )
    assert evaluation_rejects_pass("VERDICT: PASS")
    assert evaluation_rejects_pass(
        "RUNTIME_CHECK: PASS\nVERDICT: PASS\n<usage>tool_uses: 0</usage>"
    )
    assert (
        evaluation_rejects_pass(
            "**Command run:**\n x\nRUNTIME_CHECK: PASS\nVERDICT: PASS\n"
            "<usage>tool_uses: 2</usage>"
        )
        is None
    )


def test_inactivity_and_silence_never_complete() -> None:
    """Phase 6: no heuristic completion from empty / silent turns."""
    orch = OrchestrationState(completion_mode=CompletionMode.VERDICT_PASS)
    orch.apply_notification(
        _notify(EngineNotificationKind.TURN_STARTED, detail={"turn_id": "t1"})
    )
    orch.apply_notification(
        _notify(
            EngineNotificationKind.EVENT_RECEIVED,
            TextDeltaEvent(text="still working..."),
        )
    )
    orch.apply_notification(
        _notify(
            EngineNotificationKind.TURN_COMPLETED,
            TurnCompletedEvent(final_text="still working..."),
            detail={"turn_id": "t1"},
        )
    )
    assert not orch.completion_detected
    assert orch.turn_count == 1


def test_wrong_marker_does_not_complete_mode() -> None:
    orch = OrchestrationState(completion_mode=CompletionMode.VERDICT_PASS)
    orch.apply_notification(
        _notify(
            EngineNotificationKind.EVENT_RECEIVED,
            TurnCompletedEvent(final_text="IMPLEMENTATION_STATUS: COMPLETE"),
        )
    )
    assert not orch.completion_detected


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} passed")
