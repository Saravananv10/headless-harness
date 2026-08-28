"""Unit tests for Phase 5 dual-channel tracing and replay."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.completion import CompletionMode
from controller.conversation_config import ConversationConfig
from controller.conversation_runner import ConversationRunner
from controller.llm import DeterministicLLMClient
from controller.supervisor_policy import SupervisorPolicy
from controller.trace import ConversationTrace
from controller.trace_normalize import normalize_harness_event, serialize_harness_event
from controller.trace_replay import reconstruct_conversation
from engine import ExecutionEngine
from engine.types import EngineNotification, EngineNotificationKind
from interface import ConnectionConfig
from interface.events import (
    TextDeltaEvent,
    ToolCompletedEvent,
    ToolStartedEvent,
    TurnCompletedEvent,
)
from interface.models.session import HarnessSession
from interface.reference.in_memory_harness import InMemoryHarness
from engine.state import ConversationState, ConversationStatus


def test_normalize_captures_tools_agents_verification_and_markers() -> None:
    started = ToolStartedEvent(
        tool_name="Agent",
        arguments={"subagent_type": "verification"},
        invocation_id="a1",
    )
    completed = ToolCompletedEvent(
        tool_name="Agent",
        invocation_id="a1",
        output="Looks good\nVERDICT: PASS\n",
        is_error=False,
    )
    norms = normalize_harness_event(started) + normalize_harness_event(
        completed, completion_mode=CompletionMode.VERDICT_PASS
    )
    types = [n["normalized_type"] for n in norms]
    assert "agent_spawn" in types
    assert "agent_completed" in types
    assert "verification_result" in types
    assert "completion_marker" in types


def test_dual_channel_trace_and_replay() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log_root = Path(tmp)
        trace = ConversationTrace(
            "p5",
            log_root,
            completion_mode=CompletionMode.VERDICT_PASS,
        )
        state = ConversationState(
            conversation_id="c1",
            harness_session=HarnessSession(session_id="s1"),
            status=ConversationStatus.ACTIVE,
        )

        def notify(kind, event=None, detail=None):
            trace.log_engine_notification(
                EngineNotification(
                    kind=kind,
                    conversation_id="c1",
                    state=state,
                    event=event,
                    detail=detail or {},
                )
            )

        notify(
            EngineNotificationKind.TURN_STARTED,
            detail={"turn_id": "t1", "message": "build it"},
        )
        notify(
            EngineNotificationKind.EVENT_RECEIVED,
            TextDeltaEvent(text="Working "),
            detail={"turn_id": "t1"},
        )
        notify(
            EngineNotificationKind.EVENT_RECEIVED,
            ToolStartedEvent(
                tool_name="Write",
                arguments={"file_path": "a.py"},
                invocation_id="w1",
            ),
            detail={"turn_id": "t1"},
        )
        notify(
            EngineNotificationKind.EVENT_RECEIVED,
            ToolCompletedEvent(
                tool_name="Write",
                invocation_id="w1",
                output="ok",
                is_error=False,
            ),
            detail={"turn_id": "t1"},
        )
        notify(
            EngineNotificationKind.EVENT_RECEIVED,
            TurnCompletedEvent(final_text="Done\nVERDICT: PASS"),
            detail={"turn_id": "t1"},
        )
        notify(
            EngineNotificationKind.TURN_COMPLETED,
            TurnCompletedEvent(final_text="Done\nVERDICT: PASS"),
            detail={"turn_id": "t1"},
        )

        assert trace.path.is_file()
        assert trace.raw_path.is_file()

        raw_lines = [
            json.loads(line)
            for line in trace.raw_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        norm_lines = [
            json.loads(line)
            for line in trace.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert raw_lines
        assert all(r["channel"] == "raw" for r in raw_lines)
        assert all(r["channel"] == "normalized" for r in norm_lines)
        # Shared monotonic seq across both files (unique, covering 1..N)
        all_records = sorted(raw_lines + norm_lines, key=lambda r: r["seq"])
        all_seqs = [r["seq"] for r in all_records]
        assert all_seqs == list(range(1, len(all_seqs) + 1))
        assert len(set(all_seqs)) == len(all_seqs)

        replay = reconstruct_conversation(trace.directory)
        assert replay.raw_event_count == len(raw_lines)
        assert replay.normalized_event_count == len(norm_lines)
        assert replay.turns
        assert replay.turns[0].user_message == "build it"
        assert "VERDICT: PASS" in (replay.turns[0].assistant_text or "")
        assert replay.tool_pairs
        assert replay.completion_markers
        # Timeline is ordered and reconstructable
        assert replay.timeline
        seqs = [e["seq"] for e in replay.timeline]
        assert seqs == sorted(seqs)


def test_runner_writes_raw_and_normalized_for_tool_flow() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log_root = Path(tmp) / "logs"
        harness = InMemoryHarness()
        harness.connect(ConnectionConfig(endpoint="memory://p5"))
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
                run_id="p5run",
                log_root=log_root,
                inactivity_timeout_minutes=60,
                progress_timeout_minutes=60,
            ),
        )
        result = runner.run("tool_flow")
        harness.disconnect()
        assert result.trace_path
        directory = Path(result.trace_path).parent
        assert (directory / "raw_events.jsonl").is_file()
        replay = reconstruct_conversation(directory)
        assert replay.raw_event_count > 0
        assert replay.normalized_event_count > 0
        # tool_flow produces a tool request/response via intervention
        assert any(
            t.tool_requests or t.tool_responses for t in replay.turns
        ) or replay.tool_pairs


def test_serialize_harness_event_preserves_type() -> None:
    event = TextDeltaEvent(text="hi")
    payload = serialize_harness_event(event)
    assert payload["event_type"] == "text_delta"
    assert payload["payload"]["text"] == "hi"


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} passed")
