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

## Long runs and servers

- A marimo-pair `execute-code` call returns only when the cells it ran have finished. For a run that takes more than a minute or so, start the same call as a pi-bg job (`bg_run`, `kind: "job"`) and `bg_wait` on it, rather than a plain bash call that may time out.
- While that run is going the kernel is busy: any other `execute-code` call to the same notebook, even a `print`, waits behind it and looks hung. Wait for the run instead, or read the notebook state pi-marimo adds to the prompt.
- Stopping the job (`bg_kill`) stops only the client. The cells keep running until they finish or are interrupted from the notebook.
- Start a marimo server as a pi-bg service with `--no-token` and without `--headless` (marimo-pair needs the notebook open in a browser), and `keep: true` when it is the server the user works in, so it outlives the pi session. pi-bg names it after the notebook and knows it is up from its URL line; no `ready` is needed.
- With pi-marimo installed, `bg_wait` on that server's id waits for whatever cells are running in its notebook, however they were started (the browser included).

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

## Look at visual output

marimo-pair's `execute-code` returns only text, so a chart is not checked until you have seen it as an image. After a change that affects a figure, save it to a PNG from the scratchpad and open it with `read`. Pi shows the image inline, so the user sees what you saw.

Never open, screenshot or drive a marimo notebook or MarimoHub through `telebrowser`, `terminal-browser`, `chrome_live` or any other browser automation; Spencer opens notebooks himself. When the kernel is remote (a MarimoHub sandbox, whose `/tmp` the host cannot `read`), check a chart by rendering the same cell code locally against the same data (for example the host's read-only DuckDB snapshot) and reading that PNG.

```python
import tempfile, pathlib
path = pathlib.Path(tempfile.gettempdir()) / "marimo-look" / "seasonality.png"
path.parent.mkdir(exist_ok=True)
fig.savefig(path, dpi=80, bbox_inches="tight")  # arviz: ax.figure (or axes.flat[0].figure)
print(path)
```

- matplotlib, seaborn and arviz: use the cell's figure (`fig`, `ax.figure`, `g.figure`), not `plt.gcf()`, which is not the cell's figure in the scratchpad. Altair needs `vl-convert-python` (`chart.save(path)`), plotly needs `kaleido` (`fig.write_image(path)`); if neither is installed, ask before adding it.
- Keep images modest, about 1000 px wide (`dpi=80` at a normal figure size). Each image stays in the context at roughly width x height / 750 tokens and is re-sent every turn.
- Look after a visual change, not after every run, and judge it: overlapping or cut-off labels, empty panels, unreadable scales, wrong sizing. Fix and look again before presenting.
- When you present the piece, show the final image once, so the user can judge it without switching to the browser.
- Write PNGs only to the temp directory: never into the repo, and never add the export to the notebook's cells.

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

## Interactivity that survives a static export

Notebooks that get shared are published as static HTML (`marimo export html`) with no kernel
behind them. A `mo.ui` input there only sends its value to Python, so with nothing running,
moving it changes nothing. When a notebook is shared, or likely to be, choose by what the
reader's choice has to do:

- **A small fixed set of choices** (a person, a protein, a model variant): draw every choice
  in one cell and show them with `mo.ui.tabs` (or `mo.accordion`), not a dropdown driving a
  downstream cell. Switching tabs happens in the browser, so it works in the export. Wrap the
  drawing in a function, close each matplotlib figure, and keep the option list to plain
  values:

  ```python
  def _draw(_who):
      _fig, _ax = plt.subplots()
      ...
      plt.close(_fig)
      return mo.as_html(_fig)

  mo.ui.tabs({_w: _draw(_w) for _w in OPTIONS})
  ```

  Every panel is embedded, so keep it to tens of options, not hundreds.
- **Filtering or highlighting one chart:** an Altair chart with its own selector
  (`alt.binding_select`, `alt.param`) over a small summary table. The browser does the
  filtering, so it also works with no kernel.
- **Real recomputation from cheap inputs** (sliders feeding a formula or a small simulation):
  only if the notebook imports nothing heavy, a WASM app export (`marimo export html-wasm
  --mode run --execute` with `cache_cells = true`). Not for notebooks that need PyMC, nutpie,
  torch or large fits.
- **Recomputation that needs heavy libraries or fits:** leave it out of the shared page.
  Show the precomputed cases instead. Do not build server-side apps or ship fits to a server
  to make it live.

Keep an ordinary `mo.ui` widget wherever the input only matters while working (a
diagnostic, a scratch knob, a gated rerun). In those cells the exported page shows the
default value, which is fine.
