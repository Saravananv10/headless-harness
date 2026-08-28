"""Tests for debugger progress / stall detection."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from debugger.load import load_run
from debugger.progress import analyze_progress

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "debugger"


def test_stall_flagged_on_explore_fixture() -> None:
    run = load_run(FIXTURES / "run_explore_stall")
    progress = analyze_progress(run, stall_cycles=5)
    assert progress.max_consecutive_no_progress_cycles >= 5
    assert progress.forward_progress_stall is True
    assert progress.stalls


def test_no_stall_when_threshold_high() -> None:
    run = load_run(FIXTURES / "run_explore_stall")
    progress = analyze_progress(run, stall_cycles=100)
    assert progress.forward_progress_stall is False


def test_ok_run_has_progress_events() -> None:
    run = load_run(FIXTURES / "run_ok")
    progress = analyze_progress(run, stall_cycles=5)
    assert progress.progress_events
    kinds = {e.kind for e in progress.progress_events}
    assert kinds & {
        "milestone_plan",
        "milestone_implementation",
        "milestone_verify",
        "milestone_env",
        "phase_transition",
    }


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
