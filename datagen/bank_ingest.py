"""bank_ingest.py — read tasks from the local forged task bank under
artifacts/datagen_task_bank/by_category/<category>/. This is the harness's
own native task-bank format (produced by prompt_forge + datagen_dims): a
seed JSON (title/seed/category/dimensions_hint) plus, where available, an
already-LLM-expanded platform_prompt.md PRD.

Three sub-layouts exist across categories today and are all handled
transparently:
  1. flat + forged/:     <cat>/<idx>_<slug>.json + <cat>/forged/<idx>_<id>_<slug>/platform_prompt.md
  2. flat + sibling .md:  <cat>/<idx>_<slug>.json + <cat>/<idx>_<slug>.md
  3. nested by_topic/:    <cat>/by_topic/<topic>/<idx>_<slug>.json + <cat>/by_topic/<topic>/<idx>_<id>_<slug>/platform_prompt.md
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from datagen.task_spec import TaskSpec

REPO_ROOT = Path(__file__).resolve().parents[1]
BANK_ROOT = REPO_ROOT / "artifacts" / "datagen_task_bank" / "by_category"

_IDX_RE = re.compile(r"^(\d+)_")


def _match_prompt_dir(search_dir: Path, *, idx: str, task_id: str) -> Path | None:
    """Find <search_dir>/<some-dir>/platform_prompt.md whose directory name
    identifies this task. Directory naming isn't consistent across topics —
    e.g. GST dirs are idx-prefixed ("01_gst_01_...") but TDS dirs are
    id-prefixed with no numeric prefix at all ("TDS-01_..."). Try idx-prefix
    first (cheap, unambiguous), then fall back to an id substring match
    across every candidate directory that actually has a platform_prompt.md.
    """
    if not search_dir.is_dir():
        return None

    if idx:
        for cand in sorted(search_dir.glob(f"{idx}_*")):
            prompt = cand / "platform_prompt.md"
            if prompt.is_file():
                return prompt

    if task_id:
        needle = task_id.lower()
        for cand in sorted(search_dir.iterdir()):
            if not cand.is_dir():
                continue
            prompt = cand / "platform_prompt.md"
            if prompt.is_file() and needle in cand.name.lower():
                return prompt
    return None


def _load_seed_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _seed_index(seed_path: Path, seed: dict[str, Any]) -> str:
    m = _IDX_RE.match(seed_path.name)
    return m.group(1) if m else str(seed.get("index") or "")


def _spec_from_seed(
    seed: dict[str, Any],
    *,
    category: str,
    topic: str,
    platform_prompt_text: str,
    row_num: int,
) -> TaskSpec:
    idx = str(seed.get("index") or row_num).strip()
    task_id = str(seed.get("id") or f"{category}_{idx}").strip()
    title = str(seed.get("title") or task_id).strip()
    seed_text = str(seed.get("seed") or "").strip()
    dims = dict(seed.get("dimensions_hint") or {})
    return TaskSpec(
        id=task_id,
        title=title,
        description=seed_text,
        category=category,
        origin="datagen_task_bank",
        sheet=topic or category,
        row_num=row_num,
        subcategory=topic,
        platform_prompt=platform_prompt_text.strip(),
        dimensions_hint=dims,
    )


def load_category(category: str, *, root: Path = BANK_ROOT) -> list[TaskSpec]:
    """Load every task in one bank category, handling all known sub-layouts."""
    cat_dir = root / category
    if not cat_dir.is_dir():
        return []

    specs: list[TaskSpec] = []
    row_num = 0

    by_topic = cat_dir / "by_topic"
    if by_topic.is_dir():
        # Nested layout (finance_ca_practice today).
        for topic_dir in sorted(p for p in by_topic.iterdir() if p.is_dir()):
            topic = topic_dir.name
            for seed_path in sorted(topic_dir.glob("*.json")):
                seed = _load_seed_json(seed_path)
                if not seed:
                    continue
                row_num += 1
                idx = _seed_index(seed_path, seed)
                task_id = str(seed.get("id") or "")
                prompt_path = _match_prompt_dir(topic_dir, idx=idx, task_id=task_id)
                prompt_text = prompt_path.read_text(encoding="utf-8") if prompt_path else ""
                specs.append(
                    _spec_from_seed(
                        seed,
                        category=category,
                        topic=topic,
                        platform_prompt_text=prompt_text,
                        row_num=row_num,
                    )
                )
        return specs

    # Flat layout: seed JSON files directly under the category dir.
    for seed_path in sorted(cat_dir.glob("*.json")):
        seed = _load_seed_json(seed_path)
        if not seed:
            continue
        row_num += 1
        idx = _seed_index(seed_path, seed)
        task_id = str(seed.get("id") or "")

        prompt_text = ""
        forged_prompt = _match_prompt_dir(cat_dir / "forged", idx=idx, task_id=task_id)
        if forged_prompt:
            prompt_text = forged_prompt.read_text(encoding="utf-8")
        else:
            sibling_md = seed_path.with_suffix(".md")
            if sibling_md.is_file():
                prompt_text = sibling_md.read_text(encoding="utf-8")

        specs.append(
            _spec_from_seed(
                seed,
                category=category,
                topic="",
                platform_prompt_text=prompt_text,
                row_num=row_num,
            )
        )
    return specs


def list_categories(*, root: Path = BANK_ROOT) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def load_bank(categories: list[str] | None = None, *, root: Path = BANK_ROOT) -> list[TaskSpec]:
    """Load every task across the given categories (default: every bank category)."""
    cats = categories if categories is not None else list_categories(root=root)
    all_specs: list[TaskSpec] = []
    for cat in cats:
        all_specs.extend(load_category(cat, root=root))

    seen_ids: dict[str, int] = {}
    for spec in all_specs:
        seen_ids[spec.id] = seen_ids.get(spec.id, 0) + 1
        if seen_ids[spec.id] > 1:
            spec.id = f"{spec.id}-{seen_ids[spec.id]}"
    for i, spec in enumerate(all_specs, start=1):
        spec.global_index = i
    return all_specs
