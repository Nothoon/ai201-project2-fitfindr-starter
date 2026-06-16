"""
Tests for the three FitFindr tools in tools.py.

At least one test per failure mode:
- search_listings: happy path, empty result (no crash), price filtering
- suggest_outfit: populated wardrobe, empty wardrobe (general advice fallback)
- create_fit_card: valid outfit, empty/whitespace outfit (error string, no raise)

The two LLM-backed tools (suggest_outfit, create_fit_card) hit the Groq API,
so those tests monkeypatch the client to run offline and deterministically.
"""

import pytest

import tools
from tools import search_listings, suggest_outfit, create_fit_card


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []  # empty list, no exception


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_no_price_filter_finds_jackets():
    # Sanity check that "jacket" *does* match when the price ceiling is removed,
    # so test_search_price_filter isn't passing only because the list is empty.
    results = search_listings("jacket", size=None, max_price=None)
    assert len(results) > 0


# ── LLM mock ───────────────────────────────────────────────────────────────────

class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def create(self, **kwargs):
        return _FakeCompletion("  a styled outfit suggestion  ")


class _FakeChat:
    def __init__(self):
        self.completions = _FakeCompletions()


class _FakeClient:
    def __init__(self):
        self.chat = _FakeChat()


@pytest.fixture
def fake_groq(monkeypatch):
    """Replace the real Groq client with an offline stub for LLM-backed tools."""
    monkeypatch.setattr(tools, "_get_groq_client", lambda: _FakeClient())


# ── suggest_outfit ─────────────────────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe(fake_groq):
    new_item = {"title": "90s Track Jacket — Navy/White Stripe", "price": 45.0}
    wardrobe = {"items": [{"name": "white tee", "category": "tops"}]}
    result = suggest_outfit(new_item, wardrobe)
    assert isinstance(result, str)
    assert result  # non-empty


def test_suggest_outfit_empty_wardrobe(fake_groq):
    # Empty wardrobe must fall back to general advice, not raise or return "".
    new_item = {"title": "90s Track Jacket — Navy/White Stripe", "price": 45.0}
    result = suggest_outfit(new_item, {"items": []})
    assert isinstance(result, str)
    assert result.strip()


# ── create_fit_card ────────────────────────────────────────────────────────────

def test_create_fit_card_valid(fake_groq):
    new_item = {"title": "Denim Jacket", "price": 42.0, "platform": "poshmark"}
    result = create_fit_card("white tee tucked into the jacket", new_item)
    assert isinstance(result, str)
    assert result.strip()


def test_create_fit_card_empty_outfit_returns_error():
    # No LLM should be called — guard returns an error string, never raises.
    result = create_fit_card("", {"title": "Denim Jacket"})
    assert isinstance(result, str)
    assert "outfit" in result.lower()


def test_create_fit_card_whitespace_outfit_returns_error():
    result = create_fit_card("   \n  ", {"title": "Denim Jacket"})
    assert isinstance(result, str)
    assert "outfit" in result.lower()
