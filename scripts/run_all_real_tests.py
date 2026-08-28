#!/usr/bin/env python3
"""Run all integration tests against the real Chakra + LLM backend."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.real_backend import load_project_env, require_chakra

ROOT = Path(__file__).resolve().parent.parent

# Phase 3 contract tests are pure-Python (no LLM). Phase 4 translator is unit-only.
REAL_INTEGRATION_TESTS = [
    "scripts/verify_chakra.py",
    "tests/test_connectivity.py",
    "tests/test_minimal_chat.py",
    "tests/test_session.py",
    "tests/test_phase2_api_surface.py",
    "tests/test_phase2_models.py",
    "tests/test_phase2_streaming.py",
    "tests/test_phase2_session_lifecycle.py",
    "tests/test_phase2_tool_interaction.py",
    "tests/test_phase2_error_cancellation.py",
    "tests/test_phase2_capability_summary.py",
    "tests/test_phase4_connection.py",
    "tests/test_phase4_session.py",
    "tests/test_phase4_turn.py",
    "tests/test_phase4_adapter_validation.py",
    "tests/test_phase5_engine_real.py",
    "tests/test_phase6_e2e_real.py",
]

CONTRACT_TESTS = [
    "tests/test_phase3_interface.py",
    "tests/test_phase3_models.py",
    "tests/test_phase3_events.py",
    "tests/test_phase3_contract_validation.py",
    "tests/test_phase4_translator.py",
    "tests/test_phase5_state.py",
    "tests/test_phase5_dispatcher.py",
    "tests/test_phase5_engine.py",
]

PHASE6_CONTRACT_TESTS = [
    "tests/test_phase6_context.py",
    "tests/test_phase6_prompt.py",
    "tests/test_phase6_actions.py",
    "tests/test_phase6_runtime.py",
]


PHASE7_CONTRACT_TESTS = [
    "tests/test_phase7_verification.py",
    "tests/test_verification_workflow.py",
    "tests/test_completion_protocol.py",
]


def main() -> int:
    load_project_env()
    print("Checking Chakra backend connectivity...")
    client = require_chakra()
    client.disconnect()
    print("Chakra is reachable.\n")

    failed: list[str] = []

    print("=== Contract tests (no LLM) ===")
    for script in CONTRACT_TESTS + PHASE6_CONTRACT_TESTS + PHASE7_CONTRACT_TESTS:
        code = subprocess.call([sys.executable, str(ROOT / script)], cwd=ROOT)
        status = "PASS" if code == 0 else "FAIL"
        print(f"  {status}  {script}")
        if code != 0:
            failed.append(script)

    print("\n=== Real LLM integration tests ===")
    for script in REAL_INTEGRATION_TESTS:
        code = subprocess.call([sys.executable, str(ROOT / script)], cwd=ROOT)
        status = "PASS" if code == 0 else "FAIL"
        print(f"  {status}  {script}")
        if code != 0:
            failed.append(script)

    print()
    if failed:
        print(f"FAILED ({len(failed)}):", ", ".join(failed))
        return 1
    print("All tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
