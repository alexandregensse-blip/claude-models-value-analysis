# data/build.py: the build of the findings pipeline

This file implements the decision tree of `docs/DATA-PIPELINE.md` (§5) and writes the fit tables (§6). It also gives
legacy rows of today's raw-data.csv a pass-through path (§8). It runs over the schemas, vocabularies and validator in
`data/schema/`, and uses only the Python 3 standard library.

## Run

```
python3 data/build.py --fit-models catalog               # data/registry + data/findings + data/decisions.json → data/build/
python3 data/build.py --registry data/findings/examples/registry --findings data/findings/examples --out build/
python3 data/build.py ... --previous build-old/status-report.json   # adds the status diff (per measure and per source)
python3 data/build.py ... --cost-method-unstated out                # the setting below
python3 data/build.py ... --fit-models catalog                      # the fit's model list (default: models.json keys)
python3 data/build.py ... --no-lqm                                  # skip the lqm.load step
python3 data/build_lqm.py data/build/                               # the lqm.load step alone
python3 data/legacy.py raw-data.csv OUT/findings --registry OUT/registry   # raw-data.csv → legacy findings
python3 data/tests/run.py [name-filter]                             # the tests (129, about four seconds)
python3 data/tests/acceptance.py [raw-data.csv] [--registry data/registry]   # the legacy acceptance test (≈ 20 s; default: the repository's raw-data.csv)
python3 data/schema/validate.py [--verbose]                          # per-file summary; registry warnings apart
python3 data/convert/precheck.py SOURCE_ID                           # names and route heads against the registry
python3 data/convert/gaps.py data/build/status-report.json [--registry R --findings F]   # registry gaps per source
python3 data/convert/reproduce.py --tables … --table … --csv …       # per-row cost reproduction (pinned table)
```

The build runs in five steps:

1. **Validate.** It runs `validate.py`'s checks, with `--check-files` unless `--no-check-files` is given.
   - These stop the build with exit 1 and the reason: an error in the registries (models, routes, benchmarks,
     publishers and prices are required), the vocabulary or the decisions, or a file that fails its schema.
   - A bad argument gives a one-line `error:` and exit 2, never a traceback: a missing `--fit-models` file, a missing
     or malformed `--previous`, a malformed `class-ratios.json`, an `--out` that is a file, a missing folder.
   - An error that belongs to one source, fact or measure does not stop the build. The measure gets `out:no-proof`,
     but only on the axis whose facts the error concerns.
   - A decision whose measure is gone is reported as stale and is not applied.
2. **Fields.** For each tree measure it computes the run-date interval, the model, the configuration, the campaign,
   the value on the setup's scale, and the cost at the base price. Legacy measures skip this step.
3. **Statuses.** Each tree measure gets a status per axis. Decisions are applied first; after that, the first step that
   fails gives the status. A legacy measure keeps its row's status under today's admission rules.
4. **Outputs.** The tables and reports listed below.
5. **lqm.load step.** Unless `--no-lqm` is given, `data/build_lqm.py` imports `model/lqm.py` unchanged, runs `lqm.load`
   on each fit table and compares the rows it keeps with its input, matching on (group, couple, value). It writes the
   outcome back into the report and into `data.csv`. A dropped row gets:
   - `out:composite`, when a component group measured its couple;
   - `out:republished`, when its couple appears in the partner group of one of lqm's republished pairs;
   - otherwise `out:saturated`, or `out:single-couple` / `out:cost-single-couple`.

   A legacy row's status takes the `legacy:` prefix (`legacy:out:composite`, …).

   The catalogue's group-keyed maps reach the fit groups through `build_lqm.fit_maps` (group-map.json and
   group-setups.json); model/fit.py, model/precheck.py and model/validation read the tables through the same code
   (`build_lqm.load_table`), so the fit drops the rows this step reports dropped (test `fit_reads_build_tables`).

## Legacy path (migration, §8.1)

`data/legacy.py` converts each raw-data.csv record into a `legacy-row` fact with the form `legacy`. The fact's value is
the record's line verbatim, and the source's `legacy` block holds the CSV's header. Each raw-data `source` value gets
one legacy source, so the sources can be converted one by one, and each row becomes one measure on the placeholder
setup `legacy`. Only the two free-text comment lines are skipped. validate.py checks that:
- the form `legacy` and the fact type `legacy-row` go together;
- the line has the CSV's number of fields;
- with `--check-files`, it is a line of the hashed CSV;
- a legacy measure cites its one row and nothing else.

The build carries a legacy measure **as it is**:
- its status is today's admission, the filters `lqm.load` applies: `legacy:in`, or `legacy:out:<why>` where why is
  `comment` (group `#…`), `no-group`, `model-not-in-fit-list`, `effort-not-in-efforts` (a configuration outside `lqm.EFFORTS`: `between-tools`, an odd label;
  the acceptance test checks the copy) or `no-value`;
- none of the tree's steps apply: no repricing (the cost is already at today's price, with its `reprice-…` and
  `cost-out:…` flags), no uninformative step, no campaign or same-runs replacement;
- it is written to the fit tables verbatim, in the CSV's order, before every findings row. lqm.load's republication
  and split rules depend on row order;
- it is reported with `kind: legacy` and counted apart (`counts.legacy`);
- its `tree_would_say` column is informative only: the configuration and cost method that flag-map.json and the
  vocabularies give the row. It never changes the status.

**Acceptance test** (`data/tests/acceptance.py`). It converts the CSV, builds with `--fit-models catalog`, and checks
three things:
- every fit-table row is a byte-identical line of the CSV;
- `lqm.load` gives the same groups, the same rows (every computed field, in order), the same report and the same
  republished list as on the CSV itself, on both axes;
- `LEGACY_EFFORTS` equals `lqm.EFFORTS`.

On /work/.wt-px/raw-data.csv (42,296 rows, 769 sources) the result is **identical**:
- quality: 1,671 groups and 18,934 rows;
- cost: 861 groups and 10,048 rows
  (with the configurations-per-model filter: before it, 1,600 groups and 17,028 rows, 831 and 9,480).

The repository's raw-data.csv is identical too (quality 1,574 groups and 17,533 rows; cost 855 and 10,936).

**Against the real registry.** When the findings hold legacy sources (`src-legacy-*`) and the registry lacks the
placeholder setup `legacy`, its family or the publisher `legacy`, the build supplies them from data/legacy.py's
constants and lists them in the report (`build.supplied`). A legacy-only build then runs against data/registry, and the
acceptance test passes with `--registry data/registry` too (identical, 12 s).

**legacy_ref.** A converted measure may carry `legacy_ref: {line, row_sha256[, csv_sha256]}`, the raw-data.csv row it
replaces. That legacy row then becomes `legacy:out:replaced` (it is not written twice), whether its legacy file is kept
or removed. With `--previous`, `diff.by_legacy_ref` pairs each such measure with the legacy row of the previous report.
It lists, per raw-data `source`:
- the pairs whose status, group, model, effort, score or cost changed, with the new reasons, and the unchanged count;
- `unmatched_old`: the legacy rows of that source no measure claims;
- `unmatched_new`: the measures of the same findings sources that claim no row.

data/convert/mapping.py builds the mapping that gives each measure its `legacy_ref`.

**Diff per source.** Once a source is converted, `--previous` adds `diff.by_source` to the report. For each fit-table
`source`, it lists the rows whose status, value or group changed, plus the rows added and removed. Rows are matched by
(base group, model, effort), whatever their measure ids, and each change comes with the new reasons.

## Outputs (`data/build/`, the default `--out`)

The build of the repository's data (`--fit-models catalog`, with the lqm step) is committed in `data/build/`: the fit
reads its tables (model/fit.py), the site its `data.csv` and group map. `status-report.json` (≈ 150 MB) is not
committed (`.gitignore`): rebuild it to read a measure's reasons (about 10 minutes with `--check-files`, 4 GB).

