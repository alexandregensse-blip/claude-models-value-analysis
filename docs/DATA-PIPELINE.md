# Data pipeline: findings, registries, decision tree (proposal v2, 22 Oct 2026)

Status: **draft — reviewed once (/work/.salvo14/review-pipeline/review.md), revised; no code is written against it yet.**

The data the fit reads becomes a **computed table**, built by one script from what agents write (the **findings**: what
a source says) and what we define (the **registries**). **Agents write facts only.** The model, the effort, every
certainty level and every status are **computed by the build** from the facts and the registries; nobody sets them by
hand, except the maintainer's own per-measure decisions, which live in one file and are cited by id.

```
data/findings/sources/<source-id>.json   one source snapshot: its words, as facts with proofs        ← salvo agents
data/findings/measures/<source-id>.json  which facts form one measure, and on which setup          ← salvo agents
data/registry/models.json                models, names served over time, efforts, defaults, conversions, modes (dated)
data/registry/routes.json                routers and harnesses: the levels they accept and how they map them (dated)
data/registry/benchmarks.json            families, setups, headline metrics, composites (formula)
data/registry/publishers.json            publisher → maker (home effect)
data/registry/prices.json                dated prices per model and route, as_of pinned
data/registry/rules.json                 the deduction rules the build applies
data/registry/vocab.json                 closed vocabularies (fact types, cost bases, cost methods, units, anomalies, effort ids)
data/registry/flag-map.json              legacy: confound flag → fact/level (migration only, versioned, tested on every row)
data/decisions.json                      the maintainer's per-measure decisions (selector, status, reason, date)
build/fit-table.csv                      computed: the rows the fit reads (today's raw-data.csv columns + status columns)
build/status-report.json                 computed: every measure, its status per axis, its reason, and the diff to the last build
```

Saved pages, dumps and clones stay outside git in the salvo folders, which are kept; git keeps the URLs, the Wayback
captures, the sha256 of each saved file and the extracted facts.

---

## 1. Certainty levels (of a fact, and computed for each measure field)

| Level | Meaning | Tree |
|---|---|---|
| `written` | the source states it: a printed number (also a number printed on an image), a data-file value, a code or config line at the run's commit, an API id, a label | accepted |
| `read` | measured off a chart's geometry (pixels; vector paths are `written`, exact) | accepted; its reading sd enters the value's precision |
| `computed` | produced by the build with a rule of rules.json from accepted inputs | accepted when every input is accepted; the precision is propagated by the rule's formula |
| `source-estimate` | a value the source did not measure on this run: imputed, projected, filled, an "estimated" index | refused (`out:estimate`) |
| `not-established` | `absent` · `assumed` (plausible, unproven) · `contradictory` (the source states two things) · `ambiguous` (a rule gives two answers, e.g. a router tie) | refused, with the reason |

A cost the source computed from **this run's own tokens** at a stated price is `written`, basis `list-estimate` — not a
`source-estimate`. Each measure field (model, effort, run date, value, setup fields, each usage class, the price) gets its
own level; a measure is in only if every field the tree reads is accepted.

Attributes kept next to the value, never levels: the **precision model** (`printed` step from the digits · `chart-pixel`
reading sd · `exact`), the **route**, **restated-from** (with its own level), **anomalies** (with their own level).

---

## 2. Source file

```json
{"id": "src-<publisher>-<what>-<YYYY-MM-DD>", "publisher": "<publishers.json id>",
 "urls": ["…"], "wayback": ["…"], "commit": "<repo commit or null>", "sha256": {"<saved file>": "<hash>"},
 "harvested_at": "<ISO datetime UTC>", "salvo": "…", "agent": "…",
 "snapshot_of": "<earlier source id of the same board, or null>",
 "facts": [
  {"id": "F1", "says": "<vocab fact type>", "about": "<the source's entry name, verbatim>", "value": "<verbatim>",
   "level": "written|read|source-estimate|not-established:<reason>",
   "where": "<locator>", "quote": "<exact text, original language; required for prose and labels, optional for data files>",
   "translation": "<English, when not English>"}
 ],
 "tables": [{"id": "T1", "file": "<saved file>", "where": "<JSON path / CSV / table locator>", "columns": {…}}]
}
```

