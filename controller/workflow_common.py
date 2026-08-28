"""Shared helpers for generation and verification workflow policies."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from controller.context_builder import ControllerContext
from verification.parser import Verdict, parse_verdict

PLAN_FILENAME = "plan.md"
REPAIR_PLAN_FILENAME = "repair_plan.md"
IMPLEMENTATION_COMPLETE_MARKER = "IMPLEMENTATION_STATUS: COMPLETE"
REPAIR_COMPLETE_MARKER = "REPAIR_STATUS: COMPLETE"
VERIFICATION_SUBAGENT_TYPE = "verification"
EXPLORE_AGENT_TYPE = "Explore"
EXPLORE_AGENT_HINT = (
    f'For broad repository inspection, prefer Agent with subagent_type="{EXPLORE_AGENT_TYPE}" '
    "instead of reading files one-by-one. "
    "Prefer cwd set to the Repository Root. isolation=\"worktree\" is allowed when "
    "anchored to that repository; never use isolation=\"remote\"."
)

AGENT_SPAWN_FORBIDDEN = """FORBIDDEN on Agent tool:
• isolation="remote"
• cwd pointing outside the Repository Root
"""

AGENT_SPAWN_WORKTREE_OK = """Worktree isolation is allowed (Chakra default).
When using isolation="worktree", prefer cwd="{repo}" so the worktree is of this
repository. Omitting cwd is acceptable when the harness session working_directory
is already the Repository Root. All work must stay inside the project repo.
"""

ALLOWED_AGENT_SPAWN_TYPES = frozenset(
    {
        "Plan",
        "general-purpose",
        "generalPurpose",
        "Explore",
        "verification",
    }
)
_FORBIDDEN_AGENT_ISOLATION = frozenset({"remote"})


def validate_agent_spawn(
    arguments: dict[str, Any] | None,
    *,
    repo_path: str | Path,
) -> tuple[bool, str]:
    """
    Validate Agent tool arguments for repo confinement.

    Allows Chakra-default isolation=worktree. Denies remote isolation and cwd
    outside the repository. Missing cwd is OK (session working_directory anchors).
    """
    args = dict(arguments or {})
    sub = str(
        args.get("subagent_type")
        or args.get("agentType")
        or args.get("agent_type")
        or ""
    ).strip()
    if not sub:
        return False, "deny Agent: subagent_type is required"

    allowed_lower = {name.lower() for name in ALLOWED_AGENT_SPAWN_TYPES}
    if sub.lower() not in allowed_lower:
        return False, f"deny Agent: unsupported subagent_type={sub!r}"

    isolation = str(args.get("isolation") or "").strip().lower()
    if isolation in _FORBIDDEN_AGENT_ISOLATION:
        return False, f"deny Agent: isolation={isolation!r} is forbidden"

    try:
        repo = Path(str(repo_path)).expanduser().resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        return False, f"deny Agent: invalid repo_path ({exc})"

    cwd_raw = args.get("cwd")
    if cwd_raw is None or not str(cwd_raw).strip():
        return (
            True,
            f"ok Agent subagent_type={sub}; cwd omitted (session working_directory)",
        )

    try:
        cwd = Path(str(cwd_raw)).expanduser().resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        return False, f"deny Agent: invalid cwd ({exc})"

    if cwd != repo:
        return (
            False,
            f"deny Agent: cwd must equal repository root ({repo}), got {cwd}",
        )
    return True, f"ok Agent subagent_type={sub}"


def agent_spawn_instructions(
    *,
    repo_path: str,
    subagent_type: str,
    extra_prompt_bullets: list[str] | None = None,
) -> str:
    """Canonical Agent tool invocation rules for the headless harness."""
    bullets = extra_prompt_bullets or []
    prompt_lines = "\n".join(f"   - {bullet}" for bullet in bullets)
    prompt_block = f"\n  prompt must include:\n{prompt_lines}" if prompt_lines else ""
    worktree_note = AGENT_SPAWN_WORKTREE_OK.format(repo=repo_path)
    return f"""AGENT SPAWN PROTOCOL (mandatory):
Spawn the Agent tool with:
  subagent_type="{subagent_type}"
  cwd="{repo_path}"
  run_in_background=false{prompt_block}