| File | Content |
|---|---|
| `fit-quality.csv` | Rows `in` on quality, in today's `raw-data.csv` columns: legacy rows verbatim, then findings rows. `source` is the publisher id. `cost_usd` holds the raw cost of the same execution, which the republication check reads. |
| `fit-cost.csv` | Rows `in` on cost. The group is the quality group, with `~c<n>` added when the group has several cost subsets. The cost is at the base price; `score` is the score of the same execution. |
| `group-map.json` | Each fit group → its base group: the setup's first `legacy_groups` entry, else the setup id; a legacy row's group maps to itself. |
| `group-setups.json` | `groups`: each fit group of a converted measure → its setup (legacy rows have none); `setups`: each such setup's benchmark family and composite components (benchmarks.json). With `group-map.json`, what `build_lqm.fit_maps` needs to give the fit groups the catalogue's composites and families, so the fit reads the build without the status report. |
| `data.csv` | Every measure, including composite residuals and legacy rows: the fit columns plus `status_quality` and `status_cost`. The public data file (the site's CSV download links it on GitHub); precheck.py and site/sources.py read its rows in the fit. |
| `status-report.json` | Per measure: status and reason detail per axis, every computed field with its level, the facts and rules used, the flags, the row summary, the fit rows and the lqm outcome. Also the counts per reason, the stale decisions, the validation warnings and errors, and the diff against `--previous`. |

The numbers in the fit tables follow today's formats:
- scores and costs are written with the source's own digits (strings kept);
- a re-priced cost has the significant digits of the original text (`fmt` in data/precision/repricing_makers.py). A
  publisher figure at the base price is written as printed;
- `score_prec` and `cost_prec` have three significant digits, as data/precision.py writes them;
- `score_metric` is the value fact's metric term; harness, task type and complexity are the setup's;
- a findings setup is one harness × metric by definition, and validate.py enforces the metric. The per-row harness,
  metric, task type and unit of today's mixed groups come with the legacy rows, which carry their own.

The fit tables carry these confound flags:
- `EAP-run`;
- `restated-from:<Org>` when the fact names a maker, else `restated-from:<value>`;
- `vendor-reported:<Org>` for an `evaluated-by` fact naming the model's maker, else `evaluated-by:<value>`;
- `prev=<value> (<measure>)` on a row that replaced an earlier one;
- the build's own flags, which `lqm` ignores: `cost-method-assumed-single`, `cost-unrepriced`,
  `cost-uniform-factor-tiers`, `cost-base-price:<rule>`, `base-last-list-price`, `cap`, `composite-residual-refused:scale`, `stale-decision:<id>`.

## The coordinator's build rules (23 Oct)

- **A stated cost method is reproduced.** This applies when a `price-table` fact's `term` names a table of
  `price-tables.json` (a library's cards at a pinned version, or a board's own table) and the method is token-based:
  - the build recomputes the cost from the run's tokens (data/convert/reproduce.py), with the table's
    `input_includes_cache_read` and `reasoning_in_output`, unless the source states `reasoning-included-in-out`;
  - off by more than its rounding (one unit of the cost's last digit plus the token counts' rounding) → the cost is
    `not-established:contradictory` (`out:contradictory` on the cost axis);
  - no card, a card in another currency, or no tokens → accepted as written;
  - `fields.cost.reproduction` says which case applied.
- **A converter's loop** (27 Oct). `--registry-files-checked` (build.py and validate.py) skips the saved-copy checks of
  the registry's evidence only, on an unchanged registry copy; the findings' files are still checked. With one source's
  findings (and its legacy rows) a build takes seconds; the full build with every check runs at install.
- **Thinking on with a stated level** (27 Oct). On a model whose list has levels and no `think`, thinking on plus a
  stated level (setting, label, chart order) gives the level; the maker's default that thinking on alone would read is
  not used (no contradiction, no `level-from-default`).
- **A decimal comma** (27 Oct). A source whose numbers use a decimal comma carries `decimal_mark: ","`: the build reads
  '12,5' as 12.5, '1.234,5' and '1.234' as thousands; the quotes keep the printed value. A counts score may write
  "k of N" in the source's language (из, von, sur, de, su, di).
- **A run date from an id convention** counts only when the source documents the convention. The fact
  `run-date-convention` is written, quoted, and carries a `pattern` with a named group `date` (YYYYMMDD). Cited in
  `run_date`, it reads the measure's row key (the value cell's row) or its `run-id` facts, and gives a stated run date
  (rule `run-date-from-id-convention`). An undocumented convention (assumed) gives nothing.
- **A Flex or batch tier cost** (a `price-tier` fact, term flex / batch / …) is re-priced to standard by the tier's
  proven uniform factor, then priced as any cost (rule `cost-tier-factor`). The factor comes from prices.json: the
  tier entry's `factor`, or its classes as one uniform multiple of the standard's over the price date. No such entry,
  a non-uniform tier, or two factors → `out:cost-not-comparable`. The fit table carries the standard-equivalent cost.

## Settings

| Setting | Values | Effect |
|---|---|---|
| `cost_method_unstated` (`--cost-method-unstated`) | `single-per-table` (default) · `out` | A cost with no `cost-method` fact. `single-per-table`: each table, chart or prose block of a source counts as one method of its own (`unstated[<source>/<table>]`), never mixed with another source's, and the row is flagged `cost-method-assumed-single`. `out`: the cost gets `out:cost-not-comparable`. **The maintainer has not decided.** |
| `--fit-models` | a file, `catalog`, or omitted | The model list used by step 10 (≥ 2 couples), by the legacy admission, and passed to `lqm.load`. |
| `class-ratios.json` (`--class-ratios`) | optional registry file | Feeds `cost-class-ratio`. Its shape is checked, but it has no schema yet: `{"ratios": [{"model", "change": <date>, "classes": {cls: {factor, sd}}, "setups": {setup: cls}, "measures": {ref: cls}}]}`. It applies to a cost whose price date ends before `change`. Without the file, the class-ratio step never fires. |

`rules.json` is optional: the build records the rule ids it applies but reads nothing from the file. So is
`price-tables.json` (schema price-tables.schema.json; validate.py checks its cards' models and routes).

## Pilot fixes (ObviousBench conversion, 23 Oct)

- **`reasoning-included-in-out` is a boolean.** Its `term` is `true` or `false` (vocab `boolean`, required). `true`:
  the reasoning is inside output. `false`: it is added to output. No fact: both readings are tried by
  cost-delta-on-source. The HotKV example now says `term: true`.
- **Precision per column.** A table column may carry its own `precision`, which overrides the table's (exact counts
  and printed costs in one table).
- **A derived cell is a computed fact.** It has `level: computed`, `rule` (`cell-difference`: inputs[0] − the
  others; `cell-sum`) and `inputs` (facts or cells), plus the stated value. The build recomputes it and refuses it
  (`out:no-proof`, on the axis using it) when the stated value differs beyond the roundings: half a unit of each
  rounded number, and a plain integer is an exact count. Its precision is its inputs' readings combined.
  validate.py checks the rule, the inputs, and that no other fact carries them.
- **Model facts.** `fields.model.resolution` lists, per model fact, its value, the keys it gives and its outcome:
  `decided`, `agrees`, `contradicts: gives K`, `unresolved: why`, `not accepted`, or `mode: K → K-pro`.
  `decided_by` names the fact that gave the key.
  - Two facts giving two keys → `not-established:contradictory`; the detail says when one key is a mode of the other.
  - Two mode facts selecting two keys → `not-established:contradictory`.
  - **(decided)** A model fact that resolves to no key refuses the model even when another fact resolves (doubt →
    out). It gets `not-established:absent`, with the reason `unresolved model fact '<value>'`, and gaps.py lists the
    name to register.
- **validate.py's output.** It prints one section per findings or decisions file, with its own errors and warnings,
  then the registry's section: its errors in full, and its warnings counted by kind. `--verbose` lists them all.

## Registry checks added after the registry review (23 Oct)

validate.py now reports these as errors (an error stops the build):
- a model's default or conversion naming a configuration that does not exist on the record's start date. Outlasting
  the configuration's dates is an error too;
- the same for a route's `accepts` and route defaults, except that outlasting is only a warning there: a host may keep
  serving open weights after the maker's API stops;
- a price starting before the model's release;
- a price whose `to` lies after `as_of`;
- an evidence record without a saved file or a quote. A findings fact cited by `source` and `fact` carries its own.

The placeholder `legacy` setup now has a headline by decision (no evidence), and the examples' five OpenRouter
evidence records have quotes from their saved listings. data/registry had 287 errors against these checks (the review's
items 2, 5 and 6); since the registry fix of 26 Oct (below) it has **0 errors** with `--check-files`.

## Registry fix (26 Oct)

