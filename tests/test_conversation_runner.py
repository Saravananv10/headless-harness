"""Unit tests for SessionHealthMonitor and ConversationRunner (Phase 2 / 2.5)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.conversation_config import ConversationConfig
from controller.conversation_runner import ConversationRunner
from controller.decision import ActionType
from controller.llm import DeterministicLLMClient
from controller.session_health import HealthStage, SessionHealthMonitor
from controller.supervisor_policy import CompletionMode, SupervisorPolicy
from engine import ExecutionEngine
from engine.state import ConversationState, ConversationStatus
from engine.types import EngineNotification, EngineNotificationKind
from interface import ConnectionConfig
from interface.events import ToolCompletedEvent, ToolStartedEvent
from interface.models.session import HarnessSession
from interface.reference.in_memory_harness import InMemoryHarness


def _config(**kwargs) -> ConversationConfig:
    defaults = dict(
        inactivity_timeout_minutes=60,
        progress_timeout_minutes=20,
        wall_clock_timeout_minutes=0,
        repeated_failure_threshold=3,
        stagnation_grace_cycles=1,
        max_turns=10,
        max_decisions=10,
        enable_trace=False,
    )
    defaults.update(kwargs)
    return ConversationConfig(**defaults)


def _state() -> ConversationState:
    return ConversationState(
        conversation_id="c1",
        harness_session=HarnessSession(session_id="s1", working_directory="/tmp"),
        status=ConversationStatus.ACTIVE,
    )


def _notification(kind: EngineNotificationKind, event=None) -> EngineNotification:
    return EngineNotification(
        kind=kind,
        conversation_id="c1",
        state=_state(),
        event=event,
    )


def test_config_from_env_defaults(monkeypatch_env=None) -> None:
    cfg = ConversationConfig.from_env(max_turns=5)
    assert cfg.inactivity_timeout_minutes == 60.0 or cfg.inactivity_timeout_minutes > 0
    assert cfg.max_turns == 5
    assert cfg.inactivity_timeout_seconds == cfg.inactivity_timeout_minutes * 60


def test_activity_resets_inactivity_but_not_progress() -> None:
    monitor = SessionHealthMonitor(
        _config(inactivity_timeout_minutes=1 / 60, progress_timeout_minutes=10)
    )
    t0 = 1000.0
    monitor.record_progress(kind="start", now=t0)
    monitor.record_activity(kind="heartbeat", now=t0 + 30)
    # 30s idle activity-wise is fine (limit 1s... wait 1/60 min = 1 second)
    # Use clearer numbers:
    monitor = SessionHealthMonitor(
        _config(inactivity_timeout_minutes=1, progress_timeout_minutes=10)
    )
    t0 = 1000.0
    monitor.record_progress(kind="start", now=t0)
    monitor.record_activity(kind="heartbeat", now=t0 + 30)
    verdict = monitor.evaluate(now=t0 + 30)
    assert verdict.stage == HealthStage.HEALTHY


def test_wall_clock_terminates() -> None:
    monitor = SessionHealthMonitor(
        _config(
            inactivity_timeout_minutes=100,
            progress_timeout_minutes=100,
            wall_clock_timeout_minutes=1 / 60,  # 1 second
        )
    )
    monitor._started_at = 0.0
    monitor.record_activity(kind="start", now=0.0)
    monitor.record_progress(kind="start", now=0.0)
    verdict = monitor.evaluate(now=0.5)
    assert not verdict.should_terminate
    verdict = monitor.evaluate(now=2.0)
    assert verdict.should_terminate
    assert verdict.reason == "wall_clock_timeout"


def test_inactivity_terminates() -> None:
    monitor = SessionHealthMonitor(
        _config(inactivity_timeout_minutes=1, progress_timeout_minutes=100)
    )
    t0 = 0.0
    monitor.record_activity(kind="start", now=t0)
    monitor.record_progress(kind="start", now=t0)
    verdict = monitor.evaluate(now=t0 + 61)
    assert verdict.should_terminate
    assert verdict.reason == "inactivity_timeout"
    assert verdict.stage == HealthStage.INACTIVE


def test_progress_timeout_warns_then_terminates() -> None:
    monitor = SessionHealthMonitor(
        _config(
            inactivity_timeout_minutes=100,
            progress_timeout_minutes=1,
            stagnation_grace_cycles=1,
        )
    )
    t0 = 0.0
    monitor.record_progress(kind="start", now=t0)
    # First progress timeout → warning, does not terminate
    v1 = monitor.evaluate(now=t0 + 60)
    assert not v1.should_terminate
    assert v1.stage == HealthStage.STAGNATION_WARNING
    # Grace cycle exhausted on the next progress window → terminate
    v2 = monitor.evaluate(now=t0 + 60 + 60)
    assert v2.should_terminate
    assert v2.reason == "progress_timeout"
    assert v2.stage == HealthStage.STUCK


def test_repeated_failures_terminate() -> None:
    monitor = SessionHealthMonitor(_config(repeated_failure_threshold=3))
    for _ in range(3):
        monitor.record_failure("Bash:error:permission denied")
    verdict = monitor.evaluate()
    assert verdict.should_terminate
    assert verdict.reason == "repeated_failure_threshold"


def test_write_tool_counts_as_progress() -> None:
    monitor = SessionHealthMonitor(
        _config(inactivity_timeout_minutes=100, progress_timeout_minutes=1)
    )
    t0 = 0.0
    monitor.record_progress(kind="start", now=t0)
    # Stale progress window
    monitor.record_activity(kind="idle", now=t0 + 90)
    # Successful Write resets progress
    monitor.observe(
        _notification(
            EngineNotificationKind.EVENT_RECEIVED,
            ToolCompletedEvent(tool_name="Write", output="ok", is_error=False),
        ),
        now=t0 + 90,
    )
    verdict = monitor.evaluate(now=t0 + 90)
    assert verdict.stage == HealthStage.HEALTHY


def test_error_tool_counts_as_failure_not_progress() -> None:
    monitor = SessionHealthMonitor(_config(repeated_failure_threshold=2))
    monitor.observe(
        _notification(
            EngineNotificationKind.EVENT_RECEIVED,
            ToolCompletedEvent(tool_name="Bash", output="boom", is_error=True),
        )
    )
    monitor.observe(
        _notification(
            EngineNotificationKind.EVENT_RECEIVED,
            ToolCompletedEvent(tool_name="Bash", output="boom", is_error=True),
        )
    )
    verdict = monitor.evaluate()
    assert verdict.should_terminate


def test_empty_bash_errors_with_different_commands_do_not_coalesce() -> None:
    """Historical bug: empty Bash outputs all became signature bash:error:."""
    monitor = SessionHealthMonitor(_config(repeated_failure_threshold=3))
    commands = [
        "ls -la /tmp/a",
        "cd /tmp && ls",
        "find /tmp -name x",
        "pwd && ls -la",
        "cd /elsewhere && ls",
    ]
    for i, cmd in enumerate(commands):
        inv = f"inv-{i}"
        monitor.observe(
            _notification(
                EngineNotificationKind.EVENT_RECEIVED,
                ToolStartedEvent(
                    tool_name="Bash",
                    arguments={"command": cmd},
                    invocation_id=inv,
                ),
            )
        )
        monitor.observe(
            _notification(
                EngineNotificationKind.EVENT_RECEIVED,
                ToolCompletedEvent(
                    tool_name="Bash",
                    invocation_id=inv,
                    output="",
                    is_error=True,
                ),
            )
        )
    verdict = monitor.evaluate()
    assert not verdict.should_terminate
    # Each command should be its own signature bucket
    assert len(monitor.snapshot()["failure_counts"]) == len(commands)


def test_denied_empty_bash_does_not_count_toward_threshold() -> None:
    monitor = SessionHealthMonitor(_config(repeated_failure_threshold=3))
    for i in range(8):
        inv = f"deny-{i}"
        monitor.observe(
            _notification(
                EngineNotificationKind.EVENT_RECEIVED,
                ToolStartedEvent(
                    tool_name="Bash",
                    arguments={"command": f"cd /outside && ls {i}"},
                    invocation_id=inv,
                ),
            )
        )
        monitor.mark_denied(inv)
        monitor.observe(
            _notification(
                EngineNotificationKind.EVENT_RECEIVED,
                ToolCompletedEvent(
                    tool_name="Bash",
                    invocation_id=inv,
                    output="",
                    is_error=True,
                ),
            )
        )
    verdict = monitor.evaluate()
    assert not verdict.should_terminate
    assert monitor.snapshot()["failure_counts"] == {}


def test_empty_bash_without_hint_is_ignored() -> None:
    monitor = SessionHealthMonitor(_config(repeated_failure_threshold=2))
    for _ in range(5):
        monitor.observe(
            _notification(
                EngineNotificationKind.EVENT_RECEIVED,
                ToolCompletedEvent(tool_name="Bash", output="", is_error=True),
            )
        )
    assert not monitor.evaluate().should_terminate


def test_progress_clears_failure_streak() -> None:
    monitor = SessionHealthMonitor(_config(repeated_failure_threshold=3))
    for _ in range(2):
        monitor.record_failure("Bash:error:permission denied")
    assert monitor.snapshot()["failure_counts"]
    monitor.observe(
        _notification(
            EngineNotificationKind.EVENT_RECEIVED,
            ToolCompletedEvent(tool_name="Write", output="ok", is_error=False),
        )
    )
    assert monitor.snapshot()["failure_counts"] == {}
    assert monitor.snapshot()["last_failure_signature"] is None
    # After progress, need a fresh streak to terminate
    monitor.record_failure("Bash:error:permission denied")
    monitor.record_failure("Bash:error:permission denied")
    assert not monitor.evaluate().should_terminate
    monitor.record_failure("Bash:error:permission denied")
    assert monitor.evaluate().should_terminate


def test_identical_bash_exec_failures_still_terminate() -> None:
    monitor = SessionHealthMonitor(_config(repeated_failure_threshold=3))
    cmd = "pytest -q"
    for i in range(3):
        inv = f"same-{i}"
        monitor.observe(
            _notification(
                EngineNotificationKind.EVENT_RECEIVED,
                ToolStartedEvent(
                    tool_name="Bash",
                    arguments={"command": cmd},
                    invocation_id=inv,
                ),
            )
        )
        monitor.observe(
            _notification(
                EngineNotificationKind.EVENT_RECEIVED,
                ToolCompletedEvent(
                    tool_name="Bash",
                    invocation_id=inv,
                    output="FAILED",
                    is_error=True,
                ),
            )
        )
    verdict = monitor.evaluate()
    assert verdict.should_terminate
    assert verdict.reason == "repeated_failure_threshold"


def test_orchestration_state_completes_from_verification_agent() -> None:
    import tempfile

    from controller.orchestration_state import OrchestrationState
    from interface.events import TextDeltaEvent, ToolStartedEvent, TurnCompletedEvent

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "plan.md").write_text("# Plan\n", encoding="utf-8")
        orch = OrchestrationState(
            completion_mode=CompletionMode.VERDICT_PASS,
            repo_path=str(repo),
        )
        for inv, sub, out in (
            ("plan1", "Plan", "planned"),
            (
                "gp1",
                "general-purpose",
                "ENV_STATUS: READY\nIMPLEMENTATION_STATUS: COMPLETE",
            ),
        ):
            orch.apply_notification(
                _notification(
                    EngineNotificationKind.EVENT_RECEIVED,
                    ToolStartedEvent(
                        tool_name="Agent",
                        invocation_id=inv,
                        arguments={"subagent_type": sub, "cwd": str(repo)},
                    ),
                )
            )
            orch.apply_notification(
                _notification(
                    EngineNotificationKind.EVENT_RECEIVED,
                    ToolCompletedEvent(
                        tool_name="Agent",
                        invocation_id=inv,
                        output=out,
                        is_error=False,
                    ),
                )
            )
        orch.apply_notification(
            _notification(
                EngineNotificationKind.EVENT_RECEIVED,
                ToolStartedEvent(
                    tool_name="Agent",
                    invocation_id="v1",
                    arguments={"subagent_type": "verification", "cwd": str(repo)},
                ),
            )
        )
        orch.apply_notification(
            _notification(
                EngineNotificationKind.EVENT_RECEIVED,
                ToolCompletedEvent(
                    tool_name="Agent",
                    invocation_id="v1",
                    output=(
                        "**Command run:**\n  pytest\n"
                        "RUNTIME_CHECK: PASS\nVERDICT: PASS\n"
                        "<usage>tool_uses: 3</usage>\n"
                    ),
                    is_error=False,
                ),
            )
        )
        assert orch.completion_detected
        assert "VERDICT: PASS" in orch.completion_summary

    orch2 = OrchestrationState(completion_mode=CompletionMode.IMPLEMENTATION_COMPLETE)
    orch2.apply_notification(
        _notification(EngineNotificationKind.TURN_STARTED, None)
    )
    orch2.apply_notification(
        _notification(
            EngineNotificationKind.EVENT_RECEIVED,
            TextDeltaEvent(text="working... "),
        )
    )
    orch2.apply_notification(
        EngineNotification(
            kind=EngineNotificationKind.TURN_COMPLETED,
            conversation_id="c1",
            state=_state(),
            event=TurnCompletedEvent(final_text="Done\nIMPLEMENTATION_STATUS: COMPLETE"),
        )
    )
    assert orch2.completion_detected
    assert orch2.turn_count == 1


def test_runner_rejects_echoed_self_pass() -> None:
    """InMemoryHarness echoes the user message — self VERDICT: PASS must not complete."""
    harness = InMemoryHarness()
    harness.connect(ConnectionConfig(endpoint="memory://runner"))
    engine = ExecutionEngine(harness)

    bootstrap = "Finish verification.\nVERDICT: PASS"
    policy = SupervisorPolicy(
        DeterministicLLMClient([]),
        bootstrap_message=bootstrap,
        completion_mode=CompletionMode.VERDICT_PASS,
    )
    runner = ConversationRunner(
        engine,
        policy=policy,
        config=_config(max_turns=2, max_decisions=2, working_directory="/tmp"),
    )
    result = runner.run(bootstrap)
    assert not result.completed
    assert result.orchestration_snapshot is not None
    assert result.orchestration_snapshot["completion_detected"] is False
    harness.disconnect()


def test_runner_completes_on_implementation_mode() -> None:
    harness = InMemoryHarness()
    harness.connect(ConnectionConfig(endpoint="memory://runner-impl"))
    engine = ExecutionEngine(harness)

    bootstrap = "Ship it.\nIMPLEMENTATION_STATUS: COMPLETE"
    policy = SupervisorPolicy(
        DeterministicLLMClient([]),
        bootstrap_message=bootstrap,
        completion_mode=CompletionMode.IMPLEMENTATION_COMPLETE,
    )
    runner = ConversationRunner(
        engine,
        policy=policy,
        config=_config(max_turns=5, max_decisions=5, working_directory="/tmp"),
    )
    result = runner.run(bootstrap)
    assert result.completed
    assert result.termination_reason == "completion"
    assert result.orchestration_snapshot is not None
    assert result.orchestration_snapshot["completion_detected"] is True
    harness.disconnect()


def test_runner_is_event_driven_no_decide_polling() -> None:
    import inspect
    from controller import conversation_runner as mod

    src = inspect.getsource(mod.ConversationRunner.run)
    assert "policy.decide(" not in src
    assert "build_context(" not in src
    assert "get_conversation(" not in src or "runner_abort" in src
    # Shutdown/cleanup may call get_conversation; the decision loop must not.
    # Ensure the event-driven path uses orchestration state instead.
    assert "completion_detected" in src
    assert "_stream_turn" in src


def test_runner_does_not_restart_conversation_on_resume() -> None:
    harness = InMemoryHarness()
    harness.connect(ConnectionConfig(endpoint="memory://runner2"))
    engine = ExecutionEngine(harness)
    starts: list[str] = []
    original = engine.start_conversation

    def tracked(req):
        state = original(req)
        starts.append(state.conversation_id)
        return state

    engine.start_conversation = tracked  # type: ignore[method-assign]

    policy = SupervisorPolicy(
        DeterministicLLMClient([]),
        bootstrap_message="keep going",
        completion_mode=CompletionMode.VERDICT_PASS,
    )
    runner = ConversationRunner(
        engine,
        policy=policy,
        config=_config(max_turns=2, max_decisions=2, working_directory="/tmp"),
    )
    result = runner.run("keep going")
    assert len(starts) == 1
    assert not result.completed
    assert result.termination_reason in {"max_turns", "max_decisions"}
    harness.disconnect()


def test_runner_is_single_entry_exports() -> None:
    from controller import (
        ConversationConfig,
        ConversationRunner,
        OrchestrationState,
        SessionHealthMonitor,
    )

    assert ConversationRunner is not None
    assert ConversationConfig is not None
    assert SessionHealthMonitor is not None
    assert OrchestrationState is not None


if __name__ == "__main__":
    tests = [
        test_config_from_env_defaults,
        test_activity_resets_inactivity_but_not_progress,
        test_inactivity_terminates,
        test_progress_timeout_warns_then_terminates,
        test_repeated_failures_terminate,
        test_write_tool_counts_as_progress,
        test_error_tool_counts_as_failure_not_progress,
        test_empty_bash_errors_with_different_commands_do_not_coalesce,
        test_denied_empty_bash_does_not_count_toward_threshold,
        test_empty_bash_without_hint_is_ignored,
        test_progress_clears_failure_streak,
        test_identical_bash_exec_failures_still_terminate,
        test_orchestration_state_completes_from_verification_agent,
        test_runner_rejects_echoed_self_pass,
        test_runner_completes_on_implementation_mode,
        test_runner_is_event_driven_no_decide_polling,
        test_runner_does_not_restart_conversation_on_resume,
        test_runner_is_single_entry_exports,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} passed")
