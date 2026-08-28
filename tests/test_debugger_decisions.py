"""Tests for ResumeNudge.reason and controller_decision logging."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.conversation_runner import ConversationRunner
from controller.lifecycle import LifecycleObserver
from controller.resume_nudges import ResumeNudge, select_resume_nudge
from debugger.decisions import extract_decisions
from debugger.load import load_run

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "debugger"


def test_resume_nudge_dataclass_reason() -> None:
    nudge = ResumeNudge(
        kind="repair_planning",
        message="plan repair",
        reason="VERDICT: FAIL and no repair_plan.md",
    )
    assert nudge.reason
    assert "FAIL" in nudge.reason


def test_select_neutral_has_reason() -> None:
    life = LifecycleObserver(repo_path="/tmp/repo")
    nudge = select_resume_nudge(
        lifecycle=life,
        repo_path="/tmp/repo",
        user_objective="build something",
        default="Continue.",
    )
    assert nudge.kind == "neutral"
    assert nudge.reason


def test_extract_decisions_from_fixture() -> None:
    run = load_run(FIXTURES / "run_max_turns")
    decisions = extract_decisions(run)
    kinds = {(d.decision, d.kind) for d in decisions}
    assert ("resume", "neutral") in kinds
    assert ("terminate", None) in kinds


def test_controller_decision_log_shape() -> None:
    """Simulate what conversation_runner logs on resume + terminate."""
    with tempfile.TemporaryDirectory() as tmp:
        nudge = select_resume_nudge(
            lifecycle=LifecycleObserver(repo_path=tmp),
            repo_path=tmp,
            user_objective="obj",
            default="Continue.",
        )
    assert nudge.kind == "neutral"

    logged: list[dict] = []

    class FakeTrace:
        def log(self, type_: str, **kwargs):
            logged.append({"type": type_, **kwargs})

    trace = FakeTrace()
    trace.log(
        "controller_decision",
        decision="resume",
        kind=nudge.kind,
        reason=nudge.reason,
        message_preview=nudge.message[:400],
    )
    trace.log(
        "controller_decision",
        decision="terminate",
        kind=None,
        reason="max_turns",
        completed=False,
    )
    assert logged[0]["type"] == "controller_decision"
    assert logged[0]["kind"] == "neutral"
    assert logged[0]["reason"]
    assert logged[1]["decision"] == "terminate"
    assert ConversationRunner is not None


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
