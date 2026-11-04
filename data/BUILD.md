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
python3 data/tests/run.py [name-filter]                             # the tests (177 with .stan/venv/bin/python, about 13 s)
python3 data/tests/acceptance.py [raw-data.csv] [--registry data/registry]   # the legacy acceptance test (≈ 20 s; default: the repository's raw-data.csv)
python3 data/schema/validate.py [--verbose]                          # per-file summary; registry warnings apart
python3 data/convert/precheck.py SOURCE_ID                           # names and route heads against the registry
python3 data/convert/gaps.py data/build/status-report.json [--registry R --findings F]   # registry gaps per source
python3 data/convert/reproduce.py --tables … --table … --csv …       # per-row cost reproduction (pinned table)
```

The build runs in five steps:

1. **Validate.** It runs `validate.py`'s checks on the repository's files only: it never reads a saved copy (the
   maintainer, 4 Nov 2026: the findings write every value, the build is a filter; see « Added on 4 Nov 2026 (the
   findings self-sufficient) »). `--no-check-files` and `--registry-files-checked` are gone; the checks against the
   saved copies are `validate.py --check-files`, the writing agent's tool.
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
- with `validate.py --check-files` (the writer's check, not the build's), it is a line of the hashed CSV;
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
committed (`.gitignore`): rebuild it to read a measure's reasons (about 11 minutes, 4 GB).

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
- **A converter's loop** (27 Oct). `--registry-files-checked` (validate.py; build.py's until 4 Nov 2026, when the build
  stopped reading saved copies) skips the saved-copy checks of the registry's evidence only, on an unchanged registry
  copy; the findings' files are still checked. With one source's
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
    that no rule brings to the base price is brought to it by a price band (`cost-price-band`, 29 Oct) when every
    price over its price date is registered and shares the base price's classes and long-context tiers: the band is
    [raw × the smallest, raw × the largest per-class ratio base / old] over the cost's own price vectors (the bounds
    « mostly input » and « mostly output »), the row keeps the middle, the band's uniform sd added. **The band's
    reference is always the base (current) price (the maintainer, 3 Nov 2026, later: « les fourchettes de prix se
    calculent vers le prix courant »)**, never the last price seen, and each cost is banded on its own vectors (no
    condition on the other costs of its model); the banded costs keep a subset per model. A cost no band can bring
    to the current price (no registered price over its price date, or tiers / classes not shared) gets
    `out:cost-not-comparable`; the unrepriced model's own subset at an old price no longer exists. Rule 28 (the
    publisher's own figure: every price over the price date equals the base) is unchanged.
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

## Added on 3 Nov 2026 (route6)

The maintainer's decisions of 3 Nov 2026 (second set):

1. **A doubtful run date is an upper bound only** (`run-end`, « au plus tard le »), never a run date nor a lower bound:
   a date the source writes that does not say it is the run date (a scoring file's date, a report's completion date,
   a results document's date, a generated scoreboard), written only when it can only be on or after the run; in
   doubt, nothing. Applied (findings, every quote an exact substring of a saved file, the agent's normalised value
   beside the text as `written` where it differs): luminair (« **Date:** 2026-03-28 / 2026-03-30 » of each model's
   scoring file, 11 measures), llm-quant (« 报告完成时间：2026年9月30日 », 6), fable-mode (« # Benchmark results —
   2026-07-07 », 2), lhtb (each scoreboard's « _generated …_ », 16), ale (scoreboard « updated 2026-08-19 22:13 UTC »,
   4), discoverphysics (each arm's « 正式成绩单 (date) », official score sheet, 8), effortmining (the report's
   « Generated: » stamp, 60), kaybenleroll (the note's « Date: 2026-09-25. » for the three n=1 max arms, 3), miaai
   (the two cross-trial summaries' « **Date** », 2): 112 measures, 30 facts. Not applied: codereviewbench (« Skill
   matrix, 2026-10-02 » heads a document that reports a run of 3 Oct). validate.py compares an ISO date value with
   the date as written by its numbers in order (« 2026年9月30日 », « 2026-08-19 22:13 UTC »).
2. **Price bands toward the current price** (rule `cost-current-price-only`, Interpretations 30): the band's
   reference is the base price, never the last price seen, for every model. Example: GPT-5.6 Sol, base 5 / 30 / 0.5,
   the promotion 4 / 20 / 0.4 over the price date: the cost at the current price lies in raw × [1.25, 1.5] (it was
   banded toward the promotion and went out). `price_band` applies to the standard-tier cost when a proven tier factor
   applies, and a band of no width is that factor.
3. **OpenHands goes through LiteLLM**: the OpenHands Index ids are `litellm_proxy/<provider>/<model>`; each id's
   quote is copied as a route fact LiteLLM (term `litellm`) in the route slot of every measure (130), chain
   OpenHands → LiteLLM → the provider. Not a name prefix: an id under a route prefix resolves against that route's
   own names, and LiteLLM lists none (the model would no longer resolve). LiteLLM documents nothing: strict.
4. **A changelog is an « updated on » bound only when it says it records additions of models or results.** Kept:
   cognition FrontierCode (« Models added to the leaderboard and changes to how results are reported. », last entry
   13 Oct). Removed: posttrainbench (« Changelog Updated Oct 6 »: the heading does not say what it records). The other
   changelog dates are not « updated on » labels (an entry dating a given release: llmcost2026 v1.0, the arXiv
   2609.36647 dataset's 0.1.0) and are left.

Effect (`--fit-models catalog`, against f3ab153): fit-quality rows 17,696 → 17,696, couples 337; lqm.load kept
16,718 → 16,665 (−53 republished: the costs back in let republication detection match sonnet-5.5 20, gpt-5.6-sol 16,
gpt-5.6-luna 10, gpt-5.6-terra 5, fable-5 max 1, opus-5.5 medium 1). Fit-cost rows 8,307 → 9,050 (+743, all
decision 2: gpt-5.6-sol 358, gpt-5.6-luna 166, gpt-5.6-terra 112, sonnet-5.5 101, gemini-3.6-flash 6; 255 of them
were banded toward the promotion, 488 had one old price only); lqm.load kept 7,875 → 8,512; band rows 117 → 860;
cost couples 268. Decisions 1, 3, 4 move no fit row (the measures concerned were out on other grounds: the OpenHands
harness documents nothing; luminair, llm-quant, lhtb … no effort or no model established; 2 status changes only).
Claude: sonnet-5.5 cost rows 197 → 298.

Tests: `findings_doubtful_dates_run_end`, `openhands_litellm_chain`, `changelog_bound_scope`;
`cost_per_model_subset_and_single`, `cost_uniform_factor_across_tiers` and `findings_dates_route5` updated (each with a
negative control that fails when its decision is switched off).

## Added on 3 Nov 2026 (dating step 2)

**Step 2 of the dating of undated sources** (agents on the web, 3 Nov 2026; their instructions:
web2/CONSIGNE.md of the session's scratchpad). 205 sources of the step-2 list were searched for a date that bounds
the runs of their values, each proved by an exact quote of a saved file (/work/.salvo14/mig/dates2/ev/, with its
sha256): 173 dated, 15 in doubt, 17 nothing found (41 batches; reruns r1–r3 replace their sources' results in b05,
b13, b14, b16, b19, b22). Kinds, by preference: `run-date` (the source writes when the run took place), `published`,
`updated-label` (a « last updated » label, or the modification date of content identical to ours: an HTTP
`Last-Modified`, a payload's `generatedAt`), `commit` (the commit that added the values; the first commit holding
them, else the last one), `first-capture` (the earliest Wayback capture showing the values).

**How they are written** (findings, offline; the writer is dates2/py of the session's scratchpad):
- a commit → a capture `kind: commit` (its id, its date); a first capture → a capture `kind: wayback` (its URL with
  the timestamp); either is listed in `value_seen_in` of the measures whose value it carries;
- a publication, label or modification date → `published` (`where` says which), when it is earlier than the one held;
- a date per measure → a `run-date` fact (written as the run's date), `run-end` (a date on or after the run: a
  row's date, a commit for a measure whose upper bound a stated date decides), `run-start` (the start of the run).
- Every date carries its proof: a capture or `published` an `evidence` record (url, captured, file, sha256, where,
  quote; schema change: `evidence` on a capture and on `published`), a fact its file (in the sha256 map), where and
  quote. The writer checks that the file exists, that its sha256 is the agent's and the folder's SHA256SUMS, and that
  the quote is an exact substring of the file; the agents' quotes that are summaries (« … », joined fragments) are
  replaced by the line of the file that writes the date or the value. A date with no checkable proof is not written.
- A date is written only where it tightens the measure's current upper bound (or, for a start, its lower bound):
  the smallest sure upper bound, the largest sure lower bound.
- validate.py `--check-files` checks each evidence record (sha256, quote; also in a header dump or an Atom feed); a
  failure is reported under the capture id or `published` (`S.date_faults`), and the build leaves that date out — not
  the source (Source.published / Source.capture).

**The maintainer's cases (A-REVOIR.md, 3 Nov 2026), as applied:** vercel/eve PR 3769: the modification date (25 Sep)
is the bound — our harvest of 24 Sep is tighter, nothing written. GLM-5.2 / GLM-5.3-Flash: only the README's values
are dated by the README's commit, not the image's (GLM-5.3-Flash: its 24 measures all come from bench_53.png, none
dated). vb2: the board capture bounds only the values it shows (8 of 64 found on it; not the Epoch CSV rows).
clbench: the 1 May capture for every measure but Polyphony (none of the 25 is Polyphony). surgehq 15 Oct: one capture
per board (11), none for sudo-l7. surge-twi: the 14 Sep capture bounds the 8 values of the Qwen page only. hf-ale:
the commit's date where it is earlier than ours. tuabench: `Last-Modified` of a file of our sha256 → `published`.
SimpleBench: `dateAdded` per model → `run-end` on 53 measures. Convex `latestRunTime` (run-date) and epoch.ai
« Started at » (run-start, the lower bound) were already cited per measure by the conversion (cells of the run_date
slot); the epoch upper bound stays the batch's. llm_chess: the logs' `time_started_formatted` ('2026.10.08_09:08', not
read by the build) → `run-start` facts, as a local time, on the 47 measures; data.js `min_game_date` was already a
run-start. The doubts and the « nothing found » are not written, but for clbench, convex and surgehq (above).

**The maintainer's decisions of 3 Nov 2026 applied here:**
1. **A time written without its time zone** in a run date or a bound is a local time of unknown zone: its upper bound
   is the end of the day after, its lower bound the start of the day before (lhtb « 2026-08-03T23:01:31 »: upper bound
   4 Aug). The build reads it so wherever it reads a date (day_bounds: facts, cells, `published`); the dates already
   written that dropped the time are rewritten with it, the text in `written` (289 values: aibenchy « Tested on:
   2026-10-07 21:50 » 224, c0ze 5, qiita 3, lhtb 4, published 8 (note.com 5, aireiter, mcpmark, chronobay), llm_chess
   45 new). `published.value` accepts such a time (schema); validate.py `digits_agree` reads a time written before its
   date (« 14:32:46 (2026-10-11) »).
2. **codereviewbench:** the bound is the commit of 12 Oct (b04, 00047f7bf0, 17:44:38Z); the document dated 2 Oct that
   reports a run of 3 Oct is ignored.
3. **OpenHands → LiteLLM in routes.json:** `passes_through` on the harness (route `litellm`, rule
   `harness-passes-through`, the SDK's llm.py « ret = litellm_completion( », gaps-harnesses evidence): the route is a
   step of every chain the harness is in, right after it; LiteLLM documents nothing, strict.

**Not written:** 46 of the dated results. 28 tighten no bound (AA Wayback pages, cursorbench, mercor t8, scale…); 11
were already written per measure (convex ×3, epoch ×2, killswitch ×2, pokebench, swebench.com, surfsense, miaai); 4
commits whose date is in no saved file (rtx4090, simpleenglish, threadkeeper, tilth: the agents read the API without
saving it); 2 binary proofs whose quote cannot be checked (proofbench zip, superclue 2511 xlsx); toolathlon's « Date »
column (rows dated before their model's release: Qwen3.5 Plus 2025-12-17, released 2026-02-16) is held. A Wayback
capture bounds a measure only when the measure's row is in it: where the agent compared a few rows only, the rows not
found near their label are left out (28: stagehand's Sonnet 5.5, Haiku 5.5, Gemini 4 Argon rows, absent from the 23
Sep capture; frontierswe's Haiku 5.5; AA 1 and 30 Jul).

**Written:** 131 sources: 253 commit captures (69 sources; tinybird one per model, 178), 42 Wayback captures (32), 25
`published` (20 labels or modification dates, 5 publications), 164 `run-end` facts (11 sources), 45 `run-start` (1), 6
`run-date` (1). Measures newly bounded: 2,597 by a commit, 2,049 by a capture, 251 by a fact. designarena 18 and 21 Oct are dated by their
boards' own `metadata.lastUpdateTime` (not the Security page's date that route5 left out).

**Effect** (`--fit-models catalog`, against 9a0f2d9): fit-quality rows 17,696 → 17,742 (+53, −7; lqm.load kept 16,665
→ 16,711): kimi-k2.5 think +25 (the Kimi K2.6 README dated by its commit), deepseek-v4-flash-vision-exp max +7 and
deepseek-v4-flash-0731 max +4 (DeepSeek V4 Flash Vision card), kimi-k2-thinking +3, qwen3.8-max xhigh +2 …; 7 grok-4.1-fast
think rows change copy (the Gemini 3 Flash card, now dated 17 Dec 2025, is the earlier one). Quality couples 337 → 339
(deepseek-v4-flash-vision-exp max, sonnet-5 nothink). Fit-cost 9,050 → 9,039 (−11: arcprize 15 Oct gemini-3.5-flash
and gemini-3.7-flash, its price date now ending at the payload's generatedAt of 13 Oct, which no registered price
covers; AA 30 Jul grok-4.5); cost couples 268. Claude: sonnet-5 nothink +1 quality row (tinybird), no other Claude
row moves. Missing prices: 186 (model, currency) pairs, 1,397 cost measures (711 with quality in).

Tests: `local_time_no_zone`, `date_proof_checked`, `openhands_passes_through_litellm`, `findings_dates_step2`;
`findings_dates_route5` and `findings_doubtful_dates_run_end` updated (each new mechanism with a negative control
that fails when it is switched off).

## Added on 4 Nov 2026 (prices)

**The price salvo of 3–4 Nov 2026** (agents on the web; their instructions: prix1/CONSIGNE.md of the session's
scratchpad): for each (model, currency) whose costs were out for want of a price (dates2/prix.tsv, 186 pairs in 28
lots), the maker's API price in that currency, proved by an exact quote of a saved file (/work/.salvo14/mig/prix1/ev/,
sha256 in each folder's SHA256SUMS): 97 found, 18 in doubt, 114 nothing found. Written offline by the writer
prix2/py of the scratchpad (evidence.py, normalize.py, classify.py, apply.py), every proof checked again: the file
exists, its sha256 is the entry's, the quote is an exact substring of it. 22 quotes are in a text derived from the
cited file (gzip decoded, tags removed, entities decoded, whitespace collapsed; or every tag replaced by « | »): that
text is saved beside the raw file (`<raw>.<mode>.txt`, its sha256 appended to the folder's SHA256SUMS) and cited, the
raw file and its sha256 in the record's `note`; 19 quotes made of fragments joined by « … » are cited fragment by
fragment, each an exact substring. All 41 verify; no entry was refused for its proof.

**How they are written.** An entry inside a registered entry of the same price is not duplicated (5 confirmed); one
that joins a registered entry of the same price extends it, its new captures added to the evidence (18); one that
overlaps a registered entry of another price is refused; the others are new (65). A bound read from a capture lies
within the cited captures (a bound outside them is moved to them: mistral-nemo starts 29 Jul 2024, its first cited
capture; deepseek-v4.1-flash CNY ends on its last saved capture, 6 Oct); an off-peak row's last capture is its
standard row's (one quote holds both). An entry is not written before the model's release (kimi-k3 CNY starts on 17
Jul, its release, not on the capture of the 16th) nor after the registry's `as_of` (2026-10-29: a capture after it
ends the entry at `as_of`; step-3.7-flash CNY, first captured on 3 Nov, is not written). `as_of` is not raised: no
cost needs a price after 29 Oct, and raising it would turn every entry ending at its last capture of 29 Oct into a
last list price (`base-last-list-price` on most costs).

**The maintainer's decisions of 4 Nov 2026:**
- **A. A run between the release and the first capture of the pricing page** takes that capture's price from the
  release (`from_basis release`), unless a launch promotion is announced or visible, a price change is documented in
  between, or a readable capture of a maker's pricing page, on a later day than the release, does not show the
  model's price. Applied to the pairs of the salvo's lots, whose archive the agents searched, case by case from their
  notes (apply.py `A_RULE`): 37 applied (gemini-3.6-flash, gemini-3.5-flash-lite, gemini-3.1-flash-lite, kimi-k2.6,
  kimi-k2.7-code USD, gpt-5.3-chat-latest, o1, o3, o4-mini, qwen3.8-max-0902, mistral-nemo …), 42 not: (a) a launch
  promotion or price change (glm-5.3-flash 50% off, mercury-2.5 80% off, devstral-2512 free at launch, qwen2.5-7b
  free trial, qwen3-vl-235b earlier prices), (b) a later capture without the price (glm-5.3 USD on 14 Aug, qwen3.6-plus,
  qwen3.7-*, qwen3.8-27b / -max / -2.4t, grok-3, grok-4, kimi-k2.5, gpt-5.1-codex, o3-pro, mistral-small-3.2 …),
  (c) earlier captures showing the row under no region (decision E: the Alibaba 2025 Qwen3 rows), (d) the archive not
  searched over the interval (step-3.7-flash, kimi-k2-instruct, glm-5.3 CNY). Rule `price-first-capture-from-release`.
- **B. After a retirement whose alias serves another model** (deepseek-r1 after 27 May 2025 → R1-0528, gemini-3.7-flash
  after its routing to 3.8 Flash, grok-4 after 15 May 2026 → grok-4.3): no price, the line stays out. The two
  entries the agents found there (gemini-3.7-flash and 3.5-flash on 8 Oct 2026) are not written; gemini-2.0-flash ends
  at its stated shutdown (1 Jun 2026) although its price is still printed afterwards.
- **C. OpenAI's Pro mode** (gpt-5.6-sol-pro, luna-pro, terra-pro) is billed at the base model's standard rate (the
  reasoning guide, « bills those tokens at the selected model’s standard token rates »): the three Pro entries start on
  the release, 9 Jul 2026 (sol-pro from gpt-5.6-sol's capture of that day), and their entries of 9 Jul take the base
  model's long-context tier (added to the base entries on 30 Oct, not to the Pro ones).
- **D. A permanent discount** (MiniMax « 永久五折 » / « Permanent 50% off ») is the standard price: minimax-m3 USD
  0.30 / 1.20 / 0.06 and CNY 2.10 / 8.40 / 0.42 (and their > 512k tier).
- **E. Region.** A Mainland China / Beijing price is not applied to a source that does not say its region: Alibaba's
  CNY prices of qwen3-max-0123, qwen3.8-max-0902, qwen3.8-27b and qwq-32b-preview's USD price are not written.
  Alibaba's « Singapore region » table is the international price; a capture whose single USD table carries no region
  heading (July – 15 Aug 2025) is not used: four entries start at their first labelled capture.
- **F. Yuan costs of US makers' models.** Read in the sources' saved files: chinese-llm-benchmark's yuan prices are
  the catalogue of its own platform (nonelinear.com: « 模型名称标记为绿色，表示可以在本平台直接使用（包括网页和API） »,
  « 价格单位: 元/百万tokens »), a reseller, no rate stated; llm2014 runs « 优先使用OpenRouter/Zenmux中转 » (relays),
  no rate; SuperCLUE prices no US model in yuan. So nothing is converted: those costs stay out (no base price in CNY).
  The ECB rates (frankfurter, 4 Nov 2026) are kept as evidence in /work/.salvo14/mig/prix1/ev/_fx/, unused. Rule
  `cost-currency-conversion`.
- **G. A free price is never a price**: gemini-2.5-pro-exp-03-25's free tier and devstral-2512's free launch offer are
  not written; grok-2-1212's « cachedPromptTokenPrice $n0 » is not a cache-read class.
- **H. Neighbouring identities** are not priced unless models.json already names them: inkling and inkling-small (the
  serverless rows are `…:peft:262144:sampling-nvfp4`) are not written; kimi-k2-instruct and kimi-k2-instruct-0905 are
  (models.json names kimi-k2-0711-preview / kimi-k2-0905-preview as their maker API ids), each on its single capture.
- **I. Two captures of the same price cover the interval between them** unless a change is documented in it: 9 gaps
  between registry entries of the same price merged (gpt-5.3-codex 22–26 Oct, grok-3 / grok-3-mini 16 Apr 2025,
  grok-4 31 Jul 2025, gemini-2.0-flash ×2, qwen3-max-0923, qwen3-vl-32b, gpt-4o-0513 batch); not qwen2.5-7b
  (its row left the Singapore table inside the gap). The agents' bracketed entries are kept as bracketed (haiku-3
  13–14 Aug 2024, grok-4.20 29 Apr 2026, grok-2-1212). Rule `price-bracketed-captures`.
- **J. The minute / second boundary was a bug.** `validate.when(s, end=True)` read « 2026-08-16T15:59:59Z » as
  15:59:59.000000, so with the next price from 16:00:00Z the second in between was covered by neither and
  `prices_over` reported the price date not covered (DeepSeek V4 Pro 0813 on 16 Aug 2026, V3.1 on 5 Sep 2025, GLM-5.3
  Flash on 9 Sep 2026, DeepSeek V4 Pro preview on 26 Apr / 31 May 2026). An inclusive end written to the second or the
  minute now covers that whole unit (a fraction of a second is exact; a date its whole day, as before). Rule
  `price-end-inclusive-unit`.

**Dates (the maintainer, 4 Nov 2026: the points left by the dating step 2).**
1. toolathlon's « Date » column: not written (its meaning is unknown); it was held, it stays so.
2. Terminal-Bench submission dates before the release (5 rows): kept (early access).
3. SimpleBench `dateAdded` before the release (3 rows): kept.
4. designarena: each board's `lastUpdateTime` is accepted (as written on 3 Nov).
5. epoch.ai: a « Started at » does not bound the end; the upper bound stays the batch's (as written).
6. Binary proofs: proofbench — the CSV extracted from the Wayback zip of 29 Sep 2026 (the zip whose sha256 the agent
   recorded; checked equal to the zip's member) is cited, its sha256 added to its folder's SHA256SUMS: a Wayback
   capture on its 35 measures (the agent's earlier per-measure first captures, 20 Aug, have no recorded sha256: not
   used). superclue 2511 — the capture of 13 Jun 2026 is byte-identical to our workbook: its evidence quotes
   « sha256 <hash> », which validate.py accepts only when that hash is the file's and one of the source's own saved
   copies (`evidence_faults(e, path, own)`): a capture on its 165 measures.
7. A per-measure pass from the saved files only: yc-bench — the 52-model data.json of commit feb032b1 (2 Oct 2026)
   holds 43 of its 45 values (not GLM-5.3 Prime / FlashX, published on 8 Oct): a commit capture on those 43;
   codereviewbench — each value file's commit (match.json: our copy's sha256 equals the file at that commit): 16
   measures, 3 with no tighter bound; bullshitbench — not written: the saved commit list has messages only, no file
   versions, so no row is tied to the commit that last changed it (see the report).

**Effect** (`--fit-models catalog`, against a8266a2; each cost attributed to the first decision under which its price
date is covered with a base price, replayed with build.py's prices_over / base_price over the registry of each stage:
J, the salvo's entries, C, I, A — prix2/w/compare3.py): fit-quality rows 17,742 → 17,742 (lqm.load kept 16,711 →
16,708: 3 rows republished, matched by the new costs), couples 339, Claude 56 — no quality row moves. Fit-cost rows
9,039 → 9,114 (+122, −47; lqm.load kept 8,502 → 8,573), cost couples 268 → 274 (new: gpt-5.3-chat-latest solo,
gpt-5.3-codex low, gpt-5.6-terra-pro low, qwen3.8-omni-flash low / medium / nothink), Claude cost couples 55
(fable-5 high 94 → 95). Costs gained (status in, 121): A 69 (gemini-3.6-flash 22, gemini-3.5-flash-lite 20, gemini-3.1-flash-lite 5,
kimi-k2.7-code 6, gpt-5.3-chat-latest 4, kimi-k2.6 4, qwen3.8-max-0902 3, qwen3.8-omni-flash 3 …), the salvo's
prices 35 (gpt-5.3-codex 15; the first CNY prices: kimi-k3 7, glm-5.3 6, glm-5.3-flash 6 of SuperCLUE 2607,
deepseek-v4.1-flash-1017 1), J 6 (deepseek-v4-pro-0813 on 16 Aug), the proofbench dates 2, C's long-context tier 1
(gpt-5.6-terra-pro, matsonj), indirect 8. Costs lost
(47): a price date newly covered by two registered vectors, where the source's stated prices (rule B of 29 Oct) used
to stand in: the registered vectors decide, the band to the current price is wide and the cost forms a single couple
(J 26: deepseek-v4-pro-0813 21, deepseek-v4-flash-0731 5; A 21: gemini-3.6-flash, vals.ai, its 21 Jul list price and
the promotion). Price-related `out:cost-not-comparable` 1,703 → 1,367; missing prices (prix2/prix.tsv) 186 pairs /
1,397 cost measures → 156 / 1,061 (526 with quality in).

Tests: `price_end_inclusive_second`, `evidence_identical_copy`, `registry_prices_salvo_4nov`, `findings_dates_4nov`;
`findings_dates_step2` reads the « sha256 » quote of decision 6 (each new mechanism with a negative control that fails
when it is switched off: J off → the cost straddling 16:00 is out; the identical-copy rule off → its evidence is
refused; the registry of a8266a2 → A, C, I fail; the findings of a8266a2 → the dates fail).

## Added on 4 Nov 2026 (the findings self-sufficient)

The maintainer, 4 Nov 2026: « Les fichiers findings recensent tout. Ils doivent garder une liste des URL qui ont
permis leur construction, et c'est tout. Le build est censé n'être qu'un filtre simple. » So:

- **The build reads only the repository's files** (findings, registries, catalogue, decisions, settings, model/lqm.py)
  and never a saved copy (/work/.salvo14/…, a capture's or a fact's `file`). The saved copies may be removed; the
  `sha256` maps, `file` fields and evidence records stay as the trace of what the agent read.
- **Cells are facts.** A cited table cell is a fact (data/convert/cells.py, run once on 4 Nov 2026 with the files
  hashed and read a last time: 169,207 facts in 253 sources, none refused): `value` the cell as validate.table_rows
  read it (stripped; JSON numbers with their digits as written), `quote` « <row key column>: <row key> | <column>:
  <cell> » (a `$key` table: « <row key> | <column>: <cell> »), `says` the column's type (a list for a several-type
  column, schema change), `about` the row key, `level` the table's, `form` data-file, `where` « <table where> / row
  <row> / column <column> », `file`, `table`, `column` and `cell` (the reference `T<n>/<row>/<column>` it replaces; new
  schema fields), and the column's `term`, `scale`, `namespace`, `precision` (else the table's) and `note`. The
  measures and the computed facts' inputs cite the new ids. The build reads a cell fact as it read the cell: its
  value, about, level, where, table, column, term, scale, namespace and precision (not its quote, the trace); a run's
  id is its row key. A `T<n>/…` reference still cited gets the fault « its value is not written in the findings »
  (`out:no-proof` on its axis). validate.py checks that a cell fact's table, column and about are its cell's.
- **Removed from the build** (each was a read of a saved copy): the cell read (`Source.fact`: saved_path, sha256_of,
  table_rows); validate.py's `--check-files` checks run by the build by default — every saved copy's sha256
  (check_saved), a quote in its file, a legacy row in its CSV (/work/.wt-px/raw-data.csv), the dates' proofs
  (evidence_faults; a failing proof used to leave the date out: `date_faults`, gone), a measure's cell in its file, a
  `model-api-id` cell read in its file for its warning (now read from the fact), a value cell the same in every `value_seen_in` capture, the registry's
  evidence files (check_evidence_files). `--no-check-files` and `--registry-files-checked` are gone from build.py
  (acceptance.py and the tests no longer pass them).
- **Kept as the writer's tool**: `validate.py --check-files` (also `--registry-files-checked`), now checking a cell
  fact's value against its table instead of looking for its quote in the file. data/convert/precheck.py still reads a
  saved table for a `T<n>/…` model reference left (none in data/findings).

**Effect** (`--fit-models catalog`, against 0956b5a): fit-quality.csv, fit-cost.csv, data.csv, group-map.json and
group-setups.json byte-identical; status-report.json identical once each new fact id is mapped back to its cell
(`facts_used` is sorted by id, so only its order changes); validation 7,096 warnings, 0 errors, unchanged. The
build of 0956b5a with `--no-check-files` was already identical: the file checks took nothing out. Run under
data/tests/sealed.py (an audit hook refusing every open / listdir / scandir outside the repository, the `--out`
folder and Python's own install), the build gives the same outputs and attempts no access.

Tests: `build_reads_no_saved_copy` (a cell scenario whose CSV lies outside the scenario, built sealed; the copy
removed: same rows; negative control: a build reading the cell in its file again is refused and reported; a cell
cited but not written: `out:no-proof`); the cell fixtures write their cells as facts and remove the CSV before the
build; `date_proof_checked` (the build keeps a date whatever its proof; `evidence_faults`, the writer's check, still
refuses a wrong sha256 or quote); `legacy_path` (a legacy row not in its CSV stays `legacy:in`; `check_saved` reports
it); `findings_dates_step2` and `registry_prices_salvo_4nov` check a proof's file only while it is reachable, its
trace (url, file, sha256, where, quote) always; `examples` no longer needs the examples' saved copies.

## Added on 4 Nov 2026 (later: the maintainer's decisions 1–10 and the price-ratio method)

The maintainer's decisions of 4 Nov 2026, after the price and date passes above. Every new value, date or price is
written with its exact quote, its URL and its capture date; each proof was checked once, at the writing (file,
sha256, exact substring), by the writers prix4/w/{bsb,proofbench,reg}.py of the session's scratchpad.

1. **The price the source writes** (rule `cost-stated-price-registered`). When the source writes the prices it used
   (rule B's `price-table` facts with a price-class term) and they equal, on every class it states, exactly one of
   the registered price vectors over its price date, that vector alone applies: no band. Example: vals.ai legal_bench
   #M19, deepseek-v4-pro-0813, 1.32 / 3.96 (two registered vectors since J). Not equal to any, or equal to several →
   as before (the band over the registered vectors).
2. **GLM-5.3 before its API opened** (rule `price-date-after-api-opening`, models.json `api_opens`). The maker wrote that
   the API was not open yet: docs.z.ai on 15 Aug 2026 « The GLM-5.3 API is coming soon. » (USD platform), docs.bigmodel.cn
   on 17 Aug « 模型 API 将会尽快上线，敬请期待。 » (CNY platform). A cost whose single route chain is the maker's API,
   named by the source (or a harness whose `calls_route` is it), has its price date start no earlier than that day;
   the first captured price applies from that day (decision A at the API's opening: no readable pricing-page capture
   in between without the price). A run on another or an unknown route is not moved: its days before the opening stay
   uncovered, out. Qwen3.8-27B: not written — the opening date (17 Aug, newly-released-models) is the China site's,
   whose prices decision E does not apply, and no international date is saved; no cost moves either way.
3. **What blocks rule A.** A capture « without the model » blocks A only if that page lists the model when it has a
   price. Checked case by case on the saved captures: openai.com/api/pricing never lists o3-pro (a calculator menu
   only), gpt-5.1-codex or gpt-5.1-codex-mini → their first price applies from the release. Still blocking (the same
   page lists the model with its price later): kimi-k2.5, qwen3-coder-next, qwen3-vl-32b-instruct (the /models page,
   whose prices also change between Oct and Dec 2025), qwen3.6-plus, qwen3.7-flash / -plus, qwen3.8-2.4t / -27b / -max,
   grok-3, grok-3-mini, grok-4, grok-2-1212 (x.ai/api lists it at $2.00 in Apr 2025), qwen2.5-72b, qwen3-coder-480b,
   minimax-m3 CNY, aion-rp-llama-3.1-8b, muse-spark-1.1, mistral-small-3.2, gemma-4. Not decided (listed in the
   report): qwen3-max-0123, kimi-k2.7-code CNY, reka-edge.
4. **Prices of q2**: step-3.7-flash USD (8 Jun → 9 Oct 2026, joined by I to the 13 Oct entry; A from the release,
   29 May) and CNY (16 Jun → 21 Oct, A from 29 May); kimi-k2-instruct USD (kimi-k2-0711-preview, 12 Jul 2025 →
   30 Mar 2026, joined to the 17 Dec entry; A from the release). glm-5.3 CNY: nothing found (q2).
5. **Alibaba's single USD table with no region heading** on www.alibabacloud.com is the international price: the
   captures decision E had left out are used again (qwen3-235b-a22b-instruct-2507 from 24 Jul 2025,
   qwen3-30b-a3b-instruct-2507 and qwen3-coder-30b-a3b-instruct from 1 Aug, qwen2.5-7b-instruct from 14 Jun 2025 —
   the same table form, a capture of June), then A where nothing blocks it (the first three from their release).
6. **deepseek-v4.1-flash on 10 Sep 2026**: not changed. The saved announcement says « V4.1-Flash is now live on the
   DeepSeek API » and « New pricing takes effect at 04:00 UTC on Sept 10, 2026 »: it dates the new price, not the
   moment the model was first served (the release is dated « 2026/09/10 » only), so a run of that day may lie before
   04:00: out, as before.
7. **bullshitbench, one date per row**: each of the 236 measures gets a `run-end` fact, the latest `finished_at_utc` of
   its model row's responses in the response parts that data/v2/latest/manifest.json lists for the leaderboard we hold
   (its sha256 in the manifest); `where` gives the GitHub URL of the file at commit 92793d4 and the line.
8. **proofbench**: the Wayback zip of 20 Aug 2026 (sha256 18bbff41…) and its extracted CSV recorded in the source's
   map; a capture W0 on the 34 measures whose row (key and value) it holds.
9. **livebench** src-livebench-lb2-2026-10-14 G2: url https://livebench.ai/static/js/main.074b2ee8.js (the maintainer's
   reading of the 20 Oct index.html; that index is no longer on disk).
10. **arXiv URLs** written as https://arxiv.org/… (4 sources).

**The price-ratio method (a method change, before main: the maintainer's yes).** The model reads only cost relations
inside a group (its offset o_b is free); re-pricing a cost needs only the ratio « current price / price at the run's
date », which does not depend on the currency. So (`price_currency`):
- the cost's own currency when the maker prices the model in it (as before);
- else, when the maker publishes a single list (prices.json `maker_currencies`: anthropic, google, openai, xai — USD,
  each pricing page checked for every other currency), that list's ratio, band, tiers and classes; the cost keeps its
  currency and unit, and its part (basis × method × unit × currency × route) keeps its currency, so a group never mixes
  two currencies (`~c<n>`):
  - a cost with **no currency written**: as such (rule `cost-price-ratio-no-currency`);
  - a cost **in another currency**: only with a fact `maker-price-multiple` (new fact type, spend slot, term the
    list's currency) quoting the source's statement that it pays the maker's prices times one factor (a rate, or a
    relay passing the maker's prices on); rule `cost-price-ratio-other-currency`;
- several lists and the source not saying which, or a maker absent from `maker_currencies` (Alibaba, DeepSeek,
  Moonshot, Zhipu, …: several currencies, or not checked) → doubt, out;
- tokens × prices (cost-delta-on-source) and the source's own stated prices are read only in the cost's own currency;
  flag `cost-price-ratio:<list>`.
No source of the other-currency costs states such a factor: chinese-llm-benchmark pays its own platform's prices
(« 模型名称标记为绿色，表示可以在本平台直接使用… »), llm2014 runs « 优先使用OpenRouter/Zenmux中转 » and the registry knows
nothing of Zenmux (not in routes.json), SuperCLUE's yuan costs here are of Alibaba / StepFun models (makers with yuan
lists), the USD costs of Tencent models (hy3, hy4-preview) are of a maker whose USD list is not checked. So the 138
other-currency costs (121 with quality in) stay out, and the method moves the costs with no currency written: 327
reaching the cost step → 145 in the fit (104 + 21 in, 88 single couple, 20 republished).

**Effect** (`--fit-models catalog`, against 0796bfd; S/prix4/report.txt of the session's scratchpad): fit-quality rows
17,742 → 17,748 (+6, decision 7: bullshitbench rows whose run end now lies where OpenRouter's levels are known, e.g.
opus-4.8 nothink run by 29 May 2026; Claude rows opus-4.7, opus-4.8, sonnet-4.6 nothink +1 each; lqm.load kept 16,708 →
16,709, 5 republished matched by the new costs), quality couples 339, Claude 56. Fit-cost rows 9,114 →
9,366 (+252, 0 out; lqm.load kept 8,573 → 8,796): the price-ratio method 145 (haiku-5.5 20, opus-5.5 14, opus-5 11,
fable-5.1 9, gpt-6-astra 8 …: Anthropic's Haiku 5.5 system card, Epoch's archive, OpenAI's GPT-6 Astra launch),
decision 1 102 (gpt-5.6-luna 26, gpt-5.6-terra 25, deepseek-v4-pro-0813 21, gemini-3.6-flash 21, deepseek-v4-flash-0731
5: the 47 costs lost on 4 Nov are back), decision 2 5 (glm-5.3: spirebench « Z.ai API » ×3 … arxiv-2610.11539 « native
hosted APIs »), decision 3 2 (llm_chess gpt-5.1-codex low, gpt-5.1-codex-mini high); decisions 4 and 5: 15 costs from
not comparable to single couple. Cost couples 274 → 276 (gpt-5.1-codex low, gpt-5.1-codex-mini high), Claude cost
couples 55 (rows: haiku-5.5, opus-5.5, opus-5, fable-5.x, sonnet-5.5 … +1 to +7 each). Missing prices (prix.tsv):
159 (model, currency) pairs, 1,047 cost measures (521 with quality in).

Tests: `cost_stated_price_registered`, `cost_price_ratio_currency`, `cost_price_ratio_no_currency`,
`price_date_after_api_opening`, `registry_prices_4nov_later`, `findings_4nov_later` (each with negative controls;
switching the mechanism off — `maker_api_stated`, `price_currency`, `stated_prices` — makes its test fail);
`registry_prices_salvo_4nov` and `findings_dates_4nov` updated; the tests that read saved copies check them only while
reachable (`in_saved`, `sha_saved`: copies under /work/.salvo14 are being removed).

## Added on 4 Nov 2026 (the total-tokens split: a method change, before main: the maintainer's yes)

The maintainer, 4 Nov 2026: a source that gives the run's total cost and its total tokens, but no class split, and
whose own price list (input and output) at the run's date is known, gives the split by two equations — cost per call
= t_in × p_in + t_out × p_out and t_in + t_out = T — and the cost at the maker's current price is t_in × P_in + t_out ×
P_out, in the currency of the maker's list (the price-ratio method: the group absorbs the unit; a group never mixes two
currencies). The case: chinese-llm-benchmark (« 花费/千次（元） » per 1,000 questions, « 平均消耗token » per question),
run on its own platform nonelinear.com at that platform's prices (decision F: those costs as such stay out).

**Rule `cost-total-tokens-split`** (`total_tokens_split`, tried in `reprice` when no earlier rule and no band brings
the cost to the current price, so no cost already in moves):
- **The platform's prices** are the source's findings: facts `platform-price` (new fact type, spend slot; schema field
  `capture`), each one price of the platform's list as a dated capture shows it — `term` a price class, a long-context
  tier `lc><threshold>:<class>`, a cache-write multiple of the input price `<class>/input` (the list writes « 缓存写入价格
  ÷ 输入价格 », applied to every tier's input price), or `discount` / `off-peak` (its promotion fields); the capture's
  `captured` dates it.
- **Over the price date** (the cost's own, as before: [run lower bound, publication] here), the platform's vectors
  are those the captures show, under the maintainer's decisions A and I of 4 Nov read on the platform's list: from the
  release to the first capture, the first capture's price (A); between two captures of the same price, that price (I);
  after the last capture, nothing. A price change of the maker's registered list (in the list's currency) between the
  release and the first capture, or between two captures, stops A or I there (the platform follows the maker's list,
  so its price in that span is not known); two captures of different vectors leave the span between them unknown. A
  `discount` or `off-peak` field on any capture → out (a promotion visible: the price at the run's date is not known).
- **The list to price on**: the cost's currency when the maker prices the model in it, else the maker's single list
  (prices.json `maker_currencies`); else doubt, out. The current price is `base_price` in that currency (its flags
  `base-last-list-price`, `base-scheduled-list-price` carried).
- **The split** t_out = (cost per call − T × p_in) / (p_out − p_in), computed for every platform vector over the price
  date; conditions: p_in ≠ p_out; the split inside [0, T] once the source's rounding is taken into account (cost ±
  half its step, here 0.1 元 / 1,000 calls, T ± half a token) — else out.
- **Cache classes and long-context tiers.** When every platform vector over the price date is one multiple k of the
  current list on every class and tier (the same classes and tiers on both), the cost at the current price is cost × k
  whatever the run's mix over the classes and tiers (the split gives it exactly: t_in × k p_in + t_out × k p_out = k ×
  cost), its sd the cost's reading sd × k. Otherwise the split stands only when neither list has a class or tier beyond
  input and output, since the run's mix over them cannot be excluded; then the value is t_in × P_in + t_out × P_out
  and its sd propagates the cost's reading sd and the tokens' (∂/∂cost = (P_out − P_in) / (p_out − p_in), ∂/∂T = P_in −
  p_in × that); a single platform vector is then required.
- **Output**: `fields.cost.total_split` (currency, the current and platform vectors, each split with its rounding
  range, how), flag `cost-total-tokens-split:<currency>`, `cost-base-price:cost-total-tokens-split`. The row's part
  takes the list's currency and unit (`part_currency`, `part_unit`: per-1k-calls for USD), so its group never mixes it
  with the source's yuan; `currency` keeps the source's. The fit-cost row's `unit` is the part's.
- The build reads no file outside the repository (data/tests/sealed.py); `validate.py` checks a platform-price fact's
  capture, term and number.

**The platform's prices written** (chinese-llm-benchmark d44b57e, by the writer clb/w/write_platform.py of the
session's scratchpad; every proof checked at the writing: the file's sha256, the quote an exact substring of the raw
file, the value read again from the parsed JSON): nonelinear.com's catalogue `/models` (the JSON behind
static/models.html, whose script names the columns « 缓存命中价格、输入价格、输出价格 » and the info fields: discount,
step_prices, cache_write_x / cache_write_1h_x, off_peak_discount), two captures — W1, Wayback 20260715070432 (the only
capture of /models in 2026; its format has no tier, cache-write or discount field), S1, our fetch of 4 Nov 2026
15:53:49 GMT (a Wayback save was not permitted from here) — 95 facts for the 17 fit models whose costs reach the cost
step, cited by their 153 measures. The repository's history holds no input price: the board's commerce tables give
only « 输出价格 », and the README links the catalogue.

**Effect** (`--fit-models catalog`, against 4e6b610; S/clb/AVANT-APRES.txt of the session's scratchpad): fit-cost rows
9,366 → 9,411 (+45, 0 lost; lqm.load kept 8,796 → 8,841): opus-5, gpt-5.4-mini, gpt-5.4-nano, grok-4.6, grok-4.7, all
`high`, 9 tables each, each platform list 7 × the maker's on every class and tier (cost × 1/7, in USD, groups
rele-*~c2); cost couples 276 (unchanged), Claude cost couples 55, Claude rows opus-5 high 148 → 157. kimi-k2.7-code
(CNY, its list = Moonshot's, × 1) and hy4-preview (outside the fit's list) go to `out:cost-single-couple`. Refused (90):
gemini-3.8-flash, gemini-4-argon (« 限时5折 » on 4 Nov), gpt-5.3-chat-latest (last capture 15 Jul), gpt-5.4, grok-4.5
(the two captures differ), sonnet-5.5 (the maker's cache-read change of 7 Oct between the release and the first
capture), gpt-6-luna / -sol / 6.1-sol (cache-write classes not shared: 30 min / 12 h at the maker, 5 min on the
platform; 5 splits outside [0, T]), qwen3-max-0123 (Alibaba's list not established). Fit-quality rows unchanged
(17,748; 54 rows gain the build's flags in `confound`).

Tests: `cost_total_tokens_split` (negative control: the rule switched off in the build → both costs out; no platform
price → out), `cost_total_tokens_split_conditions` (the split proper and its precision; one negative per condition: a
cache class, a tier on one list, [0, T] broken and kept within the rounding, p_in = p_out, past the last capture, a
maker's change between captures (I) and before the first (A), a discount, the maker's currencies not established; a
cache-write multiple), `findings_platform_prices` (the 95 facts, their proofs while reachable; negative: none at
4e6b610). With the call to the rule removed from `reprice`, the first two fail.
