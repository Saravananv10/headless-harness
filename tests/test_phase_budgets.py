"""Unit tests for phase budgets."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.lifecycle import LifecycleObserver
from controller.phase_contracts import PhaseBudgetTracker, infer_phase


def test_explore_budget_warn_then_exceed() -> None:
    life = LifecycleObserver(repo_path="/tmp/repo")
    phases = PhaseBudgetTracker()
    phases.note_spawn("Explore")
    phases.budgets["explore"] = 3

    actions = []
    for turn in range(1, 6):
        status = phases.on_turn_completed(life, turn_count=turn)
        actions.append(status["action"])
        assert status["phase"] == "explore"

    assert "warn" in actions
    assert "exceed" in actions


def test_explore_tool_budget_exceed() -> None:
    life = LifecycleObserver(repo_path="/tmp/repo")
    phases = PhaseBudgetTracker()
    phases.note_spawn("Explore")
    phases.tool_budgets["explore"] = 5
    phases.state.current_phase = "explore"
    for _ in range(6):
        phases.note_tool("Bash")
    status = phases.check_tool_read_budgets()
    assert status["action"] == "exceed"
    assert status["tools_in_phase"] == 6


def test_explore_read_budget_warn() -> None:
    life = LifecycleObserver(repo_path="/tmp/repo")
    phases = PhaseBudgetTracker()
    phases.note_spawn("Explore")
    phases.read_budgets["explore"] = 3
    phases.state.current_phase = "explore"
    for _ in range(3):
        phases.note_read()
    status = phases.check_tool_read_budgets()
    assert status["action"] in {"warn", "exceed"}


def test_infer_phase_explore() -> None:
    life = LifecycleObserver(repo_path="/tmp/repo")
    assert infer_phase(life, spawned_subagents={"explore"}) == "explore"


def test_infer_phase_implementation() -> None:
    life = LifecycleObserver(repo_path="/tmp/repo")
    life.implementation_gp_seen = True
    assert infer_phase(life, spawned_subagents={"general-purpose"}) == "implementation"


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
