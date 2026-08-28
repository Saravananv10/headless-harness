"""Milestone 3.1 — validate harness interface design is backend-independent."""

from __future__ import annotations

import inspect
from pathlib import Path

from interface.harness import Harness, TurnStream
from phase3_common import FORBIDDEN_INTERFACE_TERMS, journal_entry

ROOT = Path(__file__).resolve().parent.parent
INTERFACE_ROOT = ROOT / "interface"


def _contains_forbidden_term(text: str, term: str) -> bool:
    import re

    return re.search(rf"\b{re.escape(term)}\b", text) is not None


def _scan_forbidden_terms() -> list[str]:
    violations: list[str] = []
    for path in INTERFACE_ROOT.rglob("*.py"):
        if "reference" in path.parts or path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8").lower()
        for term in FORBIDDEN_INTERFACE_TERMS:
            if _contains_forbidden_term(text, term):
                violations.append(f"{path.relative_to(ROOT)} contains '{term}'")
    return violations


def main() -> int:
    harness_methods = {
        name
        for name, _ in inspect.getmembers(Harness, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    turn_methods = {
        name
        for name, _ in inspect.getmembers(TurnStream, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    violations = _scan_forbidden_terms()
    ok = not violations and {
        "connect",
        "disconnect",
        "connection_info",
        "capabilities",
        "create_session",
        "resume_session",
        "send_turn",
        "get_session_status",
        "close_session",
    }.issubset(harness_methods) and {"respond", "cancel", "result"}.issubset(turn_methods)

    journal_entry(
        milestone="Milestone 3.1 — Harness Interface Design",
        objective="Define abstract harness operations without backend-specific concepts.",
        design_decisions=[
            "Single Harness ABC with TurnStream for active turns.",
            "Operations expressed as connect/session/send_turn rather than transport calls.",
            "Capabilities advertised explicitly via HarnessCapabilities.",
        ],
        implementation=[
            "interface/harness.py",
            "interface/capabilities.py",
            "interface/exceptions.py",
        ],
        validation="PASS" if ok else f"FAIL violations={violations}",
        observations=[
            f"Harness operations: {sorted(harness_methods)}",
            f"TurnStream operations: {sorted(turn_methods)}",
        ],
        conclusions=[
            "Interface is suitable for multiple adapter implementations.",
            "No backend protocol terms appear in core contract modules.",
        ],
        next_steps=["Define shared request/response/session models (Milestone 3.2)."],
    )
    if violations:
        for v in violations:
            print(v)
        return 1
    print("Milestone 3.1 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