A data file is proven by its sha256 and a locator (a `tables` entry stands for all its cells); a quote is required for
prose, labels and code. Fact types (vocab.json): `score`, `metric-definition`, `headline-metric`, `cost`, `currency`,
`cost-unit`, `cost-basis`, `cost-method`, `price-table`, `tokens-in`, `tokens-out`, `tokens-cache-read`,
`tokens-cache-write-5m`, `tokens-cache-write-1h`, `tokens-reasoning` (+ `reasoning-included-in-out`), `cached-share`,
`requests` (number of calls, for per-request tiers), `per` (task · run · suite · 1k calls), `model-name`, `model-api-id`,
`route`, `mode` (e.g. `reasoning.mode=pro`), `effort-label`, `effort-setting` (the parameter actually sent),
`no-effort-sent`, `thinking-budget`, `tools-regime`, `run-date`, `run-id`, `early-access`, `version`, `harness`, `judge`
(per row when it varies), `aggregation` (mean of n runs, which runs), `failure`, `restated-from`, `evaluated-by`,
`component-of` (with weights). Optional, never read by the tree: `items`, `attempts`, `note`.

## 3. Measure file

The agent groups the facts that make one measure and names the setup; it does **not** write our model key, effort or
levels.

```json
{"source": "src-…",
 "measures": [{"id": "M1", "setup": "<benchmarks.json setup id>", "campaign": "<run id / board version, or null>",
   "facts": {"value": "F1", "model": ["F2"], "effort": ["F3"], "run_date": ["F4"], "usage": ["F5", "F6"],
             "spend": ["F7", "F8", "F9"], "judge": null, "anomalies": [], "restated_from": null},
   "verified": {"by": "…", "at": "…", "rederived": true}}]}
```

The build computes from these: `model.id` (names served at the run date), `mode`/`line` key, `effort.id` (rules below),
every level, the run-date interval, the cost value and its subset, and the status.

---

## 4. Registries

**models.json** — the only keys. Per model: label, maker, `released` (datetime), `line`, `open_weights`; `names`: each
name (API id or display name) with the model it **serves** over a dated interval; `efforts`: the accepted levels over
dated intervals; `solo_means` (the single configuration `solo` denotes, for models without an effort parameter or with
thinking always on); `thinking`: `levels | on-off | always | none`; `default`: level per dated interval; `conversions`:
requested → served, per route, per dated interval; `modes`: request parameters that select another key (Pro → `<id>-pro`).
Dated intervals everywhere are `{from, to, evidence_from, evidence_to}`: `from` = the earliest capture showing it, `to` =
the last capture still showing it (null if current); a gap between captures is **not covered**.
Build-time identity checks: two keys of one maker whose names serve the same API id over overlapping intervals, or
identical display names, fail the build until resolved (merge, or a dated `serves`).

**routes.json** — per router (OpenRouter, Vercel AI Gateway, Bedrock…) and harness (Inspect, Pi, Claude Code, Codex
CLI, IronBee…): dated `supported_efforts` per model, the mapping rule (OpenRouter: nearest supported level, ties
`ambiguous`; on a model without an effort parameter the effort becomes a token budget → `budget-converted`), the
router's own documented default per model and date.

**benchmarks.json** — `family` (one benchmark across publishers) ⊃ `setup` (benchmark × version × subset × harness ×
tools regime × judge panel × metric) ; per setup: headline metric (the source's designated one; if none, the metric the
source ranks by; else a decision), bounds, direction, task type, complexity; composites: components, formula (weights,
normalisation), validated on complete couples, linear or not.

**publishers.json** — publisher → the maker it belongs to, or none.

**prices.json** — per model and route: list prices per token class (input, output, cache read, cache write 5m and 1h),
long-context tiers with their per-request threshold, promotions (recorded, flagged, never a base; their display on the
site is set aside for now), batch and flex factors; each with its evidence and dated interval. `as_of` is pinned per
build. The **base route** of a model is its maker's API. The **base price** is the standard list price in force on
`as_of`; for a model whose standard price never applied (sold only at its launch price until withdrawn: Gemini 3.7
Flash), the price actually charged.

