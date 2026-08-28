"""Tests for debugger.load."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from debugger.load import load_run, resolve_pipeline_dir

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "debugger"


def test_resolve_pipeline_dir_from_run_root() -> None:
    root = FIXTURES / "run_ok"
    pipe = resolve_pipeline_dir(root)
    assert pipe.name == "pipeline"
    assert (pipe / "trace.jsonl").is_file()


def test_load_run_ok() -> None:
    run = load_run(FIXTURES / "run_ok")
    assert run.run_id == "run_ok"
    assert len(run.normalized) >= 5
    assert run.summary.get("completed") is True
    assert run.verdict.get("verdict") == "PASS"


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
