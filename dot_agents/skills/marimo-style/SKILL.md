---
name: marimo-style
description: "Spencer's house rules for marimo notebooks: how changes are made (only through the marimo-pair skill, never by editing the .py file), how much at a time (one finished piece, then stop for feedback), and how the notebook reads (markdown and code in separate cells, unwrapped prose, short headings, marimo widgets where they help). Load this whenever a task touches a marimo notebook (creating, editing, extending, reviewing, or pairing on a live session), before or alongside marimo-pair. marimo-pair does not reference this skill, so load it on your own. Not a replacement for marimo-pair, which supplies the mechanics."
---

# marimo house style

These rules sit on top of the `marimo-pair` skill. marimo-pair says how to drive a live notebook;
this skill says how Spencer wants that done. Where they overlap, follow the stricter one.

## Load marimo-pair first

marimo-pair is installed per project, not globally. Before touching a notebook, load the
project's `marimo-pair` skill. If it is not available in this project, stop and tell the user
rather than working around it; offer to install it in the repo root with:

```sh
npx skills add marimo-team/marimo-pair -s marimo-pair -a codex claude-code -y
```

## Change notebooks only through marimo-pair

Every change to a notebook goes through marimo-pair's `execute-code` script and
`marimo._code_mode` (`cm`): creating, editing, moving, running, and deleting cells, adding
packages, setting UI values. No exceptions, including:

- No `Edit`, `Write`, `NotebookEdit`, or any equivalent on the notebook `.py` file.
- No shell workarounds that amount to the same thing: `sed`, `perl`, heredocs, `python -c` or
  scripts that rewrite the file, `git checkout`/`git apply` on it, `marimo convert` over it.
- Not even for "just a typo", a one-line fix, or a change the user dictated verbatim.
- Not when no session is running. Then start or find one as marimo-pair describes and make the
  change through it. Never treat "no live kernel" as permission to edit the file.

Reading the file from disk is fine, though `ctx.cells[...].code` is the current truth. If
marimo-pair cannot do something, say so and ask; do not fall back to editing the file.

## Deliver one piece at a time

By default, work on one piece at a time and stop for feedback before starting the next: one
chart, one table, one step of the analysis, or a small group of cells that only make sense
together. Do not build out a whole analysis, section, or dashboard in one pass. The user can
override this by asking for more at once.

Within that piece, iterate as much as needed to hand over something that works and looks right.
Run the cell, inspect the output (render the chart, check the table), and fix what is broken:
errors, empty or wrong data, overlapping or cut-off labels, unreadable scales, bad sizing. Only
then present it.

What you must not do is decide on your own that the piece is good and move on. Once it is
presentable, stop and wait for the user's verdict before adding the next chart, the next
analysis step, or follow-up changes. This applies most to visual output, but to analysis too.

## Keep markdown and code in separate cells

- Prose goes in markdown cells: a cell whose only job is `mo.md(...)`. Put it in its own cell
  next to the code it explains.
- Do not squeeze prose into code cells: no explanatory `mo.md` stacked with a chart via
  `mo.vstack`, no paragraphs of narrative in comments, no docstring essays. Short code comments
  that explain code are fine.
- A markdown cell may interpolate values (`mo.md(f"...")`) when the text depends on results, as
  long as the cell does nothing but render that markdown.
- `mo.vstack`/`mo.hstack` are for UI composition (a control next to the output it drives), not
  for attaching narrative to code.

## Do not hard-wrap markdown

Write each paragraph or list item as a single line and let the renderer wrap it. No manual line
breaks inside a paragraph to keep source lines short.

```python
mo.md(r"""
## Seasonality

Weekly sales peak in late November and again before Christmas, so the model needs a holiday effect on top of the yearly cycle.
""")
```

## Names: short headings, explanatory chart titles

- Sections and subsections get short, descriptive headings: "Data", "Seasonality", "Model fit",
  "Residuals". Not sentences, not findings.
- Charts can be a bit longer and say what they show: "Weekly sales by region, 2023-2024",
  "Posterior predictive vs observed demand". Still short; the explanation goes in a markdown
  cell.

## Use marimo widgets where they help

Reach for marimo's own UI when the user would plausibly want to explore rather than read a fixed
answer:

- `mo.ui.slider`, `mo.ui.dropdown`, `mo.ui.radio`, `mo.ui.date_range` for parameters someone will
  want to vary (a window size, a region, a date range, a model choice).
- `mo.ui.table` or `mo.ui.dataframe` for data the user will browse, filter, or select rows from.
- `mo.ui.altair_chart` / `mo.ui.plotly` when selecting points on a chart should drive later cells.
- `mo.ui.tabs` or `mo.accordion` to compare alternatives or tuck away detail.
- `mo.ui.run_button` or `mo.ui.form` to gate expensive recomputation.

Do not widget-ify everything: a value that will never change stays a constant. Define each
widget in its own cell and read `.value` in the cells downstream, so changing it reruns only
what depends on it. Set widget values through `cm` as marimo-pair describes.