**rules.json** — each rule: id, inputs, output, conditions, precision formula. Set: `alias-by-date`, `mode-to-line`,
`label-to-ladder`, `maker-conversion-dated`, `route-mapping-dated`, `api-default-documented` (code shows nothing sent at
the run's commit; the maker's API directly, or a router whose dated documented default is known; the default's interval
covers the run; the run date known), `no-effort-setting` (→ solo), `thinking-off` (→ nothink), `mean-of-runs` (failed
runs excluded), `percent-from-counts`, `composite-residual`, `cost-from-tokens`, `cost-publisher-figure`,
`cost-uniform-factor` (a proven uniform factor: Flex = ½, a uniform cut), `cost-class-ratio` (the class-median ratio of
METHODOLOGY §2, its spread added to the precision), `chart-reading`, `currency-fixed` (no conversion: a non-USD cost
stays in its own subset).

**decisions.json** — `{id, selector (source/setup/model/effort or measure ids), axis, status, reason, date, by}`; cited in
the status as `in:decision:<id>` / `out:decision:<id>`.

---

## 5. Decision tree

### 5.1 Facts → fields (build)
- **Model**: `names` resolves the model-name/API-id fact at the run date. The run-date interval must lie inside one
  `serves` interval; straddling a switch → `not-established:ambiguous`. `mode` facts map to the line key (`modes`); a
  route that cannot separate a mode (Pro via a router that does not say) → `not-established:absent`.
- **Effort**, first match wins:
  1. `effort-setting` written at the run's commit, at a level the model accepts at the run date → that level;
  2. an `effort-label` equal to a level name of the model's ladder → that level (`written`);
  3. an `effort-label` in other words → `label-to-ladder` when the maker's ladder makes it unique;
  4. a requested level the model does not accept → `maker-conversion-dated` (direct route) or `route-mapping-dated`
     (router/harness); the conversion's interval must **cover** the run-date interval;
  5. `no-effort-sent` → `api-default-documented`; the default's interval must cover the run-date interval;
  6. a model without effort parameter / thinking always on → `solo` (`solo_means`); thinking off → `nothink`;
  7. otherwise: `thinking-budget` → `think-<budget>`; a numeric scale (DeepSeek 1–100) → `scalar-<n>`; a router budget →
     `budget-converted`; `default` stated without a known default → `default`; nothing → `unstated`.
  Effort ids and statuses: `low medium high xhigh max solo` → ladder; `minimal nothink think-* scalar-* budget-converted
  enabled default unstated` → `out:effort-outside-ladder` or `out:effort-not-established`. A tools regime (`nt-*`) is
  part of the setup, not the effort.
- **Run date**: interval `[max(released, earliest evidence), min(run-date fact, publication, capture, commit)]`, as
  datetimes. Needed only when a dated event of the model (a `serves` switch, a conversion/default interval edge, a price
  change for the cost) falls inside `[released, upper bound]`.
- **Early access**: an `early-access` fact, or a run-date upper bound before `released`.

### 5.2 Quality axis (per measure; the first failing step gives the status)
1. **Proof**: every fact used has a locator (and a quote where required) → else `out:no-proof`.
2. **Model** accepted → else `out:model-not-established`.
3. **Effort** in the ladder → else `out:effort-outside-ladder` / `out:effort-not-established`.
4. **Value**: `written`/`read`/`computed`; `source-estimate` → `out:estimate`; an anomaly `written` (failed, partial,
   errored) → `out:failed-run`; an anomaly `assumed` (inferred failure) → `out:anomaly-assumed`; `contradictory` →
   `out:contradictory`.
5. **Metric**: the setup's headline metric; another metric of the same run is the same execution (one measure).
6. **Campaign**: two snapshots of a board are linked by `snapshot_of`. Same `run-id`, or same run date with the value
   unchanged → **continuation**: the latest value is kept, the earlier recorded as `prev`. Re-run (new run id or run
   date) → a new campaign. A regrade of the same runs is a new setup sharing the execution (its cost counts once).
7. **Composites**: a couple with **any** component measured loses the composite; a linear composite with part of its
   components measured keeps only its `composite-residual` (setup = composite × missing set × capture; residuals of an
   estimated index refused); a non-linear composite (Epoch ECI) is kept whole only for couples with no component.
