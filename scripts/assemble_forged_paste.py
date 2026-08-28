#!/usr/bin/env python3
"""Assemble CHAKRA_PASTE_ALL_10_FORGED.md — thin wrapper around upgrade_category_forges."""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "scripts" / "upgrade_category_forges.py"


def _load():
    spec = importlib.util.spec_from_file_location("upgrade_category_forges", MOD)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("category", default="games", nargs="?")
    args = p.parse_args()
    mod = _load()
    cat_dir = ROOT / "artifacts" / "datagen_task_bank" / "by_category" / args.category
    if not cat_dir.is_dir():
        print(f"Missing {cat_dir}", file=sys.stderr)
        return 1
    tasks = mod.load_tasks(cat_dir)
    for t in tasks:
        mod.ensure_dimensions(t, int(t["index"]))
    mod.assemble(args.category, tasks, cat_dir)
    mod.write_runner(cat_dir, args.category)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
