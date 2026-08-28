"""Unit tests for StatelessAutoApprover (Phase 4)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.llm import DeterministicLLMClient
from controller.tool_approver import StatelessAutoApprover
from controller.trace import ConversationTrace
from controller.conversation_config import ConversationConfig
from controller.conversation_runner import ConversationRunner
from controller.supervisor_policy import CompletionMode, SupervisorPolicy
from engine import ExecutionEngine
from interface import ConnectionConfig
from interface.reference.in_memory_harness import InMemoryHarness


def _events(tool_name: str, arguments: dict) -> list[dict]:
    return [
        {
            "event_type": "tool_started",
            "payload": {"tool_name": tool_name, "arguments": arguments},
        },
        {
            "event_type": "intervention_required",
            "payload": {"prompt": f"Approve {tool_name}?"},
        },
    ]


def test_auto_approve_does_not_use_objective_or_stage() -> None:
    approver = StatelessAutoApprover()
    with tempfile.TemporaryDirectory() as tmp:
        approval = approver.approve(
            intervention_id="int-1",
            prompt="Approve Write?",
            kind="confirm_action",
            working_directory=tmp,
            recent_events=_events("Write", {"file_path": str(Path(tmp) / "a.py")}),
        )
    assert approval.approved
    assert approval.response == "yes"
    assert approval.source.startswith("stateless_auto_approver")
    assert "stage" not in approval.reasoning.lower() or "independent" in approval.reasoning.lower()
    assert approval.tool_name == "Write"
    assert "timestamp" in approval.to_trace_dict()


def test_ambiguous_bash_approves_without_llm() -> None:
    """Guard returns None for ambiguous Bash; Phase 4 must not block on LLM."""
    approver = StatelessAutoApprover()
    with tempfile.TemporaryDirectory() as tmp:
        approval = approver.approve(
            intervention_id="int-2",
            prompt="Approve Bash?",
            kind="confirm_action",
            working_directory=tmp,
            recent_events=_events("Bash", {"command": "docker ps"}),
        )
    assert approval.approved
    assert approval.response == "yes"
    assert "llm" not in approval.source


def test_safety_still_denies_out_of_repo_read() -> None:
    approver = StatelessAutoApprover()
    with tempfile.TemporaryDirectory() as tmp:
        approval = approver.approve(
            intervention_id="int-3",
            prompt="Approve Read?",
            kind="confirm_action",
            working_directory=tmp,
            recent_events=_events("Read", {"file_path": "/etc/passwd"}),
        )
    assert not approval.approved
    assert approval.response == "no"


def test_approval_identical_across_fake_stages() -> None:
    """Same tool request yields same decision regardless of caller 'stage' labels."""
    approver = StatelessAutoApprover()
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "x.py")
        events = _events("Write", {"file_path": path})
        a = approver.approve(
            intervention_id="a",
            prompt="planning stage approve?",
            kind="confirm_action",
            working_directory=tmp,
            recent_events=events,
        )
        b = approver.approve(
            intervention_id="b",
            prompt="verification stage approve?",
            kind="confirm_action",
            working_directory=tmp,
            recent_events=events,
        )
    assert a.response == b.response
    assert a.approved == b.approved
    assert a.reasoning == b.reasoning


def test_runner_traces_tool_approvals() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log_root = Path(tmp) / "logs"
        harness = InMemoryHarness()
        harness.connect(ConnectionConfig(endpoint="memory://p4"))
        engine = ExecutionEngine(harness)
        policy = SupervisorPolicy(
            DeterministicLLMClient([]),
            bootstrap_message="tool_flow",
            completion_mode=CompletionMode.VERDICT_PASS,
        )
        runner = ConversationRunner(
            engine,
            policy=policy,
            config=ConversationConfig(
                working_directory=tmp,
                max_turns=2,
                max_decisions=2,
                enable_trace=True,
                run_id="p4test",
                log_root=log_root,
                inactivity_timeout_minutes=60,
                progress_timeout_minutes=60,
            ),
        )
        # InMemoryHarness "tool_flow" triggers intervention then completes.
        result = runner.run("tool_flow")
        harness.disconnect()

        assert result.trace_path
        lines = Path(result.trace_path).read_text(encoding="utf-8").strip().splitlines()
        records = [json.loads(line) for line in lines]
        approvals = [r for r in records if r.get("type") == "tool_approval"]
        assert approvals, "expected tool_approval entries in trace"
        entry = approvals[0]
        assert entry.get("intervention_id")
        assert entry.get("response")
        assert entry.get("timestamp")
        assert "tool_name" in entry
        # Runner must not call policy.decide_intervention (no LLM intervention source).
        assert not any(
            r.get("type") == "controller_llm_request" and r.get("purpose") == "intervention"
            for r in records
        )


def test_info_request_gets_stateless_continue() -> None:
    approver = StatelessAutoApprover()
    approval = approver.approve(
        intervention_id="info-1",
        prompt="What should I do next?",
        kind="request_information",
        working_directory="/tmp",
        recent_events=[],
    )
    assert approval.response == "continue"
    assert approval.approved


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} passed")
