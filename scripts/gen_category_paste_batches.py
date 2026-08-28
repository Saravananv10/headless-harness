#!/usr/bin/env python3
"""Generate CHAKRA_PASTE_ALL_10.md + HOW_TO for every datagen_task_bank category.

Also diversifies dimensions_hint across the 10 tasks and records seeds into
prompt_stats so the website shows planned + completed work.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BANK = ROOT / "artifacts" / "datagen_task_bank" / "by_category"

# Cycle these so each category's 10 tasks span types/dims (harness challenge).
TOPOLOGY = [
    "single_agent",
    "subagent_spawns",
    "plan_then_execute",
    "tool_swarm",
    "single_agent",
    "subagent_spawns",
    "plan_then_execute",
    "tool_swarm",
    "single_agent",
    "subagent_spawns",
]
VERIFY = [
    "static_pass",
    "unit_tests",
    "runtime_pass",
    "browser_smoke",
    "visual_diff",
    "unit_tests",
    "runtime_pass",
    "browser_smoke",
    "static_pass",
    "runtime_pass",
]
SESSION = [
    "single_shot",
    "multi_turn_repair",
    "resume_mid_task",
    "multi_turn_repair",
    "approval_gated",
    "multi_turn_repair",
    "single_shot",
    "resume_mid_task",
    "multi_turn_repair",
    "approval_gated",
]
REPO = [
    "empty_scratch",
    "empty_scratch",
    "partial_scaffold",
    "legacy_messy",
    "empty_scratch",
    "partial_scaffold",
    "empty_scratch",
    "legacy_messy",
    "empty_scratch",
    "partial_scaffold",
]
TOOLS = [
    "edit_heavy",
    "shell_heavy",
    "browser_heavy",
    "mixed",
    "edit_heavy",
    "shell_heavy",
    "browser_heavy",
    "mixed",
    "edit_heavy",
    "mixed",
]
PERSONA = [
    "solo_dev",
    "staff_eng",
    "pm_non_technical",
    "enterprise_buyer",
    "solo_dev",
    "staff_eng",
    "pm_non_technical",
    "enterprise_buyer",
    "solo_dev",
    "staff_eng",
]
COMPLEXITY = ["low", "medium", "hard", "medium", "hard", "low", "hard", "medium", "hard", "medium"]
VALUE = ["low", "medium", "hard", "hard", "medium", "low", "hard", "medium", "hard", "medium"]

CATEGORY_BLURB = {
    "games": "browser/desktop games — playable UI required",
    "ai_ml": "AI/ML apps — trainable or inferable demo with clear outputs",
    "cms_content": "CMS/content — editable content flows in browser",
    "collaborative_realtime": "realtime collab — multi-user or live-updating UI",
    "devops_infra": "DevOps/infra — scripts, pipelines, or local stack demos",
    "distributed_systems": "distributed systems — multi-process/service demo",
    "ecommerce": "ecommerce — catalog/cart/checkout browser flows",
    "finance_productivity": "finance/productivity — dashboards or workflow apps",
    "generic_fullstack": "generic fullstack — API + UI, browser-checkable",
    "iot_automation": "IoT/automation — device/sim + control UI or CLI",
    "monitoring_ops": "monitoring/ops — metrics dashboards or alert demos",
    "security_privacy": "security/privacy — auth, crypto, or privacy-preserving demos",
    "storage_files": "storage/files — upload, sync, or file-manager demos",
}


def _load_tasks(cat: str) -> list[dict]:
    d = BANK / cat
    rows = []
    for p in sorted(d.glob("*.json")):
        rows.append(json.loads(p.read_text(encoding="utf-8")))
    rows.sort(key=lambda r: int(r.get("index", 0)))
    return rows


def _diversify_dims(task: dict, i: int) -> dict:
    hint = dict(task.get("dimensions_hint") or {})
    hint["agent_topology"] = TOPOLOGY[i % 10]
    hint["verification_mode"] = VERIFY[i % 10]
    hint["session_shape"] = SESSION[i % 10]
    hint["repo_state"] = REPO[i % 10]
    hint["tool_profile"] = TOOLS[i % 10]
    hint["user_persona"] = PERSONA[i % 10]
    hint["complexity"] = COMPLEXITY[i % 10]
    hint["value"] = VALUE[i % 10]
    # keep language/artifact/task_family/business_domain from generator
    task["dimensions_hint"] = hint
    return task


def _dims_line(hint: dict) -> str:
    keys = [
        "complexity",
        "value",
        "language_runtime",
        "ui_surface",
        "persistence",
        "artifact_type",
        "task_family",
        "agent_topology",
        "verification_mode",
        "session_shape",
        "tool_profile",
        "user_persona",
        "repo_state",
        "testing_depth",
        "delivery",
        "novelty_hook",
    ]
    parts = [f"{k}={hint.get(k, '?')}" for k in keys]
    return ", ".join(parts)


def write_paste(cat: str, tasks: list[dict]) -> Path:
    out = BANK / cat / "CHAKRA_PASTE_ALL_10.md"
    blurb = CATEGORY_BLURB.get(cat, cat)
    lines = [
        f"# Category batch: {cat} (all 10) — paste into Chakra",
        "",
        "You are running a **datagen category marathon** for harness evaluation.",
        f"Category focus: **{blurb}**.",
        "",
        "## Non-negotiable rules",
        "",
        "1. Complete the **10 tasks below in order** (01 → 10). Do not skip.",
        "2. Each task is a **separate app/project** under its own folder "
        f"`task_{cat}_NN/` (use the workdir listed).",
        "3. For each task: implement until **demoable** "
        "(browser open, CLI works, or game playable). Install deps, start servers, fix bugs.",
        "4. **Do not ask for approval** between tasks — continue automatically.",
        "5. After each task: short note `DONE task_N: <title> — path + how to run`.",
        "6. **Vary implementation** across tasks — different stacks/patterns matching "
        "the dimension targets. Do not clone the same scaffold 10 times.",
        "7. Challenge the harness: use tools, tests, browser checks, repairs when dims say so.",
        "8. Prefer completing a solid MVP over endless polish; then move to the next task.",
        "",
        "## Stats / ledger",
        "",
        "Keep the stats site running once (`python -m prompt_stats serve`).",
        "Open http://127.0.0.1:8787/ — hard-refresh the page to pull latest Chakra",
        "sessions into the dashboard (no separate `collect` command).",
        "",
        "Tag every DONE note with category `" + cat + "` so logs are easy to grep.",
        "",
        "---",
        "",
    ]
    for t in tasks:
        i = int(t["index"])
        hint = t.get("dimensions_hint") or {}
        lines += [
            f"## Task {i:02d} — {t['title']}",
            f"**workdir:** `{t.get('workdir', f'task_{cat}_{i:02d}')}`",
            f"**id:** `{t['id']}`",
            f"**source:** `{t.get('source', 'original')}`",
            f"**dimensions:** {_dims_line(hint)}",
            "",
            "### User request",
            "",
            t["seed"].strip(),
            "",
            "### Done criteria for this task",
            f"- App lives under `{t.get('workdir')}/`",
            "- Runnable demo (browser / CLI / playable) without further questions",
            f"- Reflect dimensions above (esp. complexity={hint.get('complexity')}, "
            f"verification={hint.get('verification_mode')}, tools={hint.get('tool_profile')})",
            "",
            "When done, print `DONE task_" + f"{i}" + f": {t['title']}` and start the next task immediately.",
            "",
            "---",
            "",
        ]
    lines += [
        f"## After all 10 ({cat})",
        "",
        f"Print a final summary table: task id | path | stack | complexity | how to run.",
        "Then stop.",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_howto(cat: str) -> Path:
    out = BANK / cat / "HOW_TO_RUN_ALL_10.md"
    paste = f"artifacts/datagen_task_bank/by_category/{cat}/CHAKRA_PASTE_ALL_10.md"
    body = f"""# Run all 10 `{cat}` tasks in one Chakra session

