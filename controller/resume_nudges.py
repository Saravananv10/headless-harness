"""Phase-aware resume nudges for the unified Chakra conversation.

Python does not spawn subagents itself. When lifecycle flags show the pipeline
is stuck, resume messages steer Chakra toward the next required spawn using
existing verification_workflow message builders.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from controller.lifecycle import LifecycleObserver
from controller.verification_workflow import (
    build_repair_implementation_message,
    build_repair_planning_message,
    build_verification_message,
    build_verification_rerun_message,
)
from controller.workflow_common import (
    IMPLEMENTATION_COMPLETE_MARKER,
    VERIFICATION_SUBAGENT_TYPE,
    agent_spawn_instructions,
    lean_verifier_report_block,
)
from verification.parser import Verdict

# Cap re-verify-after-rejected-PASS before escalating to repair.
_MAX_REVERIFY_AFTER_REJECT = 1


@dataclass(frozen=True)
class ResumeNudge:
    kind: str
    message: str
    reason: str = ""


def select_resume_nudge(
    *,
    lifecycle: LifecycleObserver,
    repo_path: str,
    user_objective: str,
    default: str,
    log_root: str | Path | None = None,
) -> ResumeNudge:
    """
    Choose a phase-specific resume message from lifecycle state.

    Priority (highest first):
      1. Plan done / writes seen but no IMPLEMENTATION_STATUS → implement
      2. Rejected PASS without implementation → implement-first
      3. Rejected PASS with implementation, reverify budget left → re-verify
      4. Rejected PASS streak exhausted / FAIL/PARTIAL → repair
      5. Repair done, needs re-verify → verification rerun
      6. Needs first verification → verification spawn
      7. Otherwise → neutral default
    """
    life = lifecycle
    repo = (repo_path or "").strip() or (life.repo_path or "").strip() or "."
    objective = (user_objective or "").strip() or "(see original project objective)"
    raw_report = (life.last_verifier_report or "").strip() or "(no verifier report captured)"
    report = lean_verifier_report_block(
        raw_report,
        repo_path=repo,
        log_root=log_root,
    )
    cycle = max(1, int(life.verdict_fail_count) or 1)
    rejected = (
        life.last_raw_verdict == Verdict.PASS.value
        and life.last_pass_rejection
        and not life.authoritative_pass
    )

    # 1. Never verify/repair while implementation markers are missing once plan exists
    #    or main agent already wrote files without COMPLETE.
    need_implement = (life.plan_done or life.main_agent_write_count > 0) and (
        not life.implementation_complete_seen
    )
    if need_implement:
        extra = ""
        if life.main_agent_write_count > 0:
            extra = (
                f"\nNote: {life.main_agent_write_count} main-agent Write/Edit(s) were "
                "observed without IMPLEMENTATION_STATUS: COMPLETE. Spawn general-purpose "
                "to finish env + markers (do not spawn verification yet).\n"
            )
        if rejected:
            extra += (
                f"\nA VERDICT: PASS was rejected ({life.last_pass_rejection}). "
                "Finish implementation with runtime-ready env before re-verifying.\n"
            )
        return ResumeNudge(
            kind="implement",
            message=_build_implement_message(repo_path=repo, extra=extra),
            reason=(
                "plan/writes present but IMPLEMENTATION_STATUS incomplete"
                + ("; implement-first after rejected PASS" if rejected else "")
            ),
        )

    # 2–3. Rejected PASS with implementation complete
    if rejected:
        if life.rejected_pass_count <= _MAX_REVERIFY_AFTER_REJECT:
            return ResumeNudge(
                kind="reverify_after_rejected_pass",
                message=_build_rejected_pass_message(
                    repo_path=repo,
                    user_objective=objective,
                    rejection_reason=life.last_pass_rejection or "rejected PASS",
                ),
                reason=f"Rejected PASS (#{life.rejected_pass_count}): {life.last_pass_rejection}",
            )
        # Escalate to repair after reverify budget
        return ResumeNudge(
            kind="repair_planning",
            message=build_repair_planning_message(
                user_objective=objective,
                repo_path=repo,
                verifier_report=report,
                repair_cycle=cycle,
            ),
            reason=(
                f"Rejected PASS streak ({life.rejected_pass_count}) — begin repair planning"
            ),
        )

    # 4. Repair path after genuine FAIL / PARTIAL
    if life.needs_repair_and_reverify:
        if not life.repair_plan_done:
            return ResumeNudge(
                kind="repair_planning",
                message=build_repair_planning_message(
                    user_objective=objective,
                    repo_path=repo,
                    verifier_report=report,
                    repair_cycle=cycle,
                ),
                reason=(
                    f"VERDICT: {life.last_raw_verdict or 'FAIL/PARTIAL'} "
                    "and no repair_plan.md"
                ),
            )
        return ResumeNudge(
            kind="repair_implementation",
            message=build_repair_implementation_message(
                repo_path=repo,
                verifier_report=report,
            ),
            reason="repair_plan.md present — apply fixes via general-purpose",
        )

    # 5. Repair complete → re-verify
    if life.needs_verification_spawn and life.repair_gp_seen_since_last_fail:
        return ResumeNudge(
            kind="verification_rerun",
            message=build_verification_rerun_message(
                user_objective=objective,
                repo_path=repo,
                repair_cycle=cycle,
            ),
            reason="REPAIR_STATUS: COMPLETE — re-run verification",
        )

    # 6. First verification after implementation
    if life.needs_verification_spawn:
        return ResumeNudge(
            kind="verification",
            message=build_verification_message(
                user_objective=objective,
                repo_path=repo,
            ),
            reason="IMPLEMENTATION_STATUS: COMPLETE — spawn verification",
        )

    return ResumeNudge(
        kind="neutral",
        message=default,
        reason="No lifecycle gap detected — soft continue",
    )


def _build_rejected_pass_message(
    *,
    repo_path: str,
    user_objective: str,
    rejection_reason: str,
) -> str:
    spawn = agent_spawn_instructions(
        repo_path=repo_path,
        subagent_type=VERIFICATION_SUBAGENT_TYPE,
        extra_prompt_bullets=[
            "the original objective",
            f"repository root: {repo_path}",
            "activate the project-local environment (.venv / node_modules / etc.)",
            "run build, tests, and a smoke run; record commands and exit codes",
            "emit RUNTIME_CHECK: PASS only after a successful build/run with exit code 0",
            "VERDICT: PASS is illegal without RUNTIME_CHECK: PASS",
            "do not PASS on static file review alone",
        ],
    )
    return f"""HARNESS PHASE NUDGE — RE-VERIFY AFTER REJECTED PASS

