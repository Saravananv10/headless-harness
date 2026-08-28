"""Tests for recovery ExecutionPolicy gate."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.execution_policy import ExecutionPolicy, evaluate_execution_policy
from controller.recovery import RecoveryEffects


def test_deny_explore_after_policy() -> None:
    policy = ExecutionPolicy()
    policy.apply_recovery_effects(
        RecoveryEffects(deny_subagent_types=frozenset({"explore"}))
    )
    result = evaluate_execution_policy(
        tool_name="Agent",
        arguments={"subagent_type": "Explore"},
        policy=policy,
    )
    assert result is not None
    assert result.deny is True
    assert "explore" in result.reasoning.lower()


def test_allow_plan_when_explore_denied() -> None:
    policy = ExecutionPolicy()
    policy.deny_subagents("explore")
    result = evaluate_execution_policy(
        tool_name="Agent",
        arguments={"subagent_type": "Plan"},
        policy=policy,
    )
    assert result is None


def test_lock_workspace_flag() -> None:
    policy = ExecutionPolicy()
    policy.apply_recovery_effects(
        RecoveryEffects(lock_workspace=True, clear_out_of_repo_denials=True)
    )
    assert policy.lock_workspace is True
    assert policy.require_in_repo_until_success is True
    policy.note_successful_in_repo_tool()
    assert policy.require_in_repo_until_success is False


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
