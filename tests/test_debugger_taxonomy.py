"""Tests for debugger failure taxonomy."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from debugger.analyze import analyze_run
from debugger.contracts.validate import validate_contracts
from debugger.load import load_run
from debugger.metrics import extract_metrics
from debugger.phases import diagnose_phases
from debugger.progress import analyze_progress
from debugger.retries import summarize_denials
from debugger.taxonomy import classify_failures

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "debugger"


def test_classify_max_turns() -> None:
    run = load_run(FIXTURES / "run_max_turns")
    result = classify_failures(
        run,
        violations=validate_contracts(run),
        metrics=extract_metrics(run),
        progress=analyze_progress(run, stall_cycles=5),
        phases=diagnose_phases(run),
        denials=summarize_denials(run),
    )
    assert result.primary is not None
    assert result.primary.category == "Limits"
    assert result.primary.subcategory == "max_turns"


def test_classify_rejected_pass() -> None:
    run = load_run(FIXTURES / "run_pass_no_runtime")
    result = classify_failures(
        run,
        violations=validate_contracts(run),
        metrics=extract_metrics(run),
        progress=analyze_progress(run),
        phases=diagnose_phases(run),
        denials=summarize_denials(run),
    )
    assert result.primary is not None
    cats = {result.primary.category} | {s.category for s in result.secondary}
    assert "Verification" in cats or result.primary.category == "Verification"


def test_explore_stall_primary_not_max_turns() -> None:
    run = load_run(FIXTURES / "run_explore_stall")
    analysis = analyze_run(run, stall_cycles=5)
    assert analysis.failure.primary is not None
    assert analysis.failure.primary.category == "Controller"
    assert analysis.failure.primary.subcategory in {
        "Exploration stall",
        "Forward progress stall",
        "Denial loop",
    }
    assert analysis.failure.termination_outcome == "max_turns"
    secondary_cats = {(s.category, s.subcategory) for s in analysis.failure.secondary}
    assert ("Limits", "max_turns") in secondary_cats or any(
        s.category == "Limits" for s in analysis.failure.secondary
    )


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
