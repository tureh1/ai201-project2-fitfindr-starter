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

FitFindr is a multi-tool AI agent that helps users search for secondhand clothing, style a selected item with an existing wardrobe, and create a short shareable outfit caption. The main focus of this project is showing how tools connect through planning logic, shared state, and graceful error handling.

Run it with:

```bash
python app.py          # Gradio UI at http://localhost:7860
python agent.py        # CLI: happy-path + no-results demo
pytest tests/          # tool + failure-mode tests
```

## Tool Inventory

| Tool | Inputs | Output | Purpose |
|------|--------|--------|---------|
| `search_listings` | `description: str`, `size: str \| None`, `max_price: float \| None` | `list[dict]` of listing dictionaries. Each listing includes `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`. Results are ranked by keyword relevance. If nothing matches, it returns `[]`. | Searches the mock secondhand listings dataset based on the user's requested item, optional size, and optional budget. |
| `suggest_outfit` | `new_item: dict`, `wardrobe: dict` | `str` outfit suggestion. If the wardrobe has items, the response uses specific wardrobe pieces. If the wardrobe is empty, it returns general styling advice instead. | Suggests how to style the selected thrifted item with the user's current wardrobe. |
| `create_fit_card` | `outfit: str`, `new_item: dict` | `str` caption-style fit card. The response is a short 2–4 sentence shareable outfit caption that mentions the item, price, and platform. | Turns the outfit suggestion and selected item into a social-media-style outfit description. |

## Planning Loop

`run_agent(query, wardrobe)` in [agent.py](agent.py) uses a conditional planning loop with early-exit checks. The agent does not call every tool no matter what happens. Instead, each step depends on the result of the previous tool.

The loop works like this:

1. The agent creates a fresh `session` dictionary.
2. The query is parsed with `_parse_query()` into `description`, `size`, and `max_price`.
   - Price is detected from phrases like `$30`, `under $30`, or `< 30`.
   - Size is detected from phrases like `size M`, `M`, `W30`, or `US 8`.
   - The remaining words become the item description used for search.
3. The agent calls `search_listings(description, size, max_price)`.
   - If the result list is empty, the agent sets `session["error"]` to a helpful message and returns early.
   - In this no-results path, the agent does **not** call `suggest_outfit` or `create_fit_card` because there is no selected item to style.
4. If search results exist, the top-ranked result is saved as `session["selected_item"]`.
5. The selected item and wardrobe are passed into `suggest_outfit()`.
6. The returned outfit suggestion is saved as `session["outfit_suggestion"]`.
7. The outfit suggestion and selected item are passed into `create_fit_card()`.
8. The returned caption is saved as `session["fit_card"]`.
9. The completed session is returned to the Gradio app.

This makes the agent adaptive. A successful query flows through all three tools and ends with a fit card. An impossible query stops after the search tool and gives the user a specific explanation of what failed and what to try next.

## State Management

FitFindr uses one `session` dictionary to keep track of the full interaction. This makes it clear how information moves from one tool to the next without asking the user to re-enter anything.

The main state flow is:

```text
query → parsed search inputs → search_results → selected_item → outfit_suggestion → fit_card
```

Important session keys include:

| Key | What it stores | How it is used |
|-----|----------------|----------------|
| `query` | The original user request | Used as the starting point for parsing |
| `parsed` | The extracted `description`, `size`, and `max_price` | Passed into `search_listings` |
| `search_results` | The list returned by `search_listings` | Checked to decide whether the agent should continue or stop early |
| `selected_item` | The top listing chosen from the search results | Passed into `suggest_outfit` and `create_fit_card` |
| `wardrobe` | The wardrobe selected in the UI | Passed into `suggest_outfit` |
| `outfit_suggestion` | The string returned by `suggest_outfit` | Passed into `create_fit_card` |
| `fit_card` | The string returned by `create_fit_card` | Displayed in the final output panel |
| `error` | A message explaining why the workflow stopped early | Checked by `app.py` before showing the final outputs |

