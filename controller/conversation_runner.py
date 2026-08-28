"""ConversationRunner — event-driven supervisor for one Chakra conversation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from controller.context_builder import build_intervention_context
from controller.conversation_config import ConversationConfig
from controller.decision import ActionType, ControllerAction, action_to_dict
from controller.denial_tracker import DenialTracker
from controller.exceptions import ControllerRunError, TurnStallDetected
from controller.execution_policy import (
    ExecutionPolicy,
    evaluate_execution_policy,
)
from controller.explore_exit import evaluate_explore_exit
from controller.intervention_guard import StallTracker, is_echo_only_bash
from controller.orchestration_state import OrchestrationState
from controller.phase_contracts import PhaseBudgetTracker
from controller.phase_gate import evaluate_phase_gate
from controller.policies import DecisionPolicy
from controller.progress_tracker import ProgressTracker
from controller.recovery import RecoveryAction, select_recovery
from controller.workspace_confusion import WorkspaceConfusionTracker
from controller.session_health import (
    HealthVerdict,
    SessionHealthMonitor,
    SessionHealthTerminated,
)
from controller.completion import CompletionMode
from controller.supervisor_policy import SupervisorPolicy
from controller.tool_approver import StatelessAutoApprover, ToolApproval
from controller.trace import ConversationTrace, new_run_id
from engine.execution_engine import ExecutionEngine, StartConversationRequest
from engine.state import ConversationState
from engine.types import EngineNotification, EngineNotificationKind, EngineObserver
from interface.events import (
    InterventionRequiredEvent,
    ToolCompletedEvent,
    ToolStartedEvent,
)
from interface.models.requests import InterventionResponse

logger = logging.getLogger(__name__)

# Protocol resume after TURN_COMPLETED when no terminal marker was seen.
# Neutral default; OrchestrationState may replace with a phase-specific nudge.
RESUME_MESSAGE = (
    "Continue in this same conversation. Do not start a new session. "
    "Proceed with whatever remains of the repository lifecycle until the "
    "terminal completion marker is reached."
)

_PROJECT_OBJECTIVE_MARKER = "=== PROJECT OBJECTIVE ==="
_PROJECT_OBJECTIVE_END = "=================================================="


def _extract_user_objective(bootstrap_message: str) -> str:
    """Pull the PROJECT OBJECTIVE section from the unified bootstrap, if present."""
    text = bootstrap_message or ""
    start = text.find(_PROJECT_OBJECTIVE_MARKER)
    if start < 0:
        return text.strip()
    body = text[start + len(_PROJECT_OBJECTIVE_MARKER) :]
    end = body.find(_PROJECT_OBJECTIVE_END)
    if end >= 0:
        body = body[:end]
    return body.strip() or text.strip()


@dataclass
class ConversationRunResult:
    """Outcome of a ConversationRunner session."""

    objective: str
    conversation_id: str
    completed: bool
    summary: str
    turn_count: int
    actions: list[ControllerAction] = field(default_factory=list)
    final_state_snapshot: dict[str, Any] | None = None
    run_id: str | None = None
    trace_path: str | None = None
    termination_reason: str = "completion"
    health_snapshot: dict[str, Any] | None = None
    orchestration_snapshot: dict[str, Any] | None = None
    lifecycle_snapshot: dict[str, Any] | None = None

    def as_controller_result(self):
        from controller.controller import ControllerRunResult

        return ControllerRunResult(
            objective=self.objective,
            conversation_id=self.conversation_id,
            completed=self.completed,
            summary=self.summary,
            turn_count=self.turn_count,
            actions=list(self.actions),
            final_state_snapshot=self.final_state_snapshot,
            run_id=self.run_id,
            trace_path=self.trace_path,
        )


class ConversationRunner:
    """
    Event-driven supervisor for one Chakra conversation (Phase 3–4).

    - Sends bootstrap once, then blocks on streamed events.
    - Updates OrchestrationState on every engine notification.
    - Auto-approves tools via StatelessAutoApprover (no LLM, no stage policy).
    - Resumes the same conversation only after TURN_COMPLETED without a
      terminal marker (protocol requirement of turn-based streams).
    - Never polls conversation state to decide workflow steps.
    - Never starts a second conversation for intermediate events.
    """

    def __init__(
        self,
        engine: ExecutionEngine,
        *,
        policy: DecisionPolicy,
        config: ConversationConfig | None = None,
        trace: ConversationTrace | None = None,
        health: SessionHealthMonitor | None = None,
        completion_mode: CompletionMode | None = None,
        resume_message: str = RESUME_MESSAGE,
        tool_approver: StatelessAutoApprover | None = None,
    ) -> None:
        self._engine = engine
        self._config = config or ConversationConfig()
        self._trace = trace
        if self._trace is None and self._config.enable_trace:
            run_id = self._config.run_id or new_run_id()
            self._trace = ConversationTrace(
                run_id,
                self._config.log_root,
                completion_mode=completion_mode
                if completion_mode is not None
                else (
                    policy.completion_mode
                    if isinstance(policy, SupervisorPolicy)
                    else CompletionMode.VERDICT_PASS
                ),
            )
        self._policy = policy
        if self._trace is not None:
            self._policy.trace = self._trace
        self._health = health or SessionHealthMonitor(self._config)
        if completion_mode is not None:
            self._completion_mode = completion_mode
        elif isinstance(policy, SupervisorPolicy):
            self._completion_mode = policy.completion_mode
        else:
            self._completion_mode = CompletionMode.VERDICT_PASS
        self._resume_message = resume_message.strip() or RESUME_MESSAGE
        self._orch = OrchestrationState(
            completion_mode=self._completion_mode,
            max_repair_iterations=self._config.max_repair_iterations,
            repo_path=self._config.working_directory or "",
            log_root=str(self._config.log_root or ""),
        )
        self._tool_approver = tool_approver or StatelessAutoApprover()
        self._shutting_down = False
        self._progress = ProgressTracker(stall_cycles=self._config.stall_cycles)
        self._denials = DenialTracker(
            loop_threshold=self._config.denial_loop_threshold
        )
        self._phases = PhaseBudgetTracker()
        self._policy = ExecutionPolicy()
        self._workspace = WorkspaceConfusionTracker(
            threshold=self._config.workspace_confusion_threshold,
            repo_path=self._config.working_directory or "",
        )
        self._recovery_attempts = 0
        self._last_phase_budget_action: str | None = None
        self._causal_summary: str = ""
        if self._trace is not None and self._trace.completion_mode is None:
            self._trace.completion_mode = self._completion_mode

    @property
    def engine(self) -> ExecutionEngine:
        return self._engine

    @property
    def trace(self) -> ConversationTrace | None:
        return self._trace

    @property
    def config(self) -> ConversationConfig:
        return self._config

    @property
    def health(self) -> SessionHealthMonitor:
        return self._health

    @property
    def orchestration(self) -> OrchestrationState:
        return self._orch

    def run(self, bootstrap_message: str) -> ConversationRunResult:
        """Block on streamed events until completion, health stop, or safety limit."""
        if not bootstrap_message.strip():
            raise ControllerRunError("Bootstrap message must be non-empty")

        self._orch = OrchestrationState(
            completion_mode=self._completion_mode,
            max_repair_iterations=self._config.max_repair_iterations,
            repo_path=self._config.working_directory or "",
            user_objective=_extract_user_objective(bootstrap_message),
            log_root=str(self._config.log_root or ""),
        )
        self._progress = ProgressTracker(stall_cycles=self._config.stall_cycles)
        self._denials = DenialTracker(
            loop_threshold=self._config.denial_loop_threshold
        )
        self._phases = PhaseBudgetTracker()
        self._policy = ExecutionPolicy()
        self._workspace = WorkspaceConfusionTracker(
            threshold=self._config.workspace_confusion_threshold,
            repo_path=self._config.working_directory or "",
        )
        self._recovery_attempts = 0
        self._last_phase_budget_action = None
        self._causal_summary = ""
        self._shutting_down = False
        previous_observer = self._engine.set_observer(self._make_observer())
        if self._trace:
            self._trace.log(
                "run_started",
                objective=bootstrap_message,
                working_directory=self._config.working_directory,
                max_turns=self._config.max_turns,
                max_decisions=self._config.max_decisions,
                max_repair_iterations=self._config.max_repair_iterations,
                stall_cycles=self._config.stall_cycles,
                max_recovery_attempts=self._config.max_recovery_attempts,
                inactivity_timeout_minutes=self._config.inactivity_timeout_minutes,
                progress_timeout_minutes=self._config.progress_timeout_minutes,
                repeated_failure_threshold=self._config.repeated_failure_threshold,
                entry_point="ConversationRunner",
                execution_model="event_driven",
                lifecycle_owner="chakra",
            )

        state = self._engine.start_conversation(
            StartConversationRequest(
                working_directory=self._config.working_directory,
                model=self._config.model,
                metadata=dict(self._config.metadata),
            )
        )
        conversation_id = state.conversation_id
        self._orch.conversation_id = conversation_id
        if self._trace is not None:
            # Capture Chakra events that do not map to harness events (STREAM_END, etc.).
            def _raw_sink(payload: dict[str, Any], _session=state.harness_session) -> None:
                assert self._trace is not None
                self._trace.log_chakra_raw_event(
                    payload,
                    session_id=_session.session_id,
                    dropped=True,
                )

            state.harness_session.metadata["raw_event_sink"] = _raw_sink
        actions: list[ControllerAction] = []
        summary = ""
        completed = False
        termination_reason = "completion"
        self._health.record_activity(kind="conversation_started")
        self._health.record_progress(kind="conversation_started")

        try:
            # --- Bootstrap: one user message, then react only to stream events ---
            actions.append(
                ControllerAction(
                    action=ActionType.SEND_MESSAGE,
                    reasoning="Bootstrap single Chakra conversation (event-driven).",
                    message=bootstrap_message,
                )
            )
            try:
                self._stream_turn(conversation_id, bootstrap_message, bootstrap_message)
            except SessionHealthTerminated as exc:
                termination_reason = exc.verdict.reason
                summary = self._health_summary(exc.verdict)
                return self._finish(
                    bootstrap_message,
                    conversation_id,
                    completed=False,
                    summary=summary,
                    termination_reason=termination_reason,
                    actions=actions,
                )
            except TurnStallDetected as exc:
                logger.warning("Bootstrap turn stalled: %s", exc)
                if self._trace:
                    self._trace.log("turn_stall_cancelled", reason=str(exc))
                self._health.record_activity(kind="turn_stall")

            self._orch.bootstrap_sent = True
            self._update_phase_budget()

            # --- Event-driven resume loop: only after TURN_COMPLETED without marker ---
            while True:
                if self._orch.completion_detected:
                    summary = self._orch.completion_summary or "Task completed."
                    completed = True
                    termination_reason = "completion"
                    hit = self._orch.completion_hit
                    actions.append(
                        ControllerAction(
                            action=ActionType.COMPLETE,
                            reasoning=(
                                "Explicit terminal marker on terminal conversation event"
                                + (
                                    f" ({hit.marker.value} via {hit.source})"
                                    if hit
                                    else ""
                                )
                            ),
                            summary=summary,
                        )
                    )
                    break

                if self._orch.lifecycle.repair_iterations_exhausted:
                    termination_reason = "max_repair_iterations"
                    summary = (
                        f"Configured max repair iterations reached "
                        f"({self._config.max_repair_iterations}); "
                        f"observed VERDICT: FAIL count="
                        f"{self._orch.lifecycle.verdict_fail_count}."
                    )
                    completed = False
                    if self._trace:
                        self._trace.log(
                            "repair_iterations_exhausted",
                            **self._orch.lifecycle.snapshot(),
                        )
                    break

                health_verdict = self._check_health(conversation_id)
                if health_verdict.should_terminate:
                    termination_reason = health_verdict.reason
                    summary = self._health_summary(health_verdict)
                    completed = False
                    break

                if (
                    self._config.max_turns is not None
                    and self._orch.turn_count >= self._config.max_turns
                ):
                    termination_reason = "max_turns"
                    summary = (
                        f"Reached max_turns ({self._config.max_turns}) without "
                        "terminal completion marker."
                    )
                    completed = False
                    break

                if (
                    self._config.max_decisions is not None
                    and self._orch.turn_count >= self._config.max_decisions
                ):
                    termination_reason = "max_decisions"
                    summary = (
                        f"Reached max_decisions ({self._config.max_decisions}) without "
                        "terminal completion marker."
                    )
                    completed = False
                    break

                # Progress-aware resume: count cycle, maybe recover or terminate.
                self._progress.on_resume_cycle()
                recovery = self._maybe_select_recovery()
                if recovery is not None and recovery.termination_reason:
                    termination_reason = recovery.termination_reason
                    self._causal_summary = recovery.reason
                    summary = recovery.reason or f"Terminated: {termination_reason}"
                    completed = False
                    if self._trace:
                        self._trace.log(
                            "controller_decision",
                            decision="terminate",
                            kind=recovery.kind,
                            reason=termination_reason,
                            causal_summary=recovery.reason,
                            completed=False,
                        )
                    break

                if recovery is not None and recovery.message:
                    resume = recovery.message
                    reasoning = f"Recovery: {recovery.kind}"
                    self._apply_recovery_effects(recovery)
                    self._recovery_attempts += 1
                    if self._trace:
                        from dataclasses import asdict

                        # #region agent log
                        try:
                            import json as _json
                            import time as _time
                            _effects = asdict(recovery.effects)
                            _types = {k: type(v).__name__ for k, v in _effects.items()}
                            with open(
                                "/Users/anuragupperwal/Documents/Coding/Internship_Soket/temp_harness_h/.cursor/debug-ec07a5.log",
                                "a",
                                encoding="utf-8",
                            ) as _df:
                                _df.write(
                                    _json.dumps(
                                        {
                                            "sessionId": "ec07a5",
                                            "runId": "post-fix",
                                            "hypothesisId": "A",
                                            "location": "conversation_runner.py:recover_log",
                                            "message": "effects field types before trace.log",
                                            "data": {
                                                "kind": recovery.kind,
                                                "effect_types": _types,
                                                "deny_subagent_types_repr": repr(
                                                    _effects.get("deny_subagent_types")
                                                ),
                                            },
                                            "timestamp": int(_time.time() * 1000),
                                        }
                                    )
                                    + "\n"
                                )
                        except Exception:
                            pass
                        # #endregion

                        self._trace.log(
                            "controller_decision",
                            decision="recover",
                            kind=recovery.kind,
                            reason=recovery.reason,
                            message_preview=resume[:400],
                            recovery_attempt=self._recovery_attempts,
                            effects=asdict(recovery.effects),
                            execution_policy=self._policy.snapshot(),
                        )
                        # #region agent log
                        try:
                            import json as _json
                            import time as _time

                            with open(
                                "/Users/anuragupperwal/Documents/Coding/Internship_Soket/temp_harness_h/.cursor/debug-ec07a5.log",
                                "a",
                                encoding="utf-8",
                            ) as _df:
                                _df.write(
                                    _json.dumps(
                                        {
                                            "sessionId": "ec07a5",
                                            "runId": "post-fix",
                                            "hypothesisId": "A",
                                            "location": "conversation_runner.py:recover_log_ok",
                                            "message": "recover controller_decision logged successfully",
                                            "data": {"kind": recovery.kind},
                                            "timestamp": int(_time.time() * 1000),
                                        }
                                    )
                                    + "\n"
                                )
                        except Exception:
                            pass
                        # #endregion

                else:
                    resume_nudge = self._orch.resume_nudge(
                        repo_path=self._config.working_directory or "",
                        default=self._resume_message,
                    )
                    resume = resume_nudge.message
                    if resume_nudge.kind == "neutral":
                        reasoning = (
                            "Soft continue — Chakra owns Plan/GP/verify/repair "
                            "sequencing."
                        )
                    else:
                        reasoning = f"Phase nudge: {resume_nudge.kind}"
                    if self._trace:
                        self._trace.log(
                            "controller_decision",
                            decision="resume",
                            kind=resume_nudge.kind,
                            reason=resume_nudge.reason or reasoning,
                            message_preview=resume[:400],
                        )
                        if resume_nudge.kind != "neutral":
                            self._trace.log(
                                "resume_nudge",
                                kind=resume_nudge.kind,
                                reason=resume_nudge.reason,
                                message_preview=resume[:400],
                            )

                self._log_pipeline_metrics()
                actions.append(
                    ControllerAction(
                        action=ActionType.SEND_MESSAGE,
                        reasoning=reasoning,
                        message=resume,
                    )
                )
                try:
                    self._stream_turn(conversation_id, resume, bootstrap_message)
                    self._update_phase_budget()
                except SessionHealthTerminated as exc:
                    termination_reason = exc.verdict.reason
                    summary = self._health_summary(exc.verdict)
                    completed = False
                    break
                except TurnStallDetected as exc:
                    logger.warning("Turn cancelled due to intervention stall: %s", exc)
                    if self._trace:
                        self._trace.log("turn_stall_cancelled", reason=str(exc))
                    self._health.record_activity(kind="turn_stall")
                    continue

            return self._finish(
                bootstrap_message,
                conversation_id,
                completed=completed,
                summary=summary,
                termination_reason=termination_reason,
                actions=actions,
            )
        except Exception as exc:
            if self._trace:
                self._trace.log("run_failed", error=str(exc))
            self._shutting_down = True
            try:
                live = self._engine.get_conversation(conversation_id)
                if live.active_turn is not None:
                    self._engine.cancel_active_turn(
                        conversation_id, reason="runner_abort"
                    )
                self._engine.close_conversation(conversation_id)
            except SessionHealthTerminated:
                pass
            except Exception:
                logger.exception(
                    "Failed to clean up conversation %s after error", conversation_id
                )
            raise
        finally:
            self._engine.set_observer(previous_observer)

    def _stream_turn(
        self,
        conversation_id: str,
        message: str,
        objective: str,
    ) -> None:
        """Block until the turn stream ends; events update OrchestrationState via observer."""
        turn_options: dict[str, Any] = {}
        if self._config.turn_timeout_seconds is not None:
            turn_options["timeout_seconds"] = self._config.turn_timeout_seconds
        if self._trace:
            self._trace.log(
                "stream_turn_started",
                message_preview=message[:200],
                orchestration=self._orch.snapshot(),
            )
        self._engine.execute_turn(
            conversation_id,
            message,
            intervention_handler=self._make_intervention_handler(
                objective,
                conversation_id,
            ),
            model=self._config.model,
            options=turn_options or None,
        )
        if self._trace:
            self._trace.log(
                "stream_turn_finished",
                orchestration=self._orch.snapshot(),
                health=self._health.snapshot(),
            )

    def _finish(
        self,
        bootstrap_message: str,
        conversation_id: str,
        *,
        completed: bool,
        summary: str,
        termination_reason: str,
        actions: list[ControllerAction],
    ) -> ConversationRunResult:
        # Prevent observer from re-raising health terminate during cancel/close.
        self._shutting_down = True
        snapshot = None
        try:
            snapshot = self._engine.reconstruct(conversation_id)
        except Exception:
            logger.exception("Failed to reconstruct conversation %s", conversation_id)
        try:
            live = self._engine.get_conversation(conversation_id)
            if live.active_turn is not None:
                self._engine.cancel_active_turn(
                    conversation_id, reason="runner_shutdown"
                )
            self._engine.close_conversation(conversation_id)
        except SessionHealthTerminated:
            pass
        except Exception:
            logger.exception("Failed to close conversation %s", conversation_id)

        result = ConversationRunResult(
            objective=bootstrap_message,
            conversation_id=conversation_id,
            completed=completed,
            summary=summary,
            turn_count=self._orch.turn_count,
            actions=actions,
            final_state_snapshot=snapshot,
            run_id=self._trace.run_id if self._trace else None,
            trace_path=str(self._trace.path) if self._trace else None,
            termination_reason=termination_reason,
            health_snapshot=self._health.snapshot(),
            orchestration_snapshot=self._orch.snapshot(),
            lifecycle_snapshot=self._orch.lifecycle.snapshot(),
        )
        if self._trace:
            self._log_pipeline_metrics()
            self._trace.log(
                "controller_decision",
                decision="terminate",
                kind=None,
                reason=termination_reason or ("completion" if completed else "unknown"),
                causal_summary=self._causal_summary or summary,
                completed=completed,
            )
            self._trace.log(
                "run_completed",
                summary=summary,
                turn_count=result.turn_count,
                completed=completed,
                termination_reason=termination_reason,
                causal_summary=self._causal_summary or None,
                health=result.health_snapshot,
                orchestration=result.orchestration_snapshot,
                lifecycle=result.lifecycle_snapshot,
                pipeline_metrics=self._pipeline_metrics_dict(),
                actions=[action_to_dict(a) for a in actions],
            )
            self._trace.flush()
        return result


    def _update_phase_budget(self) -> None:
        life = self._orch.lifecycle
        status = self._phases.on_turn_completed(
            life,
            turn_count=self._orch.turn_count,
        )
        self._last_phase_budget_action = status.get("action")
        # Workflow progress: phase transitions + lifecycle milestones
        self._progress.note_phase(status.get("phase"))
        self._progress.sync_lifecycle_milestones(
            plan_done=life.plan_done,
            plan_agent_seen=life.plan_agent_seen,
            implementation_complete=life.implementation_complete_seen,
            env_ready=life.env_ready_seen,
            repair_complete_count=life.repair_complete_count,
            authoritative_pass=life.authoritative_pass,
            last_verdict=life.last_verdict,
            verification_agent_verdict_count=life.verification_agent_verdict_count,
        )
        if self._trace and status.get("action") in {"warn", "exceed"}:
            self._trace.log("phase_budget", **status)

    def _explore_stuck(self) -> bool:
        spawned = self._phases.spawned_subagents
        only_explore = bool(spawned) and spawned <= {"explore"}
        no_pipeline = bool(spawned) and not (
            spawned
            & {"plan", "general-purpose", "generalpurpose", "verification", "verify"}
        )
        exit_status = evaluate_explore_exit(
            lifecycle=self._orch.lifecycle,
            phases=self._phases,
            progress=self._progress,
            phase_budget_action=self._last_phase_budget_action,
            workspace_confused=self._workspace.is_confused,
            min_unique_reads=self._config.explore_min_reads,
        )
        return bool(
            exit_status.ready
            or (
                (only_explore or no_pipeline)
                and self._progress.consecutive_resumes_without_progress
                >= max(2, self._config.stall_cycles // 2)
            )
        )

    def _maybe_select_recovery(self) -> RecoveryAction | None:
        explore_exit = evaluate_explore_exit(
            lifecycle=self._orch.lifecycle,
            phases=self._phases,
            progress=self._progress,
            phase_budget_action=self._last_phase_budget_action,
            workspace_confused=self._workspace.is_confused,
            min_unique_reads=self._config.explore_min_reads,
        )
        needs = (
            self._progress.is_stalled
            or self._denials.has_denial_loop
            or self._denials.out_of_repo_dominates
            or self._workspace.is_confused
            or self._last_phase_budget_action in {"warn", "exceed"}
            or self._explore_stuck()
            or explore_exit.ready
        )
        if not needs:
            return None
        return select_recovery(
            progress=self._progress,
            denials=self._denials,
            phases=self._phases,
            lifecycle=self._orch.lifecycle,
            repo_path=self._config.working_directory or "",
            recovery_attempts_used=self._recovery_attempts,
            max_recovery_attempts=self._config.max_recovery_attempts,
            phase_budget_action=self._last_phase_budget_action,
            workspace=self._workspace,
            explore_exit=explore_exit,
        )

    def _apply_recovery_effects(self, recovery: RecoveryAction) -> None:
        effects = recovery.effects
        self._policy.apply_recovery_effects(effects)
        if effects.clear_out_of_repo_denials:
            self._denials.clear_out_of_repo_groups()
        # Clear Explore deny once Plan exists
        life = self._orch.lifecycle
        if life.plan_done or life.plan_agent_seen:
            self._policy.clear_subagent_denials("explore")

    def _pipeline_metrics_dict(self) -> dict[str, Any]:
        return {
            "useful_tool_calls": self._progress.useful_tool_calls,
            "denied_tool_calls": self._denials.total_denials,
            "forward_progress_events": self._progress.progress_event_count,
            "consecutive_resumes_without_progress": (
                self._progress.consecutive_resumes_without_progress
            ),
            "turns_in_phase": self._phases.state.turns_in_phase,
            "current_phase": self._phases.state.current_phase,
            "phase_entered_at_turn": self._phases.state.phase_entered_turn,
            "phase_transition_latency_seconds": (
                self._phases.state.last_transition_latency_seconds
            ),
            "recovery_attempts": self._recovery_attempts,
            "progress": self._progress.snapshot(),
            "denials": self._denials.snapshot(),
            "phase": self._phases.state.snapshot(),
            "execution_policy": self._policy.snapshot(),
            "workspace_confusion": self._workspace.snapshot(),
        }

    def _log_pipeline_metrics(self) -> None:
        if not self._trace:
            return
        self._trace.log("pipeline_metrics", **self._pipeline_metrics_dict())

    def _health_summary(self, verdict: HealthVerdict) -> str:
        return (
            f"Conversation terminated by session health: {verdict.reason} "
            f"(stage={verdict.stage.value}, detail={verdict.detail})"
        )

    def _check_health(self, conversation_id: str) -> HealthVerdict:
        verdict = self._health.evaluate()
        if verdict.stage.value != "healthy" and self._trace:
            self._trace.log(
                "session_health",
                stage=verdict.stage.value,
                reason=verdict.reason,
                should_terminate=verdict.should_terminate,
                detail=verdict.detail,
                snapshot=self._health.snapshot(),
            )
        if not verdict.should_terminate and verdict.stage.value == "stagnation_warning":
            logger.warning(
                "Session stagnation warning: %s detail=%s",
                verdict.reason,
                verdict.detail,
            )
        return verdict

    def _make_observer(self) -> EngineObserver:
        def observer(notification: EngineNotification) -> None:
            # Event-driven: every notification updates orchestration + health.
            self._orch.apply_notification(notification)
            self._observe_progress(notification)
            self._health.observe(notification)
            if self._trace is not None:
                self._trace.log_engine_notification(notification)
            if self._shutting_down:
                return
            verdict = self._health.evaluate()
            if verdict.should_terminate:
                try:
                    if notification.state.active_turn is not None:
                        self._engine.cancel_active_turn(
                            notification.conversation_id,
                            reason=f"health:{verdict.reason}",
                        )
                except Exception:
                    logger.exception("Health terminate cancel failed")
                raise SessionHealthTerminated(verdict)

        return observer

    def _observe_progress(self, notification: EngineNotification) -> None:
        if notification.kind != EngineNotificationKind.EVENT_RECEIVED:
            return
        event = notification.event
        if isinstance(event, ToolStartedEvent):
            args = event.arguments or {}
            self._progress.observe_tool_started(event.tool_name, args)
            self._phases.note_tool(event.tool_name)
            if event.tool_name == "Read":
                self._phases.note_read()
            if event.tool_name == "Agent":
                sub = (
                    args.get("subagent_type")
                    or args.get("agentType")
                    or args.get("agent_type")
                )
                self._phases.note_spawn(str(sub) if sub else None)
            # Mid-turn tool/read budget pressure
            mid = self._phases.check_tool_read_budgets()
            if mid.get("action") in {"warn", "exceed"}:
                self._last_phase_budget_action = mid["action"]
        elif isinstance(event, ToolCompletedEvent):
            sub = None
            if event.tool_name == "Agent":
                sub = self._orch.lifecycle.agent_type(event.invocation_id)
            self._progress.observe_tool_completed(
                event.tool_name,
                is_error=bool(event.is_error),
                output=event.output or "",
                subagent_type=sub,
            )
            # Sync milestones after Agent/text completions
            life = self._orch.lifecycle
            self._progress.sync_lifecycle_milestones(
                plan_done=life.plan_done,
                plan_agent_seen=life.plan_agent_seen,
                implementation_complete=life.implementation_complete_seen,
                env_ready=life.env_ready_seen,
                repair_complete_count=life.repair_complete_count,
                authoritative_pass=life.authoritative_pass,
                last_verdict=life.last_verdict,
                verification_agent_verdict_count=life.verification_agent_verdict_count,
            )
            if event.tool_name == "Agent" and self._orch.lifecycle.is_verification_invocation(
                event.invocation_id
            ):
                if self._orch.lifecycle.last_raw_verdict:
                    # verification_result is activity; milestone via sync above
                    pass

    def _make_intervention_handler(self, objective: str, conversation_id: str):
        """Phase 4: stateless auto-approve; objective is unused for yes/no."""
        del objective  # Explicit: approval must not depend on task/objective/stage.
        stall_tracker = StallTracker()
        last_turn_id: str | None = None

        def handler(
            event: InterventionRequiredEvent, state: ConversationState
        ) -> InterventionResponse:
            nonlocal last_turn_id
            self._health.record_activity(kind="intervention")
            turn_id = state.active_turn.turn_id if state.active_turn else None
            if turn_id != last_turn_id:
                stall_tracker.reset()
                last_turn_id = turn_id

            # Collect event snapshots for safety checks only — no stage/objective.
            snapshot = build_intervention_context(
                state,
                objective="",
                intervention_id=event.intervention_id,
                prompt=event.prompt,
                kind=event.kind.value,
            )
            recent_events = list(snapshot.get("recent_events") or [])
            approval = self._tool_approver.approve(
                intervention_id=event.intervention_id,
                prompt=event.prompt,
                kind=event.kind.value,
                working_directory=snapshot.get("working_directory")
                or self._config.working_directory,
                recent_events=recent_events,
                tool_events=list(snapshot.get("tool_events") or []),
            )
            # Lifecycle phase gate (after safety): block verify-before-implement.
            if approval.approved:
                gate = evaluate_phase_gate(
                    tool_name=approval.tool_name,
                    arguments=approval.arguments,
                    lifecycle=self._orch.lifecycle,
                )
                if gate is not None and gate.deny:
                    approval = ToolApproval(
                        intervention_id=approval.intervention_id,
                        prompt=approval.prompt,
                        kind=approval.kind,
                        response=gate.response,
                        reasoning=gate.reasoning,
                        tool_name=approval.tool_name,
                        arguments=dict(approval.arguments),
                        approved=False,
                        source="phase_gate",
                    )
            # Recovery execution policy: deny blocked subagent types.
            if approval.approved:
                pol = evaluate_execution_policy(
                    tool_name=approval.tool_name,
                    arguments=approval.arguments,
                    policy=self._policy,
                )
                if pol is not None and pol.deny:
                    approval = ToolApproval(
                        intervention_id=approval.intervention_id,
                        prompt=approval.prompt,
                        kind=approval.kind,
                        response=pol.response,
                        reasoning=pol.reasoning,
                        tool_name=approval.tool_name,
                        arguments=dict(approval.arguments),
                        approved=False,
                        source="execution_policy",
                    )
            self._record_tool_approval(approval)

            denied = approval.response.strip().lower().startswith("no")
            if denied:
                inv = _pending_invocation_id(recent_events)
                if inv:
                    self._health.mark_denied(inv)

            is_echo_bash = False
            if approval.tool_name == "Bash":
                is_echo_bash = is_echo_only_bash(
                    str(approval.arguments.get("command") or "")
                )
            stall_tracker.record(
                tool_name=approval.tool_name,
                response=approval.response,
                is_echo_bash=is_echo_bash and denied,
            )

            logger.info(
                "Tool approval %s: %s (%s) — %s",
                event.intervention_id,
                approval.response,
                approval.tool_name or approval.kind,
                approval.reasoning,
            )

            if stall_tracker.should_cancel_turn():
                self._engine.cancel_active_turn(
                    conversation_id,
                    reason="stall_detected",
                )
                raise TurnStallDetected(
                    "Intervention stall detected; cancelled turn to re-prompt backend"
                )

            return InterventionResponse(
                intervention_id=event.intervention_id,
                response=approval.response,
            )

        return handler

    def _record_tool_approval(self, approval: ToolApproval) -> None:
        denied = (not approval.approved) or approval.response.strip().lower().startswith(
            "no"
        )
        if denied:
            args = approval.arguments or {}
            target = str(
                args.get("command") or args.get("file_path") or args.get("path") or ""
            )
            reason = approval.reasoning or approval.response or "denied"
            self._denials.record(
                tool_name=approval.tool_name or "",
                reason=reason,
                target=target,
                approved=False,
            )
            self._workspace.record_denial(
                tool_name=approval.tool_name or "",
                reason=reason,
                target=target,
            )
        elif approval.approved:
            self._policy.note_successful_in_repo_tool()
        if self._trace is None:
            return
        self._trace.log_tool_approval(approval.to_trace_dict())
        self._trace.log_backend_intervention_response(
            intervention_id=approval.intervention_id,
            prompt=approval.prompt,
            response=approval.response,
            reasoning=approval.reasoning,
        )


def _pending_invocation_id(recent_events: list[dict[str, Any]]) -> str:
    """Invocation id of the tool_started event that triggered the intervention."""
    for event in reversed(recent_events):
        event_type = event.get("event_type")
        if event_type == "intervention_required":
            continue
        if event_type == "tool_started":
            payload = event.get("payload") or {}
            return str(payload.get("invocation_id") or "").strip()
        break
    return ""
