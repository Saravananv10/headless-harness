"""Unit tests for progress-aware resume/terminate decision helpers."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.conversation_config import ConversationConfig
from controller.denial_tracker import DenialTracker
from controller.lifecycle import LifecycleObserver
from controller.phase_contracts import PhaseBudgetTracker
from controller.progress_tracker import ProgressTracker
from controller.recovery import select_recovery


def test_stall_then_recover_then_terminate() -> None:
    """Simulate controller loop decision sequence without Chakra."""
    cfg = ConversationConfig(stall_cycles=3, max_recovery_attempts=1)
    progress = ProgressTracker(stall_cycles=cfg.stall_cycles)
    denials = DenialTracker(loop_threshold=cfg.denial_loop_threshold)
    phases = PhaseBudgetTracker()
    phases.note_spawn("Explore")
    life = LifecycleObserver(repo_path="/tmp/x")
    recovery_attempts = 0

    outcomes: list[str] = []
    for _ in range(6):
        progress.on_resume_cycle()
        needs = progress.is_stalled or phases.spawned_subagents <= {"explore"}
        if not needs and progress.consecutive_resumes_without_progress < 2:
            outcomes.append("resume")
            continue
        # Match runner: explore stuck after stall_cycles//2
        explore_stuck = (
            phases.spawned_subagents <= {"explore"}
            and progress.consecutive_resumes_without_progress
            >= max(2, cfg.stall_cycles // 2)
        )
        if not (progress.is_stalled or explore_stuck):
            outcomes.append("resume")
            continue
        action = select_recovery(
            progress=progress,
            denials=denials,
            phases=phases,
            lifecycle=life,
            repo_path="/tmp/x",
            recovery_attempts_used=recovery_attempts,
            max_recovery_attempts=cfg.max_recovery_attempts,
        )
        if action.termination_reason:
            outcomes.append(f"terminate:{action.termination_reason}")
            break
        outcomes.append(f"recover:{action.kind}")
        recovery_attempts += 1

    assert any(o.startswith("recover:") for o in outcomes)
    assert any(o.startswith("terminate:") for o in outcomes)
    term = [o for o in outcomes if o.startswith("terminate:")][0]
    assert "stuck_in_explore" in term or "no_forward_progress" in term


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