For example, the listing stored in `session["selected_item"]` is the same item passed into `suggest_outfit()`. Then the outfit string stored in `session["outfit_suggestion"]` is passed into `create_fit_card()`. This shows that state is passed across tools instead of being hardcoded or re-entered by the user.

## Error Handling

Each tool has its own failure behavior so the agent stays useful instead of crashing or failing silently.

| Tool | Failure mode | Response |
|------|-------------|----------|
| `search_listings` | No listings match the query | Returns `[]`. The planning loop checks for the empty list, sets `session["error"]`, and stops early. For example, when I tested `"designer ballgown size XXS under $5"`, the agent returned: `"No listings matched 'designer ballgown' (size XXS, under $5). Try broader keywords, removing the size filter, or raising your max price."` The outfit and fit-card panels stayed empty because there was no selected item to style. |
| `suggest_outfit` | Wardrobe is empty | Detects when `wardrobe["items"] == []` and switches to a general styling prompt instead of referencing specific closet pieces. It still returns a non-empty string, so the workflow can continue. The function also uses a try/except fallback so the agent does not crash if the LLM call fails. |
| `create_fit_card` | The `outfit` input is empty or whitespace | Checks the outfit string before making any LLM call. If the outfit is missing, it returns `"Can't write a fit card without an outfit suggestion — generate an outfit first."` This keeps the tool from crashing or returning a blank response. |

Each failure mode has a dedicated test in [tests/test_tools.py](tests/test_tools.py): `test_search_empty_results`, `test_suggest_outfit_empty_wardrobe`, and `test_create_fit_card_empty_outfit`.

The test suite passed with:

```text
9 passed in 0.29s
```

## AI Usage

1. **Claude — implementation support from my spec**

   `# AI used: Claude`

   `# Prompt:` I gave Claude the FitFindr project requirements, the starter file structure, the listing data fields, the wardrobe schema, and my planning requirements. I asked it to help turn my planned tool designs into code while keeping the original starter comments and template structure.

   `# Result:` Claude helped draft implementation code for `tools.py`, `agent.py`, `app.py`, and `tests/test_tools.py`. It also helped draft parts of `planning.md` and the first README update based on the project rubric.

   `# Reflection:` I used Claude as a coding assistant, but I reviewed and tested the output before accepting it. One thing I revised was the way it edited `planning.md`; I asked it not to remove the original comments or template formatting because I wanted the starter structure preserved. I also checked the planning loop myself to make sure it did not call all tools unconditionally. After implementation, I verified the tools with `pytest tests/`, checked the no-results branch, and confirmed that the app built successfully.

2. **ChatGPT — step-by-step review and rubric alignment**

   `# AI used: ChatGPT`

   `# Prompt:` I used ChatGPT to walk through the milestones, review whether my project matched the rubric, improve README wording, and plan how to test, commit, push, and record the demo.

   `# Result:` ChatGPT helped me identify that describing the planning loop as a “fixed sequence” could be misleading because the rubric asks for conditional tool use. I updated the README to explain that the agent uses early-exit checks: if `search_listings` returns `[]`, the agent stores an error and stops before calling the styling and fit-card tools.

   `# Reflection:` ChatGPT was most useful as a reviewer and guide. It helped me make the documentation clearer, but I still ran the code myself, inspected the outputs, and confirmed that all tests passed. This helped me follow the course guidance to verify AI-generated suggestions instead of trusting them automatically.

## Spec Reflection

Writing the spec before coding helped me understand the project more clearly. The most helpful part was defining each tool's inputs, outputs, and failure behavior before implementation. Because I already knew what each tool should return, it was easier to design the planning loop and decide when the agent should continue or stop early.

One way the implementation diverged from my original plan was the fallback behavior for the LLM-backed tools. Since `suggest_outfit` and `create_fit_card` depend on Groq, I added try/except fallbacks so the app and tests can still run even if the API key is missing or the LLM call fails. This made the project more reliable and easier to test.

## Notes

- Set `GROQ_API_KEY` in `.env` to get real LLM-generated outfit suggestions and captions.
- Without a Groq key, the two LLM-backed tools return deterministic fallback strings so the app and tests can still run end-to-end.
- Do not commit `.env`.