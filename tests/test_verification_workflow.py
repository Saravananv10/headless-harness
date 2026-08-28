"""Unit tests for verification / repair message builders."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.verification_workflow import (
    REPAIR_PLANNING_PHASE_MARKER,
    VERIFICATION_PHASE_MARKER,
    VERIFICATION_RERUN_MARKER,
    build_repair_implementation_message,
    build_repair_planning_message,
    build_verification_message,
    build_verification_rerun_message,
)
from controller.workflow_common import (
    self_assigned_verdict_detected,
    verification_passed,
    verification_subagent_verdict,
)
from controller.context_builder import ControllerContext


def _context(**kwargs) -> ControllerContext:
    defaults = {
        "objective": "meta",
        "conversation_id": "c1",
        "conversation_status": "active",
        "session_id": "s1",
        "session_state": "active",
        "working_directory": "/tmp",
        "turn_count": 0,
        "history": [],
        "metadata": {},
    }
    defaults.update(kwargs)
    return ControllerContext(**defaults)


def test_build_verification_message_includes_forbidden_actions() -> None:
    message = build_verification_message(
        user_objective="Build a todo CLI",
        repo_path="/tmp/repo",
        generation_summary="Implemented app",
    )
    assert VERIFICATION_PHASE_MARKER in message
    assert "FORBIDDEN" in message
    assert "headless_harness" in message
    assert 'subagent_type="verification"' in message
    assert 'cwd="/tmp/repo"' in message
    assert 'isolation="worktree"' in message
    assert "RUNTIME_CHECK: PASS" in message
    assert "illegal" in message.lower()
    assert "static file review" in message.lower()


def test_build_repair_planning_includes_plan_subagent() -> None:
    message = build_repair_planning_message(
        user_objective="Build a todo CLI",
        repo_path="/tmp/repo",
        verifier_report="VERDICT: FAIL\nmissing tests",
        repair_cycle=1,
    )
    assert REPAIR_PLANNING_PHASE_MARKER in message
    assert 'subagent_type="Plan"' in message
    assert 'cwd="/tmp/repo"' in message
    assert "VERDICT: FAIL" in message
    assert "repair_plan.md" in message


def test_build_verification_rerun_message() -> None:
    message = build_verification_rerun_message(
        user_objective="Build a todo CLI",
        repo_path="/tmp/repo",
        repair_cycle=2,
    )
    assert VERIFICATION_RERUN_MARKER in message
    assert "2" in message
    assert 'subagent_type="verification"' in message


def test_build_repair_implementation_message() -> None:
    message = build_repair_implementation_message(
        repo_path="/tmp/repo",
        verifier_report="VERDICT: FAIL\nbroken import",
    )
    assert "REPAIR" in message.upper() or "repair" in message
    assert 'subagent_type="general-purpose"' in message
    assert "REPAIR_STATUS: COMPLETE" in message or "repair" in message.lower()


def test_self_assigned_verdict_not_passed() -> None:
    history = [
        {"role": "user", "content": VERIFICATION_PHASE_MARKER, "turn_id": "t1", "timestamp": ""},
        {"role": "assistant", "content": "Looks good.\nVERDICT: PASS", "turn_id": "t1", "timestamp": ""},
    ]
    ctx = _context(
        turn_count=1,
        last_assistant_message="Looks good.\nVERDICT: PASS",
        history=history,
    )
    assert not verification_passed(ctx)
    assert self_assigned_verdict_detected(ctx)


def test_async_verification_accepted_from_read_output() -> None:
    history = [
        {"role": "user", "content": VERIFICATION_PHASE_MARKER, "turn_id": "t1", "timestamp": ""},
    ]
    tool_events = [
        {
            "event_type": "tool_started",
            "timestamp": "2026-01-01T00:00:01+00:00",
            "payload": {
                "tool_name": "Agent",
                "invocation_id": "call-async-verify",
                "arguments": {"subagent_type": "verification"},
            },
        },
        {
            "event_type": "tool_completed",
            "timestamp": "2026-01-01T00:00:02+00:00",
            "payload": {
                "tool_name": "Agent",
                "invocation_id": "call-async-verify",
                "output": "Async agent launched successfully.",
            },
        },
        {
            "event_type": "tool_completed",
            "timestamp": "2026-01-01T00:00:10+00:00",
            "payload": {
                "tool_name": "Read",
                "invocation_id": "call-read-output",
                "output": "Verifier report\nVERDICT: PASS",
            },
        },
    ]
    ctx = _context(
        turn_count=1,
        last_assistant_message="Waiting for verifier",
        history=history,
        tool_events=tool_events,
    )
    assert verification_subagent_verdict(ctx) is not None
    assert verification_passed(ctx)


def main() -> int:
    tests = [
        test_build_verification_message_includes_forbidden_actions,
        test_build_repair_planning_includes_plan_subagent,
        test_build_verification_rerun_message,
        test_build_repair_implementation_message,
        test_self_assigned_verdict_not_passed,
        test_async_verification_accepted_from_read_output,
    ]
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
