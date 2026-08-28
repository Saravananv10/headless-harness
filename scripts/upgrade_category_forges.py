#!/usr/bin/env python3
"""Upgrade all non-game category forges for gpt-oss marathons.

- Depth/fidelity by complexity (no Time-budget early-stop language)
- Align UI surface to complexity ladder (low=simple, hard=richer)
- Fill missing platform_prompt.md with deterministic PRDs from seeds
- Rebuild CHAKRA_PASTE_ALL_10_FORGED.md + PI_MARATHON_RUNNER.md
- Skip games (already done). Preserve ai_ml tasks 1–3 platform prompts by default.

  python scripts/upgrade_category_forges.py
  python scripts/upgrade_category_forges.py --only ecommerce
  python scripts/upgrade_category_forges.py --only ai_ml --preserve-through 3
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BANK = ROOT / "artifacts" / "datagen_task_bank" / "by_category"

# Spread complexities across 10 slots so categories don't homogenize
COMPLEXITY_SPREAD = [
    "low",
    "medium",
    "hard",
    "low",
    "hard",
    "medium",
    "hard",
    "low",
    "medium",
    "hard",
]

FIDELITY_SECTION = """
## Complexity & fidelity lock (datagen)
- Complexity band: **{cx}**
- UI fidelity: {ui_fidelity}
- Effort cue: {expected_effort}
- Anti-stub: {anti_stub}
- **Never** stop for time/turns/“too big”; keep using tools until acceptance criteria pass, then print DONE.
- Match the locked `language_runtime`, `ui_surface`, `persistence`, and `testing_depth` from dimensions — do not homogenize to another stack.
- **Working demo required:** primary user actions must succeed in the browser/CLI (submit → visible result, seeded data, health check). Dead HTML shells are not DONE.
- If `ui_surface` is `api_only`, still ship an operator console/static page that calls the live API unless the PRD forbids UI entirely.
""".strip()


def load_tasks(cat_dir: Path) -> list[dict]:
    tasks = []
    for jp in sorted(cat_dir.glob("*.json")):
        if jp.parent.name == "forged":
            continue
        # skip nested
        if "forged" in jp.parts:
            continue
        data = json.loads(jp.read_text(encoding="utf-8"))
        data["_path"] = str(jp)
        tasks.append(data)
    tasks.sort(key=lambda t: int(t.get("index", 0)))
    return tasks


def brand_from_title(title: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", title)
    if not words:
        return "ForgeApp"
    return "".join(w.capitalize() for w in words[:3])


def ensure_dimensions(task: dict, idx: int) -> dict:
    from datagen_dims.budgets import align_ui_to_complexity

    hint = dict(task.get("dimensions_hint") or {})
    # Prefer existing complexity if already set; else assign spread
    if not hint.get("complexity"):
        hint["complexity"] = COMPLEXITY_SPREAD[(idx - 1) % len(COMPLEXITY_SPREAD)]
    if not hint.get("value"):
        hint["value"] = hint["complexity"]
    hint = align_ui_to_complexity(hint)
    task["dimensions_hint"] = hint
    return hint


def write_task_json(task: dict) -> None:
    path = Path(task["_path"])
    payload = {k: v for k, v in task.items() if not k.startswith("_")}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def inject_fidelity(platform: str, hint: dict) -> str:
    from datagen_dims.budgets import budget_for

    cx = str(hint.get("complexity") or "medium")
    b = budget_for(cx)
    block = FIDELITY_SECTION.format(
        cx=cx,
        ui_fidelity=b["ui_fidelity"],
        expected_effort=b["expected_effort"],
        anti_stub=b.get("anti_stub") or "FORBIDDEN as DONE: non-working stub UIs",
    )
    if "Complexity & fidelity lock" in platform:
        # replace existing block
        platform = re.sub(
            r"## Complexity & fidelity lock \(datagen\).*?(?=\n## |\Z)",
            block + "\n\n",
            platform,
            count=1,
            flags=re.S,
        )
        return platform.strip() + "\n"
    # insert after first H1
    lines = platform.splitlines()
    out: list[str] = []
    inserted = False
    for i, line in enumerate(lines):
        out.append(line)
        if not inserted and line.startswith("# "):
            out.append("")
            out.append(block)
            inserted = True
    if not inserted:
        out = [block, ""] + out
    return "\n".join(out).strip() + "\n"


def synthesize_platform(category: str, task: dict, hint: dict) -> str:
    from datagen_dims.budgets import budget_for

    cx = str(hint.get("complexity") or "medium")
    b = budget_for(cx)
    title = task.get("title") or task.get("id") or "Task"
    brand = brand_from_title(title)
    seed = (task.get("seed") or "").strip()
    lang = hint.get("language_runtime") or "python"
    ui = hint.get("ui_surface") or "static_html"
    persist = hint.get("persistence") or "sqlite"
    verify = hint.get("verification_mode") or "runtime_pass"
    testing = hint.get("testing_depth") or "smoke_only"
    novelty = hint.get("novelty_hook") or "domain-specific twist"
    delivery = hint.get("delivery") or "one_command_dev_server"
    artifact = hint.get("artifact_type") or "web_fullstack"

    low_bits = (
        "- Thin file count; prefer stdlib / minimal deps\n"
        "- One primary happy path + 2–3 edge cases\n"
        "- Visuals: plain CSS, no animation libraries, no heavy chart frameworks\n"
    )
    med_bits = (
        "- Core entities + main workflows from the seed\n"
        "- Light tests or smoke as locked by testing_depth\n"
        "- Clean readable UI; charts only if ui_surface implies them\n"
    )
    hard_bits = (
        "- Richer entity model, edge cases, and verification from acceptance list\n"
        "- Multi-view or multi-endpoint surface matching ui_surface\n"
        "- Stronger README + smoke/unit coverage as locked\n"
        "- Higher visual fidelity when UI is not api_only/cli_tui\n"
    )
    depth_bits = {"low": low_bits, "medium": med_bits, "hard": hard_bits}.get(cx, med_bits)

    return f"""# {brand} — {title}

