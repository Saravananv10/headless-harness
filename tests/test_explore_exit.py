"""Tests for Explore exit criteria."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.explore_exit import evaluate_explore_exit
from controller.lifecycle import LifecycleObserver
from controller.phase_contracts import PhaseBudgetTracker
from controller.progress_tracker import ProgressTracker


def test_not_ready_before_explore_finishes() -> None:
    life = LifecycleObserver(repo_path="/tmp/repo")
    phases = PhaseBudgetTracker()
    phases.note_spawn("Explore")
    phases.state.current_phase = "explore"
    progress = ProgressTracker()
    progress.unique_in_repo_reads = 5
    # Explore not completed yet
    status = evaluate_explore_exit(
        lifecycle=life, phases=phases, progress=progress, min_unique_reads=3
    )
    assert status.ready is False


def test_ready_after_explore_complete_and_reads() -> None:
    life = LifecycleObserver(repo_path="/tmp/repo")
    phases = PhaseBudgetTracker()
    phases.note_spawn("Explore")
    phases.state.current_phase = "explore"
    progress = ProgressTracker()
    progress.explore_agent_completed = True
    progress.unique_in_repo_reads = 3
    status = evaluate_explore_exit(
        lifecycle=life, phases=phases, progress=progress, min_unique_reads=3
    )
    assert status.ready is True
    assert "reads" in status.reason.lower() or "Explore" in status.reason


def test_ready_on_budget_warn() -> None:
    life = LifecycleObserver(repo_path="/tmp/repo")
    phases = PhaseBudgetTracker()
    phases.note_spawn("Explore")
    phases.state.current_phase = "explore"
    progress = ProgressTracker()
    status = evaluate_explore_exit(
        lifecycle=life,
        phases=phases,
        progress=progress,
        phase_budget_action="warn",
    )
    assert status.ready is True


def test_ready_on_workspace_confusion() -> None:
    life = LifecycleObserver(repo_path="/tmp/repo")
    phases = PhaseBudgetTracker()
    phases.state.current_phase = "explore"
    progress = ProgressTracker()
    status = evaluate_explore_exit(
        lifecycle=life,
        phases=phases,
        progress=progress,
        workspace_confused=True,
    )
    assert status.ready is True


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