{AGENT_SPAWN_FORBIDDEN}
{worktree_note}
The subagent's shell and filesystem root MUST be Repository Root: {repo_path}.
All paths in the subagent prompt must be absolute paths under Repository Root.
"""

VERIFICATION_PHASE_MARKER = "VERIFICATION PHASE 1 — VERIFICATION"
VERIFICATION_RERUN_MARKER = "VERIFICATION PHASE 1 — VERIFICATION (re-run)"
REPAIR_PLANNING_PHASE_MARKER = "VERIFICATION PHASE 2 — REPAIR PLANNING"
REPAIR_IMPLEMENTATION_PHASE_MARKER = "VERIFICATION PHASE 3 — REPAIR IMPLEMENTATION"

_IMPLEMENTATION_COMPLETE_RE = re.compile(
    r"IMPLEMENTATION_STATUS:\s*COMPLETE",
    re.IGNORECASE,
)
_REPAIR_COMPLETE_RE = re.compile(
    r"REPAIR_STATUS:\s*COMPLETE",
    re.IGNORECASE,
)
_VERIFICATION_SUBAGENT_RE = re.compile(
    r'subagent_type["\s:=]+["\']?verification',
    re.IGNORECASE,
)
_ASYNC_AGENT_LAUNCH_RE = re.compile(
    r"Async agent launched successfully",
    re.IGNORECASE,
)


def plan_path(repo_path: str) -> Path:
    return Path(repo_path) / PLAN_FILENAME


def plan_exists(repo_path: str) -> bool:
    path = plan_path(repo_path)
    if not path.is_file():
        return False
    return bool(path.read_text(encoding="utf-8").strip())


def repair_plan_path(repo_path: str) -> Path:
    return Path(repo_path) / REPAIR_PLAN_FILENAME


def repair_plan_exists(repo_path: str) -> bool:
    """True when repair_plan.md exists and is non-empty."""
    path = repair_plan_path(repo_path)
    if not path.is_file():
        return False
    return bool(path.read_text(encoding="utf-8").strip())


def infer_technology_hint(objective: str) -> str:
    """Lightweight hint for the planning prompt; backend still auto-detects."""
    lowered = objective.lower()
    hints: list[str] = []
    if any(token in lowered for token in ("react", "vite", "typescript", "tsx")):
        hints.append("Node.js / TypeScript / React")
    if any(token in lowered for token in ("python", "pygame", "flask", "django", "fastapi")):
        hints.append("Python")
    if any(token in lowered for token in ("rust", "cargo")):
        hints.append("Rust")
    if any(token in lowered for token in ("go ", "golang")):
        hints.append("Go")
    if not hints:
        return "Determine from the objective and repository contents."
    return ", ".join(hints)


def summarize(text: str, *, limit: int = 2000) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: limit - 3] + "..."


# Default inline excerpt for repair nudges (full report lives on disk).
VERIFIER_REPORT_NUDGE_EXCERPT_LIMIT = 1500


def persist_verifier_report(
    report: str,
    *,
    repo_path: str,
    log_root: str | Path | None = None,
) -> Path:
    """
    Write the full verifier report to disk for lean resume nudges.

    Primary path: ``{repo}/repair_artifacts/last_fail_report.md``
    Optional copy under ``{log_root}/verification/last_fail_report.md``.
    """
    text = (report or "").strip() or "(empty verifier report)"
    primary = Path(repo_path) / "repair_artifacts" / "last_fail_report.md"
    primary.parent.mkdir(parents=True, exist_ok=True)
    primary.write_text(text + "\n", encoding="utf-8")
    if log_root:
        secondary = Path(log_root) / "verification" / "last_fail_report.md"
        secondary.parent.mkdir(parents=True, exist_ok=True)
        secondary.write_text(text + "\n", encoding="utf-8")
    return primary.resolve()


def lean_verifier_report_block(
    report: str,
    *,
    repo_path: str,
    log_root: str | Path | None = None,
    excerpt_limit: int = VERIFIER_REPORT_NUDGE_EXCERPT_LIMIT,
) -> str:
    """Persist full report; return short excerpt + absolute path for nudge text."""
    path = persist_verifier_report(report, repo_path=repo_path, log_root=log_root)
    excerpt = summarize(report or "", limit=excerpt_limit)
    return (
        f"{excerpt}\n\n"
        f"Full verifier report (read this for complete details):\n{path}"
    )


def summarize_preserving_markers(
    text: str,
    *,
    limit: int = 2000,
    markers: tuple[str, ...] = (
        IMPLEMENTATION_COMPLETE_MARKER,
        REPAIR_COMPLETE_MARKER,
    ),
) -> str:
    """Truncate text but keep protocol status markers if present in the source."""
    stripped = text.strip()
    if not stripped:
        return ""

    missing_markers = [
        marker
        for marker in markers
        if marker in stripped and marker not in summarize(stripped, limit=limit)
    ]
    if not missing_markers:
        return summarize(stripped, limit=limit)

    suffix = "\n\n" + "\n".join(missing_markers)
    body_limit = max(limit - len(suffix), 0)
    if body_limit == 0:
        return suffix.strip()

    body = summarize(stripped, limit=body_limit)
    return f"{body}{suffix}"


def implementation_complete_in_text(text: str) -> bool:
    """True when text contains the authoritative implementation-complete marker."""
    return bool(_IMPLEMENTATION_COMPLETE_RE.search(text or ""))


def implementation_reported_complete(context: ControllerContext) -> bool:
    text = context.last_assistant_message or ""
    return implementation_complete_in_text(text)


def repair_reported_complete(context: ControllerContext) -> bool:
    text = context.last_assistant_message or ""
    return bool(_REPAIR_COMPLETE_RE.search(text))


def history_contains_marker(context: ControllerContext, marker: str) -> bool:
    return any(
        entry.get("role") == "user" and marker in (entry.get("content") or "")
        for entry in context.history
    )


def count_user_markers(context: ControllerContext, marker: str) -> int:
    return sum(
        1
        for entry in context.history
        if entry.get("role") == "user" and marker in (entry.get("content") or "")
    )


def verification_started(context: ControllerContext) -> bool:
    return history_contains_marker(context, VERIFICATION_PHASE_MARKER) or any(
        entry.get("role") == "user"
        and VERIFICATION_RERUN_MARKER in (entry.get("content") or "")
        for entry in context.history
    )


def assistant_responded_after_marker(context: ControllerContext, marker: str) -> bool:
    seen = False
    for entry in context.history:
        if entry.get("role") == "user" and marker in (entry.get("content") or ""):
            seen = True
            continue
        if seen and entry.get("role") == "assistant":
            return True
    return seen and bool(context.last_assistant_message)


def all_tool_events(context: ControllerContext) -> list[dict[str, Any]]:
    """Tool events from all turns, falling back to recent_events."""
    if context.tool_events:
        return list(context.tool_events)
    return [
        event
        for event in context.recent_events
        if event.get("event_type") in ("tool_started", "tool_completed")
    ]


def _tool_payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload") or {}
    return payload if isinstance(payload, dict) else {}


def _conversation_text(context: ControllerContext) -> str:
    parts: list[str] = []
    for entry in context.history:
        parts.append(str(entry.get("content") or ""))
    if context.last_assistant_message:
        parts.append(context.last_assistant_message)
    for event in all_tool_events(context):
        parts.append(json.dumps(_tool_payload(event), default=str))
    return "\n".join(parts)


def _subagent_type_from_started(payload: dict[str, Any]) -> str | None:
    if payload.get("tool_name") != "Agent":
        return None
    arguments = payload.get("arguments") or {}
    if not isinstance(arguments, dict):
        return None
    subagent_type = arguments.get("subagent_type")
    return str(subagent_type) if subagent_type else None


def verification_agent_invocation_ids(context: ControllerContext) -> list[str]:
    ids: list[str] = []
    for event in all_tool_events(context):
        if event.get("event_type") != "tool_started":
            continue
        payload = _tool_payload(event)
        if _subagent_type_from_started(payload) != VERIFICATION_SUBAGENT_TYPE:
            continue
        invocation_id = payload.get("invocation_id")
        if invocation_id:
            ids.append(str(invocation_id))
    return ids


def _is_async_launch_output(output: str) -> bool:
    return bool(_ASYNC_AGENT_LAUNCH_RE.search(output))


def substantive_verification_outputs(context: ControllerContext) -> list[str]:
    """Outputs from verification Agent tool_completed or follow-up Read of subagent output."""
    outputs: list[str] = []
    verification_ids = set(verification_agent_invocation_ids(context))
    verification_spawned = bool(verification_ids)
    last_spawn_ts = ""

    for event in all_tool_events(context):
        payload = _tool_payload(event)
        if event.get("event_type") == "tool_started":
            invocation_id = str(payload.get("invocation_id") or "")
            if invocation_id in verification_ids:
                last_spawn_ts = str(event.get("timestamp") or "")
            continue
        if event.get("event_type") != "tool_completed":
            continue

        output = str(payload.get("output") or "")
        if not output.strip():
            continue

        invocation_id = str(payload.get("invocation_id") or "")
        tool_name = str(payload.get("tool_name") or "")

        if tool_name == "Agent" and invocation_id in verification_ids:
            if not _is_async_launch_output(output):
                outputs.append(output)
            continue

        if (
            verification_spawned
            and tool_name == "Read"
            and "verdict:" in output.lower()
            and str(event.get("timestamp") or "") >= last_spawn_ts
        ):
            outputs.append(output)

    return outputs


def verification_subagent_invoked(context: ControllerContext) -> bool:
    """True when the verification Agent tool was spawned at least once."""
    if verification_agent_invocation_ids(context):
        return True
    blob = _conversation_text(context)
    return bool(_VERIFICATION_SUBAGENT_RE.search(blob))


def verification_subagent_verdict(context: ControllerContext) -> Verdict | None:
    """Authoritative verdict — only from verification subagent tool evidence."""
    outputs = substantive_verification_outputs(context)
    for output in reversed(outputs):
        verdict = parse_verdict(output)
        if verdict is not None:
            return verdict
    return None


def assistant_text_after_verification_start(context: ControllerContext) -> str:
    parts: list[str] = []
    seen = False
    for entry in context.history:
        if entry.get("role") == "user" and (
            VERIFICATION_PHASE_MARKER in (entry.get("content") or "")
            or VERIFICATION_RERUN_MARKER in (entry.get("content") or "")
        ):
            seen = True
            continue
        if seen and entry.get("role") == "assistant":
            parts.append(str(entry.get("content") or ""))
    if context.last_assistant_message:
        parts.append(context.last_assistant_message)
    return "\n".join(parts)


def self_assigned_verdict_detected(context: ControllerContext) -> bool:
    """True when assistant text claims a verdict without subagent evidence."""
    if verification_subagent_verdict(context) is not None:
        return False
    if not verification_started(context):
        return False
    assistant_text = assistant_text_after_verification_start(context)
    return parse_verdict(assistant_text) is not None


def latest_verdict(context: ControllerContext) -> Verdict | None:
    return verification_subagent_verdict(context)


def latest_verifier_report(context: ControllerContext) -> str:
    outputs = substantive_verification_outputs(context)
    if outputs:
        return outputs[-1].strip()
    return (
        context.last_assistant_message or assistant_text_after_verification_start(context)
    ).strip()


def verification_passed(context: ControllerContext) -> bool:
    return verification_subagent_verdict(context) == Verdict.PASS


def repair_cycle_count(context: ControllerContext) -> int:
    return count_user_markers(context, REPAIR_PLANNING_PHASE_MARKER)


def verification_rerun_sent(context: ControllerContext, repair_cycle: int) -> bool:
    needle = f"{VERIFICATION_RERUN_MARKER} #{repair_cycle}"
    return any(
        entry.get("role") == "user" and needle in (entry.get("content") or "")
        for entry in context.history
    )


def in_active_repair(context: ControllerContext) -> bool:
    if history_contains_marker(context, REPAIR_IMPLEMENTATION_PHASE_MARKER):
        if not repair_reported_complete(context):
            return True
        cycle = repair_cycle_count(context)
        return not verification_rerun_sent(context, cycle)
    if history_contains_marker(context, REPAIR_PLANNING_PHASE_MARKER):
        return True
    return False


def repair_pending_after_fail(context: ControllerContext) -> bool:
    if latest_verdict(context) != Verdict.FAIL:
        return False
    return not in_active_repair(context)
