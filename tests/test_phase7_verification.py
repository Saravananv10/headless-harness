"""Phase 7 — verdict parsing and prompt unit tests."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.controller import ControllerRunResult
from verification.parser import Verdict, parse_verdict
from verification.prompts import build_unified_pipeline_objective
from verification.report import save_verification_artifacts


def test_parse_verdict_pass() -> None:
    text = "All checks passed.\n\nVERDICT: PASS"
    assert parse_verdict(text) == Verdict.PASS


def test_parse_verdict_fail() -> None:
    text = "Build failed.\nVERDICT: FAIL"
    assert parse_verdict(text) == Verdict.FAIL


def test_parse_verdict_partial() -> None:
    assert parse_verdict("blocked\nVERDICT: PARTIAL") == Verdict.PARTIAL


def test_parse_verdict_uses_last_match() -> None:
    text = "VERDICT: FAIL\nRetry note\nVERDICT: PASS"
    assert parse_verdict(text) == Verdict.PASS


def test_parse_verdict_missing() -> None:
    assert parse_verdict("no verdict here") is None
    assert parse_verdict("") is None


def test_build_unified_pipeline_objective_includes_lifecycle() -> None:
    prompt = build_unified_pipeline_objective(
        repo_path="/tmp/repo",
        objective="Build a todo app",
    )
    assert "/tmp/repo" in prompt
    assert "Build a todo app" in prompt
    assert "verification" in prompt.lower()
    assert "REPAIR_STATUS: COMPLETE" in prompt
    assert "RUNTIME_CHECK: PASS" in prompt
    assert ".venv" in prompt
    assert "node_modules" in prompt
    assert "DEPENDENCY MANIFESTS" in prompt
    assert "names only, no versions" in prompt
    assert "Never pin versions" in prompt


def test_build_unified_pipeline_objective_skip_verification() -> None:
    prompt = build_unified_pipeline_objective(
        repo_path="/tmp/repo",
        objective="Build a todo app",
        include_verification=False,
    )
    assert "IMPLEMENTATION_STATUS: COMPLETE" in prompt
    assert "--skip-verification" in prompt or "Do not run verification" in prompt
    assert "names only, no versions" in prompt
    assert "Never pin versions" in prompt


def test_save_verification_artifacts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp) / "run_test"
        controller_result = ControllerRunResult(
            objective="verify",
            conversation_id="conv-verify",
            completed=True,
            summary="Checks ok.\nVERDICT: PASS",
            turn_count=1,
            actions=[],
        )
        verify_dir = save_verification_artifacts(
            run_root,
            run_id="run_test",
            objective="verify",
            repository_path=str(run_root / "repository"),
            generation_summary="Built app",
            controller_result=controller_result,
        )
        assert verify_dir.name == "verification"
        assert (verify_dir / "verification_report.md").is_file()
        assert (verify_dir / "verdict.json").is_file()
        assert (verify_dir / "summary.json").is_file()
        verdict_data = json.loads((verify_dir / "verdict.json").read_text())
        assert verdict_data["verdict"] == "PASS"


def main() -> int:
    tests = [
        test_parse_verdict_pass,
        test_parse_verdict_fail,
        test_parse_verdict_partial,
        test_parse_verdict_uses_last_match,
        test_parse_verdict_missing,
        test_build_unified_pipeline_objective_includes_lifecycle,
        test_build_unified_pipeline_objective_skip_verification,
        test_save_verification_artifacts,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
    print("Phase 7 PASS" if not failed else f"Phase 7 FAIL ({failed})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