## 1. Start Chakra

```powershell
cd C:\\Users\\anshg\\.cursor\\headless_harness_datagen\\harness\\chakra
chakra --dangerously-skip-permissions
```

Optional model:

```powershell
chakra --model kimi3 --dangerously-skip-permissions
```

## 2. Paste the batch file

Open and paste the **entire** contents of:

`{paste}`

into the Chakra prompt. Press Enter once.

Chakra will work through tasks 01–10 sequentially until each is demoable.

## 3. Stats website (auto on hard refresh)

Start once (can stay running while Chakra works):

```powershell
cd C:\\Users\\anshg\\.cursor\\headless_harness_datagen
python -m prompt_stats serve
```

Open **http://127.0.0.1:8787/**. Hard-refresh the browser whenever you want latest
session time/tokens — the page runs a full collect on load. No separate `collect` step.

## 4. One-at-a-time (pipeline / forge)

```powershell
cd C:\\Users\\anshg\\.cursor\\headless_harness_datagen
python scripts/run_task_bank_category.py {cat}
```

## 5. Dimension coverage

Each of the 10 tasks targets a different mix of:

- complexity / value (low | medium | hard)
- agent_topology, verification_mode, session_shape
- tool_profile, user_persona, repo_state
- language_runtime, artifact_type, task_family

