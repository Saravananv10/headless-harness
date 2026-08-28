#!/usr/bin/env python3
"""Run an autonomous software engineering task via ConversationRunner.

Generation-only (complete on IMPLEMENTATION_STATUS: COMPLETE).
For full plan→implement→verify→repair, use main.py.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adapter.chakra import ChakraHarness
from controller import OpenAICompatibleClient, new_run_id
from controller.conversation_config import ConversationConfig
from controller.conversation_runner import ConversationRunner
from controller.supervisor_policy import CompletionMode, SupervisorPolicy
from engine import ExecutionEngine
from scripts.real_backend import connection_config, load_project_env, turn_timeout, working_directory
from verification.prompts import build_unified_pipeline_objective
from verification.report import save_pipeline_artifacts, stage_working_run_id

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Autonomous harness — ConversationRunner (generation-only)"
    )
    parser.add_argument("objective", help="High-level task objective for the controller")
    parser.add_argument(
        "--workdir",
        default="autonomous_run",
        help="Subfolder under experiments/ for the working directory",
    )
    parser.add_argument("--max-turns", type=int, default=25, help="Max backend turns")
    parser.add_argument("--max-decisions", type=int, default=30, help="Max supervisor decisions")
    parser.add_argument(
        "--run-id",
        default=None,
        help="Trace run id (default: auto-generated; traces go to logs/<run-id>/)",
    )
    parser.add_argument(
        "--no-trace",
        action="store_true",
        help="Disable JSONL conversation tracing",
    )
    args = parser.parse_args()

    load_project_env()
    workdir = working_directory(args.workdir)
    run_id = args.run_id or new_run_id()
    run_log_root = LOGS / run_id
    bootstrap = build_unified_pipeline_objective(
        repo_path=workdir,
        objective=args.objective,
        include_verification=False,
    )

    harness = ChakraHarness(default_timeout_seconds=turn_timeout())
    harness.connect(connection_config())
    engine = ExecutionEngine(harness)
    llm = OpenAICompatibleClient.from_env()
    policy = SupervisorPolicy(
        llm,
        bootstrap_message=bootstrap,
        completion_mode=CompletionMode.IMPLEMENTATION_COMPLETE,
    )
    config = ConversationConfig.from_env(
        working_directory=workdir,
        max_turns=args.max_turns,
        max_decisions=args.max_decisions,
        turn_timeout_seconds=turn_timeout(),
        run_id=stage_working_run_id("pipeline"),
        log_root=run_log_root,
        enable_trace=not args.no_trace,
    )
    runner = ConversationRunner(engine, policy=policy, config=config)

    print(f"Objective: {args.objective}")
    print(f"Working directory: {workdir}")
    print("Architecture: ConversationRunner (generation-only)")
    if runner.trace:
        print(f"Trace: {runner.trace.path}")
    print("Running autonomously...\n")

    try:
        result = runner.run(bootstrap)
        save_pipeline_artifacts(
            run_log_root,
            run_id=run_id,
            objective=bootstrap,
            repository_path=workdir,
            controller_result=result.as_controller_result(),
            termination_reason=result.termination_reason,
            health_snapshot=result.health_snapshot,
        )
    finally:
        harness.disconnect()

    print(f"\nCompleted: {result.completed}")
    print(f"Termination: {result.termination_reason}")
    print(f"Summary: {result.summary}")
    print(f"Backend turns: {result.turn_count}")
    print(f"Controller decisions: {len(result.actions)}")
    print(f"Conversation id: {result.conversation_id}")
    if result.trace_path:
        print(f"Trace: {result.trace_path}")
    print(f"Artifacts: {run_log_root / 'pipeline'}")

    if result.trace_path:
        summary_path = Path(result.trace_path).parent / "summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    "run_id": result.run_id,
                    "objective": result.objective,
                    "completed": result.completed,
                    "summary": result.summary,
                    "turn_count": result.turn_count,
                    "trace_path": result.trace_path,
                    "working_directory": workdir,
                    "architecture": "conversation_runner",
                    "termination_reason": result.termination_reason,
                    "actions": [
                        {
                            "action": a.action.value,
                            "reasoning": a.reasoning,
                            "message": a.message,
                            "summary": a.summary,
                        }
                        for a in result.actions
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Summary: {summary_path}")
    return 0 if result.completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
