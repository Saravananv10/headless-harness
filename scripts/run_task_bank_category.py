#!/usr/bin/env python3
"""Run all task-bank seeds for one forge category via main.py (auto-approves tools).

Example:
  python scripts/run_task_bank_category.py games
  python scripts/run_task_bank_category.py games --limit 2
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BANK = ROOT / "artifacts" / "datagen_task_bank" / "by_category"

from datagen_dims.budgets import budget_for  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("category", help="e.g. games")
    p.add_argument("--limit", type=int, default=0, help="Only first N tasks (0=all)")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands only",
    )
    args = p.parse_args()
    cat_dir = BANK / args.category
    if not cat_dir.is_dir():
        print(f"Missing: {cat_dir}", file=sys.stderr)
        return 1
    tasks = sorted(cat_dir.glob("*.json"))
    if args.limit > 0:
        tasks = tasks[: args.limit]
    if not tasks:
        print("No tasks", file=sys.stderr)
        return 1

    print(f"Category={args.category}  tasks={len(tasks)}")
    print("Harness auto-approves tool permissions (StatelessAutoApprover).")
    print("Ensure Chakra gRPC is running on :50051\n")

    failed = []
    for path in tasks:
        data = json.loads(path.read_text(encoding="utf-8"))
        seed = data["seed"]
        workdir = data.get("workdir") or f"task_{args.category}_{data['index']:02d}"
        hint = data.get("dimensions_hint") or {}
        cx = hint.get("complexity") or "medium"
        bud = budget_for(cx)
        env = os.environ.copy()
        env["HARNESS_WALL_CLOCK_TIMEOUT_MINUTES"] = str(bud["wall_clock_timeout_minutes"])
        env["HARNESS_PROGRESS_TIMEOUT_MINUTES"] = str(bud["progress_timeout_minutes"])
        env["HARNESS_MAX_REPAIR_ITERATIONS"] = str(bud["max_repair_iterations"])
        cmd = [
            sys.executable,
            str(ROOT / "main.py"),
            seed,
            "--forge-prompt",
            "--forge-category",
            args.category,
            "--workdir",
            workdir,
            "--max-repair-iterations",
            str(bud["max_repair_iterations"]),
            "--max-turns",
            str(bud["max_turns"]),
            "--max-decisions",
            str(bud["max_decisions"]),
        ]
        print("=" * 72)
        print(f"[{data['index']}/10] {data['title']}  complexity={cx}")
        print(
            f"  budget: wall={bud['wall_clock_timeout_minutes']}m "
            f"turns={bud['max_turns']} repairs={bud['max_repair_iterations']}"
        )
        print(" ".join(cmd[:3]), "…")
        if args.dry_run:
            continue
        proc = subprocess.run(cmd, cwd=str(ROOT), env=env)
        if proc.returncode != 0:
            failed.append(data["id"])
            print(f"FAILED {data['id']} exit={proc.returncode}")
        else:
            print(f"OK {data['id']}")

    if failed:
        print("Failed:", ", ".join(failed))
        return 1
    print("All tasks finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
