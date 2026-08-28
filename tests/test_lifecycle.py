"""Unit tests for Phase 7 lifecycle observation (verify/repair owned by Chakra)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.completion import CompletionMode
from controller.lifecycle import LifecycleObserver
from controller.orchestration_state import OrchestrationState
from engine.state import ConversationState, ConversationStatus
from engine.types import EngineNotification, EngineNotificationKind
from interface.events import ToolCompletedEvent, ToolStartedEvent, TurnCompletedEvent
from interface.models.session import HarnessSession
from verification.parser import Verdict, evaluation_rejects_pass, parse_verdict
from verification.prompts import build_unified_pipeline_objective

_PASS_OK = (
    "### Check: smoke\n"
    "**Command run:**\n"
    "  .venv/bin/pytest -q\n"
    "**Output observed:**\n"
    "  3 passed\n"
    "RUNTIME_CHECK: PASS\n"
    "VERDICT: PASS\n"
    "<usage>total_tokens: 1\ntool_uses: 5\nduration_ms: 1000</usage>\n"
)


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


def _spawn_agent(
    orch: OrchestrationState,
    invocation_id: str,
    subagent_type: str,
) -> None:
    orch.apply_notification(
        _notify(
            EngineNotificationKind.EVENT_RECEIVED,
            ToolStartedEvent(
                tool_name="Agent",
                invocation_id=invocation_id,
                arguments={"subagent_type": subagent_type, "prompt": "go", "cwd": "/tmp"},
            ),
        )
    )


def _spawn_verification(orch: OrchestrationState, invocation_id: str) -> None:
    _spawn_agent(orch, invocation_id, "verification")


def _agent_done(orch: OrchestrationState, invocation_id: str, output: str) -> None:
    orch.apply_notification(
        _notify(
            EngineNotificationKind.EVENT_RECEIVED,
            ToolCompletedEvent(
                tool_name="Agent",
                invocation_id=invocation_id,
                output=output,
                is_error=False,
            ),
        )
    )


def _complete_plan_and_implement(orch: OrchestrationState, repo: Path) -> None:
    plan = repo / "plan.md"
    plan.write_text("# Plan\nDo the work.\n", encoding="utf-8")
    orch.lifecycle.repo_path = str(repo)
    orch.repo_path = str(repo)
    _spawn_agent(orch, "plan1", "Plan")
    _agent_done(orch, "plan1", "Wrote plan.md")
    _spawn_agent(orch, "gp1", "general-purpose")
    _agent_done(
        orch,
        "gp1",
        "ENV_STATUS: READY\nImplemented.\nIMPLEMENTATION_STATUS: COMPLETE\n",
    )


def test_lifecycle_counts_fails_and_exhausts() -> None:
    life = LifecycleObserver(max_repair_iterations=3)
    life.plan_agent_seen = True
    life.env_ready_seen = True
    life.implementation_gp_seen = True
    life.implementation_complete_seen = True
    assert not life.repair_iterations_exhausted
    life.observe_text("VERDICT: FAIL", source="v1", authoritative=True)
    # Informal repair marker from main text does not count.
    life.observe_text("REPAIR_STATUS: COMPLETE", source="r1", authoritative=False)
    assert life.repair_complete_count == 0
    life.register_agent_start("gp-r1", "general-purpose")
    life.observe_text(
        "REPAIR_STATUS: COMPLETE",
        source="gp",
        authoritative=False,
        invocation_id="gp-r1",
    )
    assert life.repair_complete_count == 1
    life.observe_text("VERDICT: FAIL", source="v2", authoritative=True)
    life.observe_text("VERDICT: FAIL", source="v3", authoritative=True)
    assert life.verdict_fail_count == 3
    assert life.repair_iterations_exhausted
    life.observe_text(_PASS_OK, source="v4", authoritative=True)
    assert life.verdict_pass_seen
    assert life.authoritative_pass
    assert not life.repair_iterations_exhausted


def test_partial_counts_as_failure() -> None:
    assert parse_verdict("VERDICT: PARTIAL") == Verdict.PARTIAL
    life = LifecycleObserver(max_repair_iterations=2)
    life.plan_agent_seen = True
    life.env_ready_seen = True
    life.implementation_gp_seen = True
    life.implementation_complete_seen = True
    life.observe_text("VERDICT: PARTIAL", source="v1", authoritative=True)
    assert life.verdict_fail_count == 1
    assert life.last_verdict == "PARTIAL"
    assert life.needs_repair_and_reverify
    assert not life.authoritative_pass


def test_non_authoritative_verdict_ignored() -> None:
    life = LifecycleObserver(max_repair_iterations=3)
    life.observe_text(
        "IMPLEMENTATION_STATUS: COMPLETE\nVERDICT: PASS",
        source="main",
        authoritative=False,
    )
    # Main prose does not satisfy implementation gate.
    assert not life.implementation_complete_seen
    assert life.last_verdict is None
    assert not life.verdict_pass_seen
    assert life.needs_plan_spawn
    assert not life.needs_verification_spawn


def test_orchestration_observes_verdicts_without_python_loop() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        orch = OrchestrationState(
            completion_mode=CompletionMode.VERDICT_PASS,
            max_repair_iterations=2,
            repo_path=str(repo),
        )
        _complete_plan_and_implement(orch, repo)
        _spawn_verification(orch, "1")
        _agent_done(orch, "1", "bad\nVERDICT: FAIL")
        assert orch.lifecycle.verdict_fail_count == 1
        assert not orch.completion_detected
        assert not orch.lifecycle.repair_iterations_exhausted

        _spawn_agent(orch, "gpr1", "general-purpose")
        _agent_done(orch, "gpr1", "fixed\nREPAIR_STATUS: COMPLETE")
        _spawn_verification(orch, "2")
        _agent_done(orch, "2", "still bad\nVERDICT: FAIL")
        assert orch.lifecycle.repair_iterations_exhausted
        assert not orch.completion_detected


def test_main_agent_self_pass_does_not_complete() -> None:
    orch = OrchestrationState(completion_mode=CompletionMode.VERDICT_PASS)
    orch.apply_notification(
        _notify(
            EngineNotificationKind.EVENT_RECEIVED,
            TurnCompletedEvent(
                final_text=(
                    "Done.\nIMPLEMENTATION_STATUS: COMPLETE\nVERDICT: PASS\n"
                )
            ),
        )
    )
    assert not orch.completion_detected
    assert not orch.lifecycle.implementation_complete_seen
    assert orch.lifecycle.needs_plan_spawn
    assert orch.lifecycle.last_verdict is None


def test_verification_agent_pass_completes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        orch = OrchestrationState(
            completion_mode=CompletionMode.VERDICT_PASS,
            repo_path=str(repo),
        )
        _complete_plan_and_implement(orch, repo)
        _spawn_verification(orch, "v1")
        _agent_done(orch, "v1", _PASS_OK)
        assert orch.completion_detected
        assert orch.lifecycle.authoritative_pass
        assert orch.completion_hit is not None
        assert orch.completion_hit.source == "tool_completed:Agent"


def test_zero_tool_pass_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        orch = OrchestrationState(
            completion_mode=CompletionMode.VERDICT_PASS,
            repo_path=str(repo),
        )
        _complete_plan_and_implement(orch, repo)
        _spawn_verification(orch, "v1")
        _agent_done(
            orch,
            "v1",
            "Looks fine\nRUNTIME_CHECK: PASS\nVERDICT: PASS\n"
            "<usage>tool_uses: 0\nduration_ms: 1</usage>\n",
        )
        assert not orch.completion_detected
        assert orch.lifecycle.last_verdict == "FAIL"
        assert orch.lifecycle.needs_repair_and_reverify
        assert evaluation_rejects_pass(
            "RUNTIME_CHECK: PASS\nVERDICT: PASS\n<usage>tool_uses: 0</usage>"
        )


def test_pass_without_runtime_check_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        orch = OrchestrationState(
            completion_mode=CompletionMode.VERDICT_PASS,
            repo_path=str(repo),
        )
        _complete_plan_and_implement(orch, repo)
        _spawn_verification(orch, "v1")
        _agent_done(
            orch,
            "v1",
            "**Command run:**\n  pytest\nVERDICT: PASS\n"
            "<usage>tool_uses: 3</usage>\n",
        )
        assert not orch.completion_detected
        assert "RUNTIME_CHECK" in (orch.lifecycle.last_pass_rejection or "")


def test_premature_pass_rejected_without_plan_or_impl() -> None:
    orch = OrchestrationState(completion_mode=CompletionMode.VERDICT_PASS)
    _spawn_verification(orch, "v1")
    _agent_done(orch, "v1", _PASS_OK)
    assert not orch.completion_detected
    assert orch.lifecycle.verification_agent_verdict_count == 1
    assert orch.lifecycle.last_verdict == "FAIL"
    assert "plan.md" in (orch.lifecycle.last_pass_rejection or "")


def test_verification_fail_clears_prior_pass() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        orch = OrchestrationState(
            completion_mode=CompletionMode.VERDICT_PASS,
            repo_path=str(repo),
        )
        _complete_plan_and_implement(orch, repo)
        _spawn_verification(orch, "v1")
        _agent_done(orch, "v1", _PASS_OK)
        assert orch.completion_detected
        _spawn_verification(orch, "v2")
        _agent_done(orch, "v2", "regression\nVERDICT: FAIL")
        assert not orch.completion_detected
        assert orch.lifecycle.last_verdict == "FAIL"
        assert orch.lifecycle.needs_repair_and_reverify


def test_non_verification_agent_pass_ignored() -> None:
    orch = OrchestrationState(completion_mode=CompletionMode.VERDICT_PASS)
    orch.apply_notification(
        _notify(
            EngineNotificationKind.EVENT_RECEIVED,
            ToolStartedEvent(
                tool_name="Agent",
                invocation_id="gp1",
                arguments={"subagent_type": "general-purpose"},
            ),
        )
    )
    _agent_done(orch, "gp1", "I think it works\nVERDICT: PASS")
    assert not orch.completion_detected
    assert orch.lifecycle.last_verdict is None


def test_resume_neutral_before_plan_is_chakra_owned() -> None:
    """Pre-plan gap is telemetry only — Python does not Plan-nudge.

    Empty orch has needs_plan_spawn=True, but resume stays neutral by design
    (Chakra owns initial Plan spawn; see soft bootstrap lifecycle wording).
    """
    orch = OrchestrationState(completion_mode=CompletionMode.VERDICT_PASS)
    assert orch.lifecycle.needs_plan_spawn
    assert not orch.lifecycle.plan_done
    nudge = orch.resume_nudge(repo_path="/tmp/repo", default="Continue.")
    assert nudge.kind == "neutral"
    assert nudge.message == "Continue."


def test_resume_verification_after_implementation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        orch = OrchestrationState(
            completion_mode=CompletionMode.VERDICT_PASS,
            repo_path=str(repo),
            user_objective="Build arcade",
        )
        _complete_plan_and_implement(orch, repo)
        nudge = orch.resume_nudge(repo_path=str(repo), default="Continue.")
        assert nudge.kind == "verification"
        assert "verification" in nudge.message.lower()
        assert "RUNTIME_CHECK: PASS" in nudge.message


def test_resume_repair_planning_after_fail() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        orch = OrchestrationState(
            completion_mode=CompletionMode.VERDICT_PASS,
            repo_path=str(repo),
            user_objective="Build arcade",
        )
        _complete_plan_and_implement(orch, repo)
        _spawn_verification(orch, "v1")
        _agent_done(orch, "v1", "missing tests\nVERDICT: FAIL")
        assert orch.lifecycle.needs_repair_and_reverify
        assert orch.lifecycle.last_raw_verdict == "FAIL"
        assert "missing tests" in orch.lifecycle.last_verifier_report
        nudge = orch.resume_nudge(repo_path=str(repo), default="Continue.")
        assert nudge.kind == "repair_planning"
        assert nudge.reason
        assert "REPAIR PLANNING" in nudge.message
        assert "Plan" in nudge.message


def test_resume_reverify_after_rejected_pass() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        orch = OrchestrationState(
            completion_mode=CompletionMode.VERDICT_PASS,
            repo_path=str(repo),
            user_objective="Build arcade",
        )
        _complete_plan_and_implement(orch, repo)
        _spawn_verification(orch, "v1")
        _agent_done(
            orch,
            "v1",
            "Looks good from reading the code.\nVERDICT: PASS\n"
            "<usage>total_tokens: 1\ntool_uses: 2\nduration_ms: 10</usage>\n",
        )
        assert orch.lifecycle.last_pass_rejection
        assert orch.lifecycle.last_raw_verdict == "PASS"
        assert orch.lifecycle.last_verdict == "FAIL"
        assert orch.lifecycle.rejected_pass_count == 1
        nudge = orch.resume_nudge(repo_path=str(repo), default="Continue.")
        assert nudge.kind == "reverify_after_rejected_pass"
        assert "RUNTIME_CHECK" in nudge.message
        assert "REPAIR PLANNING" not in nudge.message


def test_resume_implement_first_after_rejected_pass_without_complete() -> None:
    """Rejected PASS before IMPLEMENTATION_STATUS → implement, not reverify."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "plan.md").write_text("# Plan\n", encoding="utf-8")
        orch = OrchestrationState(
            completion_mode=CompletionMode.VERDICT_PASS,
            repo_path=str(repo),
            user_objective="Build arcade",
        )
        orch.lifecycle.plan_agent_seen = True
        orch.lifecycle.main_agent_write_count = 3
        assert orch.lifecycle.plan_done
        # Simulate rejected PASS without implementation markers
        orch.lifecycle._record_pass_rejection(
            source="test",
            reason="missing RUNTIME_CHECK: PASS (build/run required)",
        )
        orch.lifecycle.last_raw_verdict = "PASS"
        assert not orch.lifecycle.implementation_complete_seen
        nudge = orch.resume_nudge(repo_path=str(repo), default="Continue.")
        assert nudge.kind == "implement"
        assert "general-purpose" in nudge.message
        assert "IMPLEMENTATION_STATUS" in nudge.message


