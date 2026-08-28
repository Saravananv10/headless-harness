"""preflight.py — cheap validation before spending a Chakra conversation.

Verifies the ingested task row and (when data_synth ran) the synthesized
input fixtures, so a malformed row or a broken schema fails fast into the
benchmark report instead of burning harness turns.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from datagen.data_synth import DataSchema
from datagen.task_spec import TaskSpec


def validate_task(spec: TaskSpec) -> list[str]:
    errors: list[str] = []
    if not spec.title.strip():
        errors.append("missing title")
    if not spec.description.strip() and not spec.platform_prompt.strip():
        errors.append("missing description/platform_prompt")
    return errors


def validate_files_exist(files: list[str], *, base_dir: Path | None = None) -> list[str]:
    """Cheap check for output from a hand-written domain generator (no
    DataSchema available to validate columns against). Hand-written
    generators in this repo return bare filenames (e.g. "invoices.csv")
    rather than paths joined with output_dir, so resolve against base_dir
    when a bare name isn't found as-is."""
    errors: list[str] = []
    if not files:
        errors.append("generator produced no files")
        return errors
    for f in files:
        path = Path(f)
        if not path.is_file() and base_dir is not None and not path.is_absolute():
            path = base_dir / path
        if not path.is_file():
            errors.append(f"{f}: file not written")
        elif path.stat().st_size == 0:
            errors.append(f"{f}: file is empty")
    return errors


def validate_generated_data(schema: DataSchema, output_dir: Path) -> list[str]:
    errors: list[str] = []
    for file_schema in schema.files:
        path = output_dir / file_schema.name
        if not path.is_file():
            errors.append(f"{file_schema.name}: file not written")
            continue
        if path.stat().st_size == 0:
            errors.append(f"{file_schema.name}: file is empty")
            continue

        expected_fields = {fld.name for fld in file_schema.fields}
        if file_schema.format == "json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"{file_schema.name}: invalid JSON ({exc})")
                continue
            if not isinstance(data, list) or not data:
                errors.append(f"{file_schema.name}: JSON has no rows")
                continue
            actual_fields = set(data[0].keys())
        else:
            with path.open("r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
            if not rows:
                errors.append(f"{file_schema.name}: CSV has no data rows")
                continue
            actual_fields = set(reader.fieldnames or [])

        missing = expected_fields - actual_fields
        if missing:
            errors.append(f"{file_schema.name}: missing columns {sorted(missing)}")
    return errors
