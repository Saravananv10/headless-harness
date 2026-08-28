"""Tests for prompt_forge mid-layer (no live LLM required)."""

from __future__ import annotations

from prompt_forge.categories import Category
from prompt_forge.classifier import classify_heuristic
from prompt_forge.composer import merge_objective_with_addon, wrap_platform_addon
from prompt_forge.generator import generate_platform_prompt
from prompt_forge.templates import list_templates, load_template
from controller.llm import DeterministicLLMClient


def test_all_category_templates_exist_and_are_substantial():
    templates = set(list_templates())
    for cat in Category:
        assert cat.value in templates, f"missing template for {cat.value}"
        body = load_template(cat)
        assert len(body) > 800, f"template too short: {cat.value}"


def test_classify_iot_seed():
    result = classify_heuristic(
        "Create a smart home automation dashboard with device schedules and sensor history"
    )
    assert result.category == Category.IOT_AUTOMATION


def test_classify_ecommerce_seed():
    result = classify_heuristic(
        "E-commerce inventory and order management with suppliers and low-stock alerts"
    )
    assert result.category == Category.ECOMMERCE


def test_merge_addon_keeps_seed():
    merged = merge_objective_with_addon(
        seed_or_objective="seed brief",
        platform_prompt="# Unique PRD\n\n" + ("detail\n" * 80),
    )
    assert "PLATFORM ADD-ON" in wrap_platform_addon("x")
    assert "PLATFORM ADD-ON" in merged
    assert "ORIGIN SEED" in merged
    assert "seed brief" in merged


def test_generate_platform_prompt_with_deterministic_llm():
    long_prd = "# Project Request\n\n" + (
        "Build a unique bike-shop inventory console with suppliers, "
        "purchase orders, and clerk vs manager roles.\n" * 40
    )
    llm = DeterministicLLMClient([long_prd])
    generated = generate_platform_prompt(
        "Inventory system for a local bike shop",
        llm,
        category="ecommerce",
        temperature=0.0,
    )
    assert generated.category == Category.ECOMMERCE
    assert "bike-shop" in generated.platform_prompt.lower() or "Inventory" in generated.platform_prompt
    assert len(generated.platform_prompt) > 600
