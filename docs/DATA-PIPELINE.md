# Data pipeline: findings, registries, decision tree (proposal v3, 22 Oct 2026)

Status: **draft — four independent reviews (/work/.salvo14/review-pipeline{,2,3,4}/), revised; schemas can be written;
no code yet.**

The data the fit reads becomes **computed tables**, built by one script from what agents write (the **findings**: what a
source says) and what we define (the **registries**). **Agents write facts only**: what the source says and how it says it (printed,
read off a chart, flagged by the source as an estimate…), which the verifiers check. The model, the configuration, the
campaign, every measure field's level and every status are computed by the build. The maintainer's decisions are the only hand-set
statuses; they live in one file, are pinned to the facts they judged, and are evaluated first.

```
data/findings/sources/<source-id>.json   one source snapshot: its words, as facts with proofs        ← salvo agents
data/findings/measures/<source-id>.json  which facts form one measure, and on which setup          ← salvo agents
data/registry/models.json                models, names served over time, efforts, defaults, conversions, modes (dated)
data/registry/routes.json                makers' APIs, resellers, routers, harnesses, self-hosting: level maps (dated)
data/registry/benchmarks.json            families, setups, versions, headline metrics, composites (formula)
data/registry/publishers.json            publisher → maker (home effect)
data/registry/prices.json                dated prices per model and route; as_of pinned per build
data/registry/rules.json                 deduction rules and standing rules (each dated, with who decided)
data/registry/vocab.json                 closed vocabularies: fact types, units (+ aliases), cost bases and methods,
                                         anomalies, routes, effort ids, reason codes
data/registry/flag-map.json              migration only: confound flag → fact/level, versioned, tested on every row
data/decisions.json                      the maintainer's per-measure decisions
build/fit-quality.csv, build/fit-cost.csv   computed: the rows each axis' fit reads (today's raw-data.csv columns)
build/group-map.json                     computed: fit group → base group (for families, composites, publishers)
build/status-report.json                 computed: every measure, its status per axis, its reason, the diff to the last build
```

Saved pages, dumps and clones stay outside git in the salvo folders, which are kept; git keeps their URLs, Wayback
captures, sha256 and the extracted facts.

---

## 1. Certainty levels (of a fact; computed for each measure field)

| Level | Meaning | Tree |
|---|---|---|
| `written` | the source states it: a printed number (also printed on an image), a data-file value, a code or config line, an API id, a label | accepted |
| `read` | measured off a chart's geometry (pixels); vector paths are `written` (exact) | accepted; its reading sd enters the precision |
| `computed` | produced by the build with a rule of rules.json from accepted inputs | accepted when every input is accepted; precision propagated by the rule's formula |
| `source-estimate` | a value the source did not measure on this run: imputed, projected, filled, an "estimated" index | refused (`out:estimate`) |
| `not-established` | `absent` · `assumed` · `contradictory` (the source, or two facts, state two things) · `ambiguous` (a rule gives two answers) | refused, with the reason |

A cost the source computed from this run's own tokens at a stated price, or a CLI's `total_cost_usd`, is `written` with
basis `list-estimate`. Each measure field (model, effort, run date, value, each setup field, each usage class, the price)
gets its own level; a measure is in only if every field the tree reads is accepted.

When one value is both printed and read off a chart, the printed value is used. A chart's effort labels (legend, axis,
point labels) are `written`; a level inferred from a marker's position or order alone is `not-established:assumed`.

Attributes, never levels: the **precision model** (`printed` step · `chart-pixel` sd · `exact`), the **route**,
**restated-from** and **same-runs-as** (each with its own level), **anomalies** (each with its own level).

---

## 2. Source file

