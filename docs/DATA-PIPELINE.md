# Data pipeline: findings, registries, decision tree (proposal, 22 Oct 2026)

Status: **draft for the maintainer's validation — no code is written against it yet.**

The data the fit reads (`raw-data.csv` today) becomes a **computed table**. It is built by one script from two inputs that
people and agents write: the **findings** (what a source says, and the measures we draw from it) and the **registries**
(what we define: models, efforts, benchmarks, publishers, prices, rules). Nobody sets a row's status by hand any more
(no `#` group, no `req-*` label): the decision tree below computes it, with a reason.

```
data/findings/sources/<source-id>.json    what one source says (facts, each with its proof)        ← salvo agents
data/findings/measures/<source-id>.json   the measures drawn from those facts (our keys, our rules) ← salvo agents, verifiers
data/registry/models.json                 models, aliases (dated), effort ladders and defaults (dated)
data/registry/benchmarks.json             benchmarks and setups: headline metric, bounds, task, composites (formula)
data/registry/publishers.json             publishers, the maker they belong to (home effect)
data/registry/prices.json                 dated list prices per model (classes, tiers, promotions, routes)
data/registry/rules.json                  the deduction rules a measure may cite
build/fit-table.csv                       computed: one row per accepted measure, per axis, with its status and reason
build/status-report.json                  computed: every measure, accepted or not, and why
```

Saved pages (HTML, PDF, JSON dumps, clones) stay **outside git** (salvo folders); git keeps their links, their Wayback
address, their sha256 and the extracted facts with their quotes.

---

## 1. Certainty levels

Every fact and every measure field carries one level. A level exists only because the tree treats it differently.

