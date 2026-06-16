# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

FitFindr Setup Complete

**What FitFindr needs to do (in plain terms):**
FitFindr takes a natural-language thrifting request, finds a matching secondhand listing from a mock dataset, and turns that find into a styled, shareable post. It runs three tools in a fixed sequence — `search_listings` (find the item) → `suggest_outfit` (style it against the user's wardrobe) → `create_fit_card` (write a caption). `search_listings` is triggered by the user's query; `suggest_outfit` is triggered only when the search returns at least one listing; `create_fit_card` is triggered only when an outfit suggestion was produced. If `search_listings` returns nothing, the agent stops, reports what failed, and suggests how to broaden the search — it never calls `suggest_outfit` or `create_fit_card` with empty input.

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Searches the 40-item mock listings dataset for pieces matching the user's keywords, optionally filtered by size and a maximum price, and returns the matches ranked by how well they fit the keywords (best first).

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): Free-text keywords describing the desired item, e.g. `"vintage graphic tee"`. Tokenized into lowercase words and matched against each listing's `title`, `description`, `style_tags`, `colors`, and `category`.
- `size` (str | None): A size string to filter by, e.g. `"M"`. Matching is case-insensitive and substring-based so `"M"` matches `"S/M"`, `"M/L"`, `"M (oversized)"`. `None` skips size filtering.
- `max_price` (float | None): Inclusive price ceiling, e.g. `30.0`. A listing passes if `price <= max_price`. `None` skips price filtering.

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
A `list[dict]` of full listing dicts, sorted by relevance score descending. Each dict has the original fields: `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand` (str or None), `platform`. Listings with a keyword-overlap score of 0 are dropped. Returns `[]` (empty list, never an exception) when nothing matches.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
The tool returns `[]`. The planning loop detects the empty list, sets `session["error"]` to a specific, actionable message (e.g. "No listings matched 'designer ballgown' under $5 in size XXS. Try removing the size filter, raising your budget, or using broader keywords like 'dress'.") and returns early **without** calling `suggest_outfit`.

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Given one selected listing and the user's wardrobe, asks the LLM (Groq `llama-3.3-70b-versatile`) to propose 1–2 concrete outfits pairing the new item with named wardrobe pieces, including a short styling tip.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): The selected listing dict (the item the user is considering). The tool reads its `title`, `category`, `style_tags`, `colors`, and `price` into the prompt.
- `wardrobe` (dict): A wardrobe dict shaped `{"items": [ {id, name, category, colors, style_tags, notes}, ... ]}`. May have an empty `items` list — handled explicitly.

