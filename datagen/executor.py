"""executor.py — run one task end-to-end through the existing harness
(ConversationRunner + Chakra), parallel to
runner/pipeline_executor.py::run_single_task but sourced from a TaskSpec
(datagen.bank_ingest) instead of a hand-written pipelines/<domain>
package.

Wires in the hardening subsystems built on top of the base harness:
independent re-verification of a claimed PASS, an append-only dataset
manifest, a checkpoint store for resuming a killed batch, a curation list
for permanently skipping known-good tasks, and a retry loop for transient
gRPC/session-health failures that reuses the same workdir instead of
restarting from scratch.
"""

from __future__ import annotations

import importlib
import json
import time
from pathlib import Path
from typing import Any

from controller import OpenAICompatibleClient
from controller.conversation_config import ConversationConfig
from controller.conversation_runner import ConversationRunner
from controller.repo_bootstrap import ensure_project_git_repo
from controller.supervisor_policy import CompletionMode, SupervisorPolicy
from engine import ExecutionEngine
from scripts.real_backend import turn_timeout
from verification import Verdict, parse_verdict
from verification.report import save_pipeline_artifacts, stage_working_run_id

from datagen import (
    checkpoint,
    curation,
    data_need,
    data_synth,
    dataset_manifest,
    domain_generators,
    independent_verify,
    preflight,
    prompt_compose,
)
from datagen.task_spec import TaskSpec

ARTIFACTS_ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "task_cache"

# Termination reasons that indicate an infra/session hiccup rather than a
# genuine task difficulty — worth a fresh attempt into the same workdir.
# Anything else (max_repair_iterations, no_forward_progress, stuck_in_explore,
# denial_loop, phase_budget_exceeded:*, max_turns, max_decisions,
# repeated_failure_threshold) reflects a real outcome that a blind restart
# wouldn't fix, so it is NOT retried.
_RETRYABLE_TERMINATION_REASONS = {"wall_clock_timeout", "inactivity_timeout", "progress_timeout"}


def _count_tool_calls(run_log_root: Path) -> int:
    """Count tool-related events across all .jsonl files in the run log directory."""
    count = 0
    for tf in run_log_root.rglob("*.jsonl"):
        with tf.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    kind = entry.get("type") or entry.get("event_type") or ""
                    if kind in ("tool_request", "tool_execution", "tool_approval", "agent_spawn"):
                        count += 1
                except json.JSONDecodeError:
                    pass
    return count


def _append_manifest(
    spec: TaskSpec,
    run_id: str,
    *,
    status: str,
    verdict: str = "NONE",
    authoritative_pass: bool = False,
    independent_verification_passed: bool | None = None,
    turn_count: int = 0,
    tool_executions: int = 0,
    objective: str = "",
) -> None:
    entry = dataset_manifest.ManifestEntry(
        task_id=spec.id,
        category=spec.category,
        origin=spec.origin,
        run_id=run_id,
        status=status,
        verdict=verdict,
        authoritative_pass=authoritative_pass,
        independent_verification_passed=independent_verification_passed,
        turn_count=turn_count,
        tool_executions=tool_executions,
        template_hash=dataset_manifest.compute_template_hash(),
        objective_hash=dataset_manifest.compute_objective_hash(objective) if objective else "",
    )
    dataset_manifest.append_entry(entry)


def _skip_result(
    spec: TaskSpec, run_id: str, repo_dir: Path, *, status: str, errors: list[str]
) -> dict[str, Any]:
    _append_manifest(spec, run_id, status=status)
    return {
        "global_index": spec.global_index,
        "task_id": spec.id,
        "title": spec.title,
        "category": spec.category,
        "origin": spec.origin,
        "sheet": spec.sheet,
        "needs_input_data": None,
        "status": status,
        "completed": False,
        "verdict": "NONE",
        "authoritative_pass": False,
        "tool_executions": 0,
        "turn_count": 0,
        "elapsed_seconds": 0.0,
        "run_id": run_id,
        "workdir": str(repo_dir),
        "errors": errors,
    }