So the harness sees **variety**, not 10 copies of the same shape.
"""
    out.write_text(body, encoding="utf-8")
    return out


def record_stats(tasks: list[dict], cat: str) -> int:
    try:
        from prompt_stats.hooks import record_raw_prompt
    except Exception:
        return 0
    n = 0
    for t in tasks:
        record_raw_prompt(
            prompt=t["seed"],
            source="task_bank",
            title=t.get("title"),
            category=cat,
            project=t.get("workdir"),
            extra={
                "task_id": t["id"],
                "workdir": t.get("workdir"),
                "dimensions_hint": t.get("dimensions_hint"),
                "batch": f"{cat}_all_10",
                "path_hint": f"datagen_task_bank/{cat}/{t['id']}",
            },
        )
        n += 1
    return n


def main() -> None:
    cats = sorted(p.name for p in BANK.iterdir() if p.is_dir())
    total = 0
    recorded = 0
    for cat in cats:
        tasks = _load_tasks(cat)
        if len(tasks) < 10:
            print(f"SKIP {cat}: only {len(tasks)} tasks")
            continue
        # diversify + persist JSON
        updated = []
        for i, t in enumerate(tasks[:10]):
            t = _diversify_dims(t, i)
            jp = BANK / cat / f"{t['index']:02d}_{_slug_from_id(t['id'])}.json"
            # find real json path
            matches = list((BANK / cat).glob(f"{t['index']:02d}_*.json"))
            if matches:
                matches[0].write_text(json.dumps(t, indent=2) + "\n", encoding="utf-8")
            updated.append(t)
        write_paste(cat, updated)
        write_howto(cat)
        recorded += record_stats(updated, cat)
        total += 1
        print(f"OK {cat}: paste + howto ({len(updated)} tasks)")

    master = BANK.parent / "RUN_CATEGORY_BATCHES.md"
    master.write_text(
        """# Run any category marathon (10 tasks)

Each category folder has:

- `CHAKRA_PASTE_ALL_10.md` — paste into one Chakra session
- `HOW_TO_RUN_ALL_10.md` — steps + stats refresh

## Games (example)

```powershell
cd C:\\Users\\anshg\\.cursor\\headless_harness_datagen\\harness\\chakra
chakra --dangerously-skip-permissions
```

Paste: `artifacts/datagen_task_bank/by_category/games/CHAKRA_PASTE_ALL_10.md`

Stats (once, leave running):

```powershell
cd C:\\Users\\anshg\\.cursor\\headless_harness_datagen
python -m prompt_stats serve
```

→ http://127.0.0.1:8787/ — hard-refresh the page to update (no `collect` needed)

## All categories

"""
        + "\n".join(f"- `{c}` → `by_category/{c}/CHAKRA_PASTE_ALL_10.md`" for c in cats)
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote pastes for {total} categories; recorded {recorded} seeds into prompt_stats")
    print(f"Master guide: {master}")


def _slug_from_id(tid: str) -> str:
    # games_01_breakout-clone-with-levels → breakout-clone-with-levels
    parts = tid.split("_", 2)
    return parts[2] if len(parts) >= 3 else tid


if __name__ == "__main__":
    main()
