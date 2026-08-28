"""Shared helpers for Phase 3 contract validation scripts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOURNAL = ROOT / "docs" / "development_journal.md"

FORBIDDEN_INTERFACE_TERMS = (
    "grpc",
    "protobuf",
    "chakra",
    "http",
    "websocket",
    "openclaude",
)


def append_journal(section: str) -> None:
    if not JOURNAL.exists():
        JOURNAL.write_text(
            "# Development Journal\n\n"
            "Chronological engineering record for the headless harness project.\n\n",
            encoding="utf-8",
        )
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(section)
        if not section.endswith("\n"):
            f.write("\n")


def journal_entry(
    milestone: str,
    objective: str,
    design_decisions: list[str],
    implementation: list[str],
    validation: str,
    observations: list[str],
    conclusions: list[str],
    next_steps: list[str],
) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    lines = [
        f"## {milestone}",
        f"- **Timestamp:** {ts}",
        f"- **Objective:** {objective}",
        "- **Design Decisions:**",
        *[f"  - {item}" for item in design_decisions],
        "- **Implementation Progress:**",
        *[f"  - {item}" for item in implementation],
        f"- **Validation Notes:** {validation}",
        "- **Observations:**",
        *[f"  - {item}" for item in observations],
        "- **Conclusions:**",
        *[f"  - {item}" for item in conclusions],
        "- **Next Steps:**",
        *[f"  - {item}" for item in next_steps],
        "",
    ]
    append_journal("\n".join(lines))