## Complexity & fidelity lock (datagen)
- Complexity band: **{cx}**
- UI fidelity: {b['ui_fidelity']}
- Effort cue: {b['expected_effort']}
- Anti-stub: {b.get('anti_stub', '')}
- **Never** stop for time/turns/“too big”; keep using tools until acceptance criteria pass, then print DONE.
- Match locked stack: language=`{lang}`, ui=`{ui}`, persistence=`{persist}`, testing=`{testing}`, verification=`{verify}`.
- Working demo required (submit → visible result; seeded data). Dead HTML shells are not DONE.
- If ui=`api_only`, still ship an operator console that calls the live API.

## 1. Product identity
Build **{brand}** for category `{category}`. Seed intent (honor this product, do not genericize away):

> {seed}

Artifact type: `{artifact}`. Novelty hook: {novelty}. Delivery: `{delivery}`.

## 2. Target users & jobs
- Primary user implied by the seed / domain.
- Job: complete the core workflow end-to-end offline (no cloud accounts required unless seed demands otherwise).

## 3. Core entities
Define 3–8 concrete entities with fields consistent with persistence=`{persist}`.
Include at least one audit/history or list view so the UI/API is demonstrable.

## 4. Major feature areas
Implement the features implied by the seed. Depth band rules for **{cx}**:
{depth_bits}
Also include:
- Input validation with clear errors
- A deterministic demo/seed path OR fixture data so the app is usable with zero manual setup
- Structured logging or request log if novelty/observability hooks apply

## 5. Domain workflows
Document happy path + edge cases (empty input, invalid file/type, duplicate, not-found).
Never crash on partial input.

## 6. Data & persistence
Use persistence=`{persist}` exactly. State schema auto-created on startup when applicable.
Restart behavior documented in README.

## 7. UX / API surface
ui_surface=`{ui}`:
- If `api_only` / `cli_tui`: ship CLI or HTTP API + README curls; skip rich GUI.
- If `static_html` / `desktop_window`: server-rendered or simple static pages; minimal CSS ({cx} fidelity).
- If `html_canvas` / `dashboard_charts`: include at least one hand-drawn chart/canvas or SVG viz.
- If `react_spa` / `mobile_web`: Vite/React (or equivalent) SPA with clear routes; keep deps lean.
Expose health/liveness (`/health` or CLI `--help` smoke).

