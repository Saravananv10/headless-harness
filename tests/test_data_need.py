"""Tests for datagen.data_need heuristic + LLM fallback (deterministic LLM only)."""

from __future__ import annotations

from pathlib import Path

from controller.llm import DeterministicLLMClient
from datagen import data_need
from datagen.task_spec import TaskSpec


def _spec(description: str, process_steps: str = "") -> TaskSpec:
    return TaskSpec(
        id="test-01",
        title="Test task",
        description=description,
        category="test",
        origin="bank",
        sheet="sheet",
        row_num=2,
        process_steps=process_steps,
    )


def test_gst_reconciliation_flagged_as_needing_input_data():
    spec = _spec(
        "Ingest ERP/Tally exports, purchase/sales registers, and GSTR-2B/1 data. "
        "Match invoices and flag mismatches by supplier, HSN, tax rate, and period."
    )
    needs, _ = data_need.needs_input_data(spec)
    assert needs is True


def test_greenfield_app_build_flagged_as_not_needing_input_data():
    spec = _spec(
        "Build a production-quality personal finance tracker application from scratch. "
        "Support registration/auth, isolated user data, income/expense CRUD, categories, "
        "budgets, and a dashboard."
    )
    needs, _ = data_need.needs_input_data(spec)
    assert needs is False


def test_llm_fallback_used_only_when_ambiguous_and_cached(tmp_path: Path):
    spec = _spec("Build a small internal tool.")  # ambiguous / low-signal
    cache_path = tmp_path / "cache.json"
    llm = DeterministicLLMClient(["YES"])

    needs1, _reason1 = data_need.needs_input_data_llm(spec, llm, cache_path=cache_path)
    assert needs1 is True
    assert len(llm.calls) == 1

    # Second call for the same task id must hit the cache, not the LLM again.
    needs2, _reason2 = data_need.needs_input_data_llm(spec, llm, cache_path=cache_path)
    assert needs2 is True
    assert len(llm.calls) == 1


def test_unambiguous_heuristic_never_calls_llm(tmp_path: Path):
    spec = _spec(
        "Ingest ERP/Tally exports, purchase/sales registers, and GSTR-2B/1 data. "
        "Match invoices and flag mismatches by supplier, HSN, tax rate, and period."
    )
    llm = DeterministicLLMClient([])  # would raise if called
    needs, _reason = data_need.needs_input_data_llm(spec, llm, cache_path=tmp_path / "cache.json")
    assert needs is True
    assert len(llm.calls) == 0
