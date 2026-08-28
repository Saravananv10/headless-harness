"""Phase contracts and turn / tool / read budgets for the unified pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from controller.lifecycle import LifecycleObserver, normalize_subagent_type


# Default turn budgets per phase (controller turns while phase is current).
DEFAULT_PHASE_BUDGETS: dict[str, int] = {
    "explore": 8,
    "plan": 6,
    "implementation": 20,
    "verification": 8,
    "repair": 10,
    "bootstrap": 4,
}

# Tool-call and Read budgets (no wall-clock).
DEFAULT_PHASE_TOOL_BUDGETS: dict[str, int] = {
    "explore": 25,
    "plan": 20,
    "implementation": 80,
    "verification": 30,
    "repair": 40,
    "bootstrap": 15,
}

DEFAULT_PHASE_READ_BUDGETS: dict[str, int] = {
    "explore": 12,
    "plan": 25,
    "implementation": 40,
    "verification": 20,
    "repair": 25,
    "bootstrap": 10,
}


@dataclass
class PhaseState:
    current_phase: str = "bootstrap"
    turns_in_phase: int = 0
    tools_in_phase: int = 0
    reads_in_phase: int = 0
    phase_entered_turn: int = 0
    budget_warned: bool = False
    budget_exceeded: bool = False
    phase_history: list[dict[str, Any]] = field(default_factory=list)
    last_transition_latency_seconds: float | None = None
    _phase_entered_monotonic: float | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "current_phase": self.current_phase,
            "turns_in_phase": self.turns_in_phase,
            "tools_in_phase": self.tools_in_phase,
            "reads_in_phase": self.reads_in_phase,
            "phase_entered_turn": self.phase_entered_turn,
            "budget_warned": self.budget_warned,
            "budget_exceeded": self.budget_exceeded,
            "phase_history": list(self.phase_history[-20:]),
            "last_transition_latency_seconds": self.last_transition_latency_seconds,
        }


def infer_phase(
    lifecycle: LifecycleObserver,
    *,
    spawned_subagents: set[str] | None = None,
) -> str:
    """Infer the active pipeline phase from lifecycle + spawn set."""
    spawned = {normalize_subagent_type(s) for s in (spawned_subagents or set())}
    # Highest-priority active work first
    if lifecycle.needs_repair_and_reverify or (
        lifecycle.repair_gp_seen_since_last_fail and not lifecycle.authoritative_pass
    ):
        if lifecycle.last_verdict and lifecycle.last_verdict != "PASS":
            return "repair"
        if lifecycle.repair_plan_done or lifecycle.repair_gp_seen_since_last_fail:
            return "repair"
    if lifecycle.needs_verification_spawn or lifecycle.verification_agent_verdict_count:
        if not lifecycle.authoritative_pass and (
            lifecycle.implementation_complete_seen
            or "verification" in spawned
            or "verify" in spawned
        ):
            if lifecycle.verification_agent_verdict_count or "verification" in spawned:
                return "verification"
    if lifecycle.implementation_complete_seen:
        if lifecycle.needs_verification_spawn:
            return "verification"
        return "implementation"
    if (
        lifecycle.implementation_gp_seen
        or lifecycle.env_ready_seen
        or "general-purpose" in spawned
        or "generalpurpose" in spawned
    ):
        return "implementation"
    if lifecycle.plan_done or lifecycle.plan_agent_seen or "plan" in spawned:
        if lifecycle.needs_env_or_implement_spawn:
            return "plan" if not lifecycle.plan_done else "implementation"
        return "plan"
    if "explore" in spawned:
        return "explore"
    return "bootstrap"


@dataclass
class PhaseBudgetTracker:
    """Track turns / tools / reads spent in the inferred phase and budget warnings."""

    budgets: dict[str, int] = field(
        default_factory=lambda: dict(DEFAULT_PHASE_BUDGETS)
    )
    tool_budgets: dict[str, int] = field(
        default_factory=lambda: dict(DEFAULT_PHASE_TOOL_BUDGETS)
    )
    read_budgets: dict[str, int] = field(
        default_factory=lambda: dict(DEFAULT_PHASE_READ_BUDGETS)
    )
    state: PhaseState = field(default_factory=PhaseState)
    spawned_subagents: set[str] = field(default_factory=set)

    def note_spawn(self, subagent_type: str | None) -> None:
        sub = normalize_subagent_type(subagent_type)
        if sub:
            self.spawned_subagents.add(sub)

    def note_tool(self, tool_name: str | None = None) -> None:
        """Count a non-denied tool use against the current phase tool budget."""
        self.state.tools_in_phase += 1
        del tool_name

    def note_read(self) -> None:
        """Count a Read against the current phase read budget."""
        self.state.reads_in_phase += 1

    def _budget_action_for_counts(self) -> str:
        phase = self.state.current_phase
        turn_budget = int(self.budgets.get(phase, 40))
        tool_budget = int(self.tool_budgets.get(phase, 100))
        read_budget = int(self.read_budgets.get(phase, 100))

        turns = self.state.turns_in_phase
        tools = self.state.tools_in_phase
        reads = self.state.reads_in_phase

        exceed = (
            turns > turn_budget
            or tools > tool_budget
            or reads > read_budget
        )
        warn = (
            turns >= turn_budget
            or tools >= tool_budget
            or reads >= read_budget
        )

        if exceed:
            self.state.budget_exceeded = True
            return "exceed"
        if warn and not self.state.budget_warned:
            self.state.budget_warned = True
            return "warn"
        if self.state.budget_exceeded:
            return "exceed"
        if self.state.budget_warned:
            return "warn"
        return "ok"

    def on_turn_completed(
        self,
        lifecycle: LifecycleObserver,
        *,
        turn_count: int,
        now_monotonic: float | None = None,
    ) -> dict[str, Any]:
        """
        Update phase from lifecycle; increment turns-in-phase.

        Returns a status dict: {phase, turns_in_phase, budget, action, ...}
        where action ∈ ok | warn | exceed.
        """
        import time

        ts = now_monotonic if now_monotonic is not None else time.monotonic()
        inferred = infer_phase(lifecycle, spawned_subagents=self.spawned_subagents)
        prev = self.state.current_phase
        phase_changed = inferred != prev
        if phase_changed:
            latency = None
            if self.state._phase_entered_monotonic is not None:
                latency = ts - self.state._phase_entered_monotonic
            self.state.phase_history.append(
                {
                    "from": prev,
                    "to": inferred,
                    "at_turn": turn_count,
                    "turns_spent": self.state.turns_in_phase,
                    "tools_spent": self.state.tools_in_phase,
                    "reads_spent": self.state.reads_in_phase,
                    "latency_seconds": latency,
                }
            )
            self.state.current_phase = inferred
            self.state.turns_in_phase = 0
            self.state.tools_in_phase = 0
            self.state.reads_in_phase = 0
            self.state.phase_entered_turn = turn_count
            self.state.budget_warned = False
            self.state.budget_exceeded = False
            self.state.last_transition_latency_seconds = latency
            self.state._phase_entered_monotonic = ts

        self.state.turns_in_phase += 1
        action = self._budget_action_for_counts()
        phase = self.state.current_phase
        return {
            "phase": phase,
            "turns_in_phase": self.state.turns_in_phase,
            "tools_in_phase": self.state.tools_in_phase,
            "reads_in_phase": self.state.reads_in_phase,
            "budget": int(self.budgets.get(phase, 40)),
            "tool_budget": int(self.tool_budgets.get(phase, 100)),
            "read_budget": int(self.read_budgets.get(phase, 100)),
            "action": action,
            "phase_changed": phase_changed,
            "spawned": sorted(self.spawned_subagents),
        }

    def check_tool_read_budgets(self) -> dict[str, Any]:
        """Re-evaluate tool/read budgets mid-turn (without incrementing turns)."""
        action = self._budget_action_for_counts()
        phase = self.state.current_phase
        return {
            "phase": phase,
            "turns_in_phase": self.state.turns_in_phase,
            "tools_in_phase": self.state.tools_in_phase,
            "reads_in_phase": self.state.reads_in_phase,
            "budget": int(self.budgets.get(phase, 40)),
            "tool_budget": int(self.tool_budgets.get(phase, 100)),
            "read_budget": int(self.read_budgets.get(phase, 100)),
            "action": action,
            "spawned": sorted(self.spawned_subagents),
        }

    def completion_criteria(self, phase: str | None = None) -> str:
        p = phase or self.state.current_phase
        return {
            "explore": (
                "Explore exit: spawn Plan or write plan.md. Ready after Explore "
                "completes with enough in-repo Reads, or when explore tool/turn "
                "budget warns — further Explore spawns may be denied."
            ),
            "plan": "Finish plan.md / Plan agent; then spawn general-purpose",
            "implementation": "Emit ENV_STATUS: READY and IMPLEMENTATION_STATUS: COMPLETE",
            "verification": "Spawn verification Agent; emit VERDICT with RUNTIME_CHECK",
            "repair": "Write repair_plan.md, apply fixes, emit REPAIR_STATUS: COMPLETE",
            "bootstrap": "Begin Plan or Explore toward the objective; leave Explore when ready",
        }.get(p, "Advance the pipeline")