| Level | Meaning | Tree |
|---|---|---|
| `written` | the source states it in its own words: a printed number, a data-file value, a code/config line at the run's commit, an API id, a label | accepted |
| `read` | read off a chart or an image | accepted; the reading precision enters the uncertainty |
| `computed` | obtained by a rule of `rules.json` from accepted inputs (mean of runs, percent from counts, residual of a composite, tokens × price, alias resolved by date, label translated by the maker's ladder, maker conversion dated before the run, router mapping, documented default) | accepted when the rule is registered and every input is accepted; worth its weakest input |
| `source-estimate` | the source's own estimate, imputation or projection (an AA "estimated" index, a projected score) | refused: not a measurement |
| `not-established` | with a reason: `absent`, `assumed` (plausible, not proven), `contradictory` (the source states two things) | refused; the reason tells the next search |

Not levels but attributes, kept next to the value: the **precision** (printed step, reading sd), the **route** (direct,
router, self-hosted, quantized), **restated-from** (the value is another source's: counted once, home effect), and
**anomalies** (failed or partial run, errors, truncation).

---

## 2. Source file — what the source says

One file per source snapshot. It holds the source's words only: no key of ours, no interpretation.

```json
{
 "id": "src-<publisher>-<what>-<YYYY-MM-DD>",
 "publisher": "<publishers.json id>",
 "urls": ["<the page / data file / repo URL>"],
 "wayback": ["<web.archive.org capture>"],
 "commit": "<repo commit, when the source is a repo>",
 "sha256": {"<local file name>": "<hash>"},
 "harvested_at": "<ISO datetime UTC>",
 "published_at": {"value": "<date or interval>", "level": "written", "where": "...", "quote": "..."},
 "salvo": "<salvo id>", "agent": "<agent id>",
 "facts": [
  {"id": "F1", "says": "<fact type>", "about": "<the source's name for the entry, verbatim>",
   "value": "<verbatim>", "level": "written|read|source-estimate|not-established",
   "where": "<locator: table/row/column, JSON path, file@commit line, PDF page, chart + axis>",
   "quote": "<exact text, original language>", "translation": "<English, when not English>"}
 ]
}
```

Fact types (`says`): `score`, `metric-definition`, `headline-metric`, `cost-usd`, `cost-basis`, `price-table`, `tokens-in`,
`tokens-out`, `tokens-cache-read`, `tokens-cache-write`, `tokens-reasoning`, `model-name`, `model-api-id`, `route`,
`effort-label`, `effort-setting` (the parameter actually sent), `no-effort-sent`, `thinking-budget`, `run-date`,
`version`, `harness`, `judge`, `items`, `attempts`, `aggregation` (mean of n runs…), `estimate-flag`, `failure`,
`restated-from`, `component-of` (composite membership and weights), `note`.

## 3. Measure file — what we draw from it

One file per source, next to it. Each measure is one value of one couple on one setup, and cites the facts it rests on.

```json
{
 "source": "src-…",
 "measures": [
  {"id": "M1",
   "setup": "<benchmarks.json setup id>",
   "model":  {"id": "<models.json id>", "facts": ["F2"], "rule": "<rules.json id or null>", "level": "written|computed|…"},
   "effort": {"id": "low|medium|high|xhigh|max|minimal|solo|nothink|think-<budget>|unstated|default",
              "facts": ["F3"], "rule": "…", "level": "…"},
   "run_date": {"from": "<date>", "to": "<date>", "facts": ["F4"], "level": "…"},
   "score":  {"value": 71.4, "step": 0.1, "metric": "<as in setup>", "facts": ["F1"], "rule": null, "level": "written"},
   "usage":  {"in": 1830000, "out": 412000, "cache_read": null, "cache_write": null, "reasoning": null,
              "per": "task|run|suite", "facts": ["F5", "F6"], "level": "written"},
   "spend":  {"usd": 3.12, "basis": "billed|list-estimate|router-billed|subscription|unknown",
              "price_date": {"from": "…", "to": "…"}, "method": "<free text naming the source's cost method>",
              "facts": ["F7", "F8"], "level": "written"},
   "anomalies": [],
   "verified": {"by": "<verifier id>", "at": "<datetime>", "rederived": true}}
 ]
}
```

---

## 4. Registries

**models.json** — the only keys a measure may use.
```json
{"<id>": {"label": "Gemini 3.7 Flash", "maker": "google", "released": "2026-08-13", "line": "<model id of the line, or null>",
  "open_weights": false,
  "names": [{"name": "gemini-3.7-flash", "serves": "<id>", "from": "2026-08-13", "to": "2026-10-07", "evidence": "…"},
            {"name": "gemini-3.7-flash", "serves": "gemini-3.8-flash", "from": "2026-10-08", "to": null, "evidence": "…"}],
  "efforts": [{"levels": ["minimal", "low", "medium", "high"], "from": "…", "to": null, "evidence": "…"}],
  "default": [{"level": "medium", "from": "…", "to": null, "evidence": "<doc capture URL + date>"}],
  "conversions": [{"requested": "max", "served": "xhigh", "route": "direct", "from": "<earliest dated doc>", "evidence": "…"}],
  "thinking": "levels|on-off|always|none"}}
```
**benchmarks.json** — `setup` = benchmark × version × subset × harness × judge panel; its headline metric, the metric's
bounds and direction, task type, complexity, and for a composite its components and formula (weights, normalisation,
validated on complete couples).
**publishers.json** — publisher id → the maker it belongs to (home effect) or none.
**prices.json** — per model and route: dated list prices per token class, long-context tiers, promotions (recorded and
flagged, never a base; their display on the site is set aside for now), batch/flex factors; each with its evidence. "Today's price" = the standard list price in force on the build date.
**rules.json** — each deduction rule: id, inputs (fact types / registry entries), output field, conditions. First set:
`alias-by-date`, `label-to-ladder`, `maker-conversion-dated`, `router-nearest-level-dated`, `api-default-documented`
(code shows nothing sent + direct route or a router's dated default + maker doc captured before the run + run date),
`no-effort-setting` (→ solo), `thinking-off` (→ nothink), `mean-of-runs`, `percent-from-counts`, `composite-residual`,
`cost-from-tokens`, `cost-uniform-factor` (a proven uniform price factor: Flex = ½, a uniform cut), `chart-reading`.

---

## 5. Decision tree (per measure; quality and cost axes separately)

Each step either passes or gives the measure its status with a reason code. Order matters only for the reason reported.

**Q — quality axis**
1. **Source**: URL, harvest date and at least one locator per fact used; else `out:no-proof`.
2. **Model**: `model.id` in models.json and its level accepted. A name that serves different models over time is resolved
   by `alias-by-date`; the run-date interval must lie on one side of the switch; else `out:model-not-established`.
   A route that can change the weights (self-hosted, quantized, unknown provider of open weights) is part of the setup.
3. **Effort**: level accepted and the effort in the fit ladder (`low…max`, `solo`); `minimal`, `nothink`, `think-*` are
   their own couples outside the ladder; `default`/`unstated` → `out:effort-not-established`. A conversion or a default
   needs its dated document before the run (`run_date.to` < the evidence date fails).
4. **Value**: level `written`, `read` or `computed`; `source-estimate` → `out:estimate`; anomaly `failed-run` →
   `out:failed-run`; `contradictory` → `out:contradictory`.
5. **Metric**: the setup's headline metric (another metric of the same run is the same execution: one measure, not two).
6. **Setup homogeneity**: one setup = one harness, one judge panel, one version; a re-published board is the same setup
   when it is a continuation (latest value kept, earlier one recorded) and a new setup when the runs were redone.
7. **Composites**: a couple whose components are measured loses the composite; with part of them measured, only the
   `composite-residual` of the missing part is kept (formula validated; residuals of an estimated index refused).
8. **Republication**: a value restated from another source, or identical across groups beyond chance, counts once.
9. **Group**: a setup becomes a fit group with ≥ 2 accepted couples.

**C — cost axis** (after steps 1–3, 6 of Q)
1. **Cost value**, in order of preference: tokens by class → `cost-from-tokens` at today's price; else dollars with a
   stated basis and a price date → rescaled by the price ratio (old → today) when known, or by a proven uniform factor;
   else `unknown` for the step below.
2. **Comparability (the cost rule)**: a cost enters the fit in the largest subset of the setup's measures that share **one
   cost method** and whose **price ratios between the possible price date and today are known** (unchanged, or changed
   by the same known factor). Typical subsets: the whole setup (no price moved); one model's efforts (its price moved,
   date unknown: the effort ratios hold); the models of one route. A subset of one measure carries nothing → `out:cost-
   not-comparable`.
3. **Basis**: `subscription` / CLI flat billing → `out:cost-basis`; mixed bases in a setup → one subset per basis.
4. **Promotions / off-peak** are never the base. (Showing them on the site is set aside for now — user, 22 Oct.)

Every measure ends with `in` or `out:<reason>` on each axis; the build writes both into `status-report.json`, and the
fit table holds the `in` measures with their group (setup, plus the cost subset on the cost axis).

---

## 6. Validation

- **Schema check** (build): every file valid; every key in a registry; every fact used has a locator and a quote (or a
  chart reference for `read`); every `computed` cites a registered rule whose inputs exist.
- **Re-derivation** (verifier agents): each number re-derived from the saved copy; a mismatch is an `contradictory` fact.
- **Precheck** fails when a measure in the fit lacks a proof for model, effort, value, or (when an event is in its
  window) run date; it reports the counts per reason code, before/after against the last build.
- **Audit trail**: the status report diffs between two builds show every measure that changed status and why.

## 7. Migration of the existing data

1. Convert every `raw-data.csv` row into a source fact set + measure, with levels inferred from today's flags
   (`effort-from-source`, `requested-as`, `alias-date-proven`, `cost-out`, `reprice`, …); what no flag proves becomes
   `assumed`.
2. Build; list the measures in today's fit whose status becomes `out:*-not-established`.
3. Agents re-read the sources for those measures only (saved copies first, then the live source / Wayback), source by
   source, and fill the facts.
4. Rebuild; before/after against v2026.10.21; the maintainer's yes before any fit.

## 8. Open points

- Setup ids and benchmark families: merge today's `groups.json`, `families.json`, `composites.json` into benchmarks.json.
- The fit's group = setup (+ cost subset): today's homogeneity split (publisher, harness, scale, unit) moves into the setup.
- Precision fields: `step` from the printed value, `reading_sd` for charts (today's `origins.json`).
