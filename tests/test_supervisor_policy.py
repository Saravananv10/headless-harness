"""Unit tests for SupervisorPolicy (Phase 1 single-conversation supervisor)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.context_builder import ControllerContext
from controller.decision import ActionType
from controller.llm import DeterministicLLMClient
from controller.supervisor_policy import (
    CONTINUE_MESSAGE,
    CompletionMode,
    SupervisorPolicy,
)
from controller.workflow_common import IMPLEMENTATION_COMPLETE_MARKER
from verification.prompts import build_unified_pipeline_objective


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


def _policy(
    bootstrap: str = "BOOTSTRAP OBJECTIVE",
    mode: CompletionMode = CompletionMode.VERDICT_PASS,
) -> SupervisorPolicy:
    return SupervisorPolicy(
        DeterministicLLMClient([]),
        bootstrap_message=bootstrap,
        completion_mode=mode,
    )


def test_first_decision_sends_bootstrap() -> None:
    policy = _policy("do the work")
    action = policy.decide(_context(history=[]))
    assert action.action == ActionType.SEND_MESSAGE
    assert action.message == "do the work"


def test_continues_without_stage_steering() -> None:
    policy = _policy()
    action = policy.decide(
        _context(
            turn_count=1,
            last_assistant_message="Still implementing...",
            history=[{"role": "user", "content": "bootstrap", "turn_id": "t1", "timestamp": ""}],
        )
    )
    assert action.action == ActionType.SEND_MESSAGE
    assert action.message == CONTINUE_MESSAGE
    assert "verification stage" not in (action.message or "").lower()
    assert "planning phase" not in (action.message or "").lower()


def test_completes_on_verdict_pass() -> None:
    policy = _policy(mode=CompletionMode.VERDICT_PASS)
    action = policy.decide(
        _context(
            turn_count=3,
            last_assistant_message="Looks good.\nVERDICT: PASS",
            history=[{"role": "user", "content": "bootstrap", "turn_id": "t1", "timestamp": ""}],
        )
    )
    assert action.action == ActionType.COMPLETE
    assert "VERDICT: PASS" in (action.summary or "")


def test_does_not_complete_on_verdict_fail() -> None:
    policy = _policy(mode=CompletionMode.VERDICT_PASS)
    action = policy.decide(
        _context(
            turn_count=2,
            last_assistant_message="Broken.\nVERDICT: FAIL",
            history=[{"role": "user", "content": "bootstrap", "turn_id": "t1", "timestamp": ""}],
        )
    )
    assert action.action == ActionType.SEND_MESSAGE
    assert action.message == CONTINUE_MESSAGE


def test_completes_on_implementation_marker_when_configured() -> None:
    policy = _policy(mode=CompletionMode.IMPLEMENTATION_COMPLETE)
    action = policy.decide(
        _context(
            turn_count=2,
            last_assistant_message=f"Done.\n{IMPLEMENTATION_COMPLETE_MARKER}",
            history=[{"role": "user", "content": "bootstrap", "turn_id": "t1", "timestamp": ""}],
        )
    )
    assert action.action == ActionType.COMPLETE
    assert IMPLEMENTATION_COMPLETE_MARKER in (action.summary or "")


def test_implementation_marker_ignored_in_verdict_mode() -> None:
    policy = _policy(mode=CompletionMode.VERDICT_PASS)
    action = policy.decide(
        _context(
            turn_count=2,
            last_assistant_message=f"Implemented.\n{IMPLEMENTATION_COMPLETE_MARKER}",
            history=[{"role": "user", "content": "bootstrap", "turn_id": "t1", "timestamp": ""}],
        )
    )
    assert action.action == ActionType.SEND_MESSAGE


def test_turn_limit_completes_without_marker() -> None:
    policy = _policy()
    action = policy.decide(
        _context(
            turn_count=40,
            last_assistant_message="still going",
            history=[{"role": "user", "content": "bootstrap", "turn_id": "t1", "timestamp": ""}],
            metadata={"turn_limit_reached": True},
        )
    )
    assert action.action == ActionType.COMPLETE
    assert "turn limit" in (action.reasoning or "").lower()


def test_unified_prompt_owns_full_lifecycle() -> None:
    text = build_unified_pipeline_objective(
        repo_path="/tmp/repo",
        objective="Build a CLI",
        max_repair_iterations=7,
        include_verification=True,
    )
    assert "THIS single conversation" in text or "single conversation" in text.lower()
    assert "verification" in text.lower()
    assert "VERDICT: PASS" in text
    assert "7" in text
    assert 'cwd="/tmp/repo"' in text
    assert "Do not ask the harness to start a second conversation" in text
    assert "Only the verification subagent may issue VERDICT" in text
    assert "RUNTIME_CHECK: PASS" in text
    assert "ENV_STATUS: READY" in text
    assert "Recommended lifecycle" in text
    assert "repair_plan.md" in text
    assert 'isolation="worktree" is allowed' in text
    assert "phase-specific resume" in text.lower()


def test_unified_prompt_skip_verification() -> None:
    text = build_unified_pipeline_objective(
        repo_path="/tmp/repo",
        objective="Build a CLI",
        include_verification=False,
    )
    assert IMPLEMENTATION_COMPLETE_MARKER in text
    assert "skip-verification" in text.lower() or "Do not run verification" in text


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} passed")
