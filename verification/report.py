"""Artifact persistence for generation and verification stages."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from controller.decision import ActionType
from verification.parser import Verdict, parse_verdict

if TYPE_CHECKING:
    from controller.controller import ControllerRunResult

_IMPLEMENTATION_COMPLETE_RE = re.compile(
    r"IMPLEMENTATION_STATUS:\s*COMPLETE",
    re.IGNORECASE,
)


def stage_working_run_id(stage: str) -> str:
    """Controller trace id — live JSONL written under logs/<run_id>/<stage>/working/."""
    return f"{stage}/working"


def stage_artifact_dir(run_log_root: Path, stage: str) -> Path:
    """Persisted summaries and trace copies under logs/<run_id>/<stage>/."""
    return run_log_root / stage


def _copy_trace_artifact(src: str | Path | None, dest: Path) -> None:
    """Copy working trace into artifact location when paths differ."""
    if not src:
        return
    source = Path(src)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not source.is_file():
        dest.write_text("", encoding="utf-8")
        return
    if source.resolve() == dest.resolve():
        return
    shutil.copy2(source, dest)


def save_generation_artifacts(
    run_log_root: Path,
    *,
    run_id: str,
    objective: str,
    repository_path: str,
    controller_result: ControllerRunResult,
) -> Path:
    """Persist generation summary and trace copy under run_log_root/generation/."""
    gen_dir = stage_artifact_dir(run_log_root, "generation")
    gen_dir.mkdir(parents=True, exist_ok=True)

    artifact_trace = gen_dir / "trace.jsonl"
    working_trace = controller_result.trace_path
    _copy_trace_artifact(working_trace, artifact_trace)

    completion_reasoning = None
    for action in reversed(controller_result.actions):
        if action.action == ActionType.COMPLETE:
            completion_reasoning = action.reasoning
            break

    summary = {
        "run_id": run_id,
        "objective": objective,
        "repository_path": repository_path,
        "completed": controller_result.completed,
        "summary": controller_result.summary,
        "implementation_marker_present": bool(
            _IMPLEMENTATION_COMPLETE_RE.search(controller_result.summary or "")
        ),
        "completion_reasoning": completion_reasoning,
        "turn_count": controller_result.turn_count,
        "conversation_id": controller_result.conversation_id,
        "working_trace_path": working_trace,
        "trace_path": str(artifact_trace),
        "actions": [
            {
                "action": a.action.value,
                "reasoning": a.reasoning,
                "message": a.message,
                "summary": a.summary,
            }
            for a in controller_result.actions
        ],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    (gen_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return gen_dir


def save_verification_artifacts(
    run_log_root: Path,
    *,
    run_id: str,
    objective: str,
    repository_path: str,
    generation_summary: str,
    controller_result: ControllerRunResult,
) -> Path:
    """Persist verification report, verdict, summary, and trace under run_log_root/verification/."""
    verify_dir = stage_artifact_dir(run_log_root, "verification")
    verify_dir.mkdir(parents=True, exist_ok=True)

    report = controller_result.summary
    verdict = parse_verdict(report)

    (verify_dir / "verification_report.md").write_text(report, encoding="utf-8")

    (verify_dir / "verdict.json").write_text(
        json.dumps(
            {
                "verdict": verdict.value if verdict else None,
                "parsed": verdict is not None,
                "run_id": run_id,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    artifact_trace = verify_dir / "trace.jsonl"
    _copy_trace_artifact(controller_result.trace_path, artifact_trace)

    summary: dict[str, Any] = {
        "run_id": run_id,
        "objective": objective,
        "repository_path": repository_path,
        "generation_summary": generation_summary,
        "verdict": verdict.value if verdict else None,
        "completed": controller_result.completed,
        "summary": report,
        "turn_count": controller_result.turn_count,
        "conversation_id": controller_result.conversation_id,
        "working_trace_path": controller_result.trace_path,
        "trace_path": str(artifact_trace),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    (verify_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return verify_dir


def save_pipeline_artifacts(
    run_log_root: Path,
    *,
    run_id: str,
    objective: str,
    repository_path: str,
    controller_result: ControllerRunResult,
    termination_reason: str | None = None,
    health_snapshot: dict[str, Any] | None = None,
    lifecycle_snapshot: dict[str, Any] | None = None,
) -> Path:
    """Persist single-conversation pipeline summary and trace under run_log_root/pipeline/."""
    pipeline_dir = stage_artifact_dir(run_log_root, "pipeline")
    pipeline_dir.mkdir(parents=True, exist_ok=True)

    report = controller_result.summary or ""
    # Prefer last authoritative verification-agent verdict from lifecycle.
    lifecycle_verdict: Verdict | None = None
    if lifecycle_snapshot and lifecycle_snapshot.get("last_verdict"):
        try:
            lifecycle_verdict = Verdict(str(lifecycle_snapshot["last_verdict"]))
        except ValueError:
            lifecycle_verdict = None
    verdict = lifecycle_verdict or parse_verdict(report)

    (pipeline_dir / "report.md").write_text(report, encoding="utf-8")
    (pipeline_dir / "verdict.json").write_text(
        json.dumps(
            {
                "verdict": verdict.value if verdict else None,
                "parsed": verdict is not None,
                "source": (
                    "lifecycle"
                    if lifecycle_verdict is not None
                    else ("summary" if verdict is not None else None)
                ),
                "authoritative_pass": bool(
                    (lifecycle_snapshot or {}).get("authoritative_pass")
                ),
                "run_id": run_id,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    artifact_trace = pipeline_dir / "trace.jsonl"
    _copy_trace_artifact(controller_result.trace_path, artifact_trace)

    raw_src = None
    if controller_result.trace_path:
        raw_src = Path(controller_result.trace_path).with_name("raw_events.jsonl")
    artifact_raw = pipeline_dir / "raw_events.jsonl"
    _copy_trace_artifact(raw_src, artifact_raw)

    summary: dict[str, Any] = {
        "run_id": run_id,
        "objective": objective,
        "repository_path": repository_path,
        "architecture": "single_chakra_conversation",
        "lifecycle_owner": "chakra",
        "verdict": verdict.value if verdict else None,
        "completed": controller_result.completed,
        "summary": report,
        "termination_reason": termination_reason or (
            "completion" if controller_result.completed else None
        ),
        "health_snapshot": health_snapshot,
        "lifecycle_snapshot": lifecycle_snapshot,
        "implementation_marker_present": bool(
            _IMPLEMENTATION_COMPLETE_RE.search(report)
        ),
        "turn_count": controller_result.turn_count,
        "conversation_id": controller_result.conversation_id,
        "working_trace_path": controller_result.trace_path,
        "trace_path": str(artifact_trace),
        "raw_events_path": str(artifact_raw),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    (pipeline_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    try:
        from prompt_stats.hooks import record_pipeline_event

        forge_meta = None
        forge_path = run_log_root / "prompt_forge" / "forge_meta.json"
        if forge_path.is_file():
            forge_meta = json.loads(forge_path.read_text(encoding="utf-8"))
        runtime = None
        prompt_tok = completion_tok = None
        if artifact_trace.is_file():
            from prompt_stats.collectors import _tokens_from_trace

            prompt_tok, completion_tok, runtime = _tokens_from_trace(artifact_trace)
        record_pipeline_event(
            run_id=run_id,
            objective=objective,
            repository_path=repository_path,
            summary=summary,
            runtime_seconds=runtime,
            forge_meta=forge_meta,
            prompt_tokens=prompt_tok,
            completion_tokens=completion_tok,
        )
    except Exception:
        pass

    return pipeline_dir
