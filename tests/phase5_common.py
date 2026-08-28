"""Shared helpers for Phase 5 validation and journaling."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOURNAL = ROOT / "docs" / "development_journal.md"

FORBIDDEN_IN_ENGINE = FORBIDDEN_IN_CONTROLLER = (
    "from client",
    "import client",
    "from adapter",
    "import adapter",
    "ChakraClient",
    "ChakraHarness",
    "grpc",
    "protobuf",
)


def journal_entry(
    milestone: str,
    design_decisions: list[str],
    implementation: list[str],
    validation: str,
    issues: list[str],
    observations: list[str],
    conclusions: list[str],
    next_steps: list[str],
) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    lines = [
        f"## {milestone}",
        f"- **Timestamp:** {ts}",
        "- **Design Decisions:**",
        *[f"  - {item}" for item in design_decisions],
        "- **Implementation Progress:**",
        *[f"  - {item}" for item in implementation],
        f"- **Validation Results:** {validation}",
        "- **Issues Encountered:**",
        *[f"  - {item}" for item in issues],
        "- **Observations:**",
        *[f"  - {item}" for item in observations],
        "- **Conclusions:**",
        *[f"  - {item}" for item in conclusions],
        "- **Next Steps:**",
        *[f"  - {item}" for item in next_steps],
        "",
    ]
    if not JOURNAL.exists():
        JOURNAL.write_text(
            "# Development Journal\n\n"
            "Chronological engineering record for the headless harness project.\n\n",
            encoding="utf-8",
        )
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def scan_engine_isolation() -> list[str]:
    violations: list[str] = []
    engine_root = ROOT / "engine"
    for path in engine_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for token in FORBIDDEN_IN_ENGINE:
            if token.lower() in text:
                violations.append(f"{path.relative_to(ROOT)} references `{token}`")
    return violations