The gap parts were merged and the review's must-fix items fixed (/work/.salvo14/mig/registry-fix/report.md). The build
reads two new things:
- **Split defaults.** A maker default may carry `setting`: `thinking` (what a call with no thinking field gets) or
  `effort` (the level a call that turns thinking on gets when it sends no level). A call with neither gets the whole-call
  default, else the `thinking` one; a call with a thinking-on fact (or a name selecting think) gets the `effort` one,
  else the whole-call one (`maker_defaults`). Anthropic Opus 4.5–4.8 and Sonnet 4.6: no thinking field → `nothink`,
  effort default `high` only with thinking on.
- **Per-provider route records.** A route's `level_mapping`, its route-wide `mapping` (new) and a model entry's
  `accepts`, `mapping` and `default` may carry `via` (the next step of the chain the record applies to), and the
  route-wide records `maker` and `models` (`step_filter`). A harness maps a level per provider: Inspect sends max as
  xhigh to OpenRouter, passes levels to Anthropic's 4.6+ models (minimal → low) and turns them into budgets on the
  earlier ones. Route-wide `mapping` is read after the model's own and before its `accepts`.
- `between-tools` was in the fit from 26 Oct (vocab x-terms `in_fit: true`, the coordinator); it is out again from
  29 Oct (`in_fit: false`, `out:effort-not-established`), as `lqm.EFFORTS` leaves it out (configurations per model).
- A model's configuration list may be empty: its configurations are not established (grok-4.20-multi-agent).

## Converter toolkit (`data/convert/`)

| Module | What it does |
|---|---|
| `mapping.py` | raw-data.csv rows ↔ a source's rows. Strategies are tried in order (an entry tag, then tokens + effort, …). A key pairs rows only when it is unique on both sides; ambiguous keys are reported. Unmatched rows are listed on both sides, and `legacy_ref()` gives each measure its reference. |
| `rules.py` | Value → fact-type rules for a column: `default` → no-effort-sent, `*_budget_<n>` → thinking-budget (term n), levels and `none` → the cell itself, `thinking` → thinking-on. Unknown values are reported, never cited. |
| `precheck.py` | Before a build: every model fact or cell resolved with the build's name rule (resolved, no key, several keys), and the prefix heads that name no route. |
| `gaps.py` | From a build's report, per source: heads, ids, configurations (not in the list, or none at the run date), defaults (none documented over the run) and prices (no registered or base price). |
| `reproduce.py` | The reproduction core shared with the build, and a CLI giving each row of a source CSV its status against a pinned table: reproduced / off / no-card / no-tokens, with the computed cost and the gap. |

## Settings

## Interpretations

These are the places where the spec left room. Items marked **(decided)** were settled by the coordinator on 22 Oct.
Items marked **(review)** were changed after the independent review (/work/.salvo14/review-build/review.md). Items
marked **(method)** remain method questions for the maintainer.

**Proof and reading**
1. A table cell is read from its saved file, CSV or JSON. If the file is unreachable, its sha256 does not match, or
   the table is neither, the measure gets `out:no-proof`. **YAML and HTML tables can wait**: validate.py warns about
   them.
   - **JSON tables.** The table's `where` is a JSON path in the subset `$`, `.key`, `['key']`, `[n]`, `[*]`, and
     validate.py rejects a JSON table whose `where` is not one.
   - The path leads to a list of row objects, or to an object whose values are rows; `row_key: "$key"` then means the
     object's keys.
   - A column is a key of the row object, else a dotted path inside it (`cfg.effort`).
   - Numbers are kept as written: the file is parsed with numbers left as text.
2. A value or cost that cannot be read as a number gets `out:no-proof`. **(review)** Proof is checked per axis (step 1
   reads every fact *used*). Faults in `spend` and `usage` do not take the quality out. Faults in the score, `runs`
   and `judge` do not take the cost out. A source-wide fault takes both out.

**Run date**

3. A `run-date` fact that cannot be parsed is ignored, and the default bounds stand. Several `run-date` facts give
   [earliest day, latest day]. **(review)** When stated bounds contradict each other (or the publication), the run
   date gets the widest interval, default bounds included, and the level `contradictory`. If a dated event of the
   model falls strictly inside that window, the measure gets `out:contradictory`; otherwise the run date is not
   needed. A dated event is any bound of its records in models.json or routes.json, or of its prices.
   A model released after the stated upper bound is no contradiction: that is early access by date (step 5); for an
   alias, the older candidate is then placed by that bound (28 Oct).
   A stated lower bound before the model's release is raised to the release (no early access stated or by date):
   a harness commit pinned before the model existed does not open the run before it (28 Oct).
4. The commit date is taken from the capture of that commit. When the source has no publication date, no capture and
   no commit, the upper bound is the harvest.
5. **Early access (decided).** A configuration dated from the release (`from_basis: release`) covers an early-access
   run. Without this, no early-access run could ever have a configuration. Records dated by captures are not extended
   this way, and an alias's `serves` intervals are always date-checked. **(review)** For an early-access cost, the
   price date's lower bound is the release, since list prices start there.

**Model**

6. **Alias (review).** For a name that has served several keys, the run interval is computed once for all candidates:
   its lower bound is the earliest candidate's release. A candidate wins only if that interval lies inside one of its
   `serves` intervals, so an interval straddling the switch is ambiguous and never resolves to the newer model.
   docs/DATA-PIPELINE.md §5.1 now says so.
7. A `mode` fact that matches no registered mode leaves the model not established. "A route that cannot separate the
   mode" is read as any router on the chain, because routes.json has no field for it. **(review)** When the route is
   unknown, a router among the candidate routes counts too.

**Route chain**

