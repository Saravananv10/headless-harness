"""Adaptive recovery with enforceable execution effects."""

from __future__ import annotations

from dataclasses import dataclass, field

from controller.denial_tracker import DenialTracker
from controller.explore_exit import ExploreExitStatus, evaluate_explore_exit
from controller.lifecycle import LifecycleObserver
from controller.phase_contracts import PhaseBudgetTracker
from controller.progress_tracker import ProgressTracker
from controller.workflow_common import (
    IMPLEMENTATION_COMPLETE_MARKER,
    agent_spawn_instructions,
)
from controller.workspace_confusion import WorkspaceConfusionTracker


@dataclass(frozen=True)
class RecoveryEffects:
    deny_subagent_types: frozenset[str] = field(default_factory=frozenset)
    clear_out_of_repo_denials: bool = False
    lock_workspace: bool = False


@dataclass(frozen=True)
class RecoveryAction:
    kind: str
    reason: str
    message: str
    termination_reason: str | None = None
    """If set, caller should terminate instead of resuming."""
    effects: RecoveryEffects = field(default_factory=RecoveryEffects)


def _effects_for_kind(kind: str) -> RecoveryEffects:
    if kind in {"force_plan_implement"}:
        return RecoveryEffects(deny_subagent_types=frozenset({"explore"}))
    if kind == "implement_first":
        return RecoveryEffects(
            deny_subagent_types=frozenset({"verification", "verify"}),
        )
    if kind in {"denial_strategy", "workspace_reset"}:
        return RecoveryEffects(
            clear_out_of_repo_denials=True,
            lock_workspace=True,
        )
    if kind == "repair_planning":
        return RecoveryEffects(deny_subagent_types=frozenset({"explore"}))
    if kind == "phase_budget":
        return RecoveryEffects(deny_subagent_types=frozenset({"explore"}))
    return RecoveryEffects()


