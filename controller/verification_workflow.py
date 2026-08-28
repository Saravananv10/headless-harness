"""Verification / repair message builders used by resume nudges.

The old VerificationWorkflowPolicy decide-loop was removed; Chakra owns
sequencing in the single-conversation Phase 7 path. Python still sends these
builder messages via controller/resume_nudges.py.
"""

from __future__ import annotations

from controller.workflow_common import (
    AGENT_SPAWN_FORBIDDEN,
    EXPLORE_AGENT_HINT,
    IMPLEMENTATION_COMPLETE_MARKER,
    REPAIR_COMPLETE_MARKER,
    REPAIR_IMPLEMENTATION_PHASE_MARKER,
    REPAIR_PLANNING_PHASE_MARKER,
    VERIFICATION_PHASE_MARKER,
    VERIFICATION_RERUN_MARKER,
    VERIFICATION_SUBAGENT_TYPE,
    agent_spawn_instructions,
    plan_path,
    repair_plan_path,
    summarize,
)

_VERIFICATION_FORBIDDEN = f"""FORBIDDEN during verification orchestration:
• Running builds, tests, or compilation yourself
• Reading files outside the Repository Root
• Reading harness/orchestrator source (headless_harness/, controller/, verification/)
• Self-assigning VERDICT: PASS or VERDICT: FAIL
• Fixing issues yourself — the harness orchestrates repair on FAIL
• {AGENT_SPAWN_FORBIDDEN.strip()}
"""

_VERIFICATION_REQUIRED = """REQUIRED:
• Spawn Agent using AGENT SPAWN PROTOCOL with cwd set to Repository Root
• Include objective, repo, plan.md, and generation summary in the subagent prompt
• Instruct the verification subagent to:
  – activate the project-local environment (.venv / node_modules / etc.)
  – run build, the test suite, and one smoke run
  – record **Command run** lines with exit codes (evidence of real execution)
  – emit RUNTIME_CHECK: PASS only after a successful build/run with exit code 0
  – VERDICT: PASS is **illegal** without RUNTIME_CHECK: PASS
  – Do **not** PASS on static file review alone — FAIL or PARTIAL if runtime checks fail
  – emit VERDICT: PASS only with RUNTIME_CHECK: PASS; otherwise FAIL or PARTIAL
• If subagent launches async, poll/read its .output file until a substantive report with VERDICT: appears
• Relay the verifier report verbatim — final line must be VERDICT: PASS or VERDICT: FAIL
"""


def build_verification_message(
    *,
    user_objective: str,
    repo_path: str,
    generation_summary: str = "",
) -> str:
    plan_file = plan_path(repo_path)
    summary_block = ""
    if generation_summary.strip():
        summary_block = f"\nGeneration summary:\n{summarize(generation_summary, limit=2000)}\n"
    spawn = agent_spawn_instructions(
        repo_path=repo_path,
        subagent_type=VERIFICATION_SUBAGENT_TYPE,
        extra_prompt_bullets=[
            "the original objective",
            f"repository root: {repo_path}",
            f"plan file path: {plan_file}",
            "generation summary and approach taken",
        ],
    )
    return f"""{VERIFICATION_PHASE_MARKER} (mandatory)

Implementation stage reported {IMPLEMENTATION_COMPLETE_MARKER}.
Verification cannot finish until the verification subagent returns VERDICT: PASS.

Repository Root: {repo_path}
Original objective: {user_objective}
Plan: {plan_file}
{summary_block}
Steps:
1. {spawn}
2. The verification subagent is authoritative — you cannot self-assign PASS or FAIL.
3. Relay the verifier report verbatim. The final line must be exactly VERDICT: PASS or VERDICT: FAIL.
4. Do not fix issues yourself — the harness will orchestrate repair if the verdict is FAIL.

{_VERIFICATION_FORBIDDEN}
{_VERIFICATION_REQUIRED}

{EXPLORE_AGENT_HINT}
"""


def build_verification_rerun_message(
    *,
    user_objective: str,
    repo_path: str,
    repair_cycle: int,
) -> str:
    plan_file = plan_path(repo_path)
    spawn = agent_spawn_instructions(
        repo_path=repo_path,
        subagent_type=VERIFICATION_SUBAGENT_TYPE,
        extra_prompt_bullets=[
            "the original objective",
            f"repository root: {repo_path}",
            f"plan file path: {plan_file}",
            f"re-verify after repair cycle {repair_cycle}",
        ],
    )
    return f"""{VERIFICATION_RERUN_MARKER} #{repair_cycle}

Repair cycle {repair_cycle} is complete ({REPAIR_COMPLETE_MARKER}).
Re-run independent verification before the pipeline can finish.

Repository Root: {repo_path}
Original objective: {user_objective}
Plan: {plan_file}

{spawn}
Relay the full verifier report. Final line must be VERDICT: PASS or VERDICT: FAIL.
Do NOT self-assign a verdict — only the verification subagent may issue VERDICT.

{_VERIFICATION_FORBIDDEN}
{_VERIFICATION_REQUIRED}
"""


