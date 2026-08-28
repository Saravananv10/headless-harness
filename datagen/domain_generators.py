"""domain_generators.py — prefer a hand-written, domain-accurate data
generator over the generic LLM-schema-inference engine when one already
exists for a bank task's category/topic.

pipelines/finance/data_generator.py and pipelines/cybersecurity/data_generator.py
encode real domain knowledge (actual TDS section codes, MITRE ATT&CK ids,
GSTIN-shaped identifiers, correct trial-balance debit/credit relationships)
that the generic engine can't reproduce. This registry is consulted first;
executor.py falls back to the generic engine (datagen.data_synth) only
when no entry matches.
"""

from __future__ import annotations

CATEGORY_GENERATORS: dict[str, tuple[str, str]] = {
    "finance_ca_practice": ("pipelines.finance.data_generator", "generate_all"),
    "cybersecurity_ops": ("pipelines.cybersecurity.data_generator", "generate_all"),
}

# Topic-level overrides checked first (substring match against the bank
# task's subcategory/topic folder name, e.g. "00_gst_reconciliation").
TOPIC_OVERRIDES: dict[str, tuple[str, str]] = {
    "gst": ("pipelines.finance.data_generator", "generate_gst_data"),
}


def resolve_generator(category: str, subcategory: str) -> tuple[str, str] | None:
    """Return (module_path, function_name) for a hand-written generator, or
    None if the generic schema-inference engine should be used instead."""
    sub = (subcategory or "").lower()
    for key, target in TOPIC_OVERRIDES.items():
        if key in sub:
            return target
    return CATEGORY_GENERATORS.get(category)