def select_recovery(
    *,
    progress: ProgressTracker,
    denials: DenialTracker,
    phases: PhaseBudgetTracker,
    lifecycle: LifecycleObserver,
    repo_path: str,
    recovery_attempts_used: int,
    max_recovery_attempts: int,
    phase_budget_action: str | None = None,
    workspace: WorkspaceConfusionTracker | None = None,
    explore_exit: ExploreExitStatus | None = None,
) -> RecoveryAction:
    """
    Choose escalate-nudge (with effects) or causal terminate.

    After max_recovery_attempts escalations, return terminate with causal reason.
    """
    repo = (repo_path or "").strip() or "."
    spawned = phases.spawned_subagents
    only_explore = bool(spawned) and spawned <= {"explore"}
    no_pipeline = bool(spawned) and not (
        spawned & {"plan", "general-purpose", "generalpurpose", "verification", "verify"}
    )
    stalled = progress.is_stalled or progress.consecutive_resumes_without_progress >= max(
        1, progress.stall_cycles
    )
    confused = bool(workspace and workspace.is_confused)
    if explore_exit is None:
        explore_exit = evaluate_explore_exit(
            lifecycle=lifecycle,
            phases=phases,
            progress=progress,
            phase_budget_action=phase_budget_action,
            workspace_confused=confused,
        )

    # Causal terminate after recovery budget exhausted
    if recovery_attempts_used >= max(0, max_recovery_attempts) and (
        stalled
        or denials.has_denial_loop
        or confused
        or phase_budget_action == "exceed"
        or only_explore
        or no_pipeline
        or explore_exit.ready
    ):
        if only_explore or explore_exit.ready or (
            no_pipeline and "explore" in spawned and not lifecycle.plan_agent_seen
        ):
            return RecoveryAction(
                kind="terminate",
                reason="Stuck in Explore without Plan/implement after recovery",
                message="",
                termination_reason="stuck_in_explore",
            )
        if denials.has_denial_loop or confused:
            return RecoveryAction(
                kind="terminate",
                reason=f"Denial/workspace loop after recovery: {denials.top_group}",
                message="",
                termination_reason="denial_loop",
            )
        if phase_budget_action == "exceed":
            phase = phases.state.current_phase
            return RecoveryAction(
                kind="terminate",
                reason=f"Phase budget exceeded for {phase}",
                message="",
                termination_reason=f"phase_budget_exceeded:{phase}",
            )
        return RecoveryAction(
            kind="terminate",
            reason=(
                f"No forward progress for "
                f"{progress.consecutive_resumes_without_progress} resume cycles"
            ),
            message="",
            termination_reason="no_forward_progress",
        )

    # Ordered recoveries (before terminate):
    # 0. workspace_reset when confusion dominates
    # 1. empty-subagent-result glitch (Chakra returned nothing — don't blindly re-spawn)
    # 2. implement-first if no COMPLETE
    # 3. denial/cwd strategy
    # 4. repair after rejected PASS streak / FAIL
    # 5. explore ready / force plan
    # 6. phase budget / generic stall

    if confused:
        return RecoveryAction(
            kind="workspace_reset",
            reason=(
                f"Workspace confusion x{workspace.confusion_count if workspace else 0}"
            ),
            message=_workspace_reset_message(repo=repo, workspace=workspace),
            effects=_effects_for_kind("workspace_reset"),
        )

    if progress.consecutive_empty_agent_results >= 2:
        return RecoveryAction(
            kind="empty_subagent_recovery",
            reason=(
                f"Subagent spawns returned no output x"
                f"{progress.consecutive_empty_agent_results} (backend glitch)"
            ),
            message=_empty_subagent_recovery_message(repo=repo),
        )

    if not lifecycle.implementation_complete_seen and (
        lifecycle.plan_done
        or lifecycle.main_agent_write_count > 0
        or lifecycle.last_pass_rejection
    ):
        extra = ""
        if lifecycle.main_agent_write_count > 0:
            extra = (
                f"\n{lifecycle.main_agent_write_count} Write/Edit(s) without "
                f"{IMPLEMENTATION_COMPLETE_MARKER}.\n"
            )
        return RecoveryAction(
            kind="implement_first",
            reason="Implementation incomplete — recover via general-purpose",
            message=_implement_first_message(repo=repo, extra=extra),
            effects=_effects_for_kind("implement_first"),
        )

    if denials.has_denial_loop or denials.out_of_repo_dominates:
        top = denials.top_group
        sample = top[1] if top else ""
        return RecoveryAction(
            kind="denial_strategy",
            reason=(
                f"Repeated denials (top={denials.top_group_count}, "
                f"out_of_repo={denials.out_of_repo_denials})"
            ),
            message=_denial_recovery_message(
                repo=repo,
                sample_target=sample,
                out_of_repo=denials.out_of_repo_dominates,
            ),
            effects=_effects_for_kind("denial_strategy"),
        )

    if (
        lifecycle.rejected_pass_count >= 1
        or (
            lifecycle.last_verdict
            and lifecycle.last_verdict in {"FAIL", "PARTIAL"}
        )
    ) and lifecycle.implementation_complete_seen:
        return RecoveryAction(
            kind="repair_planning",
            reason="Verification failed/rejected — recover via repair planning",
            message=_repair_recovery_message(repo=repo, lifecycle=lifecycle),
            effects=_effects_for_kind("repair_planning"),
        )

    if explore_exit.ready or only_explore or no_pipeline or (
        stalled and not lifecycle.plan_agent_seen and not lifecycle.implementation_gp_seen
    ):
        reason = explore_exit.reason if explore_exit.ready else (
            "Explore/bootstrap without Plan or general-purpose"
        )
        return RecoveryAction(
            kind="force_plan_implement",
            reason=reason,
            message=_force_plan_implement_message(
                repo=repo,
                exit_reason=explore_exit.reason if explore_exit.ready else "",
            ),
            effects=_effects_for_kind("force_plan_implement"),
        )

    if phase_budget_action in {"warn", "exceed"}:
        phase = phases.state.current_phase
        criteria = phases.completion_criteria(phase)
        return RecoveryAction(
            kind="phase_budget",
            reason=(
                f"Phase {phase} near/over budget "
                f"(turns={phases.state.turns_in_phase} "
                f"tools={phases.state.tools_in_phase} "
                f"reads={phases.state.reads_in_phase})"
            ),
            message=_phase_budget_message(repo=repo, phase=phase, criteria=criteria),
            effects=_effects_for_kind("phase_budget"),
        )

    if stalled:
        return RecoveryAction(
            kind="generic_stall",
            reason="Forward progress stall (no workflow milestones)",
            message=_generic_stall_message(repo=repo, phase=phases.state.current_phase),
        )

    return RecoveryAction(
        kind="noop",
        reason="No recovery needed",
        message="",
    )


def _implement_first_message(*, repo: str, extra: str = "") -> str:
    gp_spawn = agent_spawn_instructions(
        repo_path=repo,
        subagent_type="general-purpose",
        extra_prompt_bullets=[
            f"repository root: {repo}",
            "create/activate project-local environment",
            "implement per plan.md",
            f"emit ENV_STATUS: READY then {IMPLEMENTATION_COMPLETE_MARKER}",
        ],
    )
    return f"""HARNESS RECOVERY — IMPLEMENT FIRST

Do not spawn verification yet. Finish implementation with markers.
Repository Root: {repo}
{extra}
1. {gp_spawn}
2. Emit ENV_STATUS: READY and {IMPLEMENTATION_COMPLETE_MARKER}.
3. Only then spawn verification with real build/run + RUNTIME_CHECK: PASS.
"""


def _repair_recovery_message(*, repo: str, lifecycle: LifecycleObserver) -> str:
    reason = lifecycle.last_pass_rejection or lifecycle.last_verdict or "verification failure"
    return f"""HARNESS RECOVERY — REPAIR AFTER VERIFICATION FAILURE

Verification did not produce an authoritative PASS ({reason}).
Repository Root: {repo}

1. Spawn Plan to write repair_plan.md from the verifier report.
2. Spawn general-purpose to apply the repair plan.
3. Emit REPAIR_STATUS: COMPLETE, then re-spawn verification with RUNTIME_CHECK: PASS.
Do not soft-continue without repair.
"""


