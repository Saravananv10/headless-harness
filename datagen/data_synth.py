"""data_synth.py — generic, schema-inferring synthetic input-data engine.

Used only for tasks that data_need.needs_input_data() flags as requiring
pre-supplied external input data. Infers a small declarative schema from the
task's own narrative via one cached LLM call, then renders it deterministically
(random.seed(seed)) into CSV/JSON fixture files — no per-domain Python.
"""

from __future__ import annotations

import csv
import json
import random
import string
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from datagen.task_spec import TaskSpec

_ALLOWED_TYPES = {
    "string", "int", "float", "date", "enum",
    "email", "name", "company", "id", "foreign_key",
}

_NAME_POOL = [
    "Aarav Shah", "Meera Nair", "Rohan Gupta", "Fatima Khan", "Liam Chen",
    "Sofia Rossi", "Noah Muller", "Amara Okafor", "Wei Zhang", "Elena Petrova",
    "Diego Fernandez", "Aisha Rahman", "Lucas Silva", "Hana Kobayashi", "Omar Haddad",
]
_COMPANY_POOL = [
    "Northwind Traders", "Vertex Systems", "Bluepeak Logistics", "Solaris Retail",
    "Ironwood Manufacturing", "Cobalt Analytics", "Harborview Insurance",
    "Meridian Health Group", "Pinecrest Realty", "Argon Security Labs",
]


@dataclass
class FieldSchema:
    name: str
    type: str
    values: list[str] = field(default_factory=list)
    ref: str | None = None  # "<file_name>.<field_name>" for foreign_key


@dataclass
class FileSchema:
    name: str
    format: str  # "csv" | "json"
    fields: list[FieldSchema]
    row_count: int = 50


@dataclass
class DataSchema:
    files: list[FileSchema]

    def to_dict(self) -> dict[str, Any]:
        return {
            "files": [
                {
                    "name": f.name,
                    "format": f.format,
                    "row_count": f.row_count,
                    "fields": [
                        {"name": fld.name, "type": fld.type, "values": fld.values, "ref": fld.ref}
                        for fld in f.fields
                    ],
                }
                for f in self.files
            ]
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DataSchema":
        files: list[FileSchema] = []
        for f in data.get("files", []):
            fields_: list[FieldSchema] = []
            for fld in f.get("fields", []):
                ftype = str(fld.get("type", "string"))
                if ftype not in _ALLOWED_TYPES:
                    ftype = "string"
                fields_.append(
                    FieldSchema(
                        name=str(fld["name"]),
                        type=ftype,
                        values=[str(v) for v in fld.get("values", [])],
                        ref=fld.get("ref"),
                    )
                )
            fmt = str(f.get("format", "csv")).lower()
            if fmt not in ("csv", "json"):
                fmt = "csv"
            row_count = max(1, min(int(f.get("row_count", 50) or 50), 2000))
            files.append(FileSchema(name=str(f["name"]), format=fmt, fields=fields_, row_count=row_count))
        return cls(files=files)


@dataclass
class GenerationResult:
    output_dir: Path
    files: list[str] = field(default_factory=list)


_SCHEMA_SYSTEM = """You design tiny synthetic-data schemas for a software test-fixture generator.
Given a task brief, output ONLY a JSON object (no prose, no code fences) shaped like:
{"files": [{"name": "invoices.csv", "format": "csv", "row_count": 40,
  "fields": [{"name": "invoice_id", "type": "id"},
             {"name": "supplier", "type": "company"},
             {"name": "amount", "type": "float"},
             {"name": "status", "type": "enum", "values": ["pending", "matched", "disputed"]},
             {"name": "invoice_date", "type": "date"}]}]}
Allowed field types ONLY: string, int, float, date, enum (requires "values"), email, name,
company, id, foreign_key (requires "ref": "<other_file_name>.<field_name>").
Propose 1-3 files, 4-10 fields each, row_count between 10 and 200. Fields should match
what the task brief says it ingests/reads. Output raw JSON only."""


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def infer_schema(spec: TaskSpec, llm, *, cache_path: Path | None = None) -> DataSchema:
    """Infer a small declarative data schema from the task's narrative. Cached per task id."""
    if cache_path and cache_path.is_file():
        try:
            return DataSchema.from_dict(json.loads(cache_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError, KeyError):
            pass

    raw = llm.complete(
        [
            {"role": "system", "content": _SCHEMA_SYSTEM},
            {"role": "user", "content": spec.narrative()[:4000]},
        ],
        temperature=0.2,
    )
    data = json.loads(_strip_fences(raw))
    schema = DataSchema.from_dict(data)
    if not schema.files:
        raise ValueError(f"Inferred schema for task {spec.id} has no files")

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(schema.to_dict(), indent=2), encoding="utf-8")
    return schema


def _random_value(
    fld: FieldSchema, rng: random.Random, row_idx: int, ref_ids: dict[str, list[str]]
) -> Any:
    if fld.type == "int":
        return rng.randint(1, 100000)
    if fld.type == "float":
        return round(rng.uniform(1.0, 100000.0), 2)
    if fld.type == "date":
        base = date(2024, 1, 1)
        return (base + timedelta(days=rng.randint(0, 545))).isoformat()
    if fld.type == "enum":
        return rng.choice(fld.values) if fld.values else "unknown"
    if fld.type == "email":
        return f"user{row_idx}.{rng.randint(100, 999)}@example.com"
    if fld.type == "name":
        return rng.choice(_NAME_POOL)
    if fld.type == "company":
        return rng.choice(_COMPANY_POOL)
    if fld.type == "id":
        suffix = "".join(rng.choices(string.ascii_uppercase + string.digits, k=6))
        return f"{fld.name.upper()[:3]}-{suffix}"
    if fld.type == "foreign_key" and fld.ref:
        ref_file, _, _ = fld.ref.rpartition(".")
        pool = ref_ids.get(ref_file)
        if pool:
            return rng.choice(pool)
        return f"REF-{row_idx}"
    return f"{fld.name}_{row_idx}"


def synthesize(schema: DataSchema, output_dir: Path, *, seed: int) -> GenerationResult:
    """Deterministically render a DataSchema into CSV/JSON fixture files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    files_written: list[str] = []
    ref_ids: dict[str, list[str]] = {}

    # Files with no foreign_key fields first, so their generated ids are
    # available when a later file resolves a foreign_key reference to them.
    ordered = sorted(
        schema.files,
        key=lambda f: any(fld.type == "foreign_key" for fld in f.fields),
    )

    for file_schema in ordered:
        rows: list[dict[str, Any]] = []
        id_field = next((f.name for f in file_schema.fields if f.type == "id"), None)
        generated_ids: list[str] = []
        for row_idx in range(1, file_schema.row_count + 1):
            row = {fld.name: _random_value(fld, rng, row_idx, ref_ids) for fld in file_schema.fields}
            if id_field:
                generated_ids.append(str(row[id_field]))
            rows.append(row)
        if id_field:
            ref_ids[file_schema.name] = generated_ids

        out_path = output_dir / file_schema.name
        if file_schema.format == "json":
            out_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        else:
            fieldnames = [fld.name for fld in file_schema.fields]
            with out_path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        files_written.append(str(out_path))

    return GenerationResult(output_dir=output_dir, files=files_written)
