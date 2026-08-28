"""Unit tests for adaptive recovery nudges."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.denial_tracker import DenialTracker
from controller.lifecycle import LifecycleObserver
from controller.phase_contracts import PhaseBudgetTracker
from controller.progress_tracker import ProgressTracker
from controller.recovery import select_recovery


def test_explore_only_recovery_message() -> None:
    progress = ProgressTracker(stall_cycles=3)
    for _ in range(3):
        progress.on_resume_cycle()
    denials = DenialTracker()
    phases = PhaseBudgetTracker()
    phases.note_spawn("Explore")
    life = LifecycleObserver(repo_path="/tmp/habit")
    action = select_recovery(
        progress=progress,
        denials=denials,
        phases=phases,
        lifecycle=life,
        repo_path="/tmp/habit",
        recovery_attempts_used=0,
        max_recovery_attempts=1,
    )
    assert action.termination_reason is None
    assert action.kind == "force_plan_implement"
    assert "explore" in action.effects.deny_subagent_types
    assert "Plan" in action.message
    assert "general-purpose" in action.message
    assert "/tmp/habit" in action.message


def test_denial_loop_recovery_message() -> None:
    progress = ProgressTracker(stall_cycles=5)
    denials = DenialTracker(loop_threshold=3)
    for _ in range(3):
        denials.record(
            tool_name="Bash",
            reason="deny Bash outside repository or destructive pattern",
            target="ls /tmp",
        )
    phases = PhaseBudgetTracker()
    life = LifecycleObserver(repo_path="/tmp/repo")
    action = select_recovery(
        progress=progress,
        denials=denials,
        phases=phases,
        lifecycle=life,
        repo_path="/tmp/repo",
        recovery_attempts_used=0,
        max_recovery_attempts=1,
        phase_budget_action=None,
    )
    assert action.kind == "denial_strategy"
    assert action.effects.lock_workspace is True
    assert action.effects.clear_out_of_repo_denials is True
    assert "denied" in action.message.lower() or "DENIAL" in action.message


def test_second_recovery_terminates_causal() -> None:
    """With max_recovery_attempts=1, second call terminates."""
    progress = ProgressTracker(stall_cycles=2)
    progress.on_resume_cycle()
    progress.on_resume_cycle()
    assert progress.is_stalled
    denials = DenialTracker()
    phases = PhaseBudgetTracker()
    phases.note_spawn("Explore")
    life = LifecycleObserver(repo_path="/tmp/repo")
    action = select_recovery(
        progress=progress,
        denials=denials,
        phases=phases,
        lifecycle=life,
        repo_path="/tmp/repo",
        recovery_attempts_used=1,
        max_recovery_attempts=1,
    )
    assert action.termination_reason in {
        "stuck_in_explore",
        "no_forward_progress",
    }


def test_three_recovery_attempts_before_terminate() -> None:
    """Default budget of 3: attempts 0–2 nudge; attempt 3 terminates."""
    progress = ProgressTracker(stall_cycles=2)
    progress.on_resume_cycle()
    progress.on_resume_cycle()
    denials = DenialTracker()
    phases = PhaseBudgetTracker()
    phases.note_spawn("Explore")
    life = LifecycleObserver(repo_path="/tmp/repo")

    for used in range(3):
        action = select_recovery(
            progress=progress,
            denials=denials,
            phases=phases,
            lifecycle=life,
            repo_path="/tmp/repo",
            recovery_attempts_used=used,
            max_recovery_attempts=3,
        )
        assert action.termination_reason is None, f"attempt {used} should not terminate"
        assert action.kind == "force_plan_implement"
        assert action.message

    terminal = select_recovery(
        progress=progress,
        denials=denials,
        phases=phases,
        lifecycle=life,
        repo_path="/tmp/repo",
        recovery_attempts_used=3,
        max_recovery_attempts=3,
    )
    assert terminal.termination_reason in {
        "stuck_in_explore",
        "no_forward_progress",
    }


def test_implement_first_recovery_when_plan_done_without_complete() -> None:
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "plan.md").write_text("# Plan\n", encoding="utf-8")
        progress = ProgressTracker(stall_cycles=5)
        denials = DenialTracker()
        phases = PhaseBudgetTracker()
        life = LifecycleObserver(repo_path=str(repo))
        life.plan_agent_seen = True
        life.main_agent_write_count = 5
        assert life.plan_done
        action = select_recovery(
            progress=progress,
            denials=denials,
            phases=phases,
            lifecycle=life,
            repo_path=str(repo),
            recovery_attempts_used=0,
            max_recovery_attempts=3,
        )
        assert action.kind == "implement_first"
        assert "general-purpose" in action.message
        assert "IMPLEMENTATION_STATUS" in action.message or "COMPLETE" in action.message


def test_repair_recovery_after_rejected_pass_with_complete() -> None:
    progress = ProgressTracker(stall_cycles=2)
    progress.on_resume_cycle()
    progress.on_resume_cycle()
    denials = DenialTracker()
    phases = PhaseBudgetTracker()
    life = LifecycleObserver(repo_path="/tmp/repo")
    life.implementation_complete_seen = True
    life.rejected_pass_count = 2
    life.last_pass_rejection = "missing RUNTIME_CHECK: PASS"
    action = select_recovery(
        progress=progress,
        denials=denials,
        phases=phases,
        lifecycle=life,
        repo_path="/tmp/repo",
        recovery_attempts_used=0,
        max_recovery_attempts=3,
    )
    assert action.kind == "repair_planning"
    assert "explore" in action.effects.deny_subagent_types
    assert "repair" in action.message.lower()


def test_workspace_reset_recovery() -> None:
    from controller.workspace_confusion import WorkspaceConfusionTracker

    progress = ProgressTracker(stall_cycles=5)
    denials = DenialTracker()
    phases = PhaseBudgetTracker()
    life = LifecycleObserver(repo_path="/tmp/repo")
    ws = WorkspaceConfusionTracker(threshold=3, repo_path="/tmp/repo")
    for _ in range(3):
        ws.record_denial(
            tool_name="Read",
            reason="deny Read outside repository boundary",
            target="/Users/x/headless_harness/foo",
        )
    action = select_recovery(
        progress=progress,
        denials=denials,
        phases=phases,
        lifecycle=life,
        repo_path="/tmp/repo",
        recovery_attempts_used=0,
        max_recovery_attempts=3,
        workspace=ws,
    )
    assert action.kind == "workspace_reset"
    assert action.effects.lock_workspace is True
    assert "WORKSPACE RESET" in action.message


def test_empty_subagent_recovery_takes_priority_over_implement_first() -> None:
    """Repeated empty Agent completions must not just re-trigger implement_first
    (which would blindly re-spawn into the same void) — it needs its own,
    more targeted recovery message."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "plan.md").write_text("# Plan\n", encoding="utf-8")
        progress = ProgressTracker(stall_cycles=5)
        progress.observe_tool_completed(
            "Agent", output="(Subagent completed but returned no output.)\nagentId: a"
        )
        progress.observe_tool_completed(
            "Agent", output="(Subagent completed but returned no output.)\nagentId: b"
        )
        denials = DenialTracker()
        phases = PhaseBudgetTracker()
        life = LifecycleObserver(repo_path=str(repo))
        life.plan_agent_seen = True
        life.main_agent_write_count = 5
        action = select_recovery(
            progress=progress,
            denials=denials,
            phases=phases,
            lifecycle=life,
            repo_path=str(repo),
            recovery_attempts_used=0,
            max_recovery_attempts=3,
        )
        assert action.kind == "empty_subagent_recovery"
        assert action.termination_reason is None
        assert "no output" in action.message.lower()
        assert str(repo) in action.message


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
