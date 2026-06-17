# 🛍️ FitFindr

> A secondhand shopping stylist — because finding the piece is only half the battle; the other half is figuring out what to wear it with.

FitFindr takes a natural language request ("vintage graphic tee under $30, size M"), searches a set of mock secondhand listings, styles the best find against your wardrobe, and writes a shareable "fit card" caption. It's a small **agent**: an LLM-driven planning loop that chains three tools and passes state between them through a single session dict.

---

## Setup & Run

```bash
python -m venv .venv
source .venv/bin/activate      # Mac/Linux
# or: .venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

Add your Groq API key (free at [console.groq.com](https://console.groq.com)) to a `.env` file in the project root:

```
GROQ_API_KEY=your_key_here
```

Then launch the Gradio UI:

```bash
python app.py
```

Open the URL printed in your terminal — it's usually `http://localhost:7860`, but **check the output**, the port can differ. Type a query, pick a wardrobe, and hit **Find it**; the three panels fill with the listing, the outfit idea, and the fit card.

Run the tools' tests (LLM calls are mocked, so no key or network needed):

```bash
pytest
```

---

## Tool Inventory

The three tools live in [tools.py](tools.py). Inputs and return values below match the actual function signatures.

### 1. `search_listings`

```python
search_listings(description: str, size: str | None = None, max_price: float | None = None) -> list[dict]
```

- **Inputs:**
  - `description` (`str`) — keywords describing the item (e.g. `"vintage graphic tee"`).
  - `size` (`str | None`) — size to filter by; case-insensitive substring match (`"m"` matches `"S/M"`). `None` skips the size filter.
  - `max_price` (`float | None`) — inclusive price ceiling. `None` skips the price filter.
- **Output:** `list[dict]` — up to the **top 3** matches, each dict holding `title`, `price`, `platform`, `condition`. Sorted by relevance (keyword-overlap score, highest first). Returns an **empty list** if nothing matches — it never raises.
- **Purpose:** Find the listings most relevant to the request, after hard-filtering on size and budget.

### 2. `suggest_outfit`

```python
suggest_outfit(new_item: dict, wardrobe: dict) -> str
```

- **Inputs:**
  - `new_item` (`dict`) — the selected listing being styled.
  - `wardrobe` (`dict`) — the user's wardrobe; an `{"items": [...]}` dict that may be empty.
- **Output:** `str` — a non-empty styling write-up. With a populated wardrobe it names specific owned pieces; with an empty wardrobe it returns general styling advice instead.
- **Purpose:** Turn a found item into 1–2 concrete outfits built from pieces the user actually owns.

### 3. `create_fit_card`

```python
create_fit_card(outfit: str, new_item: dict) -> str
```

- **Inputs:**
  - `outfit` (`str`) — the styling write-up returned by `suggest_outfit`.
  - `new_item` (`dict`) — the listing being styled (so the caption can name the piece, price, and platform).
- **Output:** `str` — a short, casual 1–2 line OOTD caption (emoji ok). If `outfit` is empty/whitespace it returns a descriptive **error string** rather than raising.
- **Purpose:** Produce a shareable social caption for the find — deliberately run at a high temperature so the same input yields a fresh caption each time.

---

## How the Planning Loop Works

The loop lives in `run_agent(query, wardrobe)` in [agent.py](agent.py). It is **linear with early exits** — each step depends on the previous step succeeding, and a failure short-circuits the rest of the loop so a later tool is never called with empty input.

1. **Initialize state.** `_new_session()` builds the session dict that every later step reads from and writes to.
2. **Parse the query.** `_parse_query()` asks the LLM (in JSON mode, `temperature=0.0`) to extract `description`, `size`, and `max_price`. **Conditional:** if the JSON can't be parsed, it falls back to using the raw query as the `description` so search still gets something usable — parsing failure degrades, it doesn't crash.
3. **Search.** Calls `search_listings(description, size, max_price)`. **Conditional:** if the result list is empty, it writes a "no listings found" message to `session["error"]` and **returns immediately** — `suggest_outfit` and `create_fit_card` are skipped.
4. **Select.** With at least one result, the top-ranked listing (`search_results[0]`) becomes `selected_item`.
5. **Style.** Calls `suggest_outfit(selected_item, wardrobe)`. **Conditional:** if the returned string is empty or whitespace, it sets `session["error"]` (asking the user to add wardrobe pieces) and **returns early** — `create_fit_card` is skipped.
6. **Caption.** Calls `create_fit_card(outfit_suggestion, selected_item)` and stores the result.
7. **Return** the completed session.

The loop is "done" when either all three tools have run and `fit_card` is populated, **or** an error branch fired and set `session["error"]`. The caller checks `session["error"]` first; if it's set, the other output fields are `None`.

---

## State Management

There is exactly one piece of state per interaction: the **session dict** created by `_new_session()`. It is the single source of truth — tools don't talk to each other directly, they read inputs from the session and the loop writes their outputs back into it.