**What it returns:**
<!-- Describe the return value -->
A non-empty `str` of outfit suggestions in natural language. When the wardrobe has items, the suggestions name specific pieces from it (e.g. "your wide-leg khaki trousers + chunky white sneakers"). When the wardrobe is empty, it returns general styling advice for the item (what categories/colors/vibe pair well) rather than referencing nonexistent pieces.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
- Empty wardrobe (`wardrobe["items"] == []`): switches to a "general styling advice" prompt instead of crashing or returning `""`.
- LLM call raises (network/key error): caught; returns a plain-string fallback like "Couldn't generate an outfit suggestion right now — try pairing this with neutral basics and a contrasting shoe." The agent still proceeds (the fallback string is non-empty), so `create_fit_card` can run.

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Turns the chosen item and its outfit suggestion into a short, casual OOTD-style social caption (the kind you'd post on Depop/TikTok), using a higher LLM temperature so repeated calls vary.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): The outfit-suggestion string returned by `suggest_outfit`. Provides the vibe/context for the caption.
- `new_item` (dict): The selected listing dict — used to mention `title`, `price`, and `platform` naturally (once each).

**What it returns:**
<!-- Describe the return value -->
A 2–4 sentence `str` suitable as an Instagram/TikTok caption: casual, authentic, mentions item name + price + platform once each, captures the outfit vibe.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
- Empty/whitespace `outfit`: guards immediately and returns a descriptive error string ("Can't write a fit card without an outfit suggestion — generate an outfit first.") — no LLM call, no exception.
- LLM call raises: caught; returns a simple deterministic fallback caption built from the item fields so the panel is never blank.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->
The loop is a fixed sequence with early-exit guards — it is *not* a free-form "LLM decides" loop. Concretely, inside `run_agent(query, wardrobe)`:

1. **Initialize** `session = _new_session(query, wardrobe)`.
2. **Parse** the query into `description`, `size`, `max_price` and store in `session["parsed"]`:
   - `max_price`: regex for a number following `$`, `under`, `below`, or `<` (e.g. `under $30` → `30.0`). Else `None`.
   - `size`: regex for explicit `size X` tokens or standalone size words (`XS/S/M/L/XL`, `W##`, `US #`). Else `None`.
   - `description`: the query with the price/size phrases stripped out, leaving the keyword text.
3. **Call** `search_listings(description, size, max_price)`; store in `session["search_results"]`.
   - **Branch — empty:** `if not results:` set `session["error"]` to a specific retry message and `return session`. (No further tools run.)
   - **Branch — non-empty:** continue.
4. **Select** `session["selected_item"] = results[0]` (top-ranked match).
5. **Call** `suggest_outfit(selected_item, wardrobe)`; store in `session["outfit_suggestion"]`. (Empty wardrobe is handled inside the tool, not by the loop.)
6. **Call** `create_fit_card(outfit_suggestion, selected_item)`; store in `session["fit_card"]`.
7. **Return** `session`.

**How does it know when it's done?** When `fit_card` is set (happy path) or when `error` is set (early exit). The behavior differs by input because step 3's branch is conditional on the search result — an impossible query short-circuits after one tool call, a satisfiable one runs all three.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->
A single `session` dict (created by `_new_session`) is the one source of truth for the whole interaction. Each step writes its output into a named key, and the next step reads from that key rather than re-deriving anything:

| Key | Written by | Read by |
|-----|-----------|---------|
| `query` | caller | parse step |
| `parsed` (`{description, size, max_price}`) | parse step | `search_listings` |
| `search_results` | `search_listings` | branch check + selection |
| `selected_item` | selection step | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | caller | `suggest_outfit` |
| `outfit_suggestion` | `suggest_outfit` | `create_fit_card` |
| `fit_card` | `create_fit_card` | final output |
| `error` | any failing step | caller / UI (checked first) |

The exact dict stored in `session["selected_item"]` is the same object passed into both `suggest_outfit` and `create_fit_card` — no copying, re-querying, or hardcoding between steps. The caller (`app.py`) checks `session["error"]` first; if non-`None`, the other output fields are `None`.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Stop after this tool. Set `session["error"]` to a specific message naming the query and active filters and suggesting concrete fixes: "No listings matched '<description>'<with size/price filters>. Try broader keywords, removing the size filter, or raising your max price." Do not call `suggest_outfit`. UI shows the message in the listing panel and leaves the other two panels empty. |
| suggest_outfit | Wardrobe is empty | Don't crash. Detect `wardrobe["items"] == []` and call the LLM with a "general styling advice" prompt instead, returning advice on what categories/colors/silhouettes pair with the item. The agent proceeds to `create_fit_card`. |
| create_fit_card | Outfit input is missing or incomplete | Guard first: if `outfit` is empty/whitespace, return the string "Can't write a fit card without an outfit suggestion — generate an outfit first." No LLM call, no exception. UI shows this string in the fit-card panel. |

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

```
                        User query  +  wardrobe choice
                              │
                              ▼
                  ┌───────────────────────────┐
                  │      Planning Loop         │◄──────────────┐
                  │      run_agent()           │               │
                  └───────────────────────────┘          read/write
                              │                                │
                              ▼                                ▼
                        parse query              ┌───────────────────────────┐
                  {description, size, max_price} │      Session (dict)        │
                              │                  │  query, parsed,            │
                              ▼                  │  search_results,           │
       ┌─► search_listings(description,size,…)   │  selected_item, wardrobe,  │
       │          │                              │  outfit_suggestion,        │
       │          │ results == []                │  fit_card, error           │
       │          ├──────────────► [ERROR] set session["error"]               │
       │          │                "No listings found — try…"  ──► return ────┤  (early exit)
       │          │                                            └──────────────┘
       │          │ results == [item, ...]
       │          ▼
       │   session["selected_item"] = results[0]
       │          │
       ├─► suggest_outfit(selected_item, wardrobe)
       │          │   (empty wardrobe → general advice, handled in-tool)
       │          ▼
       │   session["outfit_suggestion"] = "..."
       │          │
       └─► create_fit_card(outfit_suggestion, selected_item)
                  │   (empty outfit → error-string guard, handled in-tool)
                  ▼
           session["fit_card"] = "..."
                  │
                  ▼
            return session  ──►  app.py maps to 3 panels
                                 (listing | outfit | fit card)
```

Data flows one direction through the session dict; the only branch that terminates early is the empty-`search_results` path, which sets `error` and returns before any LLM tool runs.

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

**Milestone 3 — Individual tool implementations:**

- **`search_listings` (Claude):** I'll paste the Tool 1 block above (inputs, return shape, failure mode) plus the TODO steps from the stub and ask Claude to implement it using `load_listings()` from `utils/data_loader.py` — no re-reading files. Before trusting it I'll verify: (a) it filters by all of `max_price`, `size` (case-insensitive substring), and keyword score; (b) it drops score-0 listings; (c) it returns `[]` rather than raising on no match. Then I'll run it on 3 queries — "vintage graphic tee" (expect tees), `max_price=10` (assert all `price <= 10`), and "designer ballgown" XXS $5 (expect `[]`).
- **`suggest_outfit` (Claude):** I'll give Claude the Tool 2 block and the wardrobe schema, asking for a Groq `llama-3.3-70b-versatile` call with two prompt branches (populated vs. empty wardrobe). I'll verify it checks `wardrobe["items"]` before building the prompt and returns a non-empty string in both branches, then test with `get_example_wardrobe()` and `get_empty_wardrobe()`.
- **`create_fit_card` (Claude):** I'll give Claude the Tool 3 block, asking for a higher-temperature Groq call and an empty-`outfit` guard. I'll verify the guard returns a string (not an exception) and that two calls on the same input produce different captions; if identical, I'll raise the temperature.

**Milestone 4 — Planning loop and state management:**

- **`run_agent` + `handle_query` (Claude):** I'll share the full Architecture diagram above plus the Planning Loop and State Management sections, and ask Claude to implement `run_agent` following the 7 numbered steps and `handle_query` in `app.py`. Before running I'll check that it branches on the `search_listings` result (early `return` on empty), writes each tool output into the named session key, and does **not** call all three tools unconditionally. I'll verify by printing `session["selected_item"]` and confirming it's the identical dict that flows into `suggest_outfit`, and by running the no-results query and confirming `fit_card` stays `None` while `error` is set.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->
The loop parses the query into `description="vintage graphic tee"`, `size=None`, `max_price=30.0` and calls `search_listings("vintage graphic tee", None, 30.0)`. Listings are scored by keyword overlap on `title`/`description`/`style_tags`. Matches under $30 include `lst_006` ("Graphic Tee — 2003 Tour Bootleg Style", $24, depop), `lst_033` ("Vintage Band Tee — Faded Grey", $19, depop), and `lst_002` ("Y2K Baby Tee", $18). The list is sorted by score; the top result (a graphic/vintage tee, e.g. `lst_006`) becomes `session["selected_item"]`. Because the list is non-empty, the loop proceeds.

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->
The loop calls `suggest_outfit(selected_item=<the graphic tee>, wardrobe=get_example_wardrobe())`. The LLM sees the tee plus the user's pieces and returns something like: "Pair the faded graphic tee with your baggy dark-wash jeans and chunky white sneakers for an effortless 90s streetwear look. Layer your vintage black denim jacket over it and add the brown leather belt to pull it together." Stored in `session["outfit_suggestion"]`.

**Step 3:**
<!-- Continue until the full interaction is complete -->
The loop calls `create_fit_card(outfit=<the suggestion>, new_item=<the graphic tee>)`. The LLM returns a caption like: "thrifted this faded graphic tee off depop for $24 and it's already my most-worn 🖤 styled it with baggy jeans + chunky sneakers and the vintage denim jacket on top. grunge-meets-streetwear, exactly my vibe." Stored in `session["fit_card"]`.

**Final output to user:**
<!-- What does the user actually see at the end? -->
The Gradio UI shows three panels — the listing details (title, price, condition, platform, size) in panel 1, the outfit suggestion in panel 2, and the fit-card caption in panel 3. On the no-results path (e.g. "designer ballgown size XXS under $5"), panel 1 shows the actionable error message and panels 2 and 3 stay empty.
