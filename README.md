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

1. Claude — planning and implementation support

Prompt: I gave Claude the FitFindr project instructions, the starter file structure, the fields in listings.json, the wardrobe schema, and my planning requirements. I also told it not to remove the original comments or starter template formatting because I wanted to preserve the structure of the repo.

Result: Claude helped me fill in planning.md, implement the three tool functions in tools.py, connect the planning loop in agent.py, complete the Gradio handler in app.py, create pytest tests, and draft the first version of the README.

Reflection: I used Claude as an implementation assistant, but I still reviewed the logic myself. For example, when Claude tried to rewrite too much of planning.md, I corrected the direction and asked it to keep the original comments and template lines. I also checked that the planning loop actually returned early when no listings were found, because the assignment required the agent to respond based on tool results instead of blindly running every tool. After the implementation, I verified the work by running pytest tests/, testing the no-results query, and checking that the app built successfully.

2. ChatGPT — step-by-step guidance, review, and refinement

Prompt: I used ChatGPT to help me understand the milestones step by step, review whether my implementation matched the rubric, improve the README wording, and plan how to test, commit, push, and record the demo.

Result: ChatGPT helped me notice that describing the planning loop as a “fixed sequence” could sound misleading, since the project requires conditional tool use. I revised the README to explain that the agent uses early-exit guards: if search_listings returns [], the agent sets an error and stops before calling the styling and fit-card tools.

Reflection: ChatGPT was most helpful for checking clarity and making sure my documentation matched the grading requirements. I used it as a reviewer rather than just copying answers. I still made sure to run the code myself, inspect the outputs, and confirm that the tests passed. This helped me follow the course guidance to verify AI-generated work instead of trusting it automatically.
   

## Spec Reflection

Writing the spec before coding helped me understand the project more clearly. The most useful part was defining each tool's input, output, and failure mode before implementation. That made it much easier to write the planning loop because I already knew what each tool should return and how the agent should respond.

One place where the implementation expanded beyond my original plan was the LLM fallback behavior. Since suggest_outfit and create_fit_card rely on Groq, I added try/except fallbacks so the app and tests can still run even if the API key is missing or the LLM call fails. This made the project more reliable and easier to test.

## Notes

- Set `GROQ_API_KEY` in `.env` to get real LLM-generated outfits and captions.
  Without it, the two LLM tools return deterministic fallback strings so the app
  and tests still run end-to-end.