8. Route facts resolve by their term, then the prefix head, then a route's spellings.
   - A chain that names only harnesses counts as route unknown.
   - **(registry review, 23 Oct)** `maker-api` closes a chain only when nothing else serves the run (a harness
     alone, or nothing). The maker's conversions and defaults reach a run only through the maker's API or a reseller,
     never after a router, a host or self-hosting. A configuration the maker converts is therefore not established
     through a router, and a router without its own documented default gives no default.
   - A reseller uses the maker's defaults, with conversions dated under its own route id.
   - **(the maintainer, 3 Nov 2026)** « OpenRouter accepte les mêmes niveaux d'effort que l'API du fabricant et les
     transmet tels quels, sauf là où sa doc documente une conversion pour ce modèle. » routes.json gives a router a
     route-wide, dated `accepts_maker` record (with its `decision` and evidence): for a model whose route ids overlap
     the run, the step's accepted levels are its own `accepts` plus the model's configurations (models.json) covering
     the run (rule `router-maker-levels`). A model `mapping` is still read first, and a level neither mapped nor
     accepted falls to `level_mapping` (nearest supported). A maker level that a model `mapping` converts over part
     of the run only is not established (doubt → out; Sonnet 4.6 runs from its release, 17 Feb, the conversion dated
     from the 19 Feb capture). OpenRouter's record runs from its first capture describing
     `reasoning.effort` (26 Feb 2025: « For models that do not support effort-based reasoning, if effort is specified
     it will be converted ») to the last capture (29 Oct 2026).
   - OpenRouter's effort → `budget_tokens` formula ("Reasoning Max Tokens for Anthropic Models") had been written as
     a `budget-converted` mapping of every Claude model; it applies only to the Claude models that take a budget and
     no effort (« For models that only support reasoning.max_tokens , the effort level will be set based on the
     percentages above. »). Kept: Sonnet 3.7, Opus 4, Opus 4.1, Sonnet 4, Sonnet 4.5, Haiku 4.5 (Anthropic: « If your
     model supports only extended thinking (Claude Sonnet 4.5 (deprecated), Claude Opus 4.5, Claude Haiku 4.5, and
     earlier Claude 4 models) … »), and Opus 4.5 (the maintainer, 3 Nov 2026: /models exposes no effort selection for
     it). Opus 4.6 and Sonnet 4.6, undecided on 3 Nov morning, were decided later that day (see "Added on 3 Nov
     2026"). Removed: Opus 4.7, Opus 4.8, Opus 5, Opus 5.5, Sonnet 5, Sonnet 5.5, Fable 5, Fable 5.1, Haiku 5.5
     (Anthropic: « Claude 4.7 and later models do not support it and reject requests that use it, returning a 400
     error. »; OpenRouter: « Claude receives both fields unchanged », « Anthropic’s xhigh and max levels stay
     reasoning efforts »). Their documented `minimal → low` is recorded from 8 Sep 2026 (« Claude accepts low ,
     medium , high , xhigh , and max ( minimal is sent as low , none is rejected). »).
   - **(the maintainer, 2 Nov 2026)** « En aucun cas on suppose l'API si on n'a pas l'info. » The route is unknown when
     the measure's `route` slot names nothing, only a harness, or a name no route resolves; `maker-api` is never
     presumed. This replaces the rule `route-presumed-maker-api` (26 Oct, commit f958e43), under which a source naming
     no router, reseller or host was taken to have run through the maker's API (flagged); rule and flag are gone.
   - When the route is unknown, the candidates are `maker-api` plus every route whose entry for the model has a
     dated record overlapping the run, each after the harness when one is named (`chains`, rule
     `route-unknown-candidates`). `over_chains` evaluates the configuration (requested level, label, mode, the maker's
     or a route's default for `no-effort-sent`) over every candidate and accepts it only if all agree; otherwise
     `not-established:absent`, detail "candidate routes disagree: …". A closed harness whose label is the level
     (`closed-harness-label`, 26 Oct) still closes its chain with `maker-api`.
   - Only the `route` slot builds the chain: a harness in the `harness` slot or a route named in another slot's
     sentence is not read. On 2 Nov the routes the converters had already cited for the run were added to the
     `route` slots (a harness-slot fact naming one route, with its `term`; a model-api-id whose prefix names a route;
     a new fact quoting a sentence about the run), never from a mention in passing. On 3 Nov the same was done for
     measures whose route was already stated and whose harness slot names another harness (point D, 964 measures).
   - **(the maintainer, 3 Nov 2026)** A harness with a `calls_route` (Claude Code → `maker-api`) closes the chain with
     that route when the slot names only harnesses (rule `harness-calls-route`); OpenRouter's own level list decides
     where it exists (rule `router-listed-levels`); a router's defaults are bridged over gaps between captures as the
     maker's (`default-bridged-gap`). See "Added on 3 Nov 2026".
   - On the cost axis the chain names the cost part (`maker-api`, a stated chain, or `unknown` when several
     candidates remain) and the reproduction card (a route-specific card only for a single chain). Re-pricing reads
     the maker's API prices for every measure, the route stated or not (see the open question in PASSES.md, 2 Nov).
9. **Undocumented steps (decided: strict; the registry will document each harness).** A non-maker step that documents
   nothing covering the run (no mapping, `accepts` or `level_mapping`) leaves the configuration not established. It is
   not assumed to be identity. This also applies to step 7 through a harness.

**Configuration**

10. Settings resolve in this order:
    - level ids, and `x-high` / `extra high`;
    - vocab spellings of kind `setting`, tried on the value and, for a table cell, on `<column>: <value>` (so a
      `reasoning_effort` cell `none` gives `nothink`);
    - `key: value` lines;
    - a number → `scalar-<n>`;
    - `adaptive`, `auto`, `dynamic`, `default` or `enabled` → not established;
    - anything else → not recognised.
11. **(review)** Every requested configuration goes through the route chain, including a level the model does not
    list: a router's nearest supported level (xhigh → high) applies. A step matches only when what comes out is one of
    the model's configurations. A result outside the list counts for nothing when another fact matches, and gives
    `out:effort-not-established` when none does.
12. **(review)** Labels resolve in this order:
    - the label rule: a label naming exactly one level ("high", "high (thinking on)") is that level;
    - then the vocab spellings of kind `label` (nothink spellings before think spellings).

    `label-to-ladder` maps lowest / least / minimum to the lowest level and highest / maximum / most to the highest.
    **(decided)** "Lowest" is `ambiguous` when `nothink` is also in the model's list. `think` is never on the ladder.
13. A `config-history` fact takes its interval from the first two ISO dates in its `where`, and that interval must
    cover the run.
14. Only configurations that are established and listed are compared for contradictions. "The more specific statement
    of the same call" covers two cases:
    - `no-effort-sent` with a name's `selects` or a thinking-on/off fact giving `think` / `nothink`;
    - **(review)** thinking on with a level: the level.
15. Budgets within 5 % are clustered per model across the build; the cluster takes the name of its smallest budget.

**Value**

16. **(decided)** A value whose level is `not-established` (absent, assumed or ambiguous) gets
    `out:value-not-established`. A contradictory value keeps `out:contradictory`.
17. **mean-of-runs.**
    - Per-run values go in the measure slot `runs`: fact type `run-score`, with `term` and `scale` as for a score. A
      fact names its run in its `run` field; a table cell's run is its row key.
    - A `failure` (or `partial`) about one run names that run; validate.py checks that it is one of the runs cited.
    - The mean is recomputed without the failed runs, but only after checking that the mean of all the runs reproduces
      the source's value (within one unit of the last digit of the value plus one of the runs).
    - It stays `out:failed-run` when a failure names no run, when the runs do not reproduce the mean, and on the cost
      axis.
    - The `partial` exception ("scored as wrong") is found in the fact's text.
18. **Uninformative (decided).** A score counts as uninformative when it is exactly equal to a bound of the setup, and
    some but not all couples of the group sit at a bound. A group where every couple is at a bound is left to lqm's
    saturated rule.
19. Scale conversion takes the target scale from the setup's `bounds`: upper 100 → percent, upper 1 → fraction. A
    `raw` score is left as it is. **percent-from-counts**: a score written as counts ('45 of 60', '3/4') has the
    scale `counts` and gives 100·k/N, k/N or k, exact, written to 6 decimals.

**Campaigns**

20. Replacement happens only between measures that passed steps 0–5, and only across sources. Sources are ordered by
    publication date, else earliest capture, else harvest. **(review)** An inherited version is the latest in natural
    order (10 after 9).
21. **Rating boards (decided).** Rating boards and run boards are treated the same way: within a campaign the later
    value replaces the earlier, and a new version starts a new campaign for both kinds.
22. A stated `same-runs-as` names the other source by its id or one of its URLs, and links measures within one
    benchmark family. **(decided)** It counts as proven when ≥ 2 shared couples have identical costs (§3's closeness
    test) and at least one score differs; identical scores are left to lqm's republication rule.
    **(review)** Only a later measure accepted on quality replaces the earlier grading, couple by couple. The earlier
    cost goes out only when the later cost is accepted.
23. **Composite residuals (decided).** A residual is computed only for a linear composite with no normalisation:
    - the weights are normalised to sum to 1, and the residual is (C − Σ present ŵ·c) / Σ missing ŵ;
    - **(review)** each component is first put on the composite's scale (×100 or ÷100 between fraction and percent
      bounds). A component on any other scale refuses the residual, flagged `composite-residual-refused:scale`;
    - components come from the same publisher, each at its latest snapshot;
    - the residual's group is the residual setup × publisher × the composite's source;
    - cost residuals are not computed: `lqm.load` drops the composite's cost row in phase 1.

**Cost**

24. Measures citing the same cost facts in one source are one cost measure. It is carried by the measure on the
    headline metric (else the first); the others copy its status and are counted once.
25. The basis comes from the `cost-basis` fact, else from the method's basis, else `unknown`. **(review)** Prices are
    read only in the cost's currency, for the base price and for the price vectors alike. A cost whose currency has no
    registered price, or whose currency is unstated, is not re-priced, and with no covered price it gets
    `out:cost-not-comparable`.
26. The price date:
    - `publisher-table` is treated as "a source that recomputes at its current price": the price date is the capture
      dates of `value_seen_in`, else the harvest;
    - a stated date is the first date found in a `price-table` fact.
27. **(decided)** The base price, in the cost's currency, is, in order:
    - the entry marked `base`;
    - else the standard maker-API price in force on `as_of`;
    - else, for a retired model (no maker-API price in force on `as_of`), its last list price: the latest standard
      maker-API entry, flagged `base-last-list-price`.
28. "The publisher's own figure at the base price" means that every price that could have applied over the price date
    equals the base price.
29. `cost-delta-on-source` applies when:
    - exactly one price vector applies over the price date;
    - tokens are given per class;
    - the usage and spend units agree.

    The tolerance is one unit of the cost's last digit, plus the largest relative rounding of the token counts × the
    computed cost. `tokens-reasoning` is tried both added to output and not, unless `reasoning-included-in-out` is
    stated.

    **Long-context tiers** are folded into the price vectors as `lc><threshold>:<class>`. They are applied only when
    `requests` and `tokens-in-per-request` are both known:
    - every call at or below the lowest threshold → the standard prices;
    - a single request above a threshold → that tier's prices;
    - otherwise the cost is not re-priceable.
30. `cost-uniform-factor` requires every candidate vector to be the same uniform multiple of the base. **(decided, the
    maintainer, 3 Nov 2026: every cost of the fit is at the current price, rule `cost-current-price-only`)** A cost
    that no rule brings to the base price gets `out:cost-not-comparable`; the unrepriced model's own subset (its
    registered prices uniform multiples of one another, a single vector counting: a cost kept at its old price,
    flagged `cost-unrepriced`) no longer exists. A price band (`cost-price-band`, 29 Oct) stays only when its reference
    vector is the base price itself. When no registered price covers the price date, the cost gets
    `out:cost-not-comparable` (as before). Rule 28 (the publisher's own figure: every price over the price date equals
    the base) is unchanged; it is the case where nothing needs bringing to the current price.
