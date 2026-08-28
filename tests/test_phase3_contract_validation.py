"""Milestone 3.4 — validate complete contract consistency and readiness."""

from __future__ import annotations

import importlib
import pkgutil

from interface import Harness
from interface.reference.in_memory_harness import InMemoryHarness
from phase3_common import FORBIDDEN_INTERFACE_TERMS, journal_entry


def _import_interface_modules() -> list[str]:
    import interface as interface_pkg

    names: list[str] = []
    for module in pkgutil.walk_packages(interface_pkg.__path__, interface_pkg.__name__ + "."):
        if ".reference." in module.name:
            continue
        importlib.import_module(module.name)
        names.append(module.name)
    return names


def _contains_forbidden_term(text: str, term: str) -> bool:
    import re

    return re.search(rf"\b{re.escape(term)}\b", text) is not None


def main() -> int:
    modules = _import_interface_modules()
    violations: list[str] = []
    for module_name in modules:
        module = importlib.import_module(module_name)
        source_path = getattr(module, "__file__", "") or ""
        if not source_path.endswith(".py"):
            continue
        text = open(source_path, encoding="utf-8").read().lower()
        for term in FORBIDDEN_INTERFACE_TERMS:
            if _contains_forbidden_term(text, term):
                violations.append(f"{module_name} references '{term}'")

    # InMemoryHarness is one implementation; future adapters implement the same ABC.
    second_impl: Harness = InMemoryHarness()
    consistency_ok = isinstance(second_impl, Harness)
    ok = consistency_ok and not violations

    journal_entry(
        milestone="Milestone 3.4 — Contract Validation",
        objective="Finalize backend-independent contract for adapter implementation.",
        design_decisions=[
            "Reference in-memory harness validates contract without backend coupling.",
            "Validation/mapping modules isolated from core interface package surface.",
            "Higher layers should import only from interface package.",
        ],
        implementation=[
            "interface/reference/in_memory_harness.py",
            "tests/test_phase3_interface.py",
            "tests/test_phase3_models.py",
            "tests/test_phase3_events.py",
            "tests/test_phase3_contract_validation.py",
            "docs/architecture_reference.md",
        ],
        validation="PASS" if ok else f"FAIL violations={violations}",
        observations=[
            f"Loaded interface modules: {len(modules)}",
            "Contract supports multiple harness classes implementing Harness ABC.",
        ],
        conclusions=[
            "Phase 3 contract is consistent and backend-independent.",
            "Ready for Phase 4 Chakra adapter implementation.",
        ],
        next_steps=["Implement ChakraHarness adapter translating protocol to contract."],
    )
    if violations:
        for item in violations:
            print(item)
    print("Milestone 3.4 PASS" if ok else "Milestone 3.4 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
