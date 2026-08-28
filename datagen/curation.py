"""curation.py — a curator's manual "this one's good, don't regenerate it"
list. Adapted from the sibling datagen_pipeline/queue.py's SKIP_DONE_KEYS
constant, made persistent and mutable instead of hardcoded in source.

Distinct from checkpoint.py: checkpoint state is automatic and reflects
whether THIS batch run already finished a task; curation is a deliberate,
durable human judgment that survives across totally different batch runs
and config changes, until someone explicitly un-marks it.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CURATION_PATH = REPO_ROOT / "artifacts" / "curation" / "skip_done.json"


@dataclass
class CurationEntry:
    reason: str = ""
    marked_at: str = ""


class CurationList:
    def __init__(self, *, path: Path = CURATION_PATH) -> None:
        self.path = path
        self._entries: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if not self.path.is_file():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._entries, indent=2, ensure_ascii=False), encoding="utf-8")

    def mark_good(self, task_id: str, *, reason: str = "") -> None:
        self._entries[task_id] = asdict(
            CurationEntry(reason=reason, marked_at=datetime.now(timezone.utc).isoformat())
        )
        self._save()

    def unmark(self, task_id: str) -> bool:
        if task_id in self._entries:
            del self._entries[task_id]
            self._save()
            return True
        return False

    def is_marked_good(self, task_id: str) -> bool:
        return task_id in self._entries

    def reason_for(self, task_id: str) -> str:
        return self._entries.get(task_id, {}).get("reason", "")

    def all_marked(self) -> list[str]:
        return sorted(self._entries.keys())
