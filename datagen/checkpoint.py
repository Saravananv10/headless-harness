"""checkpoint.py — durable per-task state so a killed batch run can resume
instead of starting over from task 1.

Adapted from the sibling datagen_pipeline/checkpoint.py design (a crash-safe
JSON store keyed by task_key), scoped down to what this package's CLI needs:
skip tasks already marked "done" on the next invocation of the same batch,
retry ones marked "failed".
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_PATH = REPO_ROOT / "artifacts" / "checkpoint" / "checkpoint.json"


@dataclass
class TaskState:
    status: str  # "running" | "done" | "failed"
    run_id: str = ""
    updated_at: str = ""
    detail: str = ""


class CheckpointStore:
    """Loads/persists per-task status keyed by task_id. Safe to share across
    a whole batch loop — every mutating call flushes to disk immediately, so
    a kill -9 mid-batch loses at most the in-flight task."""

    def __init__(self, *, path: Path = CHECKPOINT_PATH) -> None:
        self.path = path
        self._state: dict[str, dict[str, Any]] = self._load()

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.is_file():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._state, indent=2, ensure_ascii=False), encoding="utf-8")

    def _set(self, task_id: str, *, status: str, run_id: str = "", detail: str = "") -> None:
        self._state[task_id] = asdict(
            TaskState(
                status=status,
                run_id=run_id,
                detail=detail,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
        )
        self._save()

    def mark_running(self, task_id: str, *, run_id: str = "") -> None:
        self._set(task_id, status="running", run_id=run_id)

    def mark_done(self, task_id: str, *, run_id: str = "") -> None:
        self._set(task_id, status="done", run_id=run_id)

    def mark_failed(self, task_id: str, *, run_id: str = "", detail: str = "") -> None:
        self._set(task_id, status="failed", run_id=run_id, detail=detail)

    def status(self, task_id: str) -> str | None:
        entry = self._state.get(task_id)
        return entry["status"] if entry else None

    def is_done(self, task_id: str) -> bool:
        return self.status(task_id) == "done"

    def reset(self, task_id: str) -> None:
        self._state.pop(task_id, None)
        self._save()

    def reset_failed(self) -> int:
        failed = [k for k, v in self._state.items() if v.get("status") == "failed"]
        for k in failed:
            self._state.pop(k, None)
        self._save()
        return len(failed)

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in self._state.values():
            status = entry.get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
        return counts
