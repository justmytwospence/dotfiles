---
name: anki
description: |
  Create, manage, and populate Anki flashcard decks using the Anki MCP tools. Use this skill whenever the user mentions Anki, flashcards, spaced repetition, or wants to turn any content (notes, study material, conversation topics, cheat sheets, documents) into reviewable cards. Also trigger when the user says things like "help me memorize this", "make cards for this", "quiz me later on this", "add this to my deck", or "I need to remember this". Even if the user doesn't say "Anki" explicitly — if they have Anki MCP tools available and want to create flashcards or study material, use this skill. Trigger for any request involving deck creation, card review, card editing, tag management, or converting any knowledge source into spaced repetition cards.
---

# Anki Flashcard Skill

Create high-quality Anki flashcards from any source material. The goal is to produce cards that maximize long-term retention by following evidence-based principles from spaced repetition research.

## Available Tools

You have access to these Anki MCP tools:

- `anki__list_decks` — List all decks (use `include_stats: true` for card counts)
- `anki__model_names` — List available note types
- `anki__model_field_names` — Get required fields for a note type (**check this before creating cards!**)
- `anki__create_deck` — Create a deck (supports `Parent::Child` nesting, max 2 levels)
- `anki__add_notes` — Batch add up to 100 notes to a deck
- `anki__add_note` — Add a single note
- `anki__find_notes` — Search existing notes
- `anki__notes_info` — Get detailed info about existing notes
- `anki__update_note_fields` — Edit existing notes
- `anki__tag_management` — Add/remove tags
- `anki__delete_notes` — Remove notes
- `anki__get_due_cards` — See what's due for review
- `anki__present_card` — Show a card for review
- `anki__rate_card` — Rate a card (Again/Hard/Good/Easy)
- `anki__sync` — Sync with AnkiWeb
- `anki__store_media_file` — Attach images or audio to cards
- `anki__filtered_deck` — Create filtered/custom study decks

## Card Creation Workflow

### 1. Understand the source material

Before creating cards, understand what you're working with. The source determines card style:

- **Factual recall** (definitions, acronyms, formulas, syntax) → **Cloze** cards
- **Conceptual understanding** (why something works, when to use it) → **Basic** cards with scenario-based fronts
- **Error correction** (mistakes from practice) → **Cloze** cards emphasizing the correct pattern, with the wrong pattern visible as contrast
- **Vocabulary / terminology** → **Basic (and reversed card)** for bidirectional recall
- **Visual/spatial knowledge** (diagrams, anatomy, architecture) → **Image Occlusion** if the user has images to work with
- **Processes / sequences** → Series of **Cloze** cards, one per step, with step number as context

### 2. Check the deck structure

Always run `anki__list_decks` first to see what exists. Propose a deck name that fits the user's existing organization. Use `Parent::Child` hierarchy when the content has natural subcategories.

### 3. Check model fields BEFORE creating cards

Different Anki installations may have custom fields. Always call `anki__model_field_names` for the model you plan to use before your first batch of cards in a session.

**Known field requirements for default models:**

| Model | Required Fields |
|---|---|
| `Cloze` | `Text`, `Back Extra` |
| `Basic` | `Front`, `Back` |
| `Basic (and reversed card)` | `Front`, `Back` |

The `Back Extra` field on Cloze cards can be an empty string `""` but **must be present** in the fields object or the note creation will fail silently.

### 4. Structure each note correctly

Use `anki__add_notes` for batch creation (up to 100 per call). Every note **must** be wrapped in a `fields` object:

```json
{"fields": {"Text": "Cloze content {{c1::here}}", "Back Extra": ""}}
```

This will fail — missing `fields` wrapper:
```json
{"Text": "This will error"}
```

This will also fail — missing `Back Extra`:
```json
{"fields": {"Text": "Missing required field"}}
```

### 5. Use tags strategically

Always add tags to cards. Tags enable filtered study sessions (e.g., cramming just the gotchas, or just one subtopic). Good tag patterns:

- Topic tags: `sql`, `python`, `statistics`
- Type tags: `gotcha`, `syntax`, `concept`, `buzzword`
- Source tags: `interview-prep`, `chapter-3`, `lecture-5`
- Priority tags: `high-priority`, `weak-area`

---

## Principles of Effective Card Design

These principles are drawn from Piotr Wozniak's 20 Rules of Formulating Knowledge (the foundational research behind spaced repetition) and subsequent flashcard design research. They are the difference between cards that stick and cards that waste the learner's time.

### Understand before you memorize

Never create cards for material the user doesn't understand yet. If someone asks you to "make cards for this paper" but the concepts haven't been discussed or digested, help them understand first, then create cards. Memorizing without understanding is fragile — the knowledge can't be applied and decays rapidly.

### Minimum information principle

**This is the single most important rule.** Each card should test exactly one atomic piece of knowledge. The simpler the card, the easier it is to remember, the faster the review, and the more precisely the spaced repetition algorithm can schedule it.

Bad — tests multiple things at once:
> "What are the three types of joins? {{c1::INNER, LEFT, RIGHT}}"

Good — one card per join type:
> "A {{c1::LEFT}} JOIN keeps all rows from the left table, filling NULLs for non-matches"
> "An {{c1::INNER}} JOIN returns only rows that match in both tables"

When you find yourself putting a list into a single card, split it. Each item becomes its own card with enough context to stand alone.

### Use cloze deletion aggressively

Cloze deletion is almost always better than basic Q&A for factual content. It provides built-in context (the surrounding sentence), reduces the ambiguity of "what answer are they looking for?", and is faster to review. Default to cloze unless you have a specific reason to use Basic.