def build_verification_continue_message(
    *, repo_path: str, self_assigned_rejected: bool = False
) -> str:
    rejection = ""
    if self_assigned_rejected:
        rejection = (
            "\nYour previous response included a self-assigned VERDICT. "
            "That is not accepted. Wait for the verification subagent to finish "
            "and relay its report verbatim.\n"
        )
    spawn = agent_spawn_instructions(
        repo_path=repo_path,
        subagent_type=VERIFICATION_SUBAGENT_TYPE,
        extra_prompt_bullets=[
            f"repository root: {repo_path}",
            "resume or re-run verification until VERDICT appears",
        ],
    )
    return f"""{VERIFICATION_PHASE_MARKER} — continue

Repository Root: {repo_path}
{rejection}
{spawn}
If the subagent launched async, read its .output file until VERDICT: appears.
You must NOT self-assign VERDICT: PASS or VERDICT: FAIL.

{_VERIFICATION_FORBIDDEN}
"""


def build_repair_planning_message(
    *,
    user_objective: str,
    repo_path: str,
    verifier_report: str,
    repair_cycle: int,
) -> str:
    plan_file = plan_path(repo_path)
    repair_file = repair_plan_path(repo_path)
    # Lean nudges already attach a short excerpt + on-disk path; don't re-truncate.
    if "Full verifier report" in (verifier_report or ""):
        report_excerpt = verifier_report.strip()
    else:
        report_excerpt = summarize(verifier_report, limit=1500)
    spawn = agent_spawn_instructions(
        repo_path=repo_path,
        subagent_type="Plan",
        extra_prompt_bullets=[
            "the verifier report above",
            "the current repository state",
            f"the existing plan.md path: {plan_file}",
            f"write the repair plan to {repair_file} (do not wipe {plan_file})",
        ],
    )
    return f"""{REPAIR_PLANNING_PHASE_MARKER} (cycle {repair_cycle})

The verification subagent returned VERDICT: FAIL.
Repository Root: {repo_path}
Original objective: {user_objective}
Existing plan: {plan_file}
Repair plan file: {repair_file}

Verifier report:
{report_excerpt}

Steps:
1. {spawn}
2. Write a repair strategy to {repair_file}: root causes, files to change, ordered fix steps.
   Do not wipe {plan_file}.
3. Do NOT implement fixes in this turn.
4. Do NOT run verification during repair planning.
5. Repair subagents must use the project-local execution environment (.venv, node_modules, etc.).

{_VERIFICATION_FORBIDDEN}
{EXPLORE_AGENT_HINT}
"""


def build_repair_planning_continue_message(*, repo_path: str) -> str:
    plan_file = plan_path(repo_path)
    repair_file = repair_plan_path(repo_path)
    spawn = agent_spawn_instructions(
        repo_path=repo_path,
        subagent_type="Plan",
        extra_prompt_bullets=[
            f"complete the repair plan in {repair_file}",
            f"repository root: {repo_path}",
        ],
    )
    return f"""{REPAIR_PLANNING_PHASE_MARKER} — continue

Repository Root: {repo_path}
Plan file: {plan_file}
Repair plan file: {repair_file}

Complete the repair plan in {repair_file} using the Plan subagent if needed:
{spawn}
Do not begin code repair until {repair_file} reflects the repair strategy.

{_VERIFICATION_FORBIDDEN}
"""


def build_repair_implementation_message(
    *,
    repo_path: str,
    verifier_report: str,
) -> str:
    plan_file = plan_path(repo_path)
    repair_file = repair_plan_path(repo_path)
    if "Full verifier report" in (verifier_report or ""):
        report_excerpt = verifier_report.strip()
    else:
        report_excerpt = summarize(verifier_report, limit=1500)
    spawn = agent_spawn_instructions(
        repo_path=repo_path,
        subagent_type="general-purpose",
        extra_prompt_bullets=[
            "the verifier report above",
            f"the repair plan path: {repair_file}",
            f"repository root: {repo_path}",
            "instruction to fix every reported issue",
            "requirement to use project-local execution environment (.venv / isolated deps)",
        ],
    )
    return f"""{REPAIR_IMPLEMENTATION_PHASE_MARKER}

Repository Root: {repo_path}
Authoritative repair plan: {repair_file}
Original plan (context): {plan_file}

Verifier report to address:
{report_excerpt}

Steps:
1. Read {repair_file} completely (fall back to {plan_file} if missing).
2. {spawn}
3. Do NOT run verification during repair.
4. When all repairs are complete, end your final message with exactly:
   {REPAIR_COMPLETE_MARKER}

{_VERIFICATION_FORBIDDEN}
{EXPLORE_AGENT_HINT}
"""


def build_repair_implementation_continue_message(*, repo_path: str) -> str:
    plan_file = plan_path(repo_path)
    repair_file = repair_plan_path(repo_path)
    spawn = agent_spawn_instructions(
        repo_path=repo_path,
        subagent_type="general-purpose",
        extra_prompt_bullets=[
            f"continue repair per {repair_file}",
            f"repository root: {repo_path}",
            "use project-local execution environment",
        ],
    )
    return f"""{REPAIR_IMPLEMENTATION_PHASE_MARKER} — continue

Repository Root: {repo_path}
Authoritative repair plan: {repair_file}
Original plan (context): {plan_file}

Continue repair work until every verifier failure is addressed.
If you need to spawn or resume the general-purpose subagent:
{spawn}
Use the project-local execution environment for all commands.
When finished, end your final message with exactly:
{REPAIR_COMPLETE_MARKER}
Do not run verification during repair.

{_VERIFICATION_FORBIDDEN}
{EXPLORE_AGENT_HINT}
"""
