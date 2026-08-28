"""Tests for denial retry summarization."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from debugger.load import load_run
from debugger.retries import summarize_denials

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "debugger"


def test_identical_bash_denials_grouped() -> None:
    run = load_run(FIXTURES / "run_explore_stall")
    summary = summarize_denials(run)
    assert summary.total_denials == 8
    assert summary.groups
    top = summary.groups[0]
    assert top.count == 8
    assert "denied 8 times" in top.message
    assert top.tool_name == "Bash"


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
