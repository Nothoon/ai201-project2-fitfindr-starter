# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
This tool searches the listings and finds the top 3 matches.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): The description of the clothing item to seach for
- `size` (str): The size of the clothing item to search for
- `max_price` (float): The upper limit pricing of the clothing item

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
It will return the top 3 matching listings. The return result will contain the clothing item description/name, price, the origin platform, and its condition.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
If the tool returns no matching listings the agent will communicate that it found no matches to the user.

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Given a clothing item the tool will suggest other clothing items to pair it with or a complete outfit combination.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): The item to include and suggest clothing items to go with.
- `wardrobe` (dict): The users wardrobe with their current clothing.

**What it returns:**
<!-- Describe the return value -->
Returns the clothing items to pair the `new_item` with.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
If this tool returns no suggestions then the agent will communicate that it is unable to make any suggestions because of the empty wardrobe and insufficient wardrobe.

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
This tool will create a description of a complete outfit.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): The outfit suggestion text returned by `suggest_outfit` — the styling write-up describing how the new item pairs with wardrobe pieces.
- `new_item` (dict): The selected listing being styled (title, price, platform, condition) so the caption can name the actual piece and where it came from.

**What it returns:**
<!-- Describe the return value -->
Returns a `str`: a short, casual, shareable caption (1–2 lines, emoji ok) — the kind of thing someone captions an Instagram post with, not a product description. Must produce a different caption for different inputs (LLM-generated, non-deterministic).

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
If the outfit data is incomplete the agent will communciate to the user the error and instruct it to give more information.

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

The agent will extract the shopping constraints. Specfic clothing descriptions, sizing, max price, and any other details the user mentions. 

The tool it will call `search_listings` first. The agent will pass in the item description, size, and max price into search listings. If the tool returns matching listings then it will store the top result into `new_item`. If no listings are found then the agent will stop and inform the user that there were no matches.

After a listing is stored it will call `suggest_outfit` using the selected `new_item` and user's wardrobe. This should return an outfit consisting of the `new_item` and clothing items in the user's wardrobe. If the wardrobe is empty or too limited, the agent will communicate to the user that it cannot make a full suggestion and ask for more wardrobe details.

After `suggest_outfit` returns a usable outfit it will store that outfit suggestion and then call `create_fit_card`. This tool will recieve a completed outfit and create a outfit description. If `create_fit_card` returns no description it will communicate to the user about the error and request to try again with a full outfit.

The loop finishes when a final response is produced with a matching listing, outfit, suggestion, and fit card or when it reaches an error path that prevents the next tool from being called. Each step will depend on whether or not the previous tool returned any useful information.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

The agent stores information in a dictionary while user interaction is happening. The dictionary will track:
* `description`: the clothing item the user is searching for
* `size`: the requested clothing size
* `max_price`: the user's budget
* `wardrobe`: the user's current wardrobe
* `search_results`: the listing returned by `search_listings`
* `new_item`: the selected listing that will be styled
* `outfit`: the outfit suggestion returned by `suggest_outfit`
* `fit_card`: the final outfit description returned by `create_fit_card`
* `errors`: any failure messages from tools

Information will flow from on tool to the next. For example, after `search_listings` returns results, the agent saves the best matching listing as `new_item`. That same `new_item` is passed into `suggest_outfit` with the user's `wardrdobe`. After `suggest_outfit` makes an outift, the result is saved as `outfit` and passed into `create_fit_card`

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query |The agent tells the user that no matching listings were found with their current description, size, and price limit. It does not continue to suggest_outfit because there is no new_item to style. The agent can suggest that the user try a broader description, a different size, or a higher max price.|
| suggest_outfit | Wardrobe is empty |The agent tells the user that it found an item but cannot create a full outfit because the wardrobe is empty or missing. It asks the user to add wardrobe details, such as pants, shoes, jackets, or accessories they already own. It does not call create_fit_card until a usable outfit exists.|
| create_fit_card | Outfit input is missing or incomplete |The agent tells the user that it cannot create a fit card because the outfit information is incomplete. It explains which information is missing, such as the selected item, bottoms, shoes, or styling details, and stops instead of generating a weak or inaccurate caption.|

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

```text
User query: "vintage graphic tee under $30, size M,
             I wear baggy jeans + chunky sneakers"
    │
    ▼
Extract constraints  ──►  Session: description, size, max_price, wardrobe
    │
    ▼
Planning Loop ─────────────────────────────────────────────────────────┐
    │                                                                  │
    ├─► search_listings(description, size, max_price)                  │
    │       │ results=[]                                               │
    │       ├──► [ERROR] "No listings found. Try broader               │
    │       │            description / size / higher price" → return   │
    │       │                                                          │
    │       │ results=[item, ...]                                      │
    │       ▼                                                          │
    │   Session: search_results, selected_item = results[0]            │
    │       │                                                          │
    │       ▼                                                          │
    │   wardrobe empty / unusable?                                     │
    │       ├──► [ERROR] "Found an item but wardrobe is empty.         │
    │       │            Add pieces you own" → return                  │
    │       │ wardrobe ok                                              │
    │       ▼                                                          │
    ├─► suggest_outfit(selected_item, wardrobe)                        │
    │       │ outfit=None / incomplete                                 │
    │       ├──► [ERROR] "Couldn't build an outfit. Add more           │
    │       │            wardrobe items" → return                      │
    │       │                                                          │
    │       │ outfit returned                                          │
    │       ▼                                                          │
    │   Session: outfit_suggestion = "..."                             │
    │       │                                                          │
    ├─► create_fit_card(outfit_suggestion, selected_item)              │
    │       │ fit_card=None                                            │
    │       ├──► [ERROR] "Outfit info incomplete, can't caption"       │
    │       │            → return                                      │
    │       │                                                          │
    │       │ fit_card returned                                        │
    │       ▼                                                          │
    └─► Session: fit_card = "..."                                      │
            │                                           error paths ───┘
            ▼                                            all return here
        Return session
        (listing + outfit_suggestion + fit_card)
```

