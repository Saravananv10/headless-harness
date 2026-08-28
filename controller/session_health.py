"""Session health: liveness vs progress, repeated failures, stagnation (Phase 2.5)."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from controller.conversation_config import ConversationConfig
from engine.types import EngineNotification, EngineNotificationKind
from interface.events import (
    TextDeltaEvent,
    ToolCompletedEvent,
    ToolStartedEvent,
    TurnCompletedEvent,
    TurnFailedEvent,
)

# Tools that usually mean the repository is moving forward.
_PROGRESS_TOOLS = frozenset(
    {
        "Write",
        "Edit",
        "MultiEdit",
        "NotebookEdit",
        "Agent",
    }
)

_MARKER_RE = re.compile(
    r"(IMPLEMENTATION_STATUS:\s*COMPLETE|VERDICT:\s*(?:PASS|FAIL)|"
    r"REPAIR_STATUS:\s*COMPLETE|PLANNING_PHASE|IMPLEMENTATION_PHASE|"
    r"VERIFICATION_PHASE)",
    re.IGNORECASE,
)

_FAILURE_NORMALIZE_RE = re.compile(r"\s+")

# Cap pending tool metadata so long sessions cannot grow without bound.
_MAX_PENDING_TOOLS = 256


class HealthStage(str, Enum):
    HEALTHY = "healthy"
    STAGNATION_WARNING = "stagnation_warning"
    STUCK = "stuck"
    INACTIVE = "inactive"


@dataclass(frozen=True)
class HealthVerdict:
    stage: HealthStage
    should_terminate: bool
    reason: str
    detail: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def healthy(cls) -> HealthVerdict:
        return cls(stage=HealthStage.HEALTHY, should_terminate=False, reason="ok")


@dataclass
class SessionHealthMonitor:
    """
    Track conversation liveness and forward progress.

    - Activity (liveness) resets the inactivity timer.
    - Progress resets the progress timer, clears stagnation warnings, and
      clears repeated-failure counts (forward motion means not stuck).
    - Identical failures accumulate toward repeated_failure_threshold.
    - Approver denials and empty-output tool errors without a useful signature
      do not count toward that threshold.
    - Progress timeout escalates: warn → grace cycles → terminate.
    """

    config: ConversationConfig
    _started_at: float = field(default_factory=time.monotonic)
    _last_activity_at: float = field(default_factory=time.monotonic)
    _last_progress_at: float = field(default_factory=time.monotonic)
    _stage: HealthStage = HealthStage.HEALTHY
    _stagnation_cycles: int = 0
    _failure_counts: dict[str, int] = field(default_factory=dict)
    _last_failure_signature: str | None = None
    _warned: bool = False
    # invocation_id → command/args hint from ToolStartedEvent
    _pending_tools: dict[str, str] = field(default_factory=dict)
    # invocation_ids denied by the intervention approver (not real exec failures)
    _denied_invocations: set[str] = field(default_factory=set)

    def record_activity(self, *, kind: str, now: float | None = None) -> None:
        del kind  # retained for call-site clarity / future tracing
        self._last_activity_at = now if now is not None else time.monotonic()

    def record_progress(self, *, kind: str, now: float | None = None) -> None:
        del kind
        ts = now if now is not None else time.monotonic()
        self._last_activity_at = ts
        self._last_progress_at = ts
        self._stagnation_cycles = 0
        self._warned = False
        self._failure_counts.clear()
        self._last_failure_signature = None
        if self._stage in (HealthStage.STAGNATION_WARNING, HealthStage.STUCK):
            self._stage = HealthStage.HEALTHY

    def record_failure(self, signature: str, *, now: float | None = None) -> None:
        sig = _normalize_failure(signature)
        if not sig:
            return
        self.record_activity(kind="failure", now=now)
        self._failure_counts[sig] = self._failure_counts.get(sig, 0) + 1
        self._last_failure_signature = sig

    def mark_denied(self, invocation_id: str) -> None:
        """Remember a tool invocation that the approver denied (not an exec failure)."""
        inv = (invocation_id or "").strip()
        if not inv:
            return
        self._denied_invocations.add(inv)
        if len(self._denied_invocations) > _MAX_PENDING_TOOLS * 2:
            # Drop arbitrary excess; denials are only needed until completion.
            overflow = len(self._denied_invocations) - _MAX_PENDING_TOOLS
            for _ in range(overflow):
                self._denied_invocations.pop()

    def observe(self, notification: EngineNotification, *, now: float | None = None) -> None:
        """Update health from an engine notification."""
        ts = now if now is not None else time.monotonic()
        self.record_activity(kind=notification.kind.value, now=ts)

        if notification.kind == EngineNotificationKind.EVENT_RECEIVED and notification.event:
            self._observe_event(notification.event, now=ts)
        elif notification.kind == EngineNotificationKind.TURN_COMPLETED:
            final_text = str((notification.detail or {}).get("final_text") or "")
            if _MARKER_RE.search(final_text):
                self.record_progress(kind="turn_marker", now=ts)
        elif notification.kind == EngineNotificationKind.TURN_FAILED:
            code = str((notification.detail or {}).get("code") or "turn_failed")
            message = str((notification.detail or {}).get("message") or "")
            self.record_failure(f"turn_failed:{code}:{message[:160]}", now=ts)

    def _observe_event(self, event: object, *, now: float) -> None:
        if isinstance(event, TextDeltaEvent):
            if event.text and _MARKER_RE.search(event.text):
                self.record_progress(kind="text_marker", now=now)
            return

        if isinstance(event, ToolStartedEvent):
            inv = (event.invocation_id or "").strip()
            if inv:
                hint = _tool_args_hint(event.tool_name, event.arguments or {})
                self._pending_tools[inv] = hint
                if len(self._pending_tools) > _MAX_PENDING_TOOLS:
                    # Drop oldest insertion order (dict preserves order in 3.7+).
                    oldest = next(iter(self._pending_tools))
                    self._pending_tools.pop(oldest, None)
            if event.tool_name in _PROGRESS_TOOLS:
                # Spawn / start of a write is early progress signal.
                self.record_progress(kind=f"tool_started:{event.tool_name}", now=now)
            return

        if isinstance(event, ToolCompletedEvent):
            inv = (event.invocation_id or "").strip()
            hint = self._pending_tools.pop(inv, "") if inv else ""
            denied = bool(inv and inv in self._denied_invocations)
            if inv:
                self._denied_invocations.discard(inv)

            if event.is_error:
                if denied:
                    # Approver denial — not an identical bash exec loop.
                    return
                output = (event.output or "").strip()
                if not output and not hint:
                    # Empty error with no command/args context collapses to a
                    # useless signature (historically bash:error:); ignore.
                    return
                self.record_failure(
                    f"{event.tool_name}:error:{hint}:{output[:200]}",
                    now=now,
                )
                return
            if event.tool_name in _PROGRESS_TOOLS:
                self.record_progress(kind=f"tool_completed:{event.tool_name}", now=now)
                if event.output and _MARKER_RE.search(event.output):
                    self.record_progress(kind="tool_output_marker", now=now)
            elif event.output and _MARKER_RE.search(event.output):
                self.record_progress(kind="tool_output_marker", now=now)
            return

        if isinstance(event, TurnCompletedEvent):
            if event.final_text and _MARKER_RE.search(event.final_text):
                self.record_progress(kind="turn_completed_marker", now=now)
            return

        if isinstance(event, TurnFailedEvent):
            self.record_failure(f"turn_failed:{event.code}:{event.message[:160]}", now=now)

    def evaluate(self, *, now: float | None = None) -> HealthVerdict:
        ts = now if now is not None else time.monotonic()
        inactivity = self.config.inactivity_timeout_seconds
        progress = self.config.progress_timeout_seconds
        wall = self.config.wall_clock_timeout_seconds
        threshold = max(1, int(self.config.repeated_failure_threshold))
        grace = max(0, int(self.config.stagnation_grace_cycles))

        if wall > 0 and (ts - self._started_at) >= wall:
            self._stage = HealthStage.STUCK
            return HealthVerdict(
                stage=HealthStage.STUCK,
                should_terminate=True,
                reason="wall_clock_timeout",
                detail={
                    "elapsed_seconds": ts - self._started_at,
                    "limit_seconds": wall,
                },
            )

        if self._last_failure_signature:
            count = self._failure_counts.get(self._last_failure_signature, 0)
            if count >= threshold:
                self._stage = HealthStage.STUCK
                return HealthVerdict(
                    stage=HealthStage.STUCK,
                    should_terminate=True,
                    reason="repeated_failure_threshold",
                    detail={
                        "signature": self._last_failure_signature,
                        "count": count,
                        "threshold": threshold,
                    },
                )

        if inactivity > 0 and (ts - self._last_activity_at) >= inactivity:
            self._stage = HealthStage.INACTIVE
            return HealthVerdict(
                stage=HealthStage.INACTIVE,
                should_terminate=True,
                reason="inactivity_timeout",
                detail={
                    "idle_seconds": ts - self._last_activity_at,
                    "limit_seconds": inactivity,
                },
            )

        if progress > 0 and (ts - self._last_progress_at) >= progress:
            # Staged escalation: warn, continue monitoring, then terminate.
            if not self._warned:
                self._warned = True
                self._stage = HealthStage.STAGNATION_WARNING
                self._stagnation_cycles = 1
                # Give another full progress window after the warning.
                self._last_progress_at = ts
                return HealthVerdict(
                    stage=HealthStage.STAGNATION_WARNING,
                    should_terminate=False,
                    reason="progress_timeout_warning",
                    detail={
                        "stale_seconds": progress,
                        "grace_cycles": grace,
                        "cycle": self._stagnation_cycles,
                    },
                )

            self._stagnation_cycles += 1
            if self._stagnation_cycles <= grace:
                self._stage = HealthStage.STAGNATION_WARNING
                self._last_progress_at = ts
                return HealthVerdict(
                    stage=HealthStage.STAGNATION_WARNING,
                    should_terminate=False,
                    reason="progress_timeout_monitoring",
                    detail={
                        "cycle": self._stagnation_cycles,
                        "grace_cycles": grace,
                    },
                )

            self._stage = HealthStage.STUCK
            return HealthVerdict(
                stage=HealthStage.STUCK,
                should_terminate=True,
                reason="progress_timeout",
                detail={
                    "stale_seconds": ts - self._last_progress_at + progress,
                    "limit_seconds": progress,
                    "cycles": self._stagnation_cycles,
                },
            )

        if self._stage == HealthStage.STAGNATION_WARNING:
            return HealthVerdict(
                stage=HealthStage.STAGNATION_WARNING,
                should_terminate=False,
                reason="stagnation_monitoring",
                detail={"cycle": self._stagnation_cycles},
            )

        self._stage = HealthStage.HEALTHY
        return HealthVerdict.healthy()

    @property
    def stage(self) -> HealthStage:
        return self._stage

    def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        return {
            "stage": self._stage.value,
            "elapsed_seconds": now - self._started_at,
            "wall_clock_limit_seconds": self.config.wall_clock_timeout_seconds,
            "last_activity_age_seconds": now - self._last_activity_at,
            "last_progress_age_seconds": now - self._last_progress_at,
            "stagnation_cycles": self._stagnation_cycles,
            "failure_counts": dict(self._failure_counts),
            "last_failure_signature": self._last_failure_signature,
            "denied_pending": len(self._denied_invocations),
            "pending_tools": len(self._pending_tools),
        }


def _tool_args_hint(tool_name: str, arguments: dict[str, Any]) -> str:
    """Short stable hint so empty-output errors do not all share one signature."""
    if tool_name == "Bash":
        return str(arguments.get("command") or "")[:120]
    for key in ("file_path", "path", "pattern", "target_directory", "query"):
        if key in arguments and arguments[key] not in (None, ""):
            return f"{key}={str(arguments[key])[:80]}"
    return ""


def _normalize_failure(signature: str) -> str:
    return _FAILURE_NORMALIZE_RE.sub(" ", signature.strip().lower())[:240]


class SessionHealthTerminated(Exception):
    """Raised when session health requires graceful conversation termination."""

    def __init__(self, verdict: HealthVerdict) -> None:
        self.verdict = verdict
        super().__init__(verdict.reason)
