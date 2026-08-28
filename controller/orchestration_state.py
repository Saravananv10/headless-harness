"""Event-driven orchestration state for ConversationRunner (Phase 3 / 6 / 7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from controller.completion import (
    CompletionDetector,
    CompletionHit,
    CompletionMode,
    TerminalEventKind,
)
from controller.completion import TerminalMarker
from controller.lifecycle import LifecycleObserver
from controller.resume_nudges import ResumeNudge, select_resume_nudge
from controller.workflow_common import summarize_preserving_markers
from engine.types import EngineNotification, EngineNotificationKind
from interface.events import (
    TextDeltaEvent,
    ToolCompletedEvent,
    ToolStartedEvent,
    TurnCompletedEvent,
    TurnFailedEvent,
)
from verification.parser import Verdict, is_verification_failure


@dataclass
class OrchestrationState:
    """
    Runner-local state updated exclusively from streamed engine notifications.

    Completion in ``VERDICT_PASS`` mode requires an authoritative PASS from a
    verification Agent. Main-assistant self-reported VERDICT lines are ignored.
    """

    completion_mode: CompletionMode = CompletionMode.VERDICT_PASS
    max_repair_iterations: int = 15
    repo_path: str = ""
    user_objective: str = ""
    log_root: str = ""
    conversation_id: str = ""
    bootstrap_sent: bool = False
    turn_count: int = 0
    event_count: int = 0
    assistant_text: str = ""
    last_final_text: str = ""
    last_event_type: str | None = None
    completion_detected: bool = False
    completion_summary: str = ""
    completion_hit: CompletionHit | None = None
    turn_failed: bool = False
    turn_failed_message: str = ""
    awaiting_turn: bool = False
    last_turn_completed: bool = False
    last_nudge_kind: str = "neutral"
    event_log: list[dict[str, Any]] = field(default_factory=list)
    _detector: CompletionDetector = field(init=False, repr=False)
    lifecycle: LifecycleObserver = field(init=False)

    def __post_init__(self) -> None:
        self._detector = CompletionDetector(self.completion_mode)
        self.lifecycle = LifecycleObserver(
            max_repair_iterations=self.max_repair_iterations,
            repo_path=self.repo_path or "",
        )

    def apply_notification(self, notification: EngineNotification) -> None:
        """Update state from one streamed engine notification."""
        self.event_count += 1
        self.last_event_type = notification.kind.value
        if notification.conversation_id:
            self.conversation_id = notification.conversation_id

        if notification.kind == EngineNotificationKind.TURN_STARTED:
            self.awaiting_turn = True
            self.last_turn_completed = False
            self.turn_failed = False
            self.assistant_text = ""
            self._record("turn_started", notification.detail)
            return

        if notification.kind == EngineNotificationKind.EVENT_RECEIVED and notification.event:
            self._apply_event(notification.event)
            return

        if notification.kind == EngineNotificationKind.TURN_COMPLETED:
            self.awaiting_turn = False
            self.last_turn_completed = True
            self.turn_count += 1
            final_text = ""
            if notification.event and isinstance(notification.event, TurnCompletedEvent):
                final_text = notification.event.final_text or ""
            if not final_text:
                final_text = str((notification.detail or {}).get("final_text") or "")
            text = final_text or self.assistant_text
            if text:
                self.last_final_text = text
                self.assistant_text = text
                # Non-authoritative: ENV telemetry only — never accept main-agent
                # VERDICT or informal IMPLEMENTATION/REPAIR as gate satisfaction.
                self.lifecycle.observe_text(text, source="turn_completed", authoritative=False)
                self._maybe_complete_non_verdict(
                    text,
                    event_kind=TerminalEventKind.TURN_COMPLETED,
                    source="turn_completed",
                )
            self._record(
                "turn_completed",
                {"final_text": (text or "")[:500]},
            )
            return

        if notification.kind == EngineNotificationKind.TURN_FAILED:
            self.awaiting_turn = False
            self.last_turn_completed = True
            self.turn_failed = True
            self.turn_count += 1
            message = str((notification.detail or {}).get("message") or "")
            self.turn_failed_message = message
            self._record("turn_failed", {"message": message})
            return

        if notification.kind == EngineNotificationKind.INTERVENTION_REQUIRED:
            self._record("intervention_required", notification.detail)
            return

        if notification.kind == EngineNotificationKind.INTERVENTION_RESOLVED:
            self._record("intervention_resolved", notification.detail)
            return

        self._record(notification.kind.value, notification.detail)

    def _apply_event(self, event: object) -> None:
        if isinstance(event, TextDeltaEvent):
            if event.text:
                self.assistant_text += event.text
            self.last_event_type = "text_delta"
            return

        if isinstance(event, ToolStartedEvent):
            self.last_event_type = f"tool_started:{event.tool_name}"
            if event.tool_name == "Agent":
                args = event.arguments or {}
                sub = str(
                    args.get("subagent_type")
                    or args.get("agentType")
                    or args.get("agent_type")
                    or ""
                )
                self.lifecycle.register_agent_start(event.invocation_id, sub)
            elif event.tool_name in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
                self.lifecycle.note_main_agent_write()
            self._record(
                "tool_started",
                {
                    "tool_name": event.tool_name,
                    "invocation_id": event.invocation_id,
                    "subagent_type": (event.arguments or {}).get("subagent_type"),
                },
            )
            return

        if isinstance(event, ToolCompletedEvent):
            self.last_event_type = f"tool_completed:{event.tool_name}"
            output = event.output or ""
            if event.tool_name == "Agent":
                authoritative = self.lifecycle.is_verification_invocation(
                    event.invocation_id
                )
                # Call even when output is empty so Plan agent attempts are recorded.
                verdict = self.lifecycle.observe_text(
                    output,
                    source=f"tool_completed:{event.tool_name}",
                    authoritative=authoritative and bool(output.strip()),
                    invocation_id=event.invocation_id,
                )
                if authoritative and verdict is not None:
                    self._apply_authoritative_verdict(
                        verdict,
                        text=output,
                        source=f"tool_completed:{event.tool_name}",
                    )
                elif output and not authoritative:
                    self._maybe_complete_non_verdict(
                        output,
                        event_kind=TerminalEventKind.TOOL_COMPLETED,
                        source=f"tool_completed:{event.tool_name}",
                    )
                if output and not self.completion_detected:
                    self.assistant_text = f"{self.assistant_text}\n{output}".strip()
            elif output:
                self.lifecycle.observe_text(
                    output,
                    source=f"tool_completed:{event.tool_name}",
                    authoritative=False,
                )
                self._maybe_complete_non_verdict(
                    output,
                    event_kind=TerminalEventKind.TOOL_COMPLETED,
                    source=f"tool_completed:{event.tool_name}",
                )
                if not self.completion_detected:
                    self.assistant_text = f"{self.assistant_text}\n{output}".strip()
            self._record(
                "tool_completed",
                {
                    "tool_name": event.tool_name,
                    "is_error": event.is_error,
                    "output_preview": output[:300],
                    "invocation_id": event.invocation_id,
                },
            )
            return

        if isinstance(event, TurnCompletedEvent):
            self.last_final_text = event.final_text
            self.assistant_text = event.final_text or self.assistant_text
            if event.final_text:
                self.lifecycle.observe_text(
                    event.final_text,
                    source="turn_completed_event",
                    authoritative=False,
                )
                self._maybe_complete_non_verdict(
                    event.final_text,
                    event_kind=TerminalEventKind.TURN_COMPLETED,
                    source="turn_completed_event",
                )
            return

        if isinstance(event, TurnFailedEvent):
            self.turn_failed = True
            self.turn_failed_message = event.message
            return

    def _apply_authoritative_verdict(
        self,
        verdict: Verdict,
        *,
        text: str,
        source: str,
    ) -> None:
        """Gate completion on verification-Agent verdicts only."""
        if is_verification_failure(verdict):
            if self.completion_detected:
                self._clear_completion(reason=f"revoked_by_{verdict.value.lower()}")
            return
        if verdict != Verdict.PASS:
            return
        if self.completion_mode != CompletionMode.VERDICT_PASS:
            return
        if self.lifecycle.last_pass_rejection:
            if self.completion_detected:
                self._clear_completion(reason="pass_rejected")
            self._record(
                "pass_rejected",
                {"reason": self.lifecycle.last_pass_rejection},
            )
            return
        hit = self._detector.inspect(
            text,
            event_kind=TerminalEventKind.TOOL_COMPLETED,
            source=source,
        )
        if hit is None:
            hit = CompletionHit(
                marker=TerminalMarker.VERDICT_PASS,
                mode=self.completion_mode,
                event_kind=TerminalEventKind.TOOL_COMPLETED,
                source=source,
                excerpt=text.strip()[-500:],
            )
        self.completion_detected = True
        self.completion_hit = hit
        self.completion_summary = summarize_preserving_markers(text)
        self._record("completion_marker", hit.to_dict())

    def _maybe_complete_non_verdict(
        self,
        text: str,
        *,
        event_kind: TerminalEventKind,
        source: str,
    ) -> None:
        """Complete only for non-verdict modes (implementation / repair markers)."""
        if self.completion_detected:
            return
        if self.completion_mode == CompletionMode.VERDICT_PASS:
            # Never complete from unauthenticated VERDICT: PASS prose.
            return
        hit = self._detector.inspect(text, event_kind=event_kind, source=source)
        if hit is None:
            return
        self.completion_detected = True
        self.completion_hit = hit
        self.completion_summary = summarize_preserving_markers(text)
        self._record("completion_marker", hit.to_dict())

    def _clear_completion(self, *, reason: str) -> None:
        self.completion_detected = False
        self.completion_hit = None
        self.completion_summary = ""
        self._record("completion_cleared", {"reason": reason})

    def resume_nudge(self, *, repo_path: str, default: str) -> ResumeNudge:
        """
        Return a phase-aware resume nudge when lifecycle shows a gap.

        Chakra still owns Agent tool spawns; Python only steers via the
        resume message text.
        """
        repo = (repo_path or "").strip() or (self.repo_path or "").strip() or "."
        if repo and repo != self.lifecycle.repo_path:
            self.lifecycle.repo_path = repo
            self.repo_path = repo
        nudge = select_resume_nudge(
            lifecycle=self.lifecycle,
            repo_path=repo,
            user_objective=self.user_objective,
            default=default,
            log_root=self.log_root or None,
        )
        self.last_nudge_kind = nudge.kind
        if nudge.kind != "neutral":
            self._record(
                "resume_nudge",
                {
                    "kind": nudge.kind,
                    "reason": nudge.reason,
                    "message_preview": nudge.message[:300],
                },
            )
        return nudge

    def resume_message(self, *, repo_path: str, default: str) -> str:
        """Return phase-aware or neutral resume text (see ``resume_nudge``)."""
        return self.resume_nudge(repo_path=repo_path, default=default).message

    def _record(self, kind: str, detail: dict[str, Any] | None = None) -> None:
        entry = {"kind": kind}
        if detail:
            entry["detail"] = detail
        self.event_log.append(entry)
        if len(self.event_log) > 5000:
            self.event_log = self.event_log[-2500:]

    def snapshot(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "completion_mode": self.completion_mode.value,
            "bootstrap_sent": self.bootstrap_sent,
            "turn_count": self.turn_count,
            "event_count": self.event_count,
            "completion_detected": self.completion_detected,
            "completion_hit": self.completion_hit.to_dict() if self.completion_hit else None,
            "last_event_type": self.last_event_type,
            "turn_failed": self.turn_failed,
            "awaiting_turn": self.awaiting_turn,
            "last_turn_completed": self.last_turn_completed,
            "last_nudge_kind": self.last_nudge_kind,
            "completion_summary_preview": (self.completion_summary or "")[:300],
            "lifecycle": self.lifecycle.snapshot(),
        }
