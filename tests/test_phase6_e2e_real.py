"""Step 6.5 — end-to-end autonomous validation on real LLM backend."""

from __future__ import annotations

from pathlib import Path

from adapter.chakra import ChakraHarness
from controller import Controller, ControllerConfig, OpenAICompatibleClient
from engine import ExecutionEngine
from interface import ConnectionConfig
from phase6_common import journal_entry, scan_controller_isolation
from scripts.real_backend import (
    SIMPLE_PROMPT,
    connection_config,
    load_project_env,
    turn_timeout,
    working_directory,
)


def main() -> int:
    load_project_env()
    leaks = scan_controller_isolation()

    harness = ChakraHarness(default_timeout_seconds=turn_timeout())
    harness.connect(connection_config())
    engine = ExecutionEngine(harness)
    llm = OpenAICompatibleClient.from_env()

    workdir = working_directory("phase6_autonomous")
    controller = Controller(
        engine,
        llm,
        config=ControllerConfig(
            working_directory=workdir,
            max_turns=6,
            max_decisions=8,
        ),
    )

    # Tight objective for reliable autonomous completion
    objective = (
        f"{SIMPLE_PROMPT}. "
        "When the backend confirms, mark the task complete without further turns."
    )
    result = controller.run(objective)
    harness.disconnect()

    ok = (
        not leaks
        and result.completed
        and result.turn_count >= 1
        and result.summary
        and result.final_state_snapshot is not None
    )

    journal_entry(
        milestone="Step 6.5 — End-to-End Validation",
        design_decisions=[
            "Autonomous stack: Controller → ExecutionEngine → Harness → Adapter.",
            "Controller LLM uses OPENAI_* env vars; backend uses Chakra harness.",
        ],
        implementation=[
            "controller/controller.py",
            "tests/test_phase6_runtime.py",
            "tests/test_phase6_e2e_real.py",
        ],
        validation="PASS" if ok else "FAIL",
        issues=leaks or ["None"],
        observations=[
            f"Turns executed: {result.turn_count}",
            f"Actions taken: {len(result.actions)}",
            f"Workdir: {Path(workdir)}",
            f"Summary: {result.summary[:160]}",
        ],
        conclusions=["Full architecture operates autonomously from objective to completion."],
        next_steps=["Phase 7 — persona orchestration."],
    )
    print("Step 6.5 PASS" if ok else "Step 6.5 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
