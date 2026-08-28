"""Explore phase exit criteria — when exploration has gathered enough to move on."""

from __future__ import annotations

from dataclasses import dataclass

from controller.lifecycle import LifecycleObserver
from controller.phase_contracts import PhaseBudgetTracker
from controller.progress_tracker import ProgressTracker

DEFAULT_EXPLORE_MIN_READS = 3


@dataclass(frozen=True)
class ExploreExitStatus:
    ready: bool
    reason: str
    """Human-readable criterion that was met (or why not ready)."""


def explore_succeeded(lifecycle: LifecycleObserver, phases: PhaseBudgetTracker) -> bool:
    """True when Explore has been left (Plan / plan.md)."""
    if lifecycle.plan_done or lifecycle.plan_agent_seen:
        return True
    spawned = phases.spawned_subagents
    return "plan" in spawned


def evaluate_explore_exit(
    *,
    lifecycle: LifecycleObserver,
    phases: PhaseBudgetTracker,
    progress: ProgressTracker,
    phase_budget_action: str | None = None,
    workspace_confused: bool = False,
    min_unique_reads: int = DEFAULT_EXPLORE_MIN_READS,
) -> ExploreExitStatus:
    """
    Decide whether Explore/bootstrap should be forced to leave for Plan.

    Ready when still in explore/bootstrap and any of:
      1. Explore Agent completed + unique in-repo reads >= min
      2. Explore tool/turn budget warn|exceed
      3. Workspace confusion threshold hit
    """
    if explore_succeeded(lifecycle, phases):
        return ExploreExitStatus(ready=False, reason="already left Explore (Plan present)")

    phase = phases.state.current_phase
    if phase not in {"explore", "bootstrap"}:
        return ExploreExitStatus(ready=False, reason=f"not in explore/bootstrap ({phase})")

    if workspace_confused:
        return ExploreExitStatus(
            ready=True,
            reason="workspace confusion — force Plan",
        )

    if phase_budget_action in {"warn", "exceed"} and phase in {"explore", "bootstrap"}:
        return ExploreExitStatus(
            ready=True,
            reason=f"explore/bootstrap {phase_budget_action} budget — force Plan",
        )

    if progress.explore_agent_completed and progress.unique_in_repo_reads >= max(
        1, min_unique_reads
    ):
        return ExploreExitStatus(
            ready=True,
            reason=(
                f"Explore completed with {progress.unique_in_repo_reads} unique "
                f"in-repo reads (min {min_unique_reads})"
            ),
        )

    return ExploreExitStatus(
        ready=False,
        reason=(
            f"waiting: explore_done={progress.explore_agent_completed} "
            f"reads={progress.unique_in_repo_reads}/{min_unique_reads}"
        ),
    )