### Avoid sets and enumerations

"Name all 6 steps in the process" is a terrible card. If you forget one step, you fail the whole card and have to re-review all 6. Instead, create individual cards for each step:

> "In SQL clause order, {{c1::WHERE}} comes after FROM/JOIN and before GROUP BY"
> "In SQL clause order, {{c1::HAVING}} comes after GROUP BY and before ORDER BY"

If the ordering or grouping truly matters, use **overlapping cloze** to test adjacent pairs rather than the full list.

### Combat interference

When two pieces of knowledge are easily confused (e.g., `=` vs `==`, `RANK()` vs `DENSE_RANK()`, `ITT` vs `CACE`), create cards that explicitly contrast them. Put both on the same card with different cloze numbers so the learner practices distinguishing them:

> "{{c1::RANK()}} leaves gaps in ranking (1,2,2,4); {{c2::DENSE_RANK()}} does not (1,2,2,3)"

This forces the brain to build distinct memory traces rather than blurring them together.

### Optimize wording

Every word on the card should earn its place. Trim filler. Anki reviews happen thousands of times over months — even saving 2 seconds per card compounds enormously.

Verbose: "When you are writing SQL and you need to filter the results based on an aggregate function like SUM or COUNT, you should use the HAVING clause instead of the WHERE clause because WHERE is evaluated before grouping"

Tight: "Filter on aggregates with {{c1::HAVING}}, not WHERE — WHERE runs before GROUP BY"

### Use imagery and concrete examples

The brain encodes images far more durably than abstract text. When a concept can be tied to a vivid example, include it. Code snippets, concrete scenarios, and real data are better than abstract descriptions.

Abstract: "Window frames control which rows the function sees"
Concrete: "`ROWS BETWEEN 6 PRECEDING AND CURRENT ROW` = the current row + 6 prior rows (7-day moving average)"

### Provide sources and context in Back Extra

The `Back Extra` field on Cloze cards shows on the answer side. Use it for:
- Where this fact came from (textbook chapter, documentation section)
- A deeper explanation for cards where the cloze tests a surface fact
- A mnemonic or memory aid
- Related cards or concepts to connect to

This keeps the front of the card minimal (minimum information principle) while still providing the full context when needed.

### Redundancy is OK

Creating multiple cards that approach the same fact from different angles is not waste — it's **elaborative encoding**. Testing the same concept via cloze, a scenario question, and a "what's wrong with this code?" card creates multiple retrieval paths to the same memory.

### Add personal connection

Cards created from someone's own mistakes, their own practice problems, their own projects are dramatically more memorable than generic textbook cards. When building cards from a conversation where the user made errors, reference their specific mistake:

> "In SQL, use {{c1::IS NULL}}, not `ISNULL()` — ISNULL() is not a boolean check in Snowflake"

The implicit "I got this wrong once" is a powerful encoding signal.

---

## Cloze Card Syntax Reference

**Basic syntax:** `{{c1::hidden text}}` where `c1` is the cloze index.

| Pattern | Behavior |
|---|---|
| `{{c1::answer}}` | One card, one blank |
| `{{c1::A}} and {{c2::B}}` | Two cards — card 1 hides A, card 2 hides B |
| `{{c1::A}} or {{c1::B}}` | One card, both A and B hidden together |
| `{{c1::A::hint text}}` | Shows "hint text" instead of `[...]` when hidden |

**Hints:** `{{c1::Paris::capital of France}}` shows `[capital of France]` on the front instead of `[...]`. Use sparingly — hints reduce the difficulty of recall, which can reduce learning. They're useful for genuinely ambiguous cards.

**HTML in cards:** Anki renders HTML. Use it for readability:
- `<code>SELECT</code>` for inline code
- `<pre>` for code blocks
- `<b>` for emphasis
- `<br>` for line breaks
- `<ul><li>` if you must use lists (but prefer prose per minimum information principle)

**Special characters:** Escape `<` and `>` as `&lt;` and `&gt;` in card text to prevent HTML parsing issues (e.g., `x &gt; 5` not `x > 5`).

---

## Deck Organization

- **`Parent::Child`** for natural subcategories (max 2 levels)
- Keep decks focused — 5 decks of 40 cards beats 1 deck of 200 across unrelated topics
- Tags handle cross-cutting concerns better than deck hierarchy (a card can have many tags but lives in one deck)
- Respect the user's existing naming conventions when adding to their collection
- For time-boxed study (e.g., cramming before an interview), suggest a filtered deck that pulls from specific tags or due dates

---

## Proposing Cards to the User

Always propose the deck structure and a summary of the cards before creating them. Card quality is subjective and the user knows what they need to memorize better than you do. They might say "I already know that one, skip it" or "add more about X, that's where I'm weakest."

For small batches (<30), list each card. For large batches, summarize by category with counts and a few representative examples, then ask for approval.

When converting from an existing document or conversation, call out what you're skipping and why — "I left out X because it seemed like something you already have down cold. Want me to include it anyway?"

---

## Filtered Decks and Custom Study

If the user wants to study a specific subset of their cards (e.g., "just review my weak SQL cards"), use `anki__filtered_deck` to create a filtered deck with a search query. Useful queries:

- `deck:"Mozilla Interview::SQL" is:due` — due cards in a specific deck
- `tag:gotcha` — all cards with a specific tag
- `tag:gotcha -is:review` — new gotcha cards not yet reviewed
- `rated:1` — cards rated today
- `prop:lapses>3` — cards failed more than 3 times (leeches)

Filtered decks are temporary study sessions — cards return to their home deck after review.