def test_resume_repair_after_second_rejected_pass() -> None:
    """After reverify budget, second rejected PASS escalates to repair."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        orch = OrchestrationState(
            completion_mode=CompletionMode.VERDICT_PASS,
            repo_path=str(repo),
            user_objective="Build arcade",
        )
        _complete_plan_and_implement(orch, repo)
        _spawn_verification(orch, "v1")
        bad = (
            "Looks good from reading the code.\nVERDICT: PASS\n"
            "<usage>total_tokens: 1\ntool_uses: 2\nduration_ms: 10</usage>\n"
        )
        _agent_done(orch, "v1", bad)
        assert orch.lifecycle.rejected_pass_count == 1
        first = orch.resume_nudge(repo_path=str(repo), default="Continue.")
        assert first.kind == "reverify_after_rejected_pass"

        _spawn_verification(orch, "v2")
        _agent_done(orch, "v2", bad)
        assert orch.lifecycle.rejected_pass_count == 2
        second = orch.resume_nudge(repo_path=str(repo), default="Continue.")
        assert second.kind == "repair_planning"
        assert "REPAIR PLANNING" in second.message or "Plan" in second.message


def test_resume_repair_implementation_after_repair_plan() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        orch = OrchestrationState(
            completion_mode=CompletionMode.VERDICT_PASS,
            repo_path=str(repo),
            user_objective="Build arcade",
        )
        _complete_plan_and_implement(orch, repo)
        _spawn_verification(orch, "v1")
        _agent_done(orch, "v1", "broken import\nVERDICT: FAIL")
        (repo / "repair_plan.md").write_text(
            "# Repair\nFix the import.\n", encoding="utf-8"
        )
        assert orch.lifecycle.repair_plan_done
        assert orch.lifecycle.needs_repair_and_reverify
        nudge = orch.resume_nudge(repo_path=str(repo), default="Continue.")
        assert nudge.kind == "repair_implementation"
        assert "general-purpose" in nudge.message
        assert "REPAIR_STATUS: COMPLETE" in nudge.message


def test_last_verifier_report_stored() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        orch = OrchestrationState(
            completion_mode=CompletionMode.VERDICT_PASS,
            repo_path=str(repo),
        )
        _complete_plan_and_implement(orch, repo)
        _spawn_verification(orch, "v1")
        report = "Check failed: no tests\nVERDICT: FAIL"
        _agent_done(orch, "v1", report)
        assert orch.lifecycle.last_verifier_report.strip() == report
        assert orch.lifecycle.last_raw_verdict == "FAIL"


def test_plan_md_alone_marks_plan_done() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "plan.md").write_text("# Plan\nDo work.\n", encoding="utf-8")
        life = LifecycleObserver(repo_path=str(repo))
        assert life.plan_done
        assert not life.needs_plan_spawn


def test_empty_plan_agent_completion_sets_plan_agent_seen() -> None:
    orch = OrchestrationState(completion_mode=CompletionMode.VERDICT_PASS)
    _spawn_agent(orch, "plan1", "Plan")
    _agent_done(orch, "plan1", "")
    assert orch.lifecycle.plan_agent_seen


def test_unified_prompt_delegates_loop_to_chakra() -> None:
    text = build_unified_pipeline_objective(
        repo_path="/tmp/repo",
        objective="Build X",
        max_repair_iterations=5,
        include_verification=True,
    )
    assert "single conversation" in text.lower() or "THIS single conversation" in text
    assert "second conversation" in text.lower() or "second session" in text.lower()
    assert "verification" in text.lower()
    assert "repair" in text.lower()
    assert "5" in text
    assert "ENV_STATUS: READY" in text
    assert "RUNTIME_CHECK: PASS" in text
    assert "Recommended lifecycle" in text
    assert "repair_plan.md" in text
    assert 'isolation="worktree" is allowed' in text
    assert "phase-specific resume" in text.lower()


def test_main_never_starts_second_verification_session() -> None:
    src = (REPO_ROOT / "main.py").read_text(encoding="utf-8")
    assert "build_unified_pipeline_objective" in src
    assert "ConversationRunner" in src
    # Single-conversation design: no second verification session kickoff.
    assert "start_verification_session" not in src
    assert "SECOND_SESSION" not in src


def test_repair_gp_then_verification_rerun_nudge() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        orch = OrchestrationState(
            completion_mode=CompletionMode.VERDICT_PASS,
            repo_path=str(repo),
            user_objective="Build arcade",
        )
        _complete_plan_and_implement(orch, repo)
        _spawn_verification(orch, "v1")
        _agent_done(orch, "v1", "nope\nVERDICT: FAIL")
        assert orch.lifecycle.needs_repair_and_reverify
        _spawn_agent(orch, "gpr1", "general-purpose")
        _agent_done(orch, "gpr1", "fixed\nREPAIR_STATUS: COMPLETE")
        assert not orch.lifecycle.needs_repair_and_reverify
        assert orch.lifecycle.needs_verification_spawn
        nudge = orch.resume_nudge(repo_path=str(repo), default="Continue.")
        assert nudge.kind == "verification_rerun"
        assert "re-run" in nudge.message.lower() or "VERIFICATION" in nudge.message


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