The harness rejected the last VERDICT: PASS from the verification subagent.
Rejection reason: {rejection_reason}

Do NOT start new features. Re-spawn verification with real runtime checks.
VERDICT: PASS without RUNTIME_CHECK: PASS is forbidden.

Repository Root: {repo_path}
Original objective: {user_objective}

Steps:
1. {spawn}
2. Instruct the verification subagent to activate the project-local environment,
   run build/tests/smoke, record Command run + exit codes, and emit
   RUNTIME_CHECK: PASS before VERDICT: PASS. Static review alone is not enough.
3. Relay the verifier report verbatim. Do not self-assign a verdict.

If runtime verification returns VERDICT: FAIL or PARTIAL (or PASS is rejected again),
the next resume will steer repair.
"""


def _build_implement_message(*, repo_path: str, extra: str = "") -> str:
    spawn = agent_spawn_instructions(
        repo_path=repo_path,
        subagent_type="general-purpose",
        extra_prompt_bullets=[
            f"repository root: {repo_path}",
            "create/activate project-local environment",
            "implement per plan.md",
            f"emit ENV_STATUS: READY then {IMPLEMENTATION_COMPLETE_MARKER}",
        ],
    )
    return f"""HARNESS PHASE NUDGE — ENVIRONMENT + IMPLEMENT

Repository Root: {repo_path}
plan.md exists (or files were written) but implementation markers are not yet complete.
{extra}
Steps:
1. {spawn}
2. Create and activate a project-local environment (.venv / node_modules / etc.).
3. Implement per plan.md. All commands must use that environment.
4. End the general-purpose agent output with ENV_STATUS: READY and
   {IMPLEMENTATION_COMPLETE_MARKER} on their own lines.
5. Do not spawn verification until implementation is complete.
"""
