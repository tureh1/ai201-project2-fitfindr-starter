# FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
└── requirements.txt           # Python dependencies
```

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design.

---

# FitFindr — Implementation

FitFindr finds a secondhand listing for a natural-language request, styles it
against your wardrobe, and writes a shareable caption. Run it with:

```bash
python app.py          # Gradio UI at http://localhost:7860
python agent.py        # CLI: happy-path + no-results demo
pytest tests/          # tool + failure-mode tests
```

## Tool Inventory

| Tool | Inputs | Output | Purpose |
|------|--------|--------|---------|
| `search_listings` | `description: str`, `size: str \| None`, `max_price: float \| None` | `list[dict]` of listing dicts (`id, title, description, category, style_tags, size, condition, price, colors, brand, platform`), ranked by keyword relevance; `[]` if none match | Find secondhand pieces matching keywords, size, and budget |
| `suggest_outfit` | `new_item: dict` (a listing), `wardrobe: dict` (`{"items": [...]}`) | `str` — 1–2 outfit ideas naming wardrobe pieces, or general advice if the wardrobe is empty | Style the found item against the user's closet (LLM: Groq `llama-3.3-70b-versatile`) |
| `create_fit_card` | `outfit: str`, `new_item: dict` | `str` — a 2–4 sentence casual OOTD caption mentioning item/price/platform | Turn the styled outfit into a social-ready caption (LLM, higher temperature for variety) |

## Planning Loop

`run_agent(query, wardrobe)` in [agent.py](agent.py) runs a **fixed sequence with
early-exit guards**, not a free-form "LLM decides" loop:

1. Create a fresh `session` dict.
2. **Parse** the query (`_parse_query`) into `description`, `size`, `max_price`
   via regex (price after `$`/`under`/`<`; size from `size X` or standalone
   `S/M/L/...`, `W##`, `US #`; remaining text becomes the keyword description).
3. **`search_listings`** with the parsed params.
   - **If the result list is empty → set `session["error"]` and `return` early.**
     `suggest_outfit` and `create_fit_card` are *never* called with empty input.
   - If non-empty → continue.
4. Select `results[0]` (top-ranked) into `session["selected_item"]`.
5. **`suggest_outfit`** on the selected item + wardrobe.
6. **`create_fit_card`** on the outfit + selected item.
7. Return the session.

The agent's behavior therefore differs by input: an impossible query stops after
one tool call; a satisfiable one runs all three.

## State Management

A single `session` dict is the source of truth. Each step writes its output to a
named key and the next step reads from it — no re-querying or hardcoded values:

`query → parsed → search_results → selected_item → outfit_suggestion → fit_card`,
plus `wardrobe` (input) and `error` (checked first by the caller). The exact dict
in `session["selected_item"]` is the same object passed into both LLM tools.
`app.py`'s `handle_query` checks `session["error"]` first; if set, the outfit and
fit-card panels stay empty.

## Error Handling

| Tool | Failure mode | Response (concrete example from testing) |
|------|-------------|------------------------------------------|
| `search_listings` | No results | Returns `[]`; loop sets a specific error. For `"designer ballgown size XXS under $5"` → `"No listings matched 'designer ballgown' (size XXS, under $5). Try broader keywords, removing the size filter, or raising your max price."` and leaves `fit_card = None`. |
| `suggest_outfit` | Empty wardrobe | Detects `wardrobe["items"] == []` and switches to a general-styling-advice prompt; still returns a non-empty string. (Also wraps the LLM call in try/except with a non-empty fallback.) |
| `create_fit_card` | Empty/whitespace `outfit` | Guards before any LLM call and returns `"Can't write a fit card without an outfit suggestion — generate an outfit first."` — a string, never an exception. |

Each failure mode has a dedicated test in [tests/test_tools.py](tests/test_tools.py)
(`test_search_empty_results`, `test_suggest_outfit_empty_wardrobe`,
`test_create_fit_card_empty_outfit`).

## AI Usage

1. **`search_listings` implementation.** I gave Claude the Tool 1 spec block from
   `planning.md` (the three params, the ranked-`list[dict]` return shape, and the
   "return `[]`, never raise" failure mode) plus the stub's TODO steps, and asked
   it to implement the function on top of `load_listings()`. I reviewed the output
   against the spec — confirming it filtered by all three parameters, scored by
   keyword overlap, dropped score-0 listings, and used case-insensitive substring
   size matching — then verified with three queries (a tee search, a `max_price=10`
   filter, and an impossible query expecting `[]`).

2. **Planning loop + state.** I shared the Architecture diagram and the Planning
   Loop / State Management sections, and asked Claude to implement `run_agent`
   following the seven numbered steps. The first draft I reviewed called all three
   tools before checking the search result — I overrode it so the empty-results
   branch sets `session["error"]` and `return`s *before* `suggest_outfit`. I
   verified by running the no-results query and confirming `fit_card` stayed `None`
   while `error` was set.

## Spec Reflection

The spec held up well: writing the exact return shape and failure mode per tool
*before* coding meant the planning loop's branch logic (empty list → early return)
fell out of the design rather than being patched in afterward. The one thing I
added beyond the original spec was try/except fallbacks inside the two LLM tools so
the agent degrades gracefully (non-empty fallback strings) when `GROQ_API_KEY` is
missing or the API call fails — the tests pass with or without a key for that
reason.

## Notes

- Set `GROQ_API_KEY` in `.env` to get real LLM-generated outfits and captions.
  Without it, the two LLM tools return deterministic fallback strings so the app
  and tests still run end-to-end.
