"""Tests for debugger metrics and compare."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from debugger.load import load_run
from debugger.metrics import compare_metrics, extract_metrics, format_compare_table

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "debugger"


def test_extract_metrics_ok() -> None:
    run = load_run(FIXTURES / "run_ok")
    m = extract_metrics(run)
    assert m.final_status == "Passed"
    assert m.agent_count >= 2
    assert m.file_reads >= 2
    assert m.duplicate_reads >= 1
    assert m.prompt_tokens == 200


def test_compare_two_runs() -> None:
    a = extract_metrics(load_run(FIXTURES / "run_ok"))
    b = extract_metrics(load_run(FIXTURES / "run_max_turns"))
    rows = compare_metrics(a, b)
    assert any(r["metric"] == "Final Status" for r in rows)
    table = format_compare_table(rows, label_a="ok", label_b="max")
    assert "Final Status" in table
    assert "Passed" in table
    assert "Failed" in table


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