```json
{"id": "src-<publisher>-<what>-<YYYY-MM-DD>", "publisher": "<publishers.json id>",
 "urls": ["…"], "wayback": ["…"], "commit": "<repo commit or null>", "sha256": {"<saved file>": "<hash>"},
 "harvested_at": "<ISO datetime UTC>", "salvo": "…", "agent": "…",
 "snapshot_of": "<earlier source id of the same board, or null>",
 "facts": [{"id": "F1", "says": "<fact type>", "about": "<the source's entry name, verbatim>", "value": "<verbatim>",
            "level": "written|read|source-estimate|not-established:<reason>", "where": "<locator>",
            "quote": "<exact text; required for prose, labels and code>", "translation": "<English, if needed>"}],
 "tables": [{"id": "T1", "file": "<saved file>", "where": "<JSON path / CSV / table>", "columns": {…}}]}
```

A data file is proven by its sha256 and a locator (a `tables` entry stands for its cells). Fact types (vocab.json):
`score`, `metric-definition`, `headline-metric`, `cost`, `currency`, `unit` (vocabulary = today's unit list + aliases;
usage and spend share it), `cost-basis`, `cost-method`, `price-table`, `tokens-in`, `tokens-out`, `tokens-cache-read`,
`tokens-cache-write-5m`, `tokens-cache-write-1h`, `tokens-reasoning` (+ `reasoning-included-in-out`), `tokens-total` (no class split: usable only through a uniform
factor, or for ratios within one model), `cached-share`,
`requests`, `model-name`, `model-api-id`, `route`, `mode`, `effort-label`, `effort-setting` (a setting line read in code or config, with where it was read),
`thinking-on` (thinking enabled with no level, e.g. a `-thinking` id or AA "(Reasoning)"), `thinking-off`,
`no-effort-sent`, `config-history` (a config file's history over an interval), `thinking-budget`, `tools-regime`,
`run-date`, `run-start`, `run-end`, `run-id`, `version` (benchmark/protocol/board version), `early-access`, `harness`,
`judge` (per row when it varies), `aggregation` (which runs a mean covers), `failure`, `partial`, `cap`,
`restated-from`, `same-runs-as`, `evaluated-by`, `component-of` (with weights). Optional, never read by the tree:
`items`, `attempts`, `note`.

## 3. Measure file

The agent groups the facts of one measure and names the setup; it writes no key, effort, level or campaign.

```json
{"source": "src-…",
 "measures": [{"id": "M1", "setup": "<benchmarks.json setup id>",
   "facts": {"value": "F1", "model": ["F2"], "effort": ["F3"], "run_date": ["F4"], "usage": ["F5", "F6"],
             "spend": ["F7", "F8", "F9"], "version": "F10", "judge": null, "anomalies": [], "restated_from": null,
             "same_runs_as": null, "value_seen_in": ["<capture ids carrying this value>"]},
   "verified": {"by": "…", "at": "…", "rederived": true}}]}
```

---

## 4. Registries

**models.json** — the only keys. Per model: label, maker, `released` (datetime, from the maker), `line`,
`open_weights`, and its **configurations**: the list of configurations the model offers, each dated (`{from, to,
evidence}`) and each either served as itself or converted:
- levels of an effort parameter (`minimal`, `low` … `max`), `nothink` (thinking off: `reasoning_effort: none`,
  `enable_thinking: false`, `thinking: disabled`, a non-reasoning id…; the spellings are listed in vocab.json),
  `think` (thinking on with no level: the only thinking configuration of an on-off model without levels — DeepSeek
  V3.2 thinking mode, Kimi K2.5, GLM-5, the Qwen 3.5–3.7 hybrids), `think-<budget>` (thinking on with a token budget),
  `between-tools` (Sonnet 5.5's `thinking: {type: between_tools}`, combined with a level ≤ high: in the fit like every
  configuration of the model's list; 23 Oct, in the fit since 26 Oct);
- `solo` only for a model whose list is `[solo]`: nothing to set (K2.7 Code, a model with thinking always on and no
  level). Examples: Opus 5.5 `[low … max]`; GPT-5.x `[nothink, minimal, low … xhigh]`; Haiku 4.5 `[nothink,
  think-<budget>]`; a hybrid Qwen `[nothink, think]` or `[nothink, low … xhigh]`.
`names`: each API id or display name, the model it **serves** over `{from, to}` (the maker's own dates: release,
redirect, shutdown), and optionally the configuration it selects (`deepseek-chat` → nothink, a `-thinking` id →
think). Names are matched exactly, except in the Hugging Face namespace (`huggingface`: repository ids such as
`Qwen/Qwen3.8-27B`), matched case-insensitively (23 Oct). `default` (the configuration a call with no setting gets; when the maker documents the thinking default and the effort default separately, two dated records with `setting: thinking` and `setting: effort`: Anthropic Opus 4.5–4.8 and Sonnet 4.6, a call with no thinking field is thinking off, the effort default high applies with thinking on; 26 Oct), `conversions` (requested → served, per route),
`modes` (request parameters that select another key: Pro → `<id>-pro`). Configurations served as themselves start at
the release (release post, model card or API reference) unless a document dates a later addition, and last until the
maker states a change or the model's shutdown (a capability is not bounded by the last capture); `default`,
`conversions` and `modes` are dated by their evidence: `from` = the effective date the maker's document states, else
its earliest capture; `to` = the change it states, else the last capture still showing it. Between two captures showing
the same text the interval is covered; between a capture showing it and the next one not showing it, it is not; a single
capture covers its own day only. Build
checks: two keys of one maker serving one API id over overlapping intervals, or with identical display names, fail the
build until resolved.

**routes.json** — vocabulary `maker-api · reseller (Bedrock, Vertex, Azure: the maker's model resold) · host (Fireworks,
Together, DeepInfra…: open weights served by a third party) · router (OpenRouter, AI Gateway) · harness/CLI (Inspect,
Pi, Claude Code, Codex CLI, IronBee…) · self-hosted (vLLM, SGLang…)`. Per route and model, dated: the configurations it
accepts, how it maps a level (identity when documented as identity; OpenRouter nearest supported level,
ties `ambiguous`; a model without an effort parameter → a token budget: `budget-converted`), its documented default.
On a self-hosted route the maker's defaults and conversions do not apply. A harness maps a level per provider: its records name the next step they apply to (`via`), and route-wide records the maker and models (26 Oct).

**benchmarks.json** — `family` ⊃ `setup` = benchmark × subset × harness (without its version: patch releases are one
configuration) × tools regime × judge panel × metric. Per setup: headline metric (the source's designated one; if none,
the metric the source ranks by; else a decision; with its level, `written` or `not-established:assumed` when it is only
the metric held; a cost-only setup has metric `none`), bounds, direction, task type, complexity, `kind` (`rating` — Elo,
arena, re-fitted index — or `runs`); for composites the components (a setup, or a named component the
registry does not hold), the formula (weights, normalisation), validated on
complete couples, and whether it is linear (`true`, `false`, or `unknown` while the formula is not in hand: no residual). Setup ids keep today's group names where they exist (the catalog maps keep
working).

**publishers.json** — publisher → its maker, or none.

**prices.json** — per model and route: list prices per class (input, output, cache read, cache write 5m and 1h; OpenAI's 30m and 12h), per
configuration when the maker prices them differently (Qwen3-8B thinking output), long-
context tiers with their per-request threshold, promotions (recorded, flagged, never a base; their display on the site
is set aside), batch and flex factors; each dated with evidence. `as_of` pinned per build. Base route = the maker's API.
Base price = the standard list price in force on `as_of`; for a retired model, its last list price (decision 1 of
21 Oct); for a model whose standard price never applied before it was withdrawn, the price actually charged (Gemini 3.7
Flash, $0.75: the maintainer, 21 Oct).

**rules.json** — each rule: id, inputs, output, conditions, precision formula, date, decided by. Deduction rules:
`alias-by-date`, `mode-to-line`, `label-to-ladder`, `maker-conversion-dated`, `route-mapping-dated`,
`api-default-documented`, `config-unchanged-over-interval` (the config's history covers the run interval with the same
setting), `no-effort-setting`, `thinking-off`, `mean-of-runs` (failed runs excluded), `percent-from-counts`,
`composite-residual`, `scale-conversion` (fraction ↔ percent, exact), `cost-publisher-figure`, `cost-delta-on-source` (the price change applied to the source's own
cost once its formula reproduces it), `cost-uniform-factor`, `cost-class-ratio` (METHODOLOGY §2, spread added),
`chart-reading`, `currency-fixed`. Standing rules (the maintainer's): the label rule (a label that names a level of the
model's ladder is that level — LMArena kept, 22 Oct), `closed-harness-label` (a closed harness — Cursor, Antigravity, Grok CLI, Copilot, Amp, Kiro: routes with `label_as_level` — that shows a level without documenting what it sends: the label is the level sent to the maker's API, flag `harness-label-as-level:<route>`; a dated mapping of the harness wins; 26 Oct), "Pro via a router that cannot separate it → out" (20 Oct),
decision C as restated (conversions only when dated), the composite residual rule (22 Oct), the cost comparability rule
(22 Oct), uninformative scores (METHODOLOGY §2).

**decisions.json** — `{id, measures: [ids], facts_hash, axis, status, reason, date}`; evaluated first; a decision whose
facts hash no longer matches is reported, not applied.

---

## 5. Decision tree

### 5.1 Facts → fields (build)

**Run date.** A stated `run-date` (a per-run timestamp counts as one) gives the day; `run-start` and `run-end` give the
interval; a lone start or end gives that bound, the other is the default bound. Default bounds: lower = the model's
`released` (computed per candidate key for an alias; not clamped for an `early-access` run), upper = the earliest of
the source's publication, the earliest capture carrying the measure's value, and the commit. Datetimes when known.
Needed only when a dated event of the model falls inside it.

**Model.** The model-name / API-id facts resolve through `names` at the run date; for a name that has served more than one
model (an alias), the run interval must lie inside one `serves` interval (names that never moved are not date-checked,
so early-access runs pass); for an alias the run interval is one for all candidates, its lower bound the earliest
candidate's release, so an interval straddling the switch is ambiguous, never the newer model (22 Oct) (a stated run date before a redirect, or a proven bound like `alias-date-proven`, does). Two facts that
resolve to different keys → `contradictory`. `mode` facts → the line key; a route that cannot separate the mode →
`not-established:absent`. **Early access**: an `early-access` fact, or a run upper bound before `released`.

**Configuration** (the effort) — first match wins; every rule's interval must cover the run interval; "the model's
configurations" are those of models.json at the run date:
1. a model whose configurations are `[solo]` → `solo`, whatever else is stated (K2.7 Code);
2. a `thinking-budget` → `think-<budget>` (exact token count; budgets within 5 % are one value: 10k = 10,000 = 10,240);
   a numeric scale → `scalar-<n>`;
3. an `effort-setting` (a code/config line at the run, or `config-unchanged-over-interval`; read in the source's own
   call, or in a harness/router config), a `thinking-on` / `thinking-off` fact, or a `names` entry that selects a
   configuration → that configuration, when it is one of the model's configurations and every step of the route chain
   serves it as itself; a configuration the maker or a route converts goes to step 6;
4. an `effort-label` that names one of the model's configurations, served as itself → that configuration (standing label
   rule); a label naming a converted level (GLM-5.2 `low`) goes to step 6;
5. an `effort-label` in other words → `label-to-ladder` when the model's configurations make it unique;
6. a requested or converted configuration → the route chain applied in order **harness → router / reseller / host →
   maker**, each step dated (identity where documented); route unknown → every candidate route (each route of routes.json that served the model at the run date, the maker's API
   always included) is evaluated and the
   configuration is accepted only if all agree, else `not-established:absent`; a router budget → `budget-converted`;
   a tie → `ambiguous`;
7. `no-effort-sent` → `api-default-documented`: on the maker's API or a reseller, the maker's documented default (Haiku
   4.5: thinking off → `nothink`); through a router or host (route known), its own documented default for that model
   (the maintainer, 22 Oct); else `default`;
8. nothing → `unstated`.
Two facts giving two configurations (a `-thinking` id with an effort field null) → `not-established:contradictory`
unless one is the more specific statement of the same call (the id selects thinking, the null field says no level was
sent → `think`). **In the fit**: every configuration of the model's list as its own couple (`low … max`, `minimal`,
`nothink`, `think`, `solo`), **except** `think-<budget>` (recorded, `out:budget-config`: too few and an unusual use,
the maintainer, 22 Oct). A configuration not in the model's list → `out:effort-not-established`; not established
(`scalar-*` without a mapping, `budget-converted`, `enabled` without a level, `adaptive`, `default`, `unstated`,
`req-<label>`, `app-*`, `priceblend`) → `out:effort-not-established`. A tools regime (`nt-*`), a fast mode or an
application setting is part of the setup, not the configuration.

