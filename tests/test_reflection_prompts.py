"""Tests for sentinel.reflection_prompts."""
import pytest
from sentinel import reflection_prompts as rp


def test_get_prompt():
    prompt = rp.get_prompt()
    assert prompt.endswith("?")


def test_get_prompt_by_category():
    prompt = rp.get_prompt("morning")
    assert prompt in rp.PROMPTS["morning"]


def test_get_prompt_invalid_category():
    prompt = rp.get_prompt("invalid_category_xyz")
    # Should return a random prompt from any category
    assert prompt.endswith("?")


def test_get_categories():
    cats = rp.get_categories()
    assert "morning" in cats
    assert "evening" in cats
    assert "gratitude" in cats


def test_daily_prompt_consistent():
    p1 = rp.get_daily_prompt("morning")
    p2 = rp.get_daily_prompt("morning")
    assert p1 == p2


def test_daily_prompt_different_categories():
    # Different categories should generally give different prompts
    m = rp.get_daily_prompt("morning")
    assert m.endswith("?")


def test_prompts_for_category():
    prompts = rp.get_prompts_for_category("morning")
    assert len(prompts) >= 5


def test_total_prompts():
    total = rp.total_prompts()
    assert total >= 80  # We have 10+ per category, 10+ categories


def test_prompts_for_time_of_day():
    prompts = rp.prompts_for_time_of_day()
    assert isinstance(prompts, list)
    assert len(prompts) > 0


def test_all_prompts_end_with_question():
    for cat, prompts in rp.PROMPTS.items():
        for p in prompts:
            assert p.endswith("?"), f"Prompt in {cat} doesn't end with ?: {p}"


def test_has_growth_category():
    assert "growth" in rp.PROMPTS
    assert len(rp.PROMPTS["growth"]) >= 5
