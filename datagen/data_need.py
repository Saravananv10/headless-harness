"""data_need.py — hybrid detector for whether a task implies pre-supplied
external input data (vs. a from-scratch build where the agent creates its
own seed/fixture data).

Heuristic first (cheap, deterministic). An optional LLM fallback only fires
when the heuristic is ambiguous, and its answer is cached per task id so a
re-run never re-calls the LLM for the same task.
"""

from __future__ import annotations

import json
from pathlib import Path

from datagen.task_spec import TaskSpec

_INGEST_KEYWORDS = (
    "ingest", "ingests", "ingesting",
    "erp", "tally", "export", "exports",
    "register", "feed", "feeds",
    "csv", "spreadsheet", "dataset",
    "upload", "uploads",
    "log", "logs", "alert", "alerts",
    "sample", "existing data", "existing records",
    "reconcil", "correlate", "correlation",
    "cross-reference", "cross reference",
    "gstr", "26as", "ledger", "ledgers",
    "invoice", "invoices", "transaction", "transactions",
    "returns data", "prior case", "cached",
)

_GREENFIELD_KEYWORDS = (
    "build a", "build an", "create a", "create an",
    "from scratch", "production-quality", "production quality",
    "web application", "app should allow", "users should be able to",
)

_AMBIGUOUS_MARGIN = 1


def _score(text: str, keywords: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(1 for kw in keywords if kw in lowered)


def _scores(spec: TaskSpec) -> tuple[int, int]:
    text = f"{spec.description}\n{spec.process_steps}"
    return _score(text, _INGEST_KEYWORDS), _score(text, _GREENFIELD_KEYWORDS)


def needs_input_data(spec: TaskSpec) -> tuple[bool, str]:
    """Heuristic decision on whether a task needs pre-synthesized external input data."""
    ingest_score, greenfield_score = _scores(spec)
    decision = (ingest_score - greenfield_score) >= _AMBIGUOUS_MARGIN
    return decision, f"ingest_score={ingest_score} greenfield_score={greenfield_score}"


def is_ambiguous(spec: TaskSpec) -> bool:
    ingest_score, greenfield_score = _scores(spec)
    return abs(ingest_score - greenfield_score) <= _AMBIGUOUS_MARGIN


_LLM_SYSTEM = (
    "You classify software-engineering task briefs for a data-generation harness. "
    "Answer with exactly one word: YES if the task requires the agent to ingest or "
    "process pre-existing external data (e.g. financial records, logs, exports, "
    "samples) that the harness must synthesize before the agent starts; NO if the "
    "task is a from-scratch build where the agent is expected to create its own "
    "seed/fixture data."
)


def needs_input_data_llm(
    spec: TaskSpec, llm, *, cache_path: Path | None = None
) -> tuple[bool, str]:
    """LLM-backed decision, cached per task id. Falls back to the heuristic
    when the heuristic is unambiguous, or on any LLM error."""
    cache: dict[str, dict] = {}
    if cache_path and cache_path.is_file():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            cache = {}

    if spec.id in cache:
        entry = cache[spec.id]
        return bool(entry["needs_data"]), str(entry["reason"])

    heuristic_decision, heuristic_reason = needs_input_data(spec)
    if not is_ambiguous(spec):
        return heuristic_decision, heuristic_reason

    try:
        raw = llm.complete(
            [
                {"role": "system", "content": _LLM_SYSTEM},
                {"role": "user", "content": spec.narrative()[:4000]},
            ],
            temperature=0.0,
        )
        decision = raw.strip().upper().startswith("Y")
        reason = f"llm_classified ambiguous heuristic ({heuristic_reason})"
    except Exception:
        decision, reason = heuristic_decision, f"llm_error fallback ({heuristic_reason})"

    if cache_path:
        cache[spec.id] = {"needs_data": decision, "reason": reason}
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")

    return decision, reason
