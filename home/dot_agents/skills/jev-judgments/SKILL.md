---
name: jev-judgments
description: "Use the configured native System 1 waterfall (Jev and OpenAI Decisions) mid-task for typed judgments: rank or filter files, search results, log chunks or candidates; classify a batch; check source support. It returns native probabilities and rubric scores, not generated prose. Follow the /system1 provider order: operational failures notify and try the next configured rung, never an unconfigured provider or chat imitation. Use for common-sense judgment over many items; not for implementing classifier software."
---

# System 1 judgments

The native System 1 waterfall reads text or JSON and answers typed questions with probabilities, not prose. `/system1` configures its order; our order is Jev then OpenAI Decisions. `~/.pi/agent/system1.json` holds the authoritative `waterfall` array, shared by sessions using that agent directory (`PI_CODING_AGENT_DIR` overrides the directory). A legacy `backend` selects a singleton; when written alongside a waterfall it is only a first-rung compatibility mirror. Missing settings default to Jev only; invalid settings fail without inventing an order. The legacy skill name remains `jev-judgments`.

Operational failures notify the user and advance only within that order. Valid negative/uncertain judgments and safety refusals do not shop providers. Account/credential/model failures cool down for five minutes; rate-limit/transport failures for 30 seconds. Notices are deduplicated. `/system1 status` distinguishes configured order from the last actual provider; `/system1 retry` clears this process's cooldowns without probing a model.

OpenAI means the native Decisions API, not a chat-model imitation and not subscription OAuth. Use its isolated `/login system1-openai` credential or `SYSTEM1_OPENAI_API_KEY` belonging to the organization linked to claimed Pro API credits. Credits-only use requires active included credits, no purchased balance, no auto-recharge and no paid continuation; Pi cannot verify funding. Do not claim credits, configure billing, or spend on a live check without authorization. Your ordinary subscription chat login remains separate.

## When it pays off

- **Many items, one judgment each.** Which of 40 files likely hold the auth logic? Which of 300
  grep hits are definitions, not calls? Which of 80 issues are bugs vs feature requests?
- **Long text, a few questions.** Does this 5,000-line CI log contain a real failure, and in
  which block? Is this PR description consistent with the diff?
- **Verification.** Is each claim in a draft supported by the cited passage? Does each option
  violate a stated rule?
- **Picking from candidates you already have.** The classifier selects; it cannot invent a value. Find the
  candidates in code (grep, ls, a parsed list), then let it choose or score them.

Do it yourself instead when there are only a handful of items, when the answer needs exact
computation (use code), or when you need an explanation.

## How to call it

### In Pi: codemode (preferred)

Call `system1_judge` directly or through `codemode` tools. It follows the suite's configured order and returns the actual winning backend/provider/model, fallback/attempt provenance, typed answers and aggregate reported usage. If the tool is absent, ask to enable/update `pi-system1`; do not bypass the switch with a hardcoded TypeSafe model. An exhausted chain is not permission to try an unconfigured billable provider. Do not fabricate confidence, seek another provider after a valid denial, or replace native classification with chat.

```js
const files = ["src/auth/session.ts", "src/db/schema.ts", "README.md"]; // candidates from code
return await tools.system1_judge({
  state: { task: "Find where login sessions are created", files },
  questions: Object.fromEntries(files.map((f, i) => [`f${i}`, {
    type: "bool",
    instructions: `Is \`files[${i}]\` likely to contain the code for \`task\`?`,
    criteria: { true: "Likely contains it", false: "Unrelated" },
  }])),
});
```

Inspect the result for failure before using its answers. Read its actual winner and `fallback`/`attempts`, not just the preferred order. Native probability distributions support ranking; they are uncertain judgments, not proof of relevance. Reported usage aggregates failed and successful attempts; do not add per-attempt usage a second time. Dollar cost is a catalog estimate, not a verified charge or free-credit debit.

Question types (Pi's names):

| type | criteria | answer |
|---|---|---|
| `bool` | `{ true: "...", false: "..." }` | `{ probability }` (of true) |
| `choice` | `{ label: "meaning", ... }` (up to 255 labels) | `{ choice, probabilities, confidence }` |
| `score` | `["lowest level", ..., "highest level"]` | `{ score, confidence }` (expected level index) |

`state` must be a JSON object. Read the full API in Pi's `docs/codemode.md` ("Classify").

### Elsewhere (Claude Code, Codex, or a shell): jev-ask

`~/.local/bin/jev-ask` retains its legacy name but follows the same System 1 order. Pass JSON on stdin; stdout remains JSON and fallback notices go to stderr. A singleton Jev order preserves the standalone raw helper and `TYPESAFE_API_KEY` requirement. Every mixed/OpenAI order delegates to the installed suite CLI and its isolated credentials, without requiring a TypeSafe environment key before a configured fallback can run. The legacy `noul` type and nonobject state normalize to Pi's bool/object contract. A missing installation fails visibly, never through an out-of-chain raw retry. Experimental TypeSafe `box`, `assets`, `long_context`, and request-level model overrides require a singleton Jev order and are rejected before mixed-chain calls.

```bash
~/.local/bin/jev-ask <<'JSON'
{
  "state": {"log": "...last 200 lines of the failing job..."},
  "questions": {
    "real_failure": {"type": "noul", "instructions": "Does `log` show a test or build failure rather than a flaky network error?"},
    "kind": {"type": "choice", "instructions": "What kind of failure is in `log`?",
             "criteria": {"test": "A test assertion failed", "build": "Compilation or bundling failed", "infra": "Network, runner, or dependency download problem", "none": "No failure"}}
  }
}
JSON
```

## Writing good questions

- **One narrow judgment per question.** Split "is this relevant and correct?" into two.
- **Name the part of the state** with backticked paths: `files[3]`, `ticket.messages[0].text`.
- **Send only what the question needs.** Unrelated text lowers accuracy. Pre-filter in code
  (grep, head/tail, error lines) before sending a huge log; keep each request under ~24k tokens.
- **Ask independent questions together.** All questions in one request see the same state and
  run in parallel; per-item questions (`f0`, `f1`, …) in one request are cheaper than many requests.
- **Give `choice` a way out** ("none", "other") when nothing may fit.
- **Read probabilities, not just winners.** A `bool` near 0.5 means unsure, not "medium". Pick
  thresholds by consequence: act at 0.8+ when a mistake is costly, rank and take the top few when
  it is cheap. When it matters, verify the classifier's top picks yourself.

## Reporting

Treat classifier answers as evidence for your own decision, not as facts to quote. When you act on them, name the actual backend briefly ("OpenAI Decisions ranked these 3 of 40 files after Jev was unavailable; I read them"). Avoid repeating a notice already shown for every item. Never label a fallback answer as the preferred provider, imply identical confidence calibration, or infer API-credit funding from subscription chat quota.
