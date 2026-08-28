"""Shared helpers for Phase 4 adapter validation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOURNAL = ROOT / "docs" / "development_journal.md"

FORBIDDEN_OUTSIDE_ADAPTER = (
    "from client.chakra_client",
    "from client import ChakraClient",
    "import client.chakra_client",
    "ChakraClient(",
)


def append_journal(section: str) -> None:
    if not JOURNAL.exists():
        JOURNAL.write_text(
            "# Development Journal\n\n"
            "Chronological engineering record for the headless harness project.\n\n",
            encoding="utf-8",
        )
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(section if section.endswith("\n") else section + "\n")


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
    append_journal("\n".join(lines))


def scan_consumer_layer_leaks() -> list[str]:
    """Ensure higher-layer packages do not import the low-level Chakra client."""
    violations: list[str] = []
    scan_roots = [
        ROOT / "interface" / "controller",
        ROOT / "interface" / "conversation",
        ROOT / "interface" / "harness.py",
    ]
    for root in scan_roots:
        if root.is_file():
            paths = [root]
        elif root.is_dir():
            paths = list(root.rglob("*.py"))
        else:
            continue
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for token in FORBIDDEN_OUTSIDE_ADAPTER:
                if token in text:
                    violations.append(f"{path.relative_to(ROOT)} references `{token}`")
    return violations