**How to read it:** the left rail is the Planning Loop calling tools top to bottom. Each tool writes its result into the shared **Session** dict; the next tool reads from Session instead of asking the user again (`selected_item` → `suggest_outfit`, `outfit_suggestion` → `create_fit_card`). Every tool has its own `[ERROR]` branch — empty results, empty wardrobe, or incomplete data short-circuit out the right rail to the same `Return session`, skipping any remaining tools.


---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**AI tool:** Claude (Claude Code in VS Code). Same model across milestones for consistent style.

**Milestone 3 — Individual tool implementations:**

I build and verify one tool at a time, in isolation, before wiring anything together.

- **search_listings** — Input I give Claude: the **Tool 1** block above plus the `load_listings()`  from [data_loader.py](utils/data_loader.py) so it uses the loader instead of re-reading the file. Expected output: a function that filters listings by `size`, `max_price`, and a keyword/`description` match against `title`/`description`/`style_tags`, sorts by relevance, and returns the top 3 as a list of dicts (title, price, platform, condition). Verify before trusting: confirm it filters on **all three** params, returns `[]` (not a crash) on no match, and caps at 3. Test 3 queries — one with matches, one over-budget (expect fewer/empty), one nonsense description (expect empty).
- **suggest_outfit** — Input I give Claude: the **Tool 2** block plus the wardrobe schema from [wardrobe_schema.json](data/wardrobe_schema.json) so it knows the item fields (`name`, `category`, `colors`, `style_tags`, `notes`). Expected output: a function that builds an LLM prompt from `new_item` + `wardrobe` items and returns a styling string naming specific owned pieces. Verify: run with `get_example_wardrobe()` (expect it to name real items like the baggy jeans + chunky sneakers) and with `get_empty_wardrobe()` (expect the empty-wardrobe failure path, not a hallucinated outfit).
- **create_fit_card** — Input I give Claude: the **Tool 3** block, stressing the "sounds shareable, not a product description" and "different each time" requirements. Expected output: a function that prompts the LLM for a 1–2 line caption from `outfit` + `new_item`. Verify: call it twice with the same input (expect different captions), and once with two different items (expect both reference the actual piece). Reject output that reads like a listing description.

**Milestone 4 — Planning loop and state management:**

Input I give Claude: the **Planning Loop** section, the **State Management** section, and the ASCII diagram in **Architecture** (pasted verbatim — the diagram is the contract for control flow and the error branches). Expected output: a loop that (1) extracts constraints into the session dict, (2) calls the three tools in order, (3) writes each result back to the session under the keys listed in State Management, and (4) short-circuits to "return session" on each `[ERROR]` branch shown in the diagram. Verify before trusting: trace the happy path against the **Complete Interaction** walkthrough below and confirm `new_item` flows into `suggest_outfit` and `outfit` flows into `create_fit_card` without re-prompting the user. Then force each error branch — empty search results, empty wardrobe, missing outfit — and confirm the loop stops at the right step and the later tools are **not** called with empty input.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 0 — Extract constraints:** The agent parses the query into the session dict: `description="vintage graphic tee"`, `size="M"` (none given here → may stay unset/loosened), `max_price=30.0`, and `wardrobe = get_example_wardrobe()` (baggy jeans, chunky sneakers, etc.).

**Step 1 — search_listings:** Calls `search_listings("vintage graphic tee", size="M", max_price=30.0)`. Filters the listings by keyword, size, and price, sorts by relevance, returns the top 3. Agent stores them as `search_results` and sets `new_item = search_results[0]` — e.g. `lst_002 "Y2K Baby Tee — Butterfly Print", $18, depop, excellent`. (If results were `[]`, the agent stops here and tells the user to broaden the description / size / price — `suggest_outfit` is never called.)

**Step 2 — suggest_outfit:** Calls `suggest_outfit(new_item=<Y2K Baby Tee>, wardrobe=<example wardrobe>)`. Returns a styling string naming owned pieces, e.g. *"Pair it with your baggy straight-leg jeans and chunky white sneakers for an easy Y2K streetwear look — half-tuck the front and throw the black denim jacket over it."* Agent stores it as `outfit`. (If the wardrobe were empty, the agent stops and asks the user to add pieces they own — `create_fit_card` is never called.)

**Step 3 — create_fit_card:** Calls `create_fit_card(outfit=<the styling string>, new_item=<Y2K Baby Tee>)`. Returns a shareable caption, e.g. *"found this y2k butterfly baby tee on depop for $18 and it was made for my baggy jeans 🦋 full fit in stories"*. Agent stores it as `fit_card`.

**Final output to user:** The agent returns all three together — the chosen listing (title, $18, depop, excellent), the outfit suggestion from Step 2, and the fit card caption from Step 3 — so the user sees what to buy, how to wear it, and a ready-to-post caption.
