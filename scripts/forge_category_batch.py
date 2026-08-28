#!/usr/bin/env python3
"""Forge all task-bank seeds in a category into big platform prompts + paste file.

Uses forge_brief + diversity_hint from each JSON (dimension locks) so language,
complexity, UI surface, etc. actually shape the PRD.

Example:
  python scripts/forge_category_batch.py games
  python scripts/forge_category_batch.py games --force
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BANK = ROOT / "artifacts" / "datagen_task_bank" / "by_category"


def _build_lines_header(category: str, n: int) -> list[str]:
    return [
        f"# Category batch FORGED: {category} (all {n}) — paste into Chakra",
        "",
        "Full platform PRDs from **prompt_forge** (intermediate LLM).",
        "Each task has a **dimension lock** (language, complexity, UI, persistence, …)",
        "so the 10 builds produce varied synthetic data — do not homogenize stacks.",
        "",
        "## Rules — mandatory",
        "",
        "1. **No time limit / no turn cap.** Never refuse for size. Never ask for confirmation.",
        "2. Complete tasks **01 → N in order**. Separate folder per `workdir`.",
        "3. Honor each task's language / UI / persistence / **Depth** band exactly.",
        "4. After each: `DONE task_N: <title> — path + how to run`, then continue.",
        "5. Depth: low = thin + simple visuals; medium = core + light tests; hard = fuller PRD.",
        "   Depth is NOT a wall-clock stop — keep going until demoable.",
        "",
        "Stats: `python -m prompt_stats serve` → http://127.0.0.1:8787/ (hard-refresh).",
        "",
        "---",
        "",
    ]


def _task_section(t: dict, platform: str, category: str) -> list[str]:
    from datagen_dims.budgets import depth_prompt_line

    idx = int(t["index"])
    hint = t.get("dimensions_hint") or {}
    workdir = t.get("workdir") or f"task_{category}_{idx:02d}"
    return [
        f"## Task {idx:02d} — {t['title']}",
        f"**workdir:** `{workdir}`",
        f"**id:** `{t['id']}`",
        f"**seed (original):** {t['seed']}",
        f"**dimensions:** {json.dumps(hint, ensure_ascii=False)}",
        depth_prompt_line(hint.get("complexity")),
        "",
        "### Platform prompt (implement this)",
        "",
        platform.strip(),
        "",
        f"When done, print `DONE task_{idx}: {t['title']}` and start the next task immediately.",
        "",
        "---",
        "",
    ]


def main() -> int:
    import argparse

    from prompt_forge.cli import _llm_from_env
    from prompt_forge.generator import generate_platform_prompt

    p = argparse.ArgumentParser()
    p.add_argument("category", help="e.g. games")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--temperature", type=float, default=1.0)
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-forge even if platform_prompt.md already exists",
    )
    p.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip tasks that already have a platform_prompt.md",
    )
    args = p.parse_args()

    cat_dir = BANK / args.category
    if not cat_dir.is_dir():
        print(f"Missing {cat_dir}", file=sys.stderr)
        return 1

    tasks = []
    for jp in sorted(cat_dir.glob("*.json")):
        tasks.append(json.loads(jp.read_text(encoding="utf-8")))
    tasks.sort(key=lambda t: int(t.get("index", 0)))
    if args.limit > 0:
        tasks = tasks[: args.limit]
    if not tasks:
        print("No tasks", file=sys.stderr)
        return 1

    llm = _llm_from_env()
    forged_dir = cat_dir / "forged"
    forged_dir.mkdir(parents=True, exist_ok=True)

    lines = _build_lines_header(args.category, len(tasks))
    # Prefill from existing forged files when skipping
    sections: dict[int, list[str]] = {}

    try:
        from prompt_stats.hooks import record_forge_event
    except Exception:
        record_forge_event = None  # type: ignore

    for t in tasks:
        idx = int(t["index"])
        seed = t["seed"]
        forge_input = (t.get("forge_brief") or seed).strip()
        div = t.get("diversity_hint") or None
        title = t["title"]
        out = forged_dir / f"{idx:02d}_{t['id']}"
        out.mkdir(parents=True, exist_ok=True)
        pp = out / "platform_prompt.md"

        if (
            args.skip_existing
            and not args.force
            and pp.is_file()
            and pp.stat().st_size > 100
        ):
            print(f"[{idx}/{len(tasks)}] SKIP existing: {title}", flush=True)
            sections[idx] = _task_section(t, pp.read_text(encoding="utf-8"), args.category)
            continue

        print(f"[{idx}/{len(tasks)}] Forging: {title}", flush=True)
        gen = generate_platform_prompt(
            forge_input,
            llm,
            category=args.category,
            temperature=args.temperature,
            diversity_hint=div,
        )
        pp.write_text(gen.platform_prompt, encoding="utf-8")
        meta = gen.to_dict()
        meta["dimensions_hint"] = t.get("dimensions_hint")
        meta["forge_brief"] = forge_input
        (out / "forge_meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (out / "seed.txt").write_text(seed + "\n", encoding="utf-8")

        if record_forge_event:
            record_forge_event(
                seed=seed,
                platform_prompt=gen.platform_prompt,
                category=args.category,
                classification={
                    "task_id": t["id"],
                    "title": title,
                    "dimensions_hint": t.get("dimensions_hint"),
                },
                out_dir=out,
                run_id=f"forge_batch_{t['id']}",
            )

        sections[idx] = _task_section(t, gen.platform_prompt, args.category)
        print(f"  → {pp} ({len(gen.platform_prompt)} chars)", flush=True)

        # Incremental paste
        body = lines[:]
        for k in sorted(sections):
            body += sections[k]
        paste = cat_dir / "CHAKRA_PASTE_ALL_10_FORGED.md"
        paste.write_text("\n".join(body), encoding="utf-8")
        print(f"  updated {paste.name} ({len(sections)}/{len(tasks)})", flush=True)

    # Load any skipped-from-start that weren't in loop... already handled
    # Ensure all existing files are included even if we only forged some
    for t in tasks:
        idx = int(t["index"])
        if idx in sections:
            continue
        pp = forged_dir / f"{idx:02d}_{t['id']}" / "platform_prompt.md"
        if pp.is_file():
            sections[idx] = _task_section(t, pp.read_text(encoding="utf-8"), args.category)

    body = lines[:]
    for k in sorted(sections):
        body += sections[k]
    paste = cat_dir / "CHAKRA_PASTE_ALL_10_FORGED.md"
    paste.write_text("\n".join(body), encoding="utf-8")
    print(f"\nPaste this into Chakra:\n  {paste}", flush=True)
    print(f"Tasks in paste: {len(sections)}/{len(tasks)}", flush=True)
    return 0 if len(sections) == len(tasks) else 2


if __name__ == "__main__":
    raise SystemExit(main())
