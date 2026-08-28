"""Tests for phase never_reached vs failed/succeeded."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from debugger.load import load_run
from debugger.phases import diagnose_phases

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "debugger"


def test_explore_only_phases_never_reached() -> None:
    run = load_run(FIXTURES / "run_explore_stall")
    report = diagnose_phases(run)
    assert report.status_of("plan") == "never_reached"
    assert report.status_of("implementation") == "never_reached"
    assert report.status_of("verification") == "never_reached"
    assert report.status_of("repair") == "never_reached"


def test_ok_run_phases_succeeded() -> None:
    run = load_run(FIXTURES / "run_ok")
    report = diagnose_phases(run)
    assert report.status_of("plan") in {"entered", "succeeded"}
    assert report.status_of("implementation") in {"entered", "succeeded"}
    assert report.status_of("verification") == "succeeded"


def test_main_agent_writes_mark_implementation_entered() -> None:
    """Writes without general-purpose → implementation entered, not never_reached."""
    from dataclasses import replace

    run = load_run(FIXTURES / "run_explore_stall")
    summary = dict(run.summary or {})
    summary["lifecycle_snapshot"] = {
        "main_agent_write_count": 19,
        "implementation_complete_seen": False,
        "plan_done": True,
    }
    run2 = replace(run, summary=summary)
    report = diagnose_phases(run2)
    assert report.status_of("implementation") == "entered"
    phase = next(p for p in report.phases if p.phase == "implementation")
    assert "main-agent writes" in phase.evidence.lower()


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