def _force_plan_implement_message(*, repo: str, exit_reason: str = "") -> str:
    plan_spawn = agent_spawn_instructions(
        repo_path=repo,
        subagent_type="Plan",
        extra_prompt_bullets=[
            f"repository root: {repo}",
            "produce plan.md for the objective",
        ],
    )
    gp_spawn = agent_spawn_instructions(
        repo_path=repo,
        subagent_type="general-purpose",
        extra_prompt_bullets=[
            f"repository root: {repo}",
            "create/activate project-local environment",
            "implement per plan.md",
            f"emit ENV_STATUS: READY then {IMPLEMENTATION_COMPLETE_MARKER}",
        ],
    )
    exit_line = f"\nExplore exit criterion: {exit_reason}\n" if exit_reason else ""
    return f"""HARNESS RECOVERY — EXIT EXPLORE / START PIPELINE

You are stuck exploring or soft-continuing without pipeline progress.
Do NOT keep listing files or retrying denied shell commands.
Further Explore Agent spawns may be denied until Plan or plan.md exists.
{exit_line}
Repository Root (absolute): {repo}
All tools must stay under this directory.

Required next steps (in order):
1. {plan_spawn}
2. After plan.md exists: {gp_spawn}
3. Do not spawn verification until {IMPLEMENTATION_COMPLETE_MARKER} is emitted.

Stop repeating Bash that was denied. Prefer Read/Glob/Edit under the Repository Root.
"""


def _empty_subagent_recovery_message(*, repo: str) -> str:
    return f"""HARNESS RECOVERY — SUBAGENT RETURNED NO OUTPUT

Your last 2+ Agent spawns completed with zero output and zero tool uses.
This is a backend glitch, not evidence that no work exists yet — do not
just spawn another identical Agent call into the same void.

Repository Root: {repo}

Before spawning anything else:
1. Run `ls -la {repo}` and read plan.md yourself directly (do not spawn an
   Agent tool for this — use Read/Bash/Glob directly in this conversation).
2. If the files plan.md describes already exist, inspect and run their
   build/test/validation command yourself and check the real exit code —
   do not assume "no marker seen" means "nothing was done."
3. If that check succeeds, emit the appropriate status marker yourself
   ({IMPLEMENTATION_COMPLETE_MARKER} if implementation is genuinely done)
   based on what you just observed, then proceed to verification.
4. Only spawn general-purpose again if files are genuinely missing or
   incomplete, and make the prompt more explicit/directive this time.
"""


def _workspace_reset_message(
    *, repo: str, workspace: WorkspaceConfusionTracker | None
) -> str:
    sample = ""
    if workspace and workspace.last_target:
        sample = f"\nLast confused target: `{workspace.last_target[:120]}`"
    return f"""HARNESS RECOVERY — WORKSPACE RESET

The agent repeatedly accessed paths outside the assigned repository
(../, absolute paths, or harness files). Soft workspace reset in effect.
{sample}

Repository Root (absolute — use this only): {repo}

Rules:
1. Do NOT use ../ or absolute paths outside Repository Root.
2. Do NOT read harness/controller/logs source.
3. Set cwd to {repo} on every Agent spawn and Bash command.
4. Spawn Plan next (not Explore), then general-purpose implement.
"""


def _denial_recovery_message(
    *, repo: str, sample_target: str, out_of_repo: bool
) -> str:
    sample_line = f"\nLast denied target sample: `{sample_target[:120]}`" if sample_target else ""
    out = ""
    if out_of_repo:
        out = (
            "\nMany denials were outside the repository. Never cd outside "
            f"{repo}. Do not use absolute paths outside Repository Root.\n"
        )
    return f"""HARNESS RECOVERY — CHANGE STRATEGY AFTER DENIALS

Repeated identical or out-of-repo tool requests were denied.{sample_line}
{out}
Repository Root: {repo}

Rules:
1. Do NOT retry the same denied Bash/Read command.
2. Stay under Repository Root for all cwd and paths.
3. Prefer Read, Glob, Grep, Edit, Write inside the repo.
4. If you need a shell, use in-repo commands only (e.g. ls under {repo}).
5. Advance the lifecycle: Plan → general-purpose implement → verification.
"""


def _phase_budget_message(*, repo: str, phase: str, criteria: str) -> str:
    return f"""HARNESS RECOVERY — PHASE BUDGET

Current phase `{phase}` has used its turn/tool/read budget without completing.

Repository Root: {repo}
Completion criteria: {criteria}

Finish this phase now or explicitly fail it with a clear status marker.
Do not soft-continue indefinitely. Do not restart unrelated exploration.
"""


def _generic_stall_message(*, repo: str, phase: str) -> str:
    return f"""HARNESS RECOVERY — NO FORWARD PROGRESS

No workflow milestones (phase change, plan.md, IMPLEMENTATION_STATUS, VERDICT)
for several controller resumes. Tool activity alone does not count. Current phase: {phase}.

Repository Root: {repo}

Change approach: spawn the next required Agent (Plan / general-purpose / verification),
stop repeating denied tools, and emit the phase completion markers.
"""
