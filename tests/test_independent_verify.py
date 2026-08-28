"""Tests for datagen.independent_verify (re-run claimed commands for real)."""

from __future__ import annotations

import json
from pathlib import Path

from datagen import independent_verify


def _write_trace(path: Path, verification_output: str) -> None:
    record = {"type": "agent_completed", "output": verification_output}
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")


def test_extract_commands_from_trace(tmp_path: Path):
    trace_path = tmp_path / "trace.jsonl"
    _write_trace(
        trace_path,
        "Ran the smoke suite.\n**Command run**: `pytest -q` (exit 0)\nVERDICT: PASS\n",
    )
    commands = independent_verify.extract_commands_from_trace(trace_path)
    assert commands == ["pytest -q"]


def test_extract_commands_ignores_non_verification_records(tmp_path: Path):
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        json.dumps({"type": "tool_response", "output": "Command run: rm -rf /"}) + "\n",
        encoding="utf-8",
    )
    assert independent_verify.extract_commands_from_trace(trace_path) == []


def test_verify_reproduces_passing_command(tmp_path: Path):
    trace_path = tmp_path / "trace.jsonl"
    _write_trace(trace_path, "**Command run**: `python3 -c \"import sys; sys.exit(0)\"`\nVERDICT: PASS\n")
    result = independent_verify.verify(tmp_path, trace_path)
    assert result.mode == "reproduced_claimed_commands"
    assert result.passed is True
    assert result.exit_codes == [0]


def test_verify_catches_a_false_pass_claim(tmp_path: Path):
    """The claimed command actually fails when we re-run it ourselves —
    exactly the scenario independent verification exists to catch."""
    trace_path = tmp_path / "trace.jsonl"
    _write_trace(trace_path, "**Command run**: `python3 -c \"import sys; sys.exit(1)\"`\nVERDICT: PASS\n")
    result = independent_verify.verify(tmp_path, trace_path)
    assert result.passed is False
    assert result.exit_codes == [1]


def test_verify_no_commands_found_is_not_authoritative(tmp_path: Path):
    trace_path = tmp_path / "trace.jsonl"
    _write_trace(trace_path, "Everything looks fine.\nVERDICT: PASS\n")
    result = independent_verify.verify(tmp_path, trace_path)
    assert result.mode == "no_commands_found"
    assert result.passed is False


def test_save_report_writes_json(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(independent_verify, "REPORTS_ROOT", tmp_path)
    result = independent_verify.IndependentVerifyResult(
        passed=True, mode="reproduced_claimed_commands", commands=["pytest"], exit_codes=[0]
    )
    path = independent_verify.save_report(result, run_id="run_123")
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["passed"] is True
    assert data["run_id"] == "run_123"
