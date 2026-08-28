"""Tests for datagen.bank_ingest against the real local task bank
(artifacts/datagen_task_bank/by_category/).

The bank was pruned to only the categories matching the
SFT_Synthetic_Data_Domain_UseCases Excel's domains — cybersecurity_ops
(nested? no: flat + forged/) and finance_ca_practice (nested by_topic/).
The third known sub-layout (flat + sibling .md, e.g. what "ai_ml" used to
be) is covered with a synthetic fixture instead of real data, since no
pruned-in category uses it any more.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from datagen import bank_ingest

pytestmark = pytest.mark.skipif(
    not bank_ingest.BANK_ROOT.is_dir(),
    reason="artifacts/datagen_task_bank not present in this checkout",
)


def test_list_categories_matches_pruned_bank():
    cats = bank_ingest.list_categories()
    assert set(cats) == {"finance_ca_practice", "cybersecurity_ops"}


def test_pruned_categories_are_gone():
    for cat in (
        "ai_ml", "cms_content", "collaborative_realtime", "devops_infra",
        "distributed_systems", "ecommerce", "finance_productivity", "games",
        "generic_fullstack", "iot_automation", "monitoring_ops",
        "security_privacy", "storage_files",
    ):
        assert bank_ingest.load_category(cat) == []


def test_nested_by_topic_layout_finance_ca_practice():
    specs = bank_ingest.load_category("finance_ca_practice")
    assert len(specs) == 120
    for s in specs:
        assert s.title
        assert s.category == "finance_ca_practice"
        assert s.subcategory  # topic folder name
        assert s.platform_prompt.strip(), f"{s.id} missing platform_prompt"

    gst = [s for s in specs if "gst" in s.subcategory.lower()]
    assert len(gst) == 10


def test_flat_forged_layout_cybersecurity_ops():
    specs = bank_ingest.load_category("cybersecurity_ops")
    assert len(specs) == 6
    for s in specs:
        assert s.title
        assert s.platform_prompt.strip(), f"{s.id} missing platform_prompt (forged/ layout)"
        assert s.dimensions_hint.get("business_domain") == "cybersecurity"


def test_flat_sibling_md_layout_synthetic_fixture(tmp_path: Path):
    """No pruned-in category uses the flat + sibling .md layout any more
    (that was "ai_ml", now deleted) — cover it with a synthetic fixture."""
    root = tmp_path / "by_category"
    cat_dir = root / "widgets"
    cat_dir.mkdir(parents=True)
    (cat_dir / "01_widget-maker.json").write_text(
        json.dumps({"index": "01", "id": "widget_01", "title": "Widget Maker", "seed": "Build widgets."}),
        encoding="utf-8",
    )
    (cat_dir / "01_widget-maker.md").write_text("# Widget Maker PRD\n\nFull forged prompt.", encoding="utf-8")

    specs = bank_ingest.load_category("widgets", root=root)
    assert len(specs) == 1
    assert specs[0].title == "Widget Maker"
    assert specs[0].platform_prompt.strip() == "# Widget Maker PRD\n\nFull forged prompt."


def test_load_bank_assigns_stable_global_index_and_unique_ids():
    specs = bank_ingest.load_bank(["finance_ca_practice", "cybersecurity_ops"])
    assert [s.global_index for s in specs] == list(range(1, len(specs) + 1))
    assert len(set(s.id for s in specs)) == len(specs)
    assert len(specs) == 126


def test_missing_category_returns_empty_list():
    assert bank_ingest.load_category("does_not_exist_category") == []
