"""Unit tests for deterministic intervention guard (Phase 8)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.intervention_guard import (
    StallTracker,
    evaluate_intervention_guard,
    extract_pending_tool,
    is_echo_only_bash,
)
from controller.policies import DecisionPolicy


def _context(
    *,
    repo: str,
    tool_name: str,
    arguments: dict,
    tool_events: list | None = None,
) -> dict:
    return {
        "working_directory": repo,
        "recent_events": [
            {"event_type": "tool_started", "payload": {"tool_name": tool_name, "arguments": arguments}},
            {"event_type": "intervention_required", "payload": {"prompt": f"Approve {tool_name}?"}},
        ],
        "tool_events": tool_events or [],
    }


def test_extract_pending_tool_from_recent_events() -> None:
    events = [
        {"event_type": "tool_started", "payload": {"tool_name": "Bash", "arguments": {"command": "ls"}}},
        {"event_type": "intervention_required", "payload": {}},
    ]
    pending = extract_pending_tool(events)
    assert pending == ("Bash", {"command": "ls"})


def test_is_echo_only_bash_detects_completion_spam() -> None:
    cmd = 'cd /tmp/repo && echo "IMPLEMENTATION COMPLETE"'
    assert is_echo_only_bash(cmd) is True
    assert is_echo_only_bash("pytest -q") is False
    assert is_echo_only_bash('echo "done" | tee log.txt') is False


def test_auto_approve_in_repo_read() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        plan = repo / "plan.md"
        plan.write_text("# Plan", encoding="utf-8")
        result = evaluate_intervention_guard(
            _context(
                repo=str(repo),
                tool_name="Read",
                arguments={"file_path": str(plan)},
            )
        )
        assert result is not None
        assert result.response == "yes"


def test_auto_deny_out_of_repo_read() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        result = evaluate_intervention_guard(
            _context(
                repo=str(repo),
                tool_name="Read",
                arguments={"file_path": "/etc/passwd"},
            )
        )
        assert result is not None
        assert result.response == "no"


def test_auto_approve_safe_bash() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        result = evaluate_intervention_guard(
            _context(
                repo=str(repo),
                tool_name="Bash",
                arguments={"command": f"cd {repo} && pip install flask"},
            )
        )
        assert result is not None
        assert result.response == "yes"


def test_auto_deny_echo_completion_bash() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        cmd = f'cd {repo} && echo "IMPLEMENTATION COMPLETE"'
        result = evaluate_intervention_guard(
            _context(repo=str(repo), tool_name="Bash", arguments={"command": cmd})
        )
        assert result is not None
        assert result.response == "no"
        assert result.is_echo_bash is True


def test_auto_deny_repeated_identical_bash() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        cmd = f"cd {repo} && ls -la"
        tool_events = [
            {
                "event_type": "tool_started",
                "payload": {"tool_name": "Bash", "arguments": {"command": cmd}},
            },
            {
                "event_type": "tool_started",
                "payload": {"tool_name": "Bash", "arguments": {"command": cmd}},
            },
        ]
        result = evaluate_intervention_guard(
            _context(
                repo=str(repo),
                tool_name="Bash",
                arguments={"command": cmd},
                tool_events=tool_events,
            )
        )
        assert result is not None
        assert result.response == "no"


def test_auto_approve_agent_subagent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        result = evaluate_intervention_guard(
            _context(
                repo=str(repo),
                tool_name="Agent",
                arguments={
                    "subagent_type": "general-purpose",
                    "prompt": "implement",
                    "cwd": str(repo),
                },
            )
        )
        assert result is not None
        assert result.response == "yes"


def test_auto_approve_agent_missing_cwd() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        result = evaluate_intervention_guard(
            _context(
                repo=str(repo),
                tool_name="Agent",
                arguments={"subagent_type": "verification", "prompt": "verify"},
            )
        )
        assert result is not None
        assert result.response == "yes"
        assert "cwd omitted" in result.reasoning.lower()


def test_auto_approve_agent_worktree_isolation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        result = evaluate_intervention_guard(
            _context(
                repo=str(repo),
                tool_name="Agent",
                arguments={
                    "subagent_type": "verification",
                    "prompt": "verify",
                    "cwd": str(repo),
                    "isolation": "worktree",
                },
            )
        )
        assert result is not None
        assert result.response == "yes"


def test_deny_agent_remote_isolation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        result = evaluate_intervention_guard(
            _context(
                repo=str(repo),
                tool_name="Agent",
                arguments={
                    "subagent_type": "verification",
                    "prompt": "verify",
                    "cwd": str(repo),
                    "isolation": "remote",
                },
            )
        )
        assert result is not None
        assert result.response == "no"
        assert "remote" in result.reasoning.lower()


def test_deny_agent_wrong_cwd() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        other = repo / "other"
        other.mkdir()
        result = evaluate_intervention_guard(
            _context(
                repo=str(repo),
                tool_name="Agent",
                arguments={
                    "subagent_type": "Plan",
                    "prompt": "plan",
                    "cwd": str(other),
                },
            )
        )
        assert result is not None
        assert result.response == "no"
        assert "cwd" in result.reasoning.lower()


def test_guard_skips_llm_for_safe_read() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        plan = repo / "plan.md"
        plan.write_text("# Plan", encoding="utf-8")
        llm = MagicMock()
        policy = DecisionPolicy(llm)
        decision = policy.decide_intervention(
            _context(
                repo=str(repo),
                tool_name="Read",
                arguments={"file_path": str(plan)},
            )
        )
        assert decision.response == "yes"
        llm.complete.assert_not_called()


def test_stall_tracker_cancels_after_echo_denials() -> None:
    tracker = StallTracker()
    for _ in range(3):
        tracker.record(tool_name="Bash", response="no", is_echo_bash=True)
    assert tracker.should_cancel_turn() is True


def test_stall_tracker_cancels_after_many_interventions_without_writes() -> None:
    tracker = StallTracker()
    for _ in range(15):
        tracker.record(tool_name="Read", response="yes", is_echo_bash=False)
    assert tracker.should_cancel_turn() is True


def test_stall_tracker_resets_per_turn() -> None:
    tracker = StallTracker()
    tracker.record(tool_name="Bash", response="no", is_echo_bash=True)
    tracker.reset()
    assert tracker.should_cancel_turn() is False


def main() -> int:
    tests = [
        test_extract_pending_tool_from_recent_events,
        test_is_echo_only_bash_detects_completion_spam,
        test_auto_approve_in_repo_read,
        test_auto_deny_out_of_repo_read,
        test_auto_approve_safe_bash,
        test_auto_deny_echo_completion_bash,
        test_auto_deny_repeated_identical_bash,
        test_auto_approve_agent_subagent,
        test_auto_approve_agent_missing_cwd,
        test_auto_approve_agent_worktree_isolation,
        test_deny_agent_remote_isolation,
        test_deny_agent_wrong_cwd,
        test_guard_skips_llm_for_safe_read,
        test_stall_tracker_cancels_after_echo_denials,
        test_stall_tracker_cancels_after_many_interventions_without_writes,
        test_stall_tracker_resets_per_turn,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"All {len(tests)} intervention guard tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