**Campaign** (computed). A setup's campaign is its `version` (benchmark, protocol or board version). Snapshots of one
board are linked by `snapshot_of`; a snapshot without a version fact inherits the campaign of the snapshot it continues,
and a board that never states a version has one campaign. Within one campaign, a couple measured again replaces the earlier value (recorded as
`prev`): rating boards always (Elo, arena, rolling means, re-fitted indices), run boards when the version is unchanged
(a re-score or a regrade of the same runs). New couples join the current campaign. A new version is a new campaign; the
earlier campaign stays (both are measurements). `same-runs-as` (stated, or proven by identical other-axis values on all
shared couples, ≥ 2 of them, equality by METHODOLOGY §3's closeness test) links two documents: the later grading replaces the earlier, and the cost counts once.

### 5.2 Quality axis (decisions first; then the first failing step gives the status)
0. **Decision** pinned to the measure → its status (`in:decision:<id>` / `out:decision:<id>`).
1. **Proof**: every fact used has a locator (and a quote where required) → else `out:no-proof`.
2. **Model** accepted and in models.json → else `out:model-not-established`.
3. **Configuration** established, in the model's list and in the fit → else `out:budget-config` /
   `out:effort-not-established`.
4. **Value** accepted; `source-estimate` → `out:estimate`; `failure` (did not complete, infrastructure error) →
   `out:failed-run`; a source's mean that includes a failed run → recomputed by `mean-of-runs` when the per-run values
   are written, else `out:failed-run`; `partial` (items missing, not scored) → `out:partial` unless the source scores them as wrong; `cap`
   (a declared cap, scored) is a setup attribute, in; an anomaly `assumed` → `out:anomaly-assumed`; `contradictory` →
   `out:contradictory`.
5. **Metric** = the setup's headline → else `out:not-headline`.
6. **Uninformative**: a score at the floor or the ceiling of its metric for one couple while the others are not → score
   out (`out:uninformative`), its cost kept (METHODOLOGY §2).
7. **Campaign**: an earlier value replaced within its campaign → `out:superseded` (kept as `prev`).
8. **Composites**: a couple with **any** component measured loses the composite; a linear composite keeps only its
   `composite-residual` for the missing components (the residual's setup = composite × missing set; capture is its
   campaign; residuals of an estimated index refused); a non-linear composite is kept whole only for couples with no
   component. (Phase 1: the build computes the residuals; dropping the composite stays in `lqm.load`.)
9. **Republication**: `restated-from` → counted once (phase 1: `lqm.load`'s rule — the larger group keeps it; phase 2:
   the original); identical values across groups beyond chance → once (`lqm.load`).
10. **Group** = setup × publisher × campaign, ≥ 2 accepted couples of models in the fit's model list → `in`; else
   `out:single-couple`.

### 5.3 Cost axis
Steps 0–4 and 7–10 apply. Measures citing the same spend facts (one run scored under several metrics) are one cost
measure, on the headline measure's setup (else the first). A composite's cost residual is the total minus the present
components' costs, only on one unit and one run; otherwise the composite's cost is dropped. Then:
1. **Base-price value**, METHODOLOGY's order: the publisher's own figure at the base price; the price change applied to
   the source's own cost once its formula reproduces it from the run's tokens (`cost-delta-on-source`; per-request
   long-context tiers only when `requests` and per-call sizes are known); a uniform factor (`cost-uniform-factor`); the
   class-median ratio (`cost-class-ratio`); otherwise the cost is **unrepriced**, at its own basis.
   `price_date` = the date of the prices the source applied: the run date for a billed spend; the capture date for a
   source that recomputes at its current price (AA); the stated date for a list estimate, else [run lower bound,
   publication].
2. **Partition** of the setup's measures by `basis` (`billed · list-estimate · router-billed · subscription · unknown`)
   × `method` (vocab: `tokens×list`, `cli-total`, `provider-invoice`, `router-invoice`, `publisher-table`,
   `library-table` (litellm-style price tables)…; a "simulated" cost is classified per source at migration: computed from
   this run's tokens → `tokens×list`, otherwise `source-estimate`) × unit ×
   currency × route. In each part: the re-priced measures form one subset; each unrepriced model forms its own subset
   when its price change over the price-date interval is uniform across classes (its efforts' ratios hold); the others →
   `out:cost-not-comparable`.
3. A subset with fewer than 2 couples → `out:cost-single-couple`; `subscription` → `out:cost-basis`.
4. Promotions and off-peak prices are never the base. A promotion is a price charged over its interval: it is one of
   the prices a source may have applied over the price date (`prices_over`), so a window where only a promotion is
   printed is covered (26 Oct).

---

## 6. Fit tables and the fit (phase 1)

The build writes **one table per axis** in today's `raw-data.csv` columns, holding only the measures `in` on that axis:
- `fit-quality.csv`: group = setup × publisher × campaign (today's group name where it exists), the score, and the cost of
  the same execution when known (republication detection reads it; the quality fit never does);
- `fit-cost.csv`: group = the quality group × cost subset (suffix `~c<n>`), the cost at the base price, and the score of
  the same execution when known;
- `source` = the publisher's id in publishers.json (maker publishers named as `lqm.load`'s maker map: anthropic,
  openai, google, alibaba…), never a snapshot id, so publishers, unit aliases and the home effect resolve as today;
- confound flags regenerated from the facts in the exact spellings `lqm.load` reads (`EAP-run`, `restated-from:<maker>`,
  `vendor-reported:<org>`, `evaluated-by:`, …, listed in vocab.json), plus `prev`; the reading sd in its column (`score_prec` / `cost_prec`), as today;
- `group-map.json`: fit group → base group, for the group-keyed catalog maps (families, composites, group display);
  the source-keyed maps (publishers, unit aliases) are keyed by the publisher id in the `source` column.

Code changes for the tables (no change of method): `fit.py` reads one path per axis; `catalog` resolves a group
through `group-map.json`. `lqm.load`'s per-row outcome is recovered by comparing its input with the rows it keeps
(group, couple, value): a row dropped by its composites rule → `out:composite`, by its republication rule →
`out:republished`, written into the status report. **Method change** (configurations per model, 22 Oct), with its
before/after: `lqm.EFFORTS` → the configurations in the fit; METHODOLOGY §2 ("a model without an effort setting … solo",
"nothink … outside the computation") and DISPLAY-METHODOLOGY (effort ladders) rewritten; the site's effort order,
grids, monotonicity report and duels (`EFFORT_ORDER`, `ORD`, `CAP`, `EFF`) extended to `nothink`, `minimal`, `think`
(placed below `low`). The build also writes the public data file (every measure, today's columns plus `status_quality` and
`status_cost`), read by precheck.py, validation/*.py, site/sources.py (through the group map) and the CSV download;
precision.py is replaced by the facts' precision model. **Acceptance test** before any new fact is used: the legacy
facts alone must give `lqm.load` the same groups, rows and report as v2026.10.21's raw-data.csv. `lqm.load` keeps its composites rule, homogeneity split and republication rule in phase 1, and its
report is written back into the status report. Site fields stay in the site's registry.

## 7. Validation
- Schema: every file against its schema and vocab.json; every key registered; the identity checks of models.json.
- Verifier agents re-derive, for every measure `in` or changing status: each number from the saved file, each label and
  fact type (`effort-setting` vs `effort-label` vs `no-effort-sent`), the identities (model names, setup against its
  harness / judge / version / tools / metric facts); a quote must contain its value and the saved file the quote. Each
  salvo audits a sample of its `unstated` / `default` measures.
- Precheck fails when a measure `in` lacks an accepted model, effort, value or (when an event is in its window) run date;
  it reports counts per reason and the status diff to the last build.

## 8. Migration
1. Legacy facts: each `raw-data.csv` row becomes a fact set whose proof is `legacy` (its `ref` and confound text),
   accepted by step 1 only until its source is converted. A legacy measure is a pass-through (22 Oct): it carries
   today's row as it is, its status is today's (lqm.load's admission), none of the tree's steps apply, and the build
   writes it verbatim (data/legacy.py, data/BUILD.md; acceptance: data/tests/acceptance.py); `flag-map.json` maps the confound flags (4,571 distinct
   prefixes) to facts and levels — e.g. `requested-as` → requested level, `alias-date-proven` → run bound,
   `index-estimated` → `source-estimate`, AA `was-estimate=` → `prev` (our earlier estimate, replaced) — versioned,
   tested on every row, with the unmapped prefixes reported.
2. prices.json filled for every model in the fit before the first cost build; `as_of` pinned.
3. First build; the status report lists, per source, the measures of today's fit that become `out:*-not-established`
   (≈ 3,780 configuration rows carry no recognisable effort proof today; every `solo` row of a model whose list is not
`[solo]` — ≈ 1,760 in-list rows, Haiku 4.5's 375 included, ≈ 1,200 of them on hybrid models where `solo` meant
"thinking on" — is re-read into `nothink`, `think`, a level, a budget, or not established) and those still in the data that the tree now refuses
   (e.g. AA indices flagged estimated).
4. Agents convert sources to real files, worst first, re-reading the saved copy or the live source; legacy proof retires
   source by source.
5. Rebuild; before/after against v2026.10.21; the maintainer's yes before any fit.

## 9. Decisions

Decided by the maintainer during the reviews:
- **Cost method unstated** (23 Oct): for a source whose cost method is found neither in its documentation nor by
  reproducing its costs from its tokens, one table of one source is taken as one method (`cost_method_unstated =
  single-per-table`, flag `cost-method-assumed-single`).
- **Configurations per model** (22 Oct): each model has its own list of configurations; `nothink` and `minimal` enter
  the fit as couples of their model (≈ 72 + 12 couples measured by ≥ 2 publishers today); thinking budgets stay out.
  `solo` only for a model with a single configuration: every `solo` row of a model whose list is not `[solo]` (Haiku 4.5's 375 included) are re-read at migration into
  `nothink`, a budget, or not established. A method change: before/after before main.
- `api-default-documented` through a router (22 Oct): when the run is known to have gone through the router with no
  effort sent, the router's dated documented default for that model is the effort (latitude kimi-k3: OpenRouter
  `default_effort: max`, captured 21 Jul, run 23 Jul).
- **Closed harnesses** (26 Oct): the level label a closed harness shows (Cursor 371 fit rows, Antigravity 65, Grok CLI 31,
  Copilot 27, Amp 18, Kiro 15) is the level sent, as LMArena's labels, flagged; strict doubt (out, LMArena with them)
  was not retained. Rule `closed-harness-label`, route field `label_as_level`.
