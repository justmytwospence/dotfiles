---
name: jev-judgments
description: "Call TypeSafe's Jev yourself, mid-task, for fast typed judgments instead of reading or reasoning through everything: rank or filter many files, lines, search results, log chunks, or candidates; classify a batch of items; check whether claims are supported by a source; triage a long tool output. Jev answers yes/no, multiple-choice, and 0-N score questions with probabilities in ~250 ms for a tiny fraction of a cent. Use when a step needs common-sense judgment over many items or long text but no generated prose. Not for writing software that uses TypeSafe (that is the typesafe-ai skill)."
---

# Jev judgments

Jev (TypeSafe's System One model) reads text or JSON and answers typed questions with
probabilities. It never writes prose. Use it as a cheap, fast, parallel judge so you spend your
own reasoning only where it matters.

## When it pays off

- **Many items, one judgment each.** Which of 40 files likely hold the auth logic? Which of 300
  grep hits are definitions, not calls? Which of 80 issues are bugs vs feature requests?
- **Long text, a few questions.** Does this 5,000-line CI log contain a real failure, and in
  which block? Is this PR description consistent with the diff?
- **Verification.** Is each claim in a draft supported by the cited passage? Does each option
  violate a stated rule?
- **Picking from candidates you already have.** Jev selects; it cannot invent a value. Find the
  candidates in code (grep, ls, a parsed list), then let Jev choose or score them.

Do it yourself instead when there are only a handful of items, when the answer needs exact
computation (use code), or when you need an explanation.

## How to call it

### In Pi: codemode (preferred)

`codemode` scripts reach Jev through Pi's own classifier models, with Pi's credentials, and
the cost counts toward the session. Up to four calls run at once per script; `Promise.all` over
many items is fine.

```js
const jev = await models.getModelOfType("classifier", "typesafe", "jev-latest");
const files = ["src/auth/session.ts", "src/db/schema.ts", "README.md"]; // candidates from code
const r = await models.classify(jev, {
  state: { task: "Find where login sessions are created", files },
  questions: Object.fromEntries(files.map((f, i) => [`f${i}`, {
    type: "bool",
    instructions: `Is \`files[${i}]\` likely to contain the code for \`task\`?`,
    criteria: { true: "Likely contains it", false: "Unrelated" },
  }])),
});
if (r.stopReason !== "stop") return r.errorMessage; // classify never throws; check stopReason
return files.map((f, i) => [f, r.answers[`f${i}`].probability]).sort((a, b) => b[1] - a[1]);
```

Question types (Pi's names):

| type | criteria | answer |
|---|---|---|
| `bool` | `{ true: "...", false: "..." }` | `{ probability }` (of true) |
| `choice` | `{ label: "meaning", ... }` (up to 255 labels) | `{ choice, probabilities, confidence }` |
| `score` | `["lowest level", ..., "highest level"]` | `{ score, confidence }` (expected level index) |

`state` must be a JSON object. Read the full API in Pi's `docs/codemode.md` ("Classify").

### Elsewhere (Claude Code, Codex, or a shell): jev-ask

`~/.local/bin/jev-ask` sends one request (JSON on stdin) and prints the answers. It uses the
API's own names: `noul` instead of `bool`, and `state` may be a string. Needs `TYPESAFE_API_KEY`.

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
  it is cheap. When it matters, verify Jev's top picks yourself.

## Reporting

Treat Jev's answers as evidence for your own decision, not as facts to quote. When you act on
them, say so briefly ("Jev ranked these 3 of 40 files as likely; I read them").
