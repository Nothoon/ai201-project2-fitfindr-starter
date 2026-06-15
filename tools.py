"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # Tokenize the description into lowercase keywords (drop short stop-y bits).
    keywords = {tok for tok in re.findall(r"[a-z0-9]+", description.lower()) if len(tok) > 1}

    size_query = size.lower().strip() if size else None

    scored: list[tuple[int, dict]] = []
    for listing in listings:
        # Filter: price ceiling (inclusive).
        if max_price is not None and listing.get("price", 0) > max_price:
            continue

        # Filter: size (case-insensitive substring, so "m" matches "S/M").
        if size_query:
            if size_query not in str(listing.get("size", "")).lower():
                continue

        # Score: keyword overlap against title, description, and style_tags.
        haystack = " ".join([
            str(listing.get("title", "")),
            str(listing.get("description", "")),
            " ".join(listing.get("style_tags", [])),
        ]).lower()
        haystack_tokens = set(re.findall(r"[a-z0-9]+", haystack))

        score = len(keywords & haystack_tokens)
        if score == 0:
            continue

        scored.append((score, listing))

    # Sort by relevance (highest score first), then cap at the top 3.
    scored.sort(key=lambda pair: pair[0], reverse=True)

    return [
        {
            "title": listing["title"],
            "price": listing["price"],
            "platform": listing["platform"],
            "condition": listing["condition"],
        }
        for _, listing in scored[:3]
    ]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    client = _get_groq_client()

    item_name = new_item.get("title") or new_item.get("name") or "the new item"

    items = wardrobe.get("items", []) if wardrobe else []

    # Empty-wardrobe path: no owned pieces to name, so give general styling
    # advice instead of inventing items the user does not own.
    if not items:
        prompt = (
            f"A shopper is considering buying this thrifted item:\n"
            f"  {item_name}\n\n"
            f"They have NOT entered any wardrobe items yet, so you do not know "
            f"what they own. Do NOT invent or name specific pieces as if they "
            f"owned them. Instead give general styling advice: what kinds of "
            f"items would pair well with this piece, what vibe it suits, and "
            f"2-3 outfit directions they could build. Keep it to a short "
            f"paragraph."
        )
    else:
        # Format the owned pieces so the LLM can name real items.
        lines = []
        for it in items:
            parts = [it.get("name", "unnamed")]
            cat = it.get("category")
            if cat:
                parts.append(f"({cat})")
            colors = it.get("colors") or []
            if colors:
                parts.append("colors: " + ", ".join(colors))
            tags = it.get("style_tags") or []
            if tags:
                parts.append("style: " + ", ".join(tags))
            notes = it.get("notes")
            if notes:
                parts.append(f"note: {notes}")
            lines.append("  - " + " | ".join(parts))
        wardrobe_text = "\n".join(lines)

        prompt = (
            f"A shopper is considering buying this thrifted item:\n"
            f"  {item_name}\n\n"
            f"Here is their current wardrobe — these are the ONLY pieces they "
            f"own. Style the new item using ONLY items from this list. Name the "
            f"specific pieces you use. Do NOT invent items that are not listed.\n\n"
            f"{wardrobe_text}\n\n"
            f"Suggest 1-2 complete outfits that pair the new item with named "
            f"pieces from the wardrobe above. Mention which specific wardrobe "
            f"items to wear and briefly how to style them (tuck, layer, etc.). "
            f"Keep it to a short paragraph."
        )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a personal stylist. You only style outfits using "
                    "pieces the user actually owns. You never fabricate items "
                    "that are not given to you."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )

    return response.choices[0].message.content.strip()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # Replace this with your implementation
    return ""
