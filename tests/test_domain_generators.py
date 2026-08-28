"""Tests for datagen.domain_generators routing."""

from __future__ import annotations

from datagen import domain_generators


def test_gst_topic_overrides_to_gst_specific_generator():
    target = domain_generators.resolve_generator("finance_ca_practice", "00_gst_reconciliation")
    assert target == ("pipelines.finance.data_generator", "generate_gst_data")


def test_non_gst_finance_topic_uses_category_default():
    target = domain_generators.resolve_generator("finance_ca_practice", "01_tds_reconciliation")
    assert target == ("pipelines.finance.data_generator", "generate_all")


def test_cybersecurity_category_default():
    target = domain_generators.resolve_generator("cybersecurity_ops", "")
    assert target == ("pipelines.cybersecurity.data_generator", "generate_all")


def test_unknown_category_returns_none():
    assert domain_generators.resolve_generator("ai_ml", "") is None
