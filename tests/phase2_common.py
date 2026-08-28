"""Shared helpers for Phase 2 API discovery scripts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LOG_ROOT = ROOT / "logs"
PHASE2_LOG_DIR = LOG_ROOT / "phase2"
EXECUTION_LOG = LOG_ROOT / "phase2_execution_log.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_phase2_dirs() -> None:
    PHASE2_LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)


def write_json_log(name: str, payload: dict[str, Any]) -> Path:
    ensure_phase2_dirs()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = PHASE2_LOG_DIR / f"{name}_{ts}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def append_execution_log(
    milestone: str,
    objective: str,
    commands: list[str],
    observations: list[str],
    validation: str,
    conclusions: list[str],
    next_actions: list[str],
    scripts_written: list[str] | None = None,
    unexpected_behavior: list[str] | None = None,
) -> None:
    ensure_phase2_dirs()
    if not EXECUTION_LOG.exists():
        EXECUTION_LOG.write_text(
            "# Phase 2 Execution Log\n\n"
            "Chronological engineering log for Harness API Discovery.\n\n",
            encoding="utf-8",
        )
    lines = [
        f"## {milestone}",
        f"- **Timestamp:** {utc_now()}",
        f"- **Objective:** {objective}",
        "- **Commands Executed:**",
    ]
    lines.extend([f"  - `{cmd}`" for cmd in commands])
    lines.append("- **Scripts Written:**")
    for script in scripts_written or []:
        lines.append(f"  - `{script}`")
    lines.append("- **Observations:**")
    lines.extend([f"  - {item}" for item in observations])
    lines.append(f"- **Validation Results:** {validation}")
    lines.append("- **Unexpected Behaviour:**")
    for item in (unexpected_behavior or ["None"]):
        lines.append(f"  - {item}")
    lines.append("- **Conclusions:**")
    lines.extend([f"  - {item}" for item in conclusions])
    lines.append("- **Next Actions:**")
    lines.extend([f"  - {item}" for item in next_actions])
    lines.append("")
    with EXECUTION_LOG.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
