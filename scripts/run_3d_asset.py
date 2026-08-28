#!/usr/bin/env python3
"""Run a procedural 3D asset generation task with a detailed, robustness-
focused objective (see scripts/prompt_templates.py), through the same
ConversationRunner engine as scripts/run_autonomous.py.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from scripts.prompt_templates import build_3d_asset_objective

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a procedural 3D asset via a detailed LLM-script objective"
    )
    parser.add_argument("description", help="What to build, e.g. 'a low-poly pine tree'")
    parser.add_argument(
        "--format",
        action="append",
        dest="formats",
        choices=["glb", "obj", "gltf", "stl", "ply"],
        help="Export format (repeatable). Default: glb",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workdir", default="procedural_3d_asset")
    parser.add_argument("--max-turns", type=int, default=25)
    parser.add_argument("--max-decisions", type=int, default=30)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    objective = build_3d_asset_objective(
        args.description,
        formats=args.formats or ["glb"],
        seed=args.seed,
    )

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "run_autonomous.py"),
        objective,
        "--workdir", args.workdir,
        "--max-turns", str(args.max_turns),
        "--max-decisions", str(args.max_decisions),
    ]
    if args.run_id:
        cmd += ["--run-id", args.run_id]

    return subprocess.run(cmd, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
