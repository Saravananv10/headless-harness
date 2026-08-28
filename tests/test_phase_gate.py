"""Phase gate: deny verification Agent before IMPLEMENTATION_STATUS: COMPLETE."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.lifecycle import LifecycleObserver
from controller.phase_gate import evaluate_phase_gate


def test_deny_verification_without_implementation_complete() -> None:
    life = LifecycleObserver(repo_path="/tmp/repo")
    result = evaluate_phase_gate(
        tool_name="Agent",
        arguments={"subagent_type": "verification", "prompt": "verify"},
        lifecycle=life,
    )
    assert result is not None
    assert result.deny is True
    assert "IMPLEMENTATION_STATUS" in result.reasoning
    assert result.response == "no"


def test_deny_verify_alias_without_complete() -> None:
    life = LifecycleObserver(repo_path="/tmp/repo")
    result = evaluate_phase_gate(
        tool_name="Agent",
        arguments={"subagent_type": "verify"},
        lifecycle=life,
    )
    assert result is not None
    assert result.deny is True


def test_allow_verification_after_implementation_complete() -> None:
    life = LifecycleObserver(repo_path="/tmp/repo")
    life.implementation_complete_seen = True
    result = evaluate_phase_gate(
        tool_name="Agent",
        arguments={"subagent_type": "verification"},
        lifecycle=life,
    )
    assert result is None


def test_allow_plan_and_general_purpose_without_complete() -> None:
    life = LifecycleObserver(repo_path="/tmp/repo")
    for sub in ("Plan", "general-purpose", "Explore"):
        result = evaluate_phase_gate(
            tool_name="Agent",
            arguments={"subagent_type": sub},
            lifecycle=life,
        )
        assert result is None, f"unexpected deny for {sub}"


def test_non_agent_tools_unaffected() -> None:
    life = LifecycleObserver(repo_path="/tmp/repo")
    result = evaluate_phase_gate(
        tool_name="Write",
        arguments={"path": "x.py"},
        lifecycle=life,
    )
    assert result is None


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
