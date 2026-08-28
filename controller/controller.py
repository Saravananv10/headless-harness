"""Controller runtime — thin wrapper over ConversationRunner for legacy callers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from controller.context_builder import build_context
from controller.conversation_config import ConversationConfig
from controller.conversation_runner import ConversationRunner
from controller.decision import ControllerAction
from controller.exceptions import ControllerRunError
from controller.llm import LLMClient
from controller.policies import DecisionPolicy
from controller.trace import ConversationTrace, DEFAULT_LOG_ROOT, new_run_id
from engine.execution_engine import ExecutionEngine
from engine.state import ConversationState

logger = logging.getLogger(__name__)


@dataclass
class ControllerConfig:
    """Runtime limits and defaults (legacy; prefer ConversationConfig)."""

    max_turns: int = 20
    max_decisions: int = 30
    turn_timeout_seconds: float | None = None
    working_directory: str | None = None
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    run_id: str | None = None
    log_root: Path | str = DEFAULT_LOG_ROOT
    enable_trace: bool = False


@dataclass
class ControllerRunResult:
    """Outcome of an autonomous controller run."""

    objective: str
    conversation_id: str
    completed: bool
    summary: str
    turn_count: int
    actions: list[ControllerAction] = field(default_factory=list)
    final_state_snapshot: dict[str, Any] | None = None
    run_id: str | None = None
    trace_path: str | None = None


class Controller:
    """
    Legacy facade over ConversationRunner.

    Production entry points should use ConversationRunner directly.
    Controller remains for older tests and scripts that construct a Controller.
    """

    def __init__(
        self,
        engine: ExecutionEngine,
        llm: LLMClient,
        *,
        config: ControllerConfig | None = None,
        trace: ConversationTrace | None = None,
        policy: DecisionPolicy | None = None,
    ) -> None:
        self._engine = engine
        self._config = config or ControllerConfig()
        self._trace = trace
        if self._trace is None and self._config.enable_trace:
            run_id = self._config.run_id or new_run_id()
            self._trace = ConversationTrace(run_id, self._config.log_root)
        self._policy = policy or DecisionPolicy(llm, trace=self._trace)
        if policy is not None and self._trace is not None:
            self._policy.trace = self._trace
        self._llm = llm

    @property
    def engine(self) -> ExecutionEngine:
        return self._engine

    @property
    def trace(self) -> ConversationTrace | None:
        return self._trace

    def run(self, objective: str) -> ControllerRunResult:
        """Execute an objective via ConversationRunner (single conversation entry point)."""
        if not objective.strip():
            raise ControllerRunError("Objective must be non-empty")

        runner = ConversationRunner(
            self._engine,
            policy=self._policy,
            config=ConversationConfig.from_controller_config(self._config),
            trace=self._trace,
        )
        return runner.run(objective).as_controller_result()

    def decide_next_action(self, state: ConversationState, objective: str) -> ControllerAction:
        """Produce the next action without executing it (for validation and testing)."""
        context = build_context(state, objective=objective)
        return self._policy.decide(context)
