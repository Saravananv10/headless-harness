"""Tests for debugger contract validation."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from debugger.contracts.validate import validate_contracts
from debugger.load import load_run

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "debugger"


def test_pass_without_runtime_check_violation() -> None:
    run = load_run(FIXTURES / "run_pass_no_runtime")
    violations = validate_contracts(run)
    ids = {v.rule_id for v in violations}
    assert "verify.pass_requires_runtime_check" in ids
    assert any(v.severity == "error" for v in violations)


def test_allowed_subagent_ok() -> None:
    run = load_run(FIXTURES / "run_ok")
    violations = validate_contracts(run)
    assert not any(v.rule_id == "tools.allowed_subagent" for v in violations)


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
