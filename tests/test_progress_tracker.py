"""Unit tests for live ProgressTracker (workflow vs activity)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.progress_tracker import ProgressTracker


def test_denials_do_not_count_as_progress() -> None:
    pt = ProgressTracker(stall_cycles=3)
    assert pt.on_resume_cycle() == 1
    assert pt.on_resume_cycle() == 2
    assert pt.on_resume_cycle() == 3
    assert pt.is_stalled is True


def test_edit_does_not_reset_stall() -> None:
    """Activity (edits) must not reset workflow stall counter."""
    pt = ProgressTracker(stall_cycles=3)
    pt.on_resume_cycle()
    pt.on_resume_cycle()
    pt.note_edit("/tmp/a.py")
    assert pt.on_resume_cycle() == 3
    assert pt.is_stalled is True
    assert pt.activity_event_count >= 1


def test_milestone_resets_stall() -> None:
    pt = ProgressTracker(stall_cycles=3)
    pt.on_resume_cycle()
    pt.on_resume_cycle()
    pt.note_milestone("implementation")
    assert pt.on_resume_cycle() == 0
    assert pt.is_stalled is False
    assert pt.last_progress_kind == "milestone_implementation"


def test_unique_reads_are_activity_not_progress() -> None:
    pt = ProgressTracker(stall_cycles=5)
    pt.note_read("/a.py")
    pt.note_read("/a.py")
    pt.note_read("/b.py")
    assert pt.progress_event_count == 0
    assert pt.unique_in_repo_reads == 2
    assert pt.activity_event_count >= 2
    assert pt.on_resume_cycle() == 1


def test_phase_transition_is_progress() -> None:
    pt = ProgressTracker(stall_cycles=5)
    pt.note_phase("explore")
    pt.on_resume_cycle()
    pt.note_phase("plan")
    assert pt.on_resume_cycle() == 0
    assert pt.last_progress_kind == "phase_transition"


def test_explore_churn_does_not_clear_stall() -> None:
    pt = ProgressTracker(stall_cycles=3)
    for i in range(10):
        pt.note_read(f"/repo/file{i}.py")
        pt.note_useful_tool("Bash")
    pt.note_agent_spawn("Explore")
    pt.note_agent_completed(subagent_type="Explore")
    assert pt.explore_agent_completed
    for _ in range(3):
        pt.on_resume_cycle()
    assert pt.is_stalled


def test_empty_agent_result_tracked_and_reset() -> None:
    pt = ProgressTracker(stall_cycles=5)
    pt.observe_tool_completed(
        "Agent", output="(Subagent completed but returned no output.)\nagentId: x"
    )
    assert pt.consecutive_empty_agent_results == 1
    pt.observe_tool_completed(
        "Agent", output="(Subagent completed but returned no output.)\nagentId: y"
    )
    assert pt.consecutive_empty_agent_results == 2
    assert pt.max_consecutive_empty_agent_results == 2
    # A real result resets the streak.
    pt.observe_tool_completed("Agent", output="Implemented the feature and wrote tests.")
    assert pt.consecutive_empty_agent_results == 0
    assert pt.max_consecutive_empty_agent_results == 2


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