## 8. Quality, security, reliability
Offline-first where possible. No secrets. Validate sizes/types. Deterministic demo data preferred.

## 9. Documentation & testing
README: one-command run, limitations, how to demo.
testing_depth=`{testing}` — implement that level only (do not under-ship hard; do not overbuild low).

## 10. Constraints & non-goals
Do not ignore language/ui/persistence locks. No placeholder lorem-only UI. No TODO stubs on shipped paths.

## 11. Acceptance criteria
- [ ] App boots via documented command
- [ ] Happy path from seed works with fixtures/demo
- [ ] Invalid inputs rejected clearly
- [ ] Persistence/restart behavior matches lock
- [ ] Tests/smoke required by `{testing}` pass
- [ ] README enables first run without reading source
- [ ] Visual/UI fidelity matches **{cx}** band

## 12. Uniqueness / anti-clone
Keep domain language from the seed. Forbidden: generic todo-app shell, Hello World, unlabeled stubs.
""".strip() + "\n"


def platform_path(cat_dir: Path, task: dict) -> Path:
    idx = int(task["index"])
    return cat_dir / "forged" / f"{idx:02d}_{task['id']}" / "platform_prompt.md"


def write_runner(cat_dir: Path, category: str) -> None:
    forged = cat_dir / "CHAKRA_PASTE_ALL_10_FORGED.md"
    text = f"""# PASTE THIS ONLY (not the full FORGED file) — {category} marathon

You are running a **multi-turn datagen marathon**. There is **no** time limit and
**no** “single response” limit. Do **not** refuse. Do **not** ask for confirmation.
After each DONE, **immediately** start the next task.

## Forbidden self-talk (ignore and continue)
- “This is huge / cannot finish / limited time / prefer ≤N turns”
- “Please confirm / which phase next / enter plan mode”
- Homogenizing every task to the same stack (honor each task dimensions)

## How to work
**Do NOT load the whole forged file.** For each N from 01 to 10:

1. Open **only** that task’s section from:
   `{forged}`
2. Implement under `harness/chakra/task_{category}_NN/` (or the workdir named in the PRD).
3. Match **Depth (low|medium|hard)** and UI fidelity — low = thinner/simpler visuals; hard = deeper/richer.
4. Make it demoable (README + smoke/tests from the PRD). Keep calling tools until it runs.
5. Print: `DONE task_N: <title>`
6. Without stopping, go to N+1.

