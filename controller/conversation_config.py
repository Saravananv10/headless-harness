"""Configuration for a single long-lived Chakra conversation (Phase 2 / 2.5)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from controller.trace import DEFAULT_LOG_ROOT


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    return int(raw)


@dataclass
class ConversationConfig:
    """
    Limits for ConversationRunner.

    Session lifetime is gated by wall-clock budget (optional), inactivity /
    progress / repeated failures. Optional max_turns / max_decisions are
    additional safety rails.
    """

    inactivity_timeout_minutes: float = 30.0
    progress_timeout_minutes: float = 12.0
    # Hard stop for the whole conversation (0 = disabled)
    wall_clock_timeout_minutes: float = 25.0
    repeated_failure_threshold: int = 8
    stagnation_grace_cycles: int = 1
    max_repair_iterations: int = 3

    max_turns: int | None = 25
    max_decisions: int | None = 25
    turn_timeout_seconds: float | None = None

    # Progress-aware controller (stricter than session-health activity timers)
    stall_cycles: int = 5
    max_recovery_attempts: int = 3
    denial_loop_threshold: int = 3
    workspace_confusion_threshold: int = 3
    explore_min_reads: int = 3

    working_directory: str | None = None
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    run_id: str | None = None
    log_root: Path | str = DEFAULT_LOG_ROOT
    enable_trace: bool = False

    @classmethod
    def from_env(cls, **overrides: Any) -> ConversationConfig:
        """Build config from HARNESS_* env vars, then apply keyword overrides."""
        values: dict[str, Any] = {
            "inactivity_timeout_minutes": _env_float(
                "HARNESS_INACTIVITY_TIMEOUT_MINUTES", 30.0
            ),
            "progress_timeout_minutes": _env_float(
                "HARNESS_PROGRESS_TIMEOUT_MINUTES", 12.0
            ),
            "wall_clock_timeout_minutes": _env_float(
                "HARNESS_WALL_CLOCK_TIMEOUT_MINUTES", 25.0
            ),
            "repeated_failure_threshold": _env_int(
                "HARNESS_REPEATED_FAILURE_THRESHOLD", 8
            ),
            "stagnation_grace_cycles": _env_int(
                "HARNESS_STAGNATION_GRACE_CYCLES", 1
            ),
            "max_repair_iterations": _env_int(
                "HARNESS_MAX_REPAIR_ITERATIONS", 3
            ),
            "stall_cycles": _env_int("HARNESS_STALL_CYCLES", 5),
            "max_recovery_attempts": _env_int("HARNESS_MAX_RECOVERY_ATTEMPTS", 3),
            "denial_loop_threshold": _env_int("HARNESS_DENIAL_LOOP_THRESHOLD", 3),
            "workspace_confusion_threshold": _env_int(
                "HARNESS_WORKSPACE_CONFUSION_THRESHOLD", 3
            ),
            "explore_min_reads": _env_int("HARNESS_EXPLORE_MIN_READS", 3),
        }
        turn_raw = os.environ.get("HARNESS_TURN_TIMEOUT")
        if turn_raw is not None and str(turn_raw).strip():
            values["turn_timeout_seconds"] = float(turn_raw)
        values.update(overrides)
        return cls(**values)

    @classmethod
    def from_controller_config(cls, config: Any, **overrides: Any) -> ConversationConfig:
        """Adapt legacy ControllerConfig into ConversationConfig."""
        base = cls.from_env(
            max_turns=getattr(config, "max_turns", 40),
            max_decisions=getattr(config, "max_decisions", 40),
            turn_timeout_seconds=getattr(config, "turn_timeout_seconds", None),
            working_directory=getattr(config, "working_directory", None),
            model=getattr(config, "model", None),
            metadata=dict(getattr(config, "metadata", None) or {}),
            run_id=getattr(config, "run_id", None),
            log_root=getattr(config, "log_root", DEFAULT_LOG_ROOT),
            enable_trace=getattr(config, "enable_trace", False),
        )
        if overrides:
            for key, value in overrides.items():
                setattr(base, key, value)
        return base

    @property
    def inactivity_timeout_seconds(self) -> float:
        return max(0.0, float(self.inactivity_timeout_minutes) * 60.0)

    @property
    def progress_timeout_seconds(self) -> float:
        return max(0.0, float(self.progress_timeout_minutes) * 60.0)

    @property
    def wall_clock_timeout_seconds(self) -> float:
        return max(0.0, float(self.wall_clock_timeout_minutes) * 60.0)
