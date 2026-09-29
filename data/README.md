# data — collection

**Scope:** what was measured, and how to read it. A source pass touches only this part (and `docs/PASSES.md`).

## The data file: `raw-data.csv` (at the repository root)

It lives at the root because it is published with the page (`/raw-data.csv`). One row per measurement:

| Column | Content |
|---|---|
| `group` | the measurement group: one source, one task, one configuration (a leaderboard column, a system-card chart, a paper's table); a `#` prefix comments the row out |
| `source` | who published the number (a publisher's outlet; outlets of one organisation are merged by `publishers.json`) |
| `model`, `effort` | the couple; `effort` is read from the source's configuration, `default`/`nothink`/`priceblend` stay out of the fit |
| `task_type`, `complexity` | coding, agentic-tool, computer-use, reasoning-math, writing, or mixed for composites |
| `harness` | the agent or tool that ran the model (versions of one harness count as one configuration) |
| `unit`, `cost_usd`, `tokens_in`, `tokens_out`, `cached_pct` | the cost and its unit (per task, per run…) |
| `cost_prec`, `score_prec` | the reading precision of the cost and of the score: the standard deviation of the error made in reading the value off its source, in the value's unit (below) |
| `score`, `score_metric` | the score and its metric; the metric's label sets its scale (docs/METHODOLOGY.md §4) |
| `confound` | every doubt, as free-text flags (digitised, effort inferred, early access `EAP-run`, re-priced…) |
| `ref` | where the number comes from (URL, page, file) |

The admission rules are in docs/METHODOLOGY.md §2.

## Reading precision: `precision.py`, `precision/`

Every value carries the precision with which it was read (`cost_prec`, `score_prec`), which the model adds to the
row's variance. `precision.py` computes it: the rounding of a printed number (one unit of its last published digit
/ √12), the resolution of a chart that was digitised, the rounding of published token counts a cost was computed from.
Its inputs, checked source by source with quoted evidence (September 2026):

| File | Content |
|---|---|
| `precision/charts.json` | every digitised chart axis: units per pixel (recomputed from the tick coordinates), reading error in pixels (from an independent re-reading of its points), the rows read on it |
| `precision/origins.json` | per group: whether each value is printed, from a primary data file or computed, and the step of its last published digit |

A new row brings its precision: run `python3 data/precision.py` after adding rows (a printed value needs nothing
more; a digitised chart needs its entry in `precision/charts.json`).

## The catalogue: `catalog/`

What the data file needs to be read correctly, as data (read by `catalog.py`, used by the model and the site).

| File | Content |
|---|---|
| `models.json` | the models covered: label, colour variable, task-size flag; `order` (fit and grids) and `display_order` (legend) |
| `families.json` | groups that run the same benchmark (same task set, version and grading): republication detection and the panel |
| `publishers.json` | outlets of one organisation that publish its own measurements, merged into one publisher |
| `composites.json` | composite indices and the component groups they aggregate, with the publisher's documentation |
| `unit_aliases.json` | two labels one publisher uses for the same cost unit |
| `groups.json` | display label, edge type and verified configuration of each group in the sources table; `merge` folds a source's sub-benchmarks into one entry |

## Adding a source

Add its rows to `raw-data.csv` under a new `group`; if it runs a known benchmark, add the group to its family; if it
is a composite, list its components; give it a label in `groups.json`. Then refit (model/README.md): the site refuses
to build while the fit is stale.