## Start now
Read Task 01 and implement. Never end a turn with only a plan or a question.
"""
    (cat_dir / "PI_MARATHON_RUNNER.md").write_text(text, encoding="utf-8")


def assemble(category: str, tasks: list[dict], cat_dir: Path) -> None:
    from datagen_dims.budgets import depth_prompt_line

    ready: list[tuple[dict, str]] = []
    missing = []
    for t in tasks:
        pp = platform_path(cat_dir, t)
        if pp.is_file() and pp.stat().st_size > 100:
            ready.append((t, pp.read_text(encoding="utf-8")))
        else:
            missing.append(t)

    # dimension table
    table = [
        "| # | complexity | value | language | UI | persistence | verification |",
        "|---|------------|-------|----------|----|-------------|--------------|",
    ]
    for t in tasks:
        h = t.get("dimensions_hint") or {}
        table.append(
            f"| {int(t['index']):02d} | {h.get('complexity','')} | {h.get('value','')} | "
            f"{h.get('language_runtime','')} | {h.get('ui_surface','')} | "
            f"{h.get('persistence','')} | {h.get('verification_mode','')} |"
        )

    lines = [
        f"# Category batch FORGED: {category} ({len(ready)}/{len(tasks)}) — paste into Chakra",
        "",
        "Each task is a forged PRD with a **locked dimension mix**. Implementing these under",
        f"`harness/chakra/task_{category}_NN/` produces synthetic agent trajectories for stats.",
        "",
        "**Playing/demoing alone is NOT datagen** — datagen is the implement session.",
        "",
        "## Dimension coverage",
        "",
        *table,
        "",
        "Honor each task’s dimensions. **Do not** rewrite every task to the same stack.",
        "Depth bands control fidelity/effort: **low** = thin + simple visuals; **medium** = core + light tests;",
        "**hard** = fuller acceptance + richer UI when applicable. Depth ≠ a time stop.",
        "",
        "## Rules — mandatory",
        "",
        "1. **No time limit / no turn cap.** Never refuse for size. Never ask for confirmation.",
        "2. Complete tasks **01 → N in order**. Separate folder per `workdir`.",
        "3. Plan mode OFF. Implement immediately; auto-continue between tasks.",
        "4. After each: `DONE task_N: <title> — path + how to run`, then start the next.",
        "5. Match Depth + UI fidelity to complexity. Low must look/feel simpler than hard.",
        "6. README run command + smoke/test path from the PRD.",
        "",
        "Stats: `python -m prompt_stats serve` → http://127.0.0.1:8787/ (hard-refresh).",
        "",
    ]
    if missing:
        missing_ids = ", ".join(f"{int(t['index']):02d}" for t in missing)
        lines += [
            f"**Missing platform prompts:** {missing_ids}",
            "",
        ]
    lines += ["---", ""]

    for t, platform in ready:
        idx = int(t["index"])
        workdir = t.get("workdir") or f"task_{category}_{idx:02d}"
        hint = t.get("dimensions_hint") or {}
        lines += [
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

    out = cat_dir / "CHAKRA_PASTE_ALL_10_FORGED.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"  wrote {out.name} ({len(ready)}/{len(tasks)})")


def upgrade_category(
    category: str,
    *,
    preserve_through: int = 0,
    force_synth: bool = False,
) -> None:
    cat_dir = BANK / category
    if not cat_dir.is_dir():
        print(f"skip missing {category}")
        return
    print(f"\n=== {category} ===")
    tasks = load_tasks(cat_dir)
    if not tasks:
        print("  no tasks")
        return

    for t in tasks:
        idx = int(t["index"])
        hint = ensure_dimensions(t, idx)
        write_task_json(t)

        pp = platform_path(cat_dir, t)
        pp.parent.mkdir(parents=True, exist_ok=True)
        meta = pp.parent / "forge_meta.json"

        preserve = idx <= preserve_through
        if preserve and pp.is_file() and pp.stat().st_size > 100 and not force_synth:
            text = inject_fidelity(pp.read_text(encoding="utf-8"), hint)
            pp.write_text(text, encoding="utf-8")
            print(f"  {idx:02d} preserved+fidelity")
            continue

        if pp.is_file() and pp.stat().st_size > 100 and not force_synth:
            text = inject_fidelity(pp.read_text(encoding="utf-8"), hint)
            pp.write_text(text, encoding="utf-8")
            print(f"  {idx:02d} upgraded fidelity")
        else:
            text = synthesize_platform(category, t, hint)
            pp.write_text(text, encoding="utf-8")
            meta.write_text(
                json.dumps(
                    {
                        "source": "upgrade_category_forges.synthesize",
                        "complexity": hint.get("complexity"),
                        "ui_surface": hint.get("ui_surface"),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            print(f"  {idx:02d} synthesized PRD")

        # seed.txt convenience
        seed_path = pp.parent / "seed.txt"
        if not seed_path.exists():
            seed_path.write_text((t.get("seed") or "") + "\n", encoding="utf-8")

    assemble(category, tasks, cat_dir)
    write_runner(cat_dir, category)
    print(f"  runner OK")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--preserve-through", type=int, default=0)
    ap.add_argument(
        "--force-synth",
        action="store_true",
        help="Rewrite platform prompts even when present",
    )
    ap.add_argument("--include-games", action="store_true")
    args = ap.parse_args()

    cats = (
        [args.only]
        if args.only
        else sorted(d.name for d in BANK.iterdir() if d.is_dir())
    )
    if not args.include_games:
        cats = [c for c in cats if c != "games"]

    for cat in cats:
        preserve = args.preserve_through
        if cat == "ai_ml" and args.preserve_through == 0 and args.only is None:
            # default: leave task 1–3 prompts alone when upgrading whole bank
            preserve = 3
        if args.only == "ai_ml" and args.preserve_through == 0:
            preserve = 3
        upgrade_category(
            cat,
            preserve_through=preserve,
            force_synth=args.force_synth,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