31. In the partition, the route key is the single candidate chain, else `unknown`.

**Fit tables and groups**

32. A group is named:
    - by its setup id;
    - plus `@<publisher>` only when the setup has several publishers in the build;
    - plus `#<campaign>` only when the setup has several campaigns;
    - for cost groups, plus `~c<n>` only when the quality group has several cost subsets.

    Legacy rows keep their own group.
33. `data.csv` holds every measure:
    - its `effort` is the configuration, or its level when not established;
    - its `model` is `?<verbatim>` when not established;
    - a cost-only measure has a blank quality status, and a measure with no cost has a blank cost status.
34. A decision `in` overrides every step, including the group step, and its couple counts in its group. A headline
    decision with a `publisher` decides for that publisher's measures.
35. `lqm.EFFORTS` holds every configuration the build writes (`nothink`, `minimal`, `low` … `max`, `think`, `solo`;
    configurations-per-model method change, 29 Oct): the vocab terms `in_fit: true` but `think-<n>`, both ways (a test).
    A fit-table row `lqm.load` filters out for its configuration gets `out:effort-not-established` (`legacy:out:
    effort-not-in-efforts` for a legacy row), so that no status says `in` for a row the fit drops; one filtered for
    another reason (a model outside the fit's list) is recorded as `lqm_outcome` only, the tree's status stands.
36. Precision:
    - printed: the step / √12 (the precision's `step`, else the last written digit);
    - chart-pixel: the given `sd`, or blank when none is given;
    - exact: 0.

## The review's fixtures

All 26 of the review's fixtures are in the suite (`data/tests/review_tests.py`), and every one passes. One
expectation was changed, because the spec makes it wrong: `same_runs_regrade_later_refused`. The review expected the
earlier a1 to stay `in`. But the accepted regrade b2 does replace b1 (same runs), and that leaves a1 alone in its
group, so a1 is `out:single-couple`. What the test is about still holds: the refused a2 replaces nothing. robust.py's
34 cases end in a result or a clean error; none gives a traceback.

## Schema changes made for the pilot fixes (23 Oct)

- `vocab.json`:
  - the vocabulary `boolean`;
  - closed terms for `reasoning-included-in-out` (boolean) and `price-tier` (price kinds);
  - fact types `run-date-convention` (slot `run_date`) and `price-tier` (slot `spend`);
  - the level `computed`;
  - rule ids `cell-difference`, `cell-sum`, `run-date-from-id-convention`, `cost-tier-factor` and
    `cost-reproduction`.
- `source.schema.json`:
  - the fact fields `rule`, `inputs` and `pattern`;
  - a table column's `precision`.
- `measure.schema.json`: `legacy_ref`.
- `price-tables.schema.json`: new.
- `validate.py`:
  - computed facts, run-date conventions, price tiers and pinned tables;
  - `legacy_ref` claimed once;
  - price-tables.json cards;
  - the per-file summary.

## Schema changes made for the build (22 Oct)

- `vocab.json`:
  - fact types `run-score`, `tokens-in-per-request` and `legacy-row`;
  - measure slots `runs` and `legacy`;
  - the fact form `legacy`;
  - the score scale `counts`;
  - the reason codes `out:value-not-established` and `legacy:in` / `legacy:out:<why>`.
- `measure.schema.json`: the slots `runs` and `legacy`.
- `source.schema.json`: the fact field `run`, the source's `legacy` block, and a JSON path as a JSON table's `where`.
- `validate.py`:
  - JSON tables;
  - run-scores and the failures naming their run;
  - counts scores;
  - legacy facts and measures;
  - a decision on a missing measure is a warning (reported, not applied);
  - file caches keyed by modification time.

## Tests

`python3 data/tests/run.py` runs 129 fixtures (counts below as of 23 Oct; `fit_reads_build_tables` and `site_ladder_switch` added 29 Oct, `cfg7_default_bridged_gap` and `cost_stated_prices` later that day): 55 in run.py (the build's, the merge's `ext_*`, and the registry fix's
`ext_split_default_thinking_and_effort` and `ext_harness_per_provider`; `ext_between_tools_in_fit` replaces the
not-fitted test), the review's 26, and 15 for the pilot fixes and the registry review (data/tests/pilot_tests.py). Between them they cover:
- every reason code;
- configuration steps 1–8;
- the run-date, campaign and cost rules;
- JSON tables, mean-of-runs, percent-from-counts and long-context tiers;
- a retired model's base price;
- decisions and the stale hash;
- the legacy path and the per-source diff;
- clean errors for bad arguments;
- the three examples.

Separately, 45 faults were planted, each switching one step off in turn in build.py, build_lqm.py or validate.py:
- the original 23;
- one for each review fix;
- one each for the digit formats;
- one for argument checking;
- five for the legacy path.

Every one made a test fail. For the pilot fixes and the registry review, 30 more faults were planted and 29 are
caught. The other one
(dropping the "documented" check on a run-date convention) cannot change an outcome: the level filter before it, and
validate.py's quote rule, refuse an undocumented convention anyway. `data/tests/acceptance.py` is the legacy
acceptance test. As a negative control, it
reports a dropped row, two swapped rows and a changed digit.

**The fit reads the build (29 Oct).** The final data set is in the repository: data/findings holds the converted
sources and the legacy files of the 10 sources kept as legacy (not convertible or held: arxiv-2607.15524,
arxiv-2609.34913, codesota-openrouter, github-ai-arena, github-costrouter, github-effort-pick, note-tank_ai,
tokenvalue-2609.33970, youtube-aiseikatsu, youtube-ichbinfabian; 73 measures); the registry has the setup and publisher
`legacy` (the build no longer supplies them); `raw-data.csv` at the root is the frozen legacy input those files and
the converted measures' `legacy_ref` point to (v2026.10.21 repriced, sha256 489b5d48…). `validate.py --check-files`:
1,928 files, 0 errors. The build (`--fit-models catalog`, lqm step) gives lqm.load quality 1,608 groups / 17,705 rows
and cost 923 / 8,403, as the reviewed after-build (/work/.salvo14/mig/final/after; its tables differ only by the 10
`between-tools` rows, out since 5096cac). What still reads `raw-data.csv`: data/legacy.py and data/tests/acceptance.py
(the legacy path, IDENTICAL), data/convert/mapping.py (a conversion's legacy_ref) and validate.py --legacy-coverage;
data/precision.py still names it (it wrote the precision columns; the facts' precision model replaces it, it is not run any more).

## Not implemented yet

- cost residuals of composites;
- conversion between currencies (`currency-fixed`);
- YAML and HTML tables.

**Price band (29 Oct, the maintainer).** An unrepriced cost whose price vectors over its price date differ in some
classes only (Sonnet 5.5's cache read halved on 7 Oct) is no longer out: at the latest vector its cost lies between
raw × the smallest and raw × the largest per-class ratio; the row keeps the middle, its sd grows by the band's uniform
sd, flag and rule `cost-price-band`. Vectors of different tiering stay out.

## Added on 29 Oct, later

**A default bridged over a gap without captures (rule A, the maintainer, 29 Oct).** A model's documented default
covers only its records' intervals, so a run between two records fell on `no documented default of <key> covering the
run`. When two default records of the same model and the same `setting` give the same configuration on both sides of
a span no record covers, the span is covered too (`ctx.bridged_defaults`: the records of one setting walked in order of
their start, consecutive ones of one configuration merged), only if:
- the two records give the same configuration (another configuration between them ends the chain; validate.py already
  refuses defaults of one setting that overlap, so no other record can state another configuration inside the span);
- no name of the model (`names`, any route) starts or ends inside the span (a name that changed meaning across it →
  no bridge);
- the records are of one setting (`thinking`, `effort` or the whole call: never across settings) and of one model key.

A bridged record is used only where no record of its setting covers the run, so every run a record covered keeps its
outcome. The span carries the basis `bridged` (`fields.default_bridged`: `[{from, to, basis: bridged}]`), the measure
the rule `default-bridged-gap` and the flag `default-bridged` (in the fit tables' confound column). Bridged spans in
the registry of 29 Oct: qwen3.6-plus (think, 21 May → 19 Oct), qwen3.5-plus (think, 8 Jun → 19 Oct), qwen3.5-flash
(think, 14 Jun → 19 Oct), sonnet-4.5 (nothink, 1 Apr → 28 Sep), opus-4.5 (thinking off, 1 Apr → 1 Jul → 28 Sep) and
opus-4.7 (thinking off, 1 Jul → 28 Sep); sonnet-3.7's span (25 Feb → 23 May 2025) is not bridged, its OpenRouter id
starts inside it (3 Mar 2025). In the build of 29 Oct it decides 9 measures (2 come into the quality fit, 1 into the cost fit); the 27 vals.ai qwen3.6-plus runs stay out: their run interval starts at the release (2 Apr), before the first record (18 Apr), which no bridge covers. Test `cfg7_default_bridged_gap` (and its negative controls: another configuration after
the gap, another record inside it, a name starting inside it, a record of another setting on one side).

**A cost priced by the source's own stated prices (rule B, the maintainer, 29 Oct: "if the source gives the price,
where is the problem?").** A `price-table` fact (or a table column `says: price-table`) whose `term` is a price class
(vocab `price_class`: input, output, cache-read…) states the price the source applied to that class: `value` is the
price per million tokens in the cost's currency, the agent's reading, with `written` the printed text (validate.py:
a number, and a term that is a price class or a price-tables.json id). The build reads them as the cost's own price
vector (`stated_prices`; two different prices for one class → not used, `fields.cost.stated_prices.why`). When no
registered price covers the cost's price date (`prices over the price date not registered`) and a base price is
registered, the stated vector stands for the prices over the price date and the cost is re-priced to the base price
by the usual steps (the publisher's figure, the delta on its tokens, a uniform factor over the classes both state;
equal prices → factor 1); rule and flag `cost-stated-prices`, `fields.cost.stated_prices.used`. A registered price
over the price date still decides (the stated vector is then reported, unused), so no cost re-priced before changes. A
class price is never a price date (a date stays its own `price-table` fact), and a class term is not a pinned table
(`cost-reproduction`). A Flex / batch tier cost is not priced this way. Test `cost_stated_prices` (negative controls:
nothing stated, two input prices, a registered price over the price date, no base price, a price written in the source's
notation).

vals.ai: each board's `Input / Output Cost` (older layout: `Cost In / Out`) cell became two such facts (input, output),
quoted with the row's visible text up to the cell, cited by every cost measure of the row: 4,112 facts in 51 sources, 2,056 of vals.ai's 2,091 cost measures (24 rows not on the page, 11 models on several rows of one board, left without). In the build of 29 Oct the rule prices 404 costs, 278 of them come into the fit (245 by a uniform factor, 33 at equal prices; the others are single couples or composites), among them 25 of vals.ai's 26 qwen3.8-27b costs; lqm.load cost 922 groups / 8,680 rows (before 923 / 8,403). Over the price dates the registry covers, the stated vector equals the registered one for 712 costs and differs for 65 (Gemini 3.8 Flash and Gemini 4 Argon shown at their list price during a promotion, DeepSeek V4 Flash 0731, GPT-5.6 Sol): there the registered price decides. A cost stated
this way prices input and output only; a run's cache reads (vals.ai's token totals carry them, outside the measure's
usage slot) are taken at the ratio of those two classes.

## Added on 30 Oct

**A uniform factor across long-context tiers (the maintainer, 30 Oct).** A cost whose model has long-context tiers
(on the base vector or on a vector over its price date) was re-priced only once `requests` and per-call sizes told
which side of the threshold its calls fell; otherwise it stayed unrepriced (`long-context tiers: requests and per-call
sizes not stated: not re-priceable`) and formed a subset of its own model, so only its own efforts' ratios counted —
groups of one model, whose offsets mixed badly in the cost fit of 29–30 Oct. When every price vector over the price
date relates to the base vector by one common factor on every class of the base vector, its tiers included
(`exact_factor`: the same tiers on both sides, every class of the base priced, one ratio throughout), the cost at the
base price is exactly cost × that factor whatever the token mix and whichever side of a threshold the calls fell: the
base value is cost × factor, the uncertainty × the factor, rule and flag `cost-uniform-factor-tiers`, and the measure
joins the re-priced subset of its part. Equal vectors stay `cost-publisher-figure` (× 1); several vectors at different
factors to the base (a launch price and the cut over one price date; Gemini 3.6 Flash's list price and its promotion)
and changes in some classes only (Sonnet 5.5's and Grok 4.5's cache read, GPT-5.6 Sol's promotion) are not exact and
keep the unrepriced path (own subset, `cost-price-band`). A promotion is never the base, as before. Without tiers
nothing changes: the existing uniform factor (`cost-uniform-factor`) already applied there. Test
`cost_uniform_factor_across_tiers` (negative controls: a change in the tier's cache read only; the tier missing on the
old side; two prices over the price date at × 0.2 and × 0.1).

The registry's 9 Jul standard entries of GPT-5.6 Luna and Terra lacked the long-context tier their own evidence quotes
(the 9 Jul page's 'Long context' columns: luna 2 / 0.2 / 9, terra 5 / 0.5 / 22.5); added, so both changed on 30 Jul by
× 0.2 and × 0.8 on every class and tier. In the build of 30 Oct the rule re-prices 219 costs (luna 109 at × 0.2, terra
110 at × 0.8; 212 were in the fit in single-model subsets, 7 single couples), all in 24 re-priced groups with other
models; the 40 single-model groups of luna and terra they formed are gone (oai56-lifesci: ~c1 luna, ~c2 terra and ~c3
gpt-5.4 / 5.5 / 5.6-sol are one group). With the tier registered, 286 luna and terra costs whose price date spans the
30 Jul cut (two vectors, × 1 and × 0.2 or × 0.8 to the base: not exact) pass today's rule for a uniform change over the
interval and come in as subsets of their own model (before: `out:cost-not-comparable`, the vectors' tiers differed):
53 such groups. lqm.load cost 936 groups / 8,966 rows / 275 couples (before 922 / 8,680 / 275), single-model cost
groups 285 (before 272); quality unchanged (1,607 / 17,714 / 334, the same prepared data).

## Added on 3 Nov 2026

The maintainer's decisions of 3 Nov 2026 (after « OpenRouter accepte les mêmes niveaux d'effort que l'API du fabricant
… », same day):

1. **Opus 4.6 and Sonnet 4.6 through OpenRouter: the effort passes as sent**, as for Claude 4.7 and later. OpenRouter's
   doc converts only « For models that only support reasoning.max_tokens , the effort level will be set based on the
   percentages above. », and /api/v1/models lists their levels (« "supported_efforts":["max","high","medium","low"] »
   from the 27 Jun 2026 capture). Their six `budget-converted` mappings are removed from routes.json; their
   `minimal → low` is recorded from 8 Sep 2026, as for 4.7+ (« Claude accepts low , medium , high , xhigh , and max
   ( minimal is sent as low , none is rejected). »).
2. **Opus 4.5: the conversion is kept** — /models exposes no effort selection for it (« "reasoning":{"mandatory":false} »).
3. **Gemini 2.5 (Pro, Flash, Flash-Lite): the conversion is kept.**
4. **OpenRouter's own list of a model's levels decides where it exists** (rule `router-listed-levels`). Where
   /api/v1/models lists the model's levels at the run date (`supported_efforts`, recorded as level `accepts` records of
   the model whose evidence quotes `supported_efforts`: `catalogue_listed`; a level read from OpenRouter's docs, such as
   "Can be high", is not the catalogue listing), they are what OpenRouter accepts: a level it does not list falls to its `level_mapping` (nearest
   supported, a tie → `ambiguous`). The maker's levels (`accepts_maker`, rule `router-maker-levels`) count only where
   /models lists no level of the model at the run date (before `supported_efforts` appears in the catalogue, 27 Jun 2026,
   or for a model it never lists). Thinking off / on (`nothink`, `think`) kept the maker's beside a listing in this
   first reading; the maintainer decided otherwise later the same day (see "Added on 3 Nov 2026, later": the listing
   decides them too, rule `router-listed-thinking`). The run interval is cut at every bound of the model's level records inside it
   (`listing_pieces`); each piece is read with its listing, or with the maker's levels where nothing is listed, and the
   step's result is kept only if every piece gives the same (else `not-established:absent`, detail "openrouter: the
   levels it accepts for K change over the run (…)"). Example: glm-5.2 at max, listed xhigh / high / none: max → xhigh
   (nearest), which the maker serves converted, so through OpenRouter it is not established. The level records that the
   old budget mapping had kept out of the Claude entries (Opus 4.6, 4.7, 4.8, 5, 5.5, Sonnet 4.6, 5, 5.5, Haiku 5.5,
   Fable 5) were added from the saved catalogue captures (runs of captures listing the same levels, first and last
   capture quoted).
5. **OpenRouter's defaults bridged over a gap between captures** (rule `default-bridged-gap`, as the maker's of 29
   Oct): `ctx.bridged_route_defaults(route, key)` merges two default records of one setting (and one `via`) giving the
   same configuration on both sides of a span no record covers, with the same conditions — another configuration
   between them ends the chain, and a name of the model (models.json) or a route id of the model (routes.json `ids`)
   starting or ending inside the span forbids the bridge; a bridged record is used only where no record covers the run;
   flag `default-bridged`, `fields.default_bridged`. Example: opus-4.8 on OpenRouter, nothink 29 May – 21 Jul and from 28
   Jul: the week between is covered. A default that differs from the maker's (Opus 5.5: high at OpenRouter, medium at
   Anthropic) stays as recorded.
6. **Claude Code goes directly to Anthropic** (rule `harness-calls-route`). routes.json gives a harness a
   `calls_route` (route, rule, date, decided_by, decision): when the route slot names only harnesses and all carry the
   same `calls_route`, that route closes the chain and no other candidate route is weighed. Claude Code →
   `maker-api`. No evidence saved in the registry states it (the 27 Mar 2026 model-config capture even names Bedrock,
   Vertex AI and direct API access as providers): the maintainer's decision of 3 Nov 2026. A route the slot names (a
   router, reseller, host) still makes the chain.
7. **A harness cited for the run beside a stated route joins the chain (point D).** Measures whose route slot names a
   route and whose harness slot names a harness not in the route slot (Terminus-2 + OpenRouter for quesma-baba) got
   that harness fact added to their route slot, by the path of 2 Nov (a harness-slot fact naming exactly one harness by
   its term or its value; a table cell only when its value is a spelling of the harness): 964 measures of 23 sources.
   Not applied (doubt): a quote about other models of the source (arxiv-2607.02436 F1 for its LM Studio Qwen runs), four
   harnesses without the measure's (arxiv-2605.10912 F2), a harness for some tasks only (arxiv-2609.36777 F6), a
   harness's tools rather than the harness (arxiv-2609.30123 F1); harnesses cited only in other slots (setup, other,
   spend) were not read.

Not changed (the maintainer): closed harnesses keep the maker's level for the label shown (`closed-harness-label`);
the repricing to the base price stays at the maker's tariff (OpenRouter charges the provider's prices).

Tests: `router_listed_levels`, `router_default_bridged_gap`, `harness_calls_route`, `harness_beside_stated_route`,
`registry_openrouter_budget_models` (each with its negative controls); `router_maker_levels` now gives its Opus-5.5-like
model no listed level (with one listed, decision 4 applies).

## Added on 3 Nov 2026, later

The maintainer's decisions of 3 Nov 2026, after the pass above:

1. **OpenRouter's listing decides thinking off / on too** (rule `router-listed-thinking`). Thinking off (`nothink`) is
   accepted only where /api/v1/models lists « none » for the model at the run date; where the listing exists without
   it, thinking off follows the route's rule (`level_mapping`, nearest supported, thinking off being the lowest step of
   the order `LISTABLE` = nothink, minimal … max; a tie → `ambiguous`), and the maker's thinking off / on count only
   where nothing is listed (`serve`: the listed regime keeps of the maker's configurations only those that are neither
   levels nor thinking off / on; `accept_or_map`: a thinking off asked for is mapped among the accepted levels, a level
   asked for still among the levels only). A route not named leaves the line out when the candidates disagree (maker
   API → nothink, OpenRouter → low). Thinking on without a level (`think`), which a listing never names, is not
   established under a listing (not decided by the maintainer; no measure concerned). Example: haiku-5.5 thinking off
   through OpenRouter on 13–14 Oct 2026 (listed low … max, « none » only from 15 Oct): → low.
   The maintainer's example, gpt-5.5, lists « none » from the first capture carrying `supported_efforts` (27 Jun 2026),
   so its nothink lines do not move; most other models list « none » only from 15 Oct 2026 (DeepSeek V4, GLM-5.2, Kimi
   K3, Gemini 3 Flash, Claude 4.6 – 5, Haiku 5.5, Qwen3.8-27B …).
2. **Registry pass: OpenRouter's `supported_efforts` copied mechanically** from every saved, dated /api/v1/models
   capture (196 captures, 2025-05-03 – 2026-10-29: wb-all, routes/evidence/openrouter, arb/apidefault/evidence/or,
   bd/b3/src/orwb, gaps-openrouter/wb-models, reg10/ev/live29; undated copies left out). Per model key and id at the
   capture date: runs of captures giving the same list; one level `accepts` record per listed value (« none » →
   nothink) from the first to the last capture of the run (`earliest-capture` / `last-capture`), evidence = the first
   and the last capture (file, sha256, `where` data[id=…].reasoning, quote the raw `"reasoning":{…}`); a start stated
   from OpenRouter's `created` date is kept when the run starts at that record's own first capture. Records are clipped
   to the model's own configuration dates (validate.py refuses a level the model has not then; `to_basis` stated, as
   before): the early ends the maintainer saw (DeepSeek V4 previews xhigh to 10 Aug / 19 Jul, gpt-5.1-codex and the
   codex models to 22 Jul, gemini-3.5-flash and 3.7-flash to 7 Oct) are the models' shutdowns in models.json, not
   captures left uncopied; past them the captures still list the levels (to 29 Oct). Listing records 446 → 515 over 37
   model keys; a value the model never has is copied too (warning "accepts …, not in the model's configurations"
   183 → 215; e.g. qwen3.8-max minimal, which OpenRouter lists).
3. **Claude Code with a model it has no entry for**: what Claude Code sends by default comes from its own saved docs
   only, never the maker's default. Saved docs: CHANGELOG 2.0.67 (npm 11 Dec 2025) « Thinking mode is now enabled by
   default for Opus 4.5 », without a budget (MAX_THINKING_TOKENS's default is in no saved capture) or an effort
   (model-config lists effort from Opus 4.6); nothing for Sonnet 4.5 or Haiku 4.5. A budget unknown names no
   configuration of Opus 4.5, so no default is recorded (note in routes.json claude-code); their lines stay out.
4. **Claude Code with another route stated** (komodor, Bedrock, Fireworks…): checked on the extracted quotes, the rule
   unchanged (a route the slot names makes the chain). 237 measures of 17 sources name Claude Code and a route (125 the
   maker's API, 112 another route); the quotes establish the route for the run in komodor (« Same agent (SREGym's stock Claude Code, CLI
   2.1.302) … on every Kimi K3 provider » with the row's provider), arxiv-2605.26548 (Bedrock), arxiv-2608.02670,
   arxiv-2609.04298, arxiv-2610.10513, bughuntbench, kernelbench, runebench, mazebench (OpenRouter), rtl-bench
   (llama-server), vercel-eve (AI Gateway). One conversion error fixed: arxiv-2607.02436 M13/M14 (Qwen in LM Studio)
   cited as harness F1 « Claude Code CLI ran Claude Opus 4.7, Claude Opus 4.6, Claude Sonnet 4.6 », a sentence on
   the Claude runs; their harness is now a fact copying their own table row (« claude_qwen_3.6_high_with_playwright
   Claude Code Qwen 3.6 High … »). In doubt, not changed: komodor M7 (Sonnet 5 · Bedrock baseline), whose harness
   quote speaks of the Kimi K3 providers.
5. **Harnesses cited only in setup / other / spend slots** (69 measures of 9 sources): a quote that describes the run
   gives the harness by the usual path (a harness fact copying it): arxiv-2610.12569 (M1 Codex CLI « GPT-5.5 with
   Codex CLI », M8 Claude Code « Claude Opus 4.8 with Claude Code », nine mini-swe-agent « All these models are paired
   with mini-swe-agent »), arxiv-2610.04432 M3–M9 (F2 « Seven model configurations use OpenCode 1.18.29 », the two
   others named in the same sentence), vals multi-agent M1–M4 (« opus’s costs are the list-price totals claude code
   reports »): 22 measures. Nothing for the 47 others: mentions in passing (rtx4090's test designer, bughuntbench's notes
   on other rows, runebench's cost script), a model name read as a harness (openrouter gpqa / tau2 « terminus »), or a
   harness already in the slot (arxiv-2610.11123).

Effect (`--fit-models catalog`, against 1fd65f4; attribution by a build with decision 1 off): fit-quality rows 17,781
→ 17,630 (lqm.load kept 16,775 → 16,632): 25 in, 176 out, 24 in both with another configuration — decision 1: 25 in
(sonnet-5 high 9 and opus-4.7 high 9 from Artificial Analysis, whose effort facts gave nothink and high: the nothink
reading is no longer established through OpenRouter, so the contradiction is no longer seen; kimi-k3 low 7, thinking
off → low), 174 out (nothink: qwen3.8-27b 31, opus-4.8 20, deepseek-v4.1-flash 20, glm-5.2 18, sonnet-5 17, haiku-5.5
16, deepseek-v4-pro-0813 14, opus-5 12, sonnet-4.6 8 …), 24 nothink → low / high; decision 2: 2 out (qwen3.8-max low:
OpenRouter lists minimal, which the model has not); decisions 3–5: none. Fit-cost rows 9,123 → 9,071 (kept 8,610 →
8,562): 7 in, 59 out, 7 changed, all decision 1. Couples gone: quality deepseek-v4-flash-0731, qwen3.8-27b, sonnet-5
nothink; cost deepseek-v4-pro-0813, deepseek-v4.1-flash, glm-5.2, qwen3.8-27b, sonnet-5 nothink.

Tests: `router_listed_thinking`, `registry_openrouter_listing_copied`, `harness_without_entry_no_presumption`,
`findings_harness_points_4_5` (each with a negative control that fails when its decision is switched off);
`router_listed_levels` now expects thinking off unlisted → the nearest listed level.

## Added on 3 Nov 2026 (route5)

The maintainer's decisions of 3 Nov 2026 on the points left open by the two passes above (routes, then dates):

1. **A contradiction the source writes is seen before the route** (rule `contradiction-before-route`). The effort
   facts are reconciled first on what they read (the configuration each asks for, before any route step), with the
   same rules as after it (`reconcile`: a level beside thinking on → the level; the more specific statement of the
   same call; a reading outside the model's configurations counts for nothing beside one inside). Readings that still
   disagree → `not-established:contradictory`, whatever the route then serves. Example: Artificial Analysis
   …-21#M1263, opus-4.7, facts nothink (F68) and high: thinking off is not served through OpenRouter, so high used to
   enter alone; now out. Readings from a default (`no-effort-sent`) are not readings and stay after the route.
2. **Thinking off asked for a model that has none at its maker** (kimi-k3 through OpenRouter): not established, no
   nearest level (`accept_or_map`; rule `router-listed-thinking`). Thinking off on a model that has it at its maker,
   « none » not listed, still goes to the nearest listed level.
3. **A level the router lists but the maker has not** (qwen3.8-max minimal): the line stays out (« minimal is not one
   of the model's configurations »); the listing is kept as copied. Frozen by `router_listed_level_model_lacks`.
4. **Opus 4.5 under Claude Code**: the saved docs (reg10/ev/live29 costs and model-config) say extended thinking is on
   by default with a fixed budget lowered by MAX_THINKING_TOKENS; its default is in no saved capture; a budget is out
   of the fit (22 Oct). The quotes are in routes.json claude-code `note`; nothing else is recorded; the lines stay out.
5. **Thinking on without a level under a router's listing**: accepted (`think`) where the listing names at least one
   level at the run date; a listing naming no level does not accept it. No measure is concerned today.
6. **komodor**: M7 (Sonnet 5 · Bedrock baseline) keeps Claude Code, its harness fact now copying the README, line 4
   (« We took an AI SRE agent running on a closed model (Claude Code on Claude Sonnet 5) »). Every config's route
   slot gets LiteLLM (fact copied from METHOD.md line 14, « | Model routing | LiteLLM `v1.101.6` sidecar … Claude Code
   and the judge both call it … »): chain Claude Code → LiteLLM → Bedrock / the host. routes.json gains `litellm`
   (class router, spellings only; nothing on what it passes on, no name prefix), so the strict rule (Interpretations 9)
   applies. The 7 measures were already out (M7: no effort fact; M1–M6: Claude Code has no default for kimi-k3).
7. **Every cost of the fit is at the current price** (rule `cost-current-price-only`, Interpretations 30): a cost no
   rule brings to the base price → `out:cost-not-comparable`; no subset of its own at an old price any more; a price
   band stays only when its reference vector is the base price. Example: the Sonnet 5.5 launch page (28 Sep), its
   Terminal-Bench 4.0 costs at the 0.20 cache-read price (0.10 from 7 Oct).
8. **Dates** (findings, offline, every quote an exact substring of a saved file):
   - a board's « last updated » label is written as `published`, as vals.ai's « Updated M/D/YYYY »: the upper bound
     of the run dates of every value on the page, not a publication date (`where` says so). 11 of the 17 cases;
     not written: designarena ×2 (the date is the Security page's `lastUpdated` in the payload), bird-bench (a news
     item's date), and three labels older than the release of a model the board shows (stagehand « Updated September
     3, 2026 » with Opus 5.5, wildclawbench « Updated 2026-07-20 » with qwen3.8-max, pinchbench « 08/18/2026 » with
     deepseek-v4.1-flash): such a label is stale, not an upper bound;
   - a page modified after publication: the modification date (JSON-LD `dateModified`, an « Update » line, Qiita
     `updated_at`) as `published`, the certain upper bound of the saved content (the schema has one date field; `where`
     says it is a modification date). 8 sources;
   - a printed run date: a `run-date` fact on the measures it covers: scorch-bench (« Run on 2026-10-09 », 9 measures,
     one fact per results file), roboco (« 실험일: 2026-10-18 (KST) », 30). The other printed dates of the list were
     already run-date facts, or are left (in doubt: a scoring file's date, a report's completion date, a results
     document's title date, a scoreboard's generation stamp; proposals in the step-2 list);
   - the date of another page than the values' (Gemini cards …): left empty.

Effect (`--fit-models catalog`, against b0fcfd1): fit-quality rows 17,716 → 17,696 (lqm.load kept 16,723 → 16,718):
25 out (decision 1: opus-4.7 high 9, sonnet-5 high 9; decision 2: kimi-k3 low 7), 5 in (scorch-bench kimi-k3 max and
qwen3.6-35b-a3b think, dated by its run date; 3 sonnet-5 high rows of AA 19 Oct no longer superseded by the 21 Oct rows
now out), no configuration changed; couples 337, Claude 55. Fit-cost rows 9,072 → 8,307 (kept 8,568 → 7,875): 765
out, 0 in — decision 7: 743 (gpt-5.6-sol 296, gpt-5.6-luna 166, gpt-5.6-terra 112, sonnet-5.5 96 + 5, gemini-3.6-flash
6 …); 1,183 measures of every status get `out:cost-not-comparable` by it; bands kept at the base price 109 (sonnet-5.5,
grok-4.5); dates: 15 (a price date ending at the label no longer covered by a registered price: aibenchy, cognition, nextjs; gemini-3.7-flash 9, gemini-3.5-flash 4 …); decision 2:
7. Cost couples 269 → 268 (gpt-5.2-codex xhigh: nextjs's single row, price date now 16 Oct). Claude cost rows:
sonnet-5.5 298 → 197.

Tests: `contradiction_before_route`, `thinking_off_without_nothink_at_maker`, `router_listed_level_model_lacks`,
`claude_code_opus45_budget_note`, `komodor_litellm_chain`, `findings_dates_route5`; `router_listed_thinking` (thinking
on under a listing), `cost_per_model_subset_and_single` and `cost_uniform_factor_across_tiers` updated (each with a
negative control that fails when its decision is switched off).
