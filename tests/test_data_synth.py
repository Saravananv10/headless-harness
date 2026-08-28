"""Tests for datagen.data_synth (deterministic rendering, no live LLM)."""

from __future__ import annotations

import json
from pathlib import Path

from controller.llm import DeterministicLLMClient
from datagen import data_synth
from datagen.task_spec import TaskSpec

_SCHEMA_JSON = json.dumps(
    {
        "files": [
            {
                "name": "customers.csv",
                "format": "csv",
                "row_count": 5,
                "fields": [
                    {"name": "customer_id", "type": "id"},
                    {"name": "name", "type": "name"},
                ],
            },
            {
                "name": "invoices.csv",
                "format": "csv",
                "row_count": 8,
                "fields": [
                    {"name": "invoice_id", "type": "id"},
                    {"name": "customer_id", "type": "foreign_key", "ref": "customers.csv.customer_id"},
                    {"name": "amount", "type": "float"},
                    {"name": "status", "type": "enum", "values": ["pending", "paid"]},
                ],
            },
        ]
    }
)


def _spec() -> TaskSpec:
    return TaskSpec(
        id="test-01",
        title="Test",
        description="Ingest customer and invoice data and reconcile.",
        category="test",
        origin="bank",
        sheet="sheet",
        row_num=2,
    )


def test_infer_schema_parses_llm_json_and_caches(tmp_path: Path):
    cache_path = tmp_path / "schema.json"
    llm = DeterministicLLMClient([_SCHEMA_JSON])
    schema = data_synth.infer_schema(_spec(), llm, cache_path=cache_path)
    assert len(schema.files) == 2
    assert cache_path.is_file()

    # Second call for the same cache path must hit the cache, not the LLM again.
    schema2 = data_synth.infer_schema(_spec(), llm, cache_path=cache_path)
    assert len(schema2.files) == 2
    assert len(llm.calls) == 1


def test_synthesize_writes_deterministic_csv_with_resolved_foreign_keys(tmp_path: Path):
    schema = data_synth.DataSchema.from_dict(json.loads(_SCHEMA_JSON))
    out_dir = tmp_path / "data"
    result = data_synth.synthesize(schema, out_dir, seed=123)
    assert len(result.files) == 2
    assert (out_dir / "customers.csv").is_file()
    assert (out_dir / "invoices.csv").is_file()

    customer_ids = set()
    with (out_dir / "customers.csv").open(encoding="utf-8") as fh:
        for line in fh.readlines()[1:]:
            customer_ids.add(line.split(",")[0])
    with (out_dir / "invoices.csv").open(encoding="utf-8") as fh:
        for line in fh.readlines()[1:]:
            fk = line.split(",")[1]
            assert fk in customer_ids  # every foreign key resolves to a real customer id

    result_again = data_synth.synthesize(schema, tmp_path / "data2", seed=123)
    original = (out_dir / "invoices.csv").read_text(encoding="utf-8")
    repeat = (tmp_path / "data2" / "invoices.csv").read_text(encoding="utf-8")
    assert original == repeat  # same seed -> identical output
    assert len(result_again.files) == 2
