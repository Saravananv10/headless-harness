"""dataset_manifest.py — an append-only, content-addressed record of every
task this pipeline has attempted, and a way to cut an immutable dataset
version from it.

Today's logs/<run-id>/pipeline/ folders are real, useful per-run artifacts
but aren't a dataset object — nothing ties a batch of runs together, and
regenerating the same task tomorrow with a changed prompt template is
indistinguishable from today's run except by timestamp. This closes that
gap with two primitives: an append-only ledger of every attempt
(entries.jsonl), and freeze_dataset(), which hashes a set of entries into an
immutable, versioned snapshot — the same idea DVC/lakeFS-style content
addressing uses, implemented with stdlib hashlib/json only.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_ROOT = REPO_ROOT / "artifacts" / "dataset_manifest"
ENTRIES_PATH = MANIFEST_ROOT / "entries.jsonl"
SNAPSHOTS_DIR = MANIFEST_ROOT / "snapshots"

_DEFAULT_TEMPLATE_PATHS = (
    REPO_ROOT / "verification" / "prompts.py",
    REPO_ROOT / "datagen" / "prompt_compose.py",
)


def compute_template_hash(paths: list[Path] | None = None) -> str:
    """Fingerprint the file(s) that determine what text Chakra actually
    receives. Changes whenever the prompt contract changes."""
    paths = paths if paths is not None else list(_DEFAULT_TEMPLATE_PATHS)
    hasher = hashlib.sha256()
    for path in sorted(paths, key=str):
        if path.is_file():
            hasher.update(path.read_bytes())
    return hasher.hexdigest()


def compute_objective_hash(objective: str) -> str:
    return hashlib.sha256(objective.encode("utf-8")).hexdigest()


@dataclass
class ManifestEntry:
    task_id: str
    category: str
    origin: str
    run_id: str
    status: str
    verdict: str = "NONE"
    authoritative_pass: bool = False
    independent_verification_passed: bool | None = None
    turn_count: int = 0
    tool_executions: int = 0
    template_hash: str = ""
    objective_hash: str = ""
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def append_entry(entry: ManifestEntry, *, path: Path = ENTRIES_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")


def load_entries(*, path: Path = ENTRIES_PATH) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _dataset_id(entries: list[dict[str, Any]]) -> str:
    canonical = json.dumps(entries, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def freeze_dataset(
    *,
    filter_run_ids: set[str] | None = None,
    entries_path: Path = ENTRIES_PATH,
    snapshots_dir: Path = SNAPSHOTS_DIR,
) -> dict[str, Any]:
    """Cut an immutable, content-addressed snapshot from the current
    manifest entries. Same input entries always produce the same dataset_id."""
    entries = load_entries(path=entries_path)
    if filter_run_ids is not None:
        entries = [e for e in entries if e.get("run_id") in filter_run_ids]

    entries_sorted = sorted(entries, key=lambda e: (e.get("category", ""), e.get("task_id", "")))
    dataset_id = _dataset_id(entries_sorted)

    by_category: dict[str, dict[str, int]] = {}
    for e in entries_sorted:
        cat = e.get("category") or "unknown"
        stats = by_category.setdefault(cat, {"total": 0, "passed": 0})
        stats["total"] += 1
        if e.get("status") == "PASSED":
            stats["passed"] += 1

    snapshot = {
        "dataset_id": dataset_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "entry_count": len(entries_sorted),
        "passed_count": sum(1 for e in entries_sorted if e.get("status") == "PASSED"),
        "template_hashes": sorted({e.get("template_hash", "") for e in entries_sorted}),
        "by_category": by_category,
        "entries": entries_sorted,
    }

    snapshots_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshots_dir / f"{dataset_id}.json"
    snapshot_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    snapshot["_path"] = str(snapshot_path)
    return snapshot
