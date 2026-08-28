#!/usr/bin/env python3
"""Forge CHAKRA_PASTE_ALL_10_FORGED.md for every category (or one).

  python scripts/forge_all_categories.py
  python scripts/forge_all_categories.py --only games --force
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "artifacts" / "datagen_task_bank" / "by_category"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--only", default=None, help="Single category")
    p.add_argument("--force", action="store_true")
    p.add_argument("--skip-existing", action="store_true", default=True)
    args = p.parse_args()

    cats = [args.only] if args.only else sorted(
        d.name for d in BANK.iterdir() if d.is_dir()
    )
    # Prefer games first when forging all
    if not args.only and "games" in cats:
        cats = ["games"] + [c for c in cats if c != "games"]

    rc = 0
    for cat in cats:
        cmd = [sys.executable, str(ROOT / "scripts" / "forge_category_batch.py"), cat]
        if args.force:
            cmd.append("--force")
        elif args.skip_existing:
            cmd.append("--skip-existing")
        print("\n" + "=" * 72, flush=True)
        print(f"FORGE CATEGORY: {cat}", flush=True)
        print("=" * 72, flush=True)
        proc = subprocess.run(cmd, cwd=str(ROOT))
        if proc.returncode not in (0, 2):
            rc = proc.returncode
            print(f"FAILED {cat} exit={proc.returncode}", flush=True)
        else:
            # assemble for consistency
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "assemble_forged_paste.py"), cat],
                cwd=str(ROOT),
            )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