| Key | Written by | Holds |
|-----|-----------|-------|
| `query` | `_new_session` (at start) | the original user query |
| `parsed` | step 2 | `{description, size, max_price}` from the LLM parse |
| `search_results` | step 3 | list returned by `search_listings` |
| `selected_item` | step 4 | the top result — the item that gets styled |
| `wardrobe` | `_new_session` (at start) | the chosen wardrobe dict |
| `outfit_suggestion` | step 5 | string returned by `suggest_outfit` |
| `fit_card` | step 6 | string returned by `create_fit_card` |
| `error` | any error branch | the message that caused early termination (else `None`) |

**How data flows between tools:** `selected_item` (written after search) is read straight into `suggest_outfit`; its output `outfit_suggestion` is then read straight into `create_fit_card`. Nothing is re-derived and the user is never re-prompted mid-loop. The UI ([app.py](app.py)) reads `error`, `selected_item`, `outfit_suggestion`, and `fit_card` off the returned session to populate its three panels.

---

## Error Handling

The strategy is **fail soft inside the tools, branch in the loop**: a tool never raises on the expected failure modes — it returns a safe sentinel (empty list, general-advice string, or error string), and the planning loop turns that sentinel into a user-facing message and stops before calling the next tool.

| Tool | Failure mode | Handling |
|------|-------------|----------|
| `search_listings` | No listing matches the query | Returns `[]` (never raises). The loop detects the empty list, writes a "try a broader description / different size / higher price" message to `session["error"]`, and returns before styling. |
| `suggest_outfit` | Empty wardrobe | The tool itself doesn't fail — it switches to a general-advice prompt that's instructed *not* to name pieces the user doesn't own. If the model still returns nothing usable, the loop's empty/whitespace guard sets an error asking the user to add wardrobe items and skips the fit card. |
| `create_fit_card` | Outfit text missing/incomplete | A guard at the top returns a descriptive error string ("Can't write a fit card yet — the outfit details are missing…") **without** calling the LLM or raising. |

**Concrete example from testing.** The example query `"designer ballgown size XXS under $5"` is a deliberate no-results case. In `tests/test_tools.py`, `test_search_empty_results` asserts:

```python
search_listings("designer ballgown", size="XXS", max_price=5) == []
```

That empty list propagates up: `run_agent` sets `session["error"]`, and end-to-end the UI shows *"No listings found for that search. Try a broader description, a different size, or a higher max price."* in the listing panel with the outfit and fit-card panels left blank — no crash, no half-finished output. All 9 tests pass (`pytest` → `9 passed`).

---

## Spec Reflection

**One way the spec helped.** The ASCII architecture diagram and the Planning Loop section in [planning.md](planning.md) pinned down the *error branches* before any code existed — each tool's `[ERROR]` arrow short-circuiting to a single "return session." `run_agent` is essentially a direct transcription of that diagram: the two early `return session` statements (empty search results, empty outfit) exist because the diagram said they had to, which kept later tools from ever running on empty input.

**One way the implementation diverged.** The original starter docstring for `search_listings` described returning the *full* listing dicts (`id`, `title`, `description`, `category`, `style_tags`, `colors`, `brand`, …). The implementation instead returns a **trimmed** dict of just `title`, `price`, `platform`, `condition`, capped at the top 3 — matching the narrowed Tool 1 spec I wrote in planning.md. Why: those four fields are all the downstream tools and the fit card actually need, and a smaller payload keeps the LLM prompts focused. The visible trade-off: `app.py`'s listing panel was written against the fuller shape, so its Size / Colors / Style / Brand lines fall back to `"—"`. (Easy follow-up: either carry those fields through `search_listings` or drop them from the panel.)

---

## AI Usage

**Instance 1 — `search_listings`.** I gave Claude the Tool 1 block from planning.md (inputs, return shape, "returns `[]` on no match") plus `load_listings()` from [utils/data_loader.py](utils/data_loader.py) so it would use the loader instead of re-reading the file. It produced a keyword-overlap scorer with size and price filters. **What I changed:** I overrode the return shape to a trimmed 4-field dict capped at the top 3 (the first draft returned full listing dicts), and tightened the matching — dropping 1-character tokens from the keyword set and making the size filter a case-insensitive *substring* match so `"M"` matches `"S/M"`. I verified it against three queries (a match, an over-budget query, and a nonsense description that must return `[]`).

**Instance 2 — `suggest_outfit` / `create_fit_card` prompts.** I gave Claude the Tool 2 and Tool 3 blocks plus the wardrobe schema from [data/wardrobe_schema.json](data/wardrobe_schema.json), stressing two requirements: the stylist must only use pieces the user owns, and the fit card must read like a social caption, not a product description. **What I overrode:** I added a strict system prompt ("never fabricate items not given to you") and a dedicated empty-wardrobe branch that gives general advice rather than inventing a closet; for the fit card I raised the temperature to `1.1` and added explicit "do NOT write a spec-sheet / 'condition: excellent'" instructions after early drafts kept producing listing-style blurbs. I verified by calling the fit card twice on the same input (expecting different captions) and running `suggest_outfit` with both the example and empty wardrobes.

---

## Demo

[Watch the demo video](./demo.mkv)
