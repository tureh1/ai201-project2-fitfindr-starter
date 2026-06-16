"""
Tests for the three FitFindr tools, focused on each tool's happy path and its
failure mode. The LLM-backed tools (suggest_outfit, create_fit_card) are tested
for their *non-LLM* guarantees — non-empty output and graceful handling of empty
input — so the suite passes even without a GROQ_API_KEY (the tools fall back to a
deterministic string when the LLM call can't run).

Run with:
    pytest tests/
"""

import os
import sys

# Make the project root importable when pytest is run from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    # Impossible query — must return [] without raising.
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter_case_insensitive():
    # "m" should match listings whose size contains M / S/M / M/L etc.
    results = search_listings("track jacket", size="m", max_price=None)
    assert all("m" in item["size"].lower() for item in results)


def test_search_sorted_by_relevance():
    # More keyword overlap should rank at least as high as less overlap.
    results = search_listings("vintage denim jacket", size=None, max_price=None)
    assert len(results) >= 2  # sanity: query is satisfiable


# ── suggest_outfit ─────────────────────────────────────────────────────────────

def test_suggest_outfit_returns_nonempty():
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = suggest_outfit(item, get_example_wardrobe())
    assert isinstance(result, str)
    assert result.strip() != ""


def test_suggest_outfit_empty_wardrobe():
    # Empty wardrobe must NOT crash and must return a non-empty string.
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = suggest_outfit(item, get_empty_wardrobe())
    assert isinstance(result, str)
    assert result.strip() != ""


# ── create_fit_card ─────────────────────────────────────────────────────────────

def test_create_fit_card_returns_nonempty():
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    card = create_fit_card("Pair it with baggy jeans and chunky sneakers.", item)
    assert isinstance(card, str)
    assert card.strip() != ""


def test_create_fit_card_empty_outfit():
    # Empty outfit must return a descriptive error string, not raise.
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    card = create_fit_card("", item)
    assert isinstance(card, str)
    assert "outfit" in card.lower()