8. **Republication**: `restated-from` (accepted) → the original is kept; if it is not in the data, the restatement, with
   home = (original publisher = maker); identical values across groups beyond chance (lqm.load's rule) count once.
9. **Decision** (`decisions.json`) overrides, cited.
10. **Group** = setup × publisher × campaign, with ≥ 2 accepted couples → `in`; else `out:single-couple`.

### 5.3 Cost axis
Steps 1–4 and 6–10 of 5.2 apply (estimates, failed runs, composites and republication included). Then:
1. **Cost value at the base price**, first that applies: the publisher's own figure at today's price; the run's tokens per
   class × the base price (`cost-from-tokens`; per-request long-context tiers only when `requests` and per-call sizes are
   known, else the measure is not re-priceable); a stated cost rescaled by the old→base price factor when the price at
   the price date is known (`cost-uniform-factor` or the per-class factor on the run's tokens); `cost-class-ratio`;
   otherwise the cost stays at its own basis, **unrepriced**, for step 2.
   `price_date` = the date of the prices the source applied: the run date for a billed spend; the capture/reading date for
   a source that recomputes at its current price (AA); the stated date for a list estimate.
2. **Partition**: the setup's measures are split by `basis` × `method` × `unit` × `currency` × `route` (closed
   vocabularies). Within a part, the re-priced measures form one subset; the unrepriced ones form one subset per model,
   and only when the model's price change over the price-date interval is uniform across token classes, or its class
   tokens are known (its efforts' ratios then hold); measures with no known price over their interval and models whose
   change is not uniform → `out:cost-not-comparable`.
3. A subset with fewer than 2 couples → `out:cost-single-couple`. `subscription` / flat CLI billing →
   `out:cost-basis`.
4. Promotions and off-peak prices are never the base.

The cost group = group × subset.

---

## 6. The fit table and the fit

Phase 1 (this redesign): the build writes `build/fit-table.csv` with today's `raw-data.csv` columns — group (setup ×
publisher × campaign [× cost subset]), source, model, effort, task_type, complexity, harness, unit, cost_usd,
cost_prec, tokens, score, score_metric, score_prec, cached_pct, confound (flags regenerated from the facts: home,
restated-from, evaluated-by, EAP-run, reading sd, `prev`…), ref — for every measure `in` on at least one axis (the other
axis' value kept when known, since republication detection uses it), plus `status_quality`, `status_cost`. `lqm.load`
reads it unchanged; steps 7–8 (composites, republication) and the homogeneity split stay in `lqm.load` in phase 1, and
its report is written back into the status report (so they run once). Phase 2 may move them into the build.
Site fields (label, colour, order, display order, group labels, unit aliases) stay in the site's registry.

## 7. Validation

- Schema: every file against its schema and vocab.json; every key in a registry; identity checks of models.json.
- Re-derivation by verifier agents: for every measure `in`, or changing status, each number re-derived from the saved
  file; a mismatch makes the fact `contradictory`.
- Precheck fails when a measure `in` lacks an accepted model, effort, value or (when an event is in its window) run date;
  reports counts per reason, and the status diff to the last build.

## 8. Migration

1. **Legacy facts**: each `raw-data.csv` row becomes a source fact set whose proof is `legacy` (the row's `ref` and its
   confound text), accepted by step 1 only until that row's source is converted; `flag-map.json` maps the confound flags
   (4,571 distinct prefixes) to facts and levels, versioned and tested on every row, with a report of unmapped prefixes.
2. **prices.json** filled for every model in the fit before the first cost build (79 models have no price history today);
   `as_of` pinned.
3. First build; the status report lists, per source, the measures of today's fit that become `out:*-not-established`
   (≈ 3,780 ladder rows carry no recognisable effort proof today: anthropic-syscard, artificialanalysis, vals.ai…).
4. Agents convert sources to real source/measure files, worst sources first, re-reading the saved copy or the live
   source where a fact is missing; legacy proof retires source by source.
5. Rebuild; before/after against v2026.10.21; the maintainer's yes before any fit.
