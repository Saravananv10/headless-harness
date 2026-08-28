#!/usr/bin/env python3
"""Assign unique dimension vectors + forge briefs to every task-bank JSON.

Each of the 10 tasks per category gets a distinct mix of:
  language, complexity, value, topology, verification, tools, persona,
  repo_state, session_shape, plus synthetic axes (ui_surface, persistence,
  testing_depth, novelty_hook, delivery).

Category index offsets the cycle so games/01 ≠ ecommerce/01.
Also regenerates short CHAKRA_PASTE_ALL_10.md files.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BANK = ROOT / "artifacts" / "datagen_task_bank" / "by_category"

from datagen_dims.budgets import budget_for  # noqa: E402

# Per-task cycles (length 10). Offset by category so combos differ across cats.
LANG = [
    "python",
    "typescript",
    "javascript",
    "csharp",
    "cpp",
    "rust",
    "go",
    "java",
    "typescript",
    "python",
]
# Category-specific preferred lang palette (overrides generic when present)
LANG_BY_CAT: dict[str, list[str]] = {
    "games": [
        "python",
        "typescript",
        "javascript",
        "csharp",
        "cpp",
        "rust",
        "javascript",
        "typescript",
        "python",
        "go",
    ],
    "ai_ml": [
        "python",
        "python",
        "typescript",
        "python",
        "javascript",
        "python",
        "go",
        "python",
        "rust",
        "python",
    ],
    "ecommerce": [
        "typescript",
        "python",
        "javascript",
        "csharp",
        "java",
        "typescript",
        "go",
        "python",
        "excel_office",
        "typescript",
    ],
    "devops_infra": [
        "python",
        "go",
        "typescript",
        "python",
        "python",
        "rust",
        "javascript",
        "java",
        "go",
        "typescript",
    ],
    "distributed_systems": [
        "go",
        "rust",
        "python",
        "java",
        "csharp",
        "go",
        "typescript",
        "python",
        "rust",
        "javascript",
    ],
}
COMPLEXITY = ["low", "medium", "hard", "low", "hard", "medium", "hard", "medium", "low", "hard"]
VALUE = ["low", "medium", "hard", "medium", "hard", "low", "hard", "medium", "medium", "hard"]
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
    "plan_then_execute",
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
    "single_shot",
    "multi_turn_repair",
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
UI = [
    "cli_tui",
    "html_canvas",
    "react_spa",
    "desktop_window",
    "static_html",
    "api_only",
    "excel_workbook",
    "mobile_web",
    "dashboard_charts",
    "game_loop_window",
]
PERSIST = [
    "json_file",
    "sqlite",
    "memory_only",
    "localstorage",
    "csv_files",
    "sqlite",
    "json_file",
    "postgres_optional",
    "memory_only",
    "sqlite",
]
TEST_DEPTH = [
    "smoke_only",
    "unit_light",
    "unit_plus_smoke",
    "integration_light",
    "smoke_only",
    "unit_light",
    "unit_plus_smoke",
    "browser_smoke",
    "smoke_only",
    "unit_plus_smoke",
]
NOVELTY = [
    "domain twist: niche audience + unusual constraint",
    "must include a live demo mode with sample data",
    "offline-first; no cloud accounts",
    "accessibility-first keyboard UX",
    "deterministic --seed for reproducible runs",
    "export/import round-trip as acceptance",
    "observability: structured logs + simple metrics endpoint",
    "plugin/extension hook (one stub plugin)",
    "multi-theme or multi-difficulty presets",
    "chaos toggle: inject one recoverable failure path",
]
DELIVERY = [
    "single_readme_run",
    "docker_compose_optional",
    "one_command_dev_server",
    "cli_entry_plus_ui",
    "notebook_plus_script",
    "static_build_preview",
    "worker_plus_api",
    "monorepo_client_server",
    "library_plus_demo_app",
    "one_command_dev_server",
]

LANG_LABEL = {
    "python": "Python 3.10+",
    "typescript": "TypeScript (Node or Vite)",
    "javascript": "JavaScript (Node or browser)",
    "csharp": "C# (.NET)",
    "cpp": "C++17",
    "rust": "Rust",
    "go": "Go",
    "java": "Java 17+",
    "excel_office": "Excel / Office scripts or openpyxl",
    }


def _pick(seq: list, i: int, offset: int = 0):
    return seq[(i + offset) % len(seq)]


def diversify_task(task: dict, cat: str, cat_idx: int, i: int) -> dict:
    """i is 0-based task index."""
    off = cat_idx * 2 + 1
    langs = LANG_BY_CAT.get(cat, LANG)
    hint = dict(task.get("dimensions_hint") or {})
    lang = _pick(langs, i, 0)
    cx = _pick(COMPLEXITY, i, off)
    hint.update(
        {
            "language_runtime": lang,
            "complexity": cx,
            "value": _pick(VALUE, i, off),
            "agent_topology": _pick(TOPOLOGY, i, off),
            "verification_mode": _pick(VERIFY, i, off),
            "session_shape": _pick(SESSION, i, off),
            "repo_state": _pick(REPO, i, off),
            "tool_profile": _pick(TOOLS, i, off),
            "user_persona": _pick(PERSONA, i, off),
            "ui_surface": _pick(UI, i, off),
            "persistence": _pick(PERSIST, i, off),
            "testing_depth": _pick(TEST_DEPTH, i, off),
            "novelty_hook": _pick(NOVELTY, i, off),
            "delivery": _pick(DELIVERY, i, off),
            "modality": "text_code",
        }
    )
    if lang == "excel_office":
        hint["modality"] = "tabular_excel"
        hint["ui_surface"] = "excel_workbook"
    if cat == "games":
        # Keep variety but stay playable-game shaped
        game_ui = [
            "game_loop_window",
            "html_canvas",
            "react_spa",
            "desktop_window",
            "html_canvas",
            "game_loop_window",
            "react_spa",
            "html_canvas",
            "desktop_window",
            "static_html",
        ]
        game_persist = [
            "json_file",
            "localstorage",
            "sqlite",
            "memory_only",
            "json_file",
            "sqlite",
            "localstorage",
            "memory_only",
            "json_file",
            "sqlite",
        ]
        hint["ui_surface"] = game_ui[i % 10]
        hint["persistence"] = game_persist[i % 10]
        hint["modality"] = "text_code"
        if hint["language_runtime"] == "excel_office":
            hint["language_runtime"] = "typescript"

    bud = budget_for(cx)
    label = LANG_LABEL.get(lang, lang)
    lock = (
        f"[DIMENSION LOCK — mandatory for this synthetic run]\n"
        f"- language_runtime: {lang} ({label})\n"
        f"- complexity: {cx} → {bud['forge_scope']}\n"
        f"- value: {hint['value']}\n"
        f"- ui_surface: {hint['ui_surface']}\n"
        f"- persistence: {hint['persistence']}\n"
        f"- verification_mode: {hint['verification_mode']}\n"
        f"- testing_depth: {hint['testing_depth']}\n"
        f"- tool_profile: {hint['tool_profile']}\n"
        f"- user_persona: {hint['user_persona']}\n"
        f"- agent_topology: {hint['agent_topology']}\n"
        f"- session_shape: {hint['session_shape']}\n"
        f"- repo_state: {hint['repo_state']}\n"
        f"- delivery: {hint['delivery']}\n"
        f"- novelty: {hint['novelty_hook']}\n"
        f"- time_budget_minutes: {bud['wall_clock_timeout_minutes']}\n"
        f"Do NOT switch stacks. Honor language + UI surface + persistence exactly.\n"
    )
    seed = (task.get("seed") or "").strip()
    # Strip prior lock if re-run
    if seed.startswith("[DIMENSION LOCK"):
        parts = seed.split("\n\n", 1)
        seed = parts[1].strip() if len(parts) > 1 else seed

    task["dimensions_hint"] = hint
    task["forge_brief"] = f"{lock}\nUSER SEED:\n{seed}"
    task["seed"] = seed  # keep clean seed for stats
    return task


def diversity_hint_text(hint: dict) -> str:
    return (
        "HARD CONSTRAINTS for uniqueness (must appear in the PRD):\n"
        f"- Stack/language: {hint.get('language_runtime')}\n"
        f"- UI surface: {hint.get('ui_surface')}\n"
        f"- Persistence: {hint.get('persistence')}\n"
        f"- Complexity band: {hint.get('complexity')} "
        f"({budget_for(hint.get('complexity')).get('forge_scope')})\n"
        f"- Verification: {hint.get('verification_mode')}; "
        f"tests: {hint.get('testing_depth')}\n"
        f"- Persona voice: {hint.get('user_persona')}\n"
        f"- Novelty: {hint.get('novelty_hook')}\n"
        f"- Delivery: {hint.get('delivery')}\n"
        "Invent a unique product name and niche; do not reuse generic tutorial apps."
    )


def main() -> None:
    # Late import: paste helpers live beside this script
    sys.path.insert(0, str(ROOT / "scripts"))
    import gen_category_paste_batches as pastes  # type: ignore

    cats = sorted(p.name for p in BANK.iterdir() if p.is_dir())
    for ci, cat in enumerate(cats):
        tasks = []
        for jp in sorted((BANK / cat).glob("*.json")):
            t = json.loads(jp.read_text(encoding="utf-8"))
            tasks.append((jp, t))
        tasks.sort(key=lambda x: int(x[1].get("index", 0)))
        updated = []
        for i, (jp, t) in enumerate(tasks[:10]):
            t = diversify_task(t, cat, ci, i)
            t["diversity_hint"] = diversity_hint_text(t["dimensions_hint"])
            jp.write_text(json.dumps(t, indent=2) + "\n", encoding="utf-8")
            updated.append(t)
        if len(updated) >= 10:
            pastes.write_paste(cat, updated)
            pastes.write_howto(cat)
        print(f"{cat}: diversified {len(updated)} tasks")
    print("Done. Next: python scripts/forge_category_batch.py <category>")


if __name__ == "__main__":
    main()
