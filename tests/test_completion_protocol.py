"""Unit tests for generation completion protocol helpers."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller.controller import ControllerRunResult
from controller.decision import ActionType, ControllerAction
from controller.workflow_common import (
    IMPLEMENTATION_COMPLETE_MARKER,
    implementation_complete_in_text,
    summarize_preserving_markers,
)
from verification.report import save_generation_artifacts


def test_implementation_complete_in_text_exact_marker() -> None:
    assert implementation_complete_in_text("Done.\nIMPLEMENTATION_STATUS: COMPLETE")
    assert not implementation_complete_in_text("## Implementation Complete")


def test_summarize_preserving_markers_keeps_tail_marker() -> None:
    body = "x" * 2500
    text = f"{body}\n\n{IMPLEMENTATION_COMPLETE_MARKER}"
    summary = summarize_preserving_markers(text, limit=2000)
    assert len(summary) <= 2000 + len(IMPLEMENTATION_COMPLETE_MARKER) + 4
    assert IMPLEMENTATION_COMPLETE_MARKER in summary
    assert implementation_complete_in_text(summary)


def test_summarize_preserving_markers_short_text_unchanged() -> None:
    text = f"Short message.\n{IMPLEMENTATION_COMPLETE_MARKER}"
    assert summarize_preserving_markers(text) == text


def test_save_generation_artifacts_records_completion_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_root = Path(tmp) / "run_test"
        controller_result = ControllerRunResult(
            objective="generate",
            conversation_id="conv-gen",
            completed=True,
            summary=f"Summary text.\n{IMPLEMENTATION_COMPLETE_MARKER}",
            turn_count=2,
            actions=[
                ControllerAction(
                    action=ActionType.COMPLETE,
                    reasoning="Implementation complete; verification runs in separate stage.",
                    summary=f"Summary text.\n{IMPLEMENTATION_COMPLETE_MARKER}",
                )
            ],
        )
        save_generation_artifacts(
            run_root,
            run_id="run_test",
            objective="generate",
            repository_path=str(run_root / "repository"),
            controller_result=controller_result,
        )
        data = json.loads((run_root / "generation" / "summary.json").read_text())
        assert data["implementation_marker_present"] is True
        assert "verification runs in separate stage" in (data["completion_reasoning"] or "")


def main() -> int:
    tests = [
        test_implementation_complete_in_text_exact_marker,
        test_summarize_preserving_markers_keeps_tail_marker,
        test_summarize_preserving_markers_short_text_unchanged,
        test_save_generation_artifacts_records_completion_evidence,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
    if failed:
        print(f"\n{failed} test(s) failed")
        return 1
    print(f"\nAll {len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