def run_task(
    spec: TaskSpec,
    *,
    harness,
    llm: OpenAICompatibleClient,
    experiments_dir: Path,
    logs_dir: Path,
    data_seed: int = 42,
    max_turns: int = 25,
    max_decisions: int = 25,
    max_repair_iterations: int = 3,
    llm_detect_data_need: bool = False,
    llm_expand: bool = False,
    checkpoint_store: checkpoint.CheckpointStore | None = None,
    curation_list: curation.CurationList | None = None,
    force_rerun: bool = False,
    max_retries: int = 1,
) -> dict[str, Any]:
    """Execute one task end-to-end and return a result summary dict."""

    workdir_name = f"task_{spec.global_index:04d}_{spec.id}"
    repo_dir = experiments_dir / spec.origin / workdir_name
    repo_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*75}")
    print(f"Task [{spec.global_index:04d}] {spec.id}: {spec.title}")
    print(f"  Category: {spec.category}  |  Source: {spec.origin} / {spec.sheet}")
    print(f"  Workdir: {repo_dir}")
    print(f"{'='*75}\n")

    if not force_rerun and curation_list is not None and curation_list.is_marked_good(spec.id):
        print(f"<-- CURATED_SKIP: marked good ({curation_list.reason_for(spec.id)})")
        run_id = f"skip_{spec.global_index:04d}_{spec.id}_{int(time.time())}"
        return _skip_result(spec, run_id, repo_dir, status="CURATED_SKIP", errors=[])

    if not force_rerun and checkpoint_store is not None and checkpoint_store.is_done(spec.id):
        print("<-- CHECKPOINT_SKIP: already done in a prior batch run")
        run_id = f"skip_{spec.global_index:04d}_{spec.id}_{int(time.time())}"
        return _skip_result(spec, run_id, repo_dir, status="CHECKPOINT_SKIP", errors=[])

    task_errors = preflight.validate_task(spec)
    if task_errors:
        print(f"<-- INPUT_INVALID: {task_errors}")
        if checkpoint_store is not None:
            checkpoint_store.mark_failed(spec.id, detail="input_invalid")
        run_id = f"run_{spec.global_index:04d}_{spec.id}_{int(time.time())}"
        return _skip_result(spec, run_id, repo_dir, status="INPUT_INVALID", errors=task_errors)

    task_artifacts = ARTIFACTS_ROOT / spec.origin / spec.id
    unique_seed = data_seed + spec.global_index * 100
    data_dir: Path | None = None
    data_files: list[str] = []

    if llm_detect_data_need:
        cache_path = task_artifacts / "data_need_cache.json"
        needs_data, reason = data_need.needs_input_data_llm(spec, llm, cache_path=cache_path)
    else:
        needs_data, reason = data_need.needs_input_data(spec)
    print(f"--> Data-need: {needs_data} ({reason})")

    if needs_data:
        data_dir = repo_dir / "data"
        generator_target = domain_generators.resolve_generator(spec.category, spec.subcategory)

        if generator_target:
            module_path, fn_name = generator_target
            try:
                fn = getattr(importlib.import_module(module_path), fn_name)
                gen_result = fn(data_dir, seed=unique_seed)
                data_files = gen_result.files
                print(f"    Generated via {module_path}.{fn_name}: {len(data_files)} file(s) in {data_dir}")
                gen_errors = preflight.validate_files_exist(data_files, base_dir=data_dir)
                if gen_errors:
                    print(f"<-- INPUT_INVALID: {gen_errors}")
                    run_id = f"run_{spec.global_index:04d}_{spec.id}_{int(time.time())}"
                    if checkpoint_store is not None:
                        checkpoint_store.mark_failed(spec.id, detail="input_invalid")
                    return _skip_result(spec, run_id, repo_dir, status="INPUT_INVALID", errors=gen_errors)
            except Exception as exc:
                print(f"    Domain generator {module_path}.{fn_name} failed ({exc}); "
                      f"falling back to the generic schema-inference engine")
                generator_target = None

        if not generator_target:
            schema_cache = task_artifacts / "schema.json"
            try:
                schema = data_synth.infer_schema(spec, llm, cache_path=schema_cache)
                gen_result = data_synth.synthesize(schema, data_dir, seed=unique_seed)
                data_files = gen_result.files
                print(f"    Synthesized {len(data_files)} input file(s) in {data_dir}")
            except Exception as exc:
                print(f"<-- INPUT_INVALID: data synthesis failed: {exc}")
                run_id = f"run_{spec.global_index:04d}_{spec.id}_{int(time.time())}"
                if checkpoint_store is not None:
                    checkpoint_store.mark_failed(spec.id, detail="data_synth_failed")
                return _skip_result(spec, run_id, repo_dir, status="INPUT_INVALID", errors=[str(exc)])

            data_errors = preflight.validate_generated_data(schema, data_dir)
            if data_errors:
                print(f"<-- INPUT_INVALID: {data_errors}")
                run_id = f"run_{spec.global_index:04d}_{spec.id}_{int(time.time())}"
                if checkpoint_store is not None:
                    checkpoint_store.mark_failed(spec.id, detail="input_invalid")
                return _skip_result(spec, run_id, repo_dir, status="INPUT_INVALID", errors=data_errors)

    ensure_project_git_repo(repo_dir)

    objective = prompt_compose.compose_objective(
        spec,
        repo_path=str(repo_dir),
        max_repair_iterations=max_repair_iterations,
        include_verification=True,
        data_dir=data_dir,
        data_files=data_files,
        llm_expand=llm_expand,
        llm=llm,
    )

    if checkpoint_store is not None:
        checkpoint_store.mark_running(spec.id)

    # --- The actual conversation attempt, retried up to max_retries times on
    # a transient failure. Same repo_dir every attempt (ensure_project_git_repo
    # above already ran once; Chakra continues inside the existing repo per
    # the sandbox rules), so a retry resumes into whatever the prior attempt
    # already built rather than starting from scratch. Each attempt gets its
    # own run_id/trace so nothing is overwritten.
    total_attempts = max(1, max_retries + 1)
    final: dict[str, Any] | None = None

    for attempt in range(1, total_attempts + 1):
        run_id = f"run_{spec.global_index:04d}_{spec.id}_{int(time.time())}"
        run_log_root = logs_dir / run_id

        engine = ExecutionEngine(harness)
        policy = SupervisorPolicy(llm, bootstrap_message=objective, completion_mode=CompletionMode.VERDICT_PASS)
        config = ConversationConfig.from_env(
            working_directory=str(repo_dir),
            max_turns=max_turns,
            max_decisions=max_decisions,
            max_repair_iterations=max_repair_iterations,
            turn_timeout_seconds=turn_timeout(),
            run_id=stage_working_run_id(f"task_{spec.global_index:04d}_a{attempt}"),
            log_root=run_log_root,
            enable_trace=True,
        )

        runner = ConversationRunner(engine, policy=policy, config=config)
        start_time = time.time()

        try:
            result = runner.run(objective)
        except Exception as exc:
            # A crash (e.g. dropped gRPC connection) rather than a clean
            # ConversationRunResult — always worth a retry if any remain.
            print(f"\n<-- ATTEMPT {attempt}/{total_attempts} CRASHED: {exc}")
            if attempt < total_attempts:
                continue
            elapsed = round(time.time() - start_time, 2)
            _append_manifest(spec, run_id, status="ERROR", objective=objective)
            if checkpoint_store is not None:
                checkpoint_store.mark_failed(spec.id, run_id=run_id, detail=str(exc))
            return {
                "global_index": spec.global_index, "task_id": spec.id, "title": spec.title,
                "category": spec.category, "origin": spec.origin, "sheet": spec.sheet,
                "needs_input_data": needs_data, "status": "ERROR", "completed": False,
                "verdict": "NONE", "authoritative_pass": False, "tool_executions": 0,
                "turn_count": 0, "elapsed_seconds": elapsed, "run_id": run_id,
                "workdir": str(repo_dir), "attempt": attempt, "error": str(exc),
            }

        elapsed = round(time.time() - start_time, 2)

        if result.termination_reason in _RETRYABLE_TERMINATION_REASONS and attempt < total_attempts:
            print(
                f"\n<-- ATTEMPT {attempt}/{total_attempts} hit a retryable stall "
                f"({result.termination_reason}); retrying into the same workdir."
            )
            continue

        save_pipeline_artifacts(
            run_log_root,
            run_id=run_id,
            objective=objective,
            repository_path=str(repo_dir),
            controller_result=result.as_controller_result(),
            termination_reason=result.termination_reason,
            health_snapshot=result.health_snapshot,
            lifecycle_snapshot=result.lifecycle_snapshot,
        )

        life = result.lifecycle_snapshot or {}
        authoritative = bool(life.get("authoritative_pass"))
        last_verdict_str = life.get("last_verdict")
        verdict = (
            parse_verdict(result.summary or "")
            if not last_verdict_str
            else Verdict(str(last_verdict_str))
        )

        tool_calls_count = _count_tool_calls(run_log_root)
        self_reported_pass = (
            result.completed and verdict == Verdict.PASS and authoritative and tool_calls_count >= 1
        )

        independent_passed: bool | None = None
        if self_reported_pass:
            trace_path = run_log_root / "pipeline" / "trace.jsonl"
            iv_result = independent_verify.verify(repo_dir, trace_path)
            independent_verify.save_report(iv_result, run_id=run_id)
            independent_passed = iv_result.passed
            status_str = "PASSED" if iv_result.passed else "SELF_REPORTED_ONLY"
            print(f"    Independent verification: {iv_result.mode} -> passed={iv_result.passed}")
        else:
            status_str = "FAILED"

        print(f"\n<-- Task [{spec.global_index:04d}] {spec.id} Result: {status_str} (attempt {attempt}/{total_attempts})")
        print(f"    Turns: {result.turn_count} | Tool Executions: {tool_calls_count} | Time: {elapsed}s")
        print(f"    Verdict: {verdict.value if verdict else 'NONE'} (Authoritative: {authoritative})\n")

        _append_manifest(
            spec, run_id, status=status_str, verdict=verdict.value if verdict else "NONE",
            authoritative_pass=authoritative, independent_verification_passed=independent_passed,
            turn_count=result.turn_count, tool_executions=tool_calls_count, objective=objective,
        )

        if checkpoint_store is not None:
            if status_str in ("PASSED", "SELF_REPORTED_ONLY"):
                checkpoint_store.mark_done(spec.id, run_id=run_id)
            else:
                checkpoint_store.mark_failed(spec.id, run_id=run_id, detail=status_str)

        final = {
            "global_index": spec.global_index,
            "task_id": spec.id,
            "title": spec.title,
            "category": spec.category,
            "origin": spec.origin,
            "sheet": spec.sheet,
            "needs_input_data": needs_data,
            "status": status_str,
            "completed": result.completed,
            "verdict": verdict.value if verdict else "NONE",
            "authoritative_pass": authoritative,
            "independent_verification_passed": independent_passed,
            "tool_executions": tool_calls_count,
            "turn_count": result.turn_count,
            "elapsed_seconds": elapsed,
            "run_id": run_id,
            "workdir": str(repo_dir),
            "attempt": attempt,
        }
        break

    assert final is not None  # loop always returns or sets `final` before exhausting attempts
    return final
