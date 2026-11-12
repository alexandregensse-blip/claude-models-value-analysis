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
python3 data/build.py ... --jobs 4                                  # worker processes for the per-file stages (default 2)
python3 data/build.py ... --no-cache                                # a full build: no stage read from the cache
python3 data/build.py ... --cache DIR                               # the stage cache folder (default data/.build-cache)
python3 data/build_lqm.py data/build/                               # the lqm.load step alone
python3 data/legacy.py raw-data.csv OUT/findings --registry OUT/registry   # raw-data.csv → legacy findings
python3 data/tests/run.py [name-filter]                             # the tests (177 with .stan/venv/bin/python, about 13 s)
python3 data/tests/acceptance.py [raw-data.csv] [--registry data/registry]   # the legacy acceptance test (≈ 20 s; default: the repository's raw-data.csv)
python3 data/schema/validate.py [--verbose]                          # per-file summary; registry warnings apart
python3 data/convert/precheck.py SOURCE_ID                           # names and route heads against the registry
python3 data/convert/gaps.py data/build/status-report.json [--registry R --findings F]   # registry gaps per source
python3 data/convert/reproduce.py --tables … --table … --csv …       # per-row cost reproduction (pinned table)
```

**Stages, blocks, cache and workers (11 Nov 2026).** The whole build is cut in units, each with a key (a sha256 of
everything it reads). Per file: `check-source`, `check-measures`, `measure-fields` (a source's or a measure file's
checks and fields; a source's key holds its own file and the ids it looks up, a measure file's its file and its
source's key). After the fields, every step runs block by block: by model (budgets, base price), by source (campaigns,
steps 0–5 and 0–4, stated same-runs-as, versions R1 `version_runs`, copies, runs, measures sharing a cost measure,
report rows and text), by group or group × couple (uninformative, campaign supersession, groups, cost subsets), by
publisher × couple (composite residuals), by family × pair of sources (proven same-runs-as), by set of linked sources
(same-runs-as applied), by setup (group names), the declared runs (one block), lqm.load (one block: its rules read the
whole fit tables; model/lqm.py unchanged). A block's key is the step, the build's common inputs (the code `data/*.py`,
`data/schema/`, `data/convert/*.py`, `model/lqm.py`, `model/catalog.py`, every registry file, the class ratios, the
settings, the fit's model list, the decisions, the folders, Python's version), the block's id, its members' keys and
what else it reads (e.g. the sources a decision names, the versions of a snapshot chain); a measure's key after a block
is the sha256 of its state, so a block recomputed for a new source leaves the other measures' keys as they were and the
blocks after it that do not hold the change are read from the cache (a new Claude source recomputes no block holding an
OpenAI measure: test in the commit). A block whose key is in the cache is read back; an entry under a key it does not
hold is refused and recomputed. The heavy steps run on `--jobs` forked workers (default 2: keep 2 while a fit runs).
The cache folder (default `data/.build-cache/` when the findings are `data/findings`, none otherwise; outside git) keeps
the last build's entries. `--no-cache` computes everything and neither reads nor writes the cache; `data/tests/sealed.py`
always adds it. The outputs are byte for byte those of a full build (test `stage_cache_and_workers`). The time of each
step is printed on stderr at the end; `<cache>/last-build.json` lists the blocks computed and their measures' makers.

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
| `group-setups.json` | `groups`: each fit group of a converted measure → its setup (legacy rows have none); `setups`: each such setup's benchmark family, composite components and score direction (benchmarks.json; `direction` since 10 Nov 2026). With `group-map.json`, what `build_lqm.fit_maps` needs to give the fit groups the catalogue's composites and families and lqm's `DIRECTION_OF` (a `lower` score is turned at f(y), rule `score-direction`), so the fit reads the build without the status report. |
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
| `cost_method_unstated` (`--cost-method-unstated`) | `single-per-table` (default) · `out` | A cost with no `cost-method` fact. `single-per-table`: each table, chart or prose block of a page counts as one method of its own (`unstated[<page>/<table>]`, the page being the root of the source's `snapshot_of` chain: rule R4, the maintainer, 11 Nov 2026; it was the source, i.e. each capture), never mixed with another page's, and the row is flagged `cost-method-assumed-single`. `out`: the cost gets `out:cost-not-comparable`. **The maintainer has not decided.** |
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
31. In the partition, the route key is the price applied, not the number of candidate chains nor what the registry
    knows of them **(rule R3, the maintainer, 11 Nov 2026; it was « the single candidate chain, else `unknown` »)**.
    The route that bills a chain is its first step that is not a harness; its registered prices over the price date
    (inside the span it served the model; standard and promotion records, a promotion being a price charged) are read
    against the maker's prices charged over the same days
    (input and output in both, the classes both list, the same long-context thresholds; days with no registered route
    price are not read). A stated chain: `maker-api` when it reaches the maker's API or its route's registered prices
    all equal the maker's, else the route's id (its own price, or none registered). The route unknown (several
    candidates): `unknown` when a candidate route has a registered price that differs from the maker's, else
    `maker-api` — a candidate route with no registered price is no evidence of another price.

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

**The board's own output prices in time: partial captures** (the maintainer, 4 Nov 2026: « il faut vérifier » the
« × 7 » applied back to each release by A). The board's commerce tables (`leaderboard/commerce1-4.md`, column « 输出价格 »)
at every commit of each file from 20 Jan to 27 Oct 2026 (114 versions, fetched with `gh api …/contents/…?ref=<sha>`,
the commit dates from the commits API) are written as `platform-price` facts of term `output` dated by their commit
(captures G2–G58, kind commit; d44b57e is G1): 259 facts for the 17 models, by the writer clb2/w/write_commerce.py of
the session's scratchpad (every proof checked at the writing: the file's sha256, the quote an exact substring, the
value in it). Each such capture shows the output price alone: a **partial capture**. `platform_vectors` keeps it
apart from the full captures (input and output); `platform_over` builds A and I from the full captures only, and each
partial capture inside a span A or I uses must show that span's price on every class it shows, else the span's price
is not known (out: « capture G<n> (<date>) shows output …, not the … of the span … »). A partial capture never prices
a run alone and never extends a span past the last full capture (no input price). The five models priced by the
split: every one of their 89 commit prices is 7 × the maker's USD output price in force at the commit (opus-5 175.0
from 28 Jul; gpt-5.4-mini 31.5 from 18 Mar; gpt-5.4-nano 8.75 from 18 Mar; grok-4.6 42.0 from 17 Aug; grok-4.7 42.0
from 26 Sep): the 45 costs stay.

**Rule `cost-class-cannot-apply`** (`class_cannot_apply`, inside `total_tokens_split`; the maintainer, 4 Nov 2026:
« fais au mieux »). A class that cannot apply to calls of the run's size is left out of the split, on both lists and
in every comparison A and I make (the maker's registered prices included). Tried only when the split with every
class fails, first without the long-context tiers, then without the tiers and the cache:
- **Tiers.** A tier `lc><N>` applies to a call of more than N input tokens (the lists' own threshold; the platform
  writes « 输入 token 数落在哪一档，该次调用就按该档单价计费 »). Left out when the input per call from the split, at the
  top of the source's rounding (`t_in_high`), is below every N. Flag `cost-class-cannot-apply:tier><N>`.
- **Cache.** prices.json `cache_minimums` (schema prices.schema.json): by maker and model, the minimum cacheable prompt
  length the maker's documentation states, with the exact quote (writer clb2/w/write_cache_minimums.py; captures of
  4 Nov 2026). Anthropic: 512 tokens for Opus 5.5, Opus 5, Sonnet 5.5, Fable 5 / 5.1, Mythos 5, Haiku 5.5 (1,024, 2,048
  or 4,096 for the older models), « Shorter prompts cannot be cached, even if marked with `cache_control` », « These
  minimums apply on every platform where each model is available ». OpenAI: « The minimum cacheable prompt length is
  1,024 tokens for GPT-5.6 and later and varies by request settings for earlier models » (GPT-5.6 / 6 / 6.1: 1,024;
  gpt-5.3-chat-latest, gpt-5.4, -mini, -nano: null). xAI: « The xAI API performs prompt caching **automatically** », no
  minimum written (null, every grok). A null or absent minimum: the cache is not excluded (doubt). Left out when
  `t_in_high` is below the minimum. Flag `cost-class-cannot-apply:cache<<N>`.
- **The platform's own cache.** The platform resells the maker's API and nothing it writes excludes a cache of its own
  (its catalogue prices « 缓存命中 » for every model). A split that needs the cache left out therefore stays out —
  doubt, counted apart: `out:cost-not-comparable`, its detail « doubt (cache-reseller): … the split gives <value> … »
  and the value it would take in `fields.cost.total_split_cache_doubt`. A split that needs the tiers only enters. (Changed by the maintainer's decisions
  of 4 Nov 2026, later, below: the doubt is lifted when the platform bills the maker's cache, and the rule applies
  only to a source that states one call per question.)
- The input per call is the mean the split gives (T × 1,000 calls); the rule reads it as every call's size, as
  `effective_classes` reads a stated tokens-in-per-request (one board's questions, of one kind).

**Effect** (`--fit-models catalog`, against f9af9f5; S/clb2/AVANT-APRES.txt of the session's scratchpad): fit-cost rows
9,411 → 9,420 (+9, 0 lost; lqm.load kept 8,841 → 8,850): gpt-5.4 `high`, 9 tables (the tier lc>272000 left out, input
per call ≤ 240 tokens; W1, whose format has no tier field, then equals S1, I holds; cost × 1/7). Cost couples 276
(unchanged), Claude cost couples 55, Claude rows unchanged; fit-quality rows unchanged (17,748; the 9 rows gain the
build's flags in `confound`). Kept apart, doubt cache-reseller (27, out): gpt-6-luna 6, gpt-6-sol 6, gpt-6.1-sol 7
(OpenAI GPT-5.6 and later, < 1,024), sonnet-5.5 8 (Anthropic, < 512; the maker's cache-read change of 7 Oct then no
longer stops A). Reason changed: grok-4.5 9 (xAI's cache not excluded), sonnet-5.5 1 (input per call up to 690 ≥
512). The 45 costs of the five models, the 89 commit prices all 7 × the maker's, unchanged.

Tests: `cost_split_partial_captures` (the same output price in A and in I → in; another price inside I, inside A →
out; a partial capture after the last full one does not extend it; partial captures alone price nothing),
`cost_class_cannot_apply` (W1 without a tier, S1 with one, 200 input tokens per call → in, flag tier>200000; negative
control: the rule switched off → out as before; 300,000 input tokens per call → out; the cache: no minimum recorded,
a null minimum → out; 512 → the doubt (cache-reseller), value 4.2 kept apart; a minimum of 200 against 200.5 tokens
→ out; a maker's cache-read change before the first capture left out with the cache, an input change still stops A),
`findings_platform_prices_commerce` (the 259 facts, their proofs; the five models' 89 prices 7 × the maker's at
each date; negative: none at f9af9f5). In `cost_total_tokens_split_conditions`, « a tier on one list only » (200
input tokens per call) now enters by the tier rule. Mutations: the partial check removed → `cost_split_partial_captures`
fails; the retries removed → `cost_total_tokens_split_conditions` and `cost_class_cannot_apply` fail.

**The maintainer's decisions on rule `cost-class-cannot-apply`** (4 Nov 2026, later):
1. **The doubt « the reseller's own cache » is lifted when the platform bills the maker's cache**
   (`platform_rebills_cache`). nonelinear.com shows for its cache class the same multiple of the maker's list as for
   input and output (× 7): it passes the maker's bill on, cache included. When the maker establishes
   (prices.json `cache_minimums`) that the cache cannot apply to calls of this size, the split without the cache then
   enters at the reseller too. Condition, for the model and at the run's date, else doubt (cache-reseller), out: the
   platform's vectors over the price date with the cache kept (`platform_over` without the tiers only, so A and I
   compare the cache classes too and the platform's cache price at the run's date is known), the maker's registered
   list over the same span one vector, and on every class both lists name — input, output and cache-read at least,
   the tiers left out — the platform's price k × the maker's, one k. A class one list names and the other does not
   (nonelinear's « 5 分钟缓存写入 » against OpenAI's 30-minute and 12-hour writes) is written down in
   `total_split.cache_rebilled`, not compared.
2. **One call per question.** The rule (its tiers and its cache) applies only to a source that sends each question as
   one call, with no conversation read back (not a multi-turn agent, whose returned input — questions, past
   reasoning, tool results — grows and is cached). The source establishes it itself: a fact `one-call-per-question`
   (new fact type, slot `usage`; `value` the words, `quote` the exact protocol, evaluation-code or README text) in
   the measure's usage; without it, out, the reason « rule cost-class-cannot-apply not applied: the source does not
   establish that each question is one call ». The input per call the split gives is an indication, not a proof. A
   split that needs no class left out does not need the fact.
3. **The long-context tier left out** (the input per call below its threshold): accepted, under 2.

**chinese-llm-benchmark: one call per question not established.** Searched (gh, 4 Nov 2026) in
jeinlee1991/chinese-llm-benchmark at main (pushed 27 Oct 2026): README.md, CHANGELOG.md, 每周最新模型.md, LMArena+AA.md,
opendata/2025高考各省真题/README.md, the leaderboard pages of the nine tables (总分, 通用能力, 专业能力, 推理与数学计算,
语言与指令遵从, 教育, 金融, 法律与行政公务, 医疗与心理健康: a chart and the table, no text), the tree (no evaluation code;
eval/评测数据.xlsx only), GitHub code search (« 多轮 », « 单轮 »); and nonelinear.com's badcase page (one « prompt » and
the models' « response » per item: an indication, not a protocol). No text says each question is one call. The
README says the opposite for two of the nine tables: « “通用能力”为“推理与数学计算”、“语言与指令遵从”、“agent与工具调用”、
“coding” 4大领域平均分 », under « 8、agent与工具调用排行榜 » « 计算TAU和BFCL-V3的平均分 », of BFCL-V3 « 首创多轮、多步函数调用场景 »,
of Terminal-Bench (9.2, coding) « 用于评估智能体和语言模型在容器化环境中执行有价值工作的能力 » — the same text in the README at
d44b57e (the run's commit) — so the total (总分) and 通用能力 average multi-turn agent runs. So no fact is written
and the rule does not apply to this source.

**Effect** (`--fit-models catalog`, against ec6dae3; S/clb3/AVANT-APRES.txt of the session's scratchpad): fit-cost rows
9,420 → 9,411 (−9, 0 entered; lqm.load kept 8,850 → 8,841): gpt-5.4 `high`, its 9 tables, entered at ec6dae3 by the
tier left out, leave (one call per question not established). Cost couples 276 (unchanged: gpt-5.4 `high` has other
rows), Claude cost couples 55, Claude rows unchanged; fit-quality unchanged (17,748 rows, 339 couples). The 27 costs
kept apart at ec6dae3 as the reseller doubt stay out, now for condition 2 (gpt-6-luna 6, gpt-6-sol 6, gpt-6.1-sol 7:
« classes or tiers beyond input and output … »; sonnet-5.5 8: « the maker's registered price changes between the
release and the first capture »). Condition 1 on them, read with condition 2 switched off (a build of the session's
scratchpad, S/clb3/hyp, not kept): gpt-6-luna 6, gpt-6-sol 6, gpt-6.1-sol 7 would enter
(S1, their only capture: cache-read, input and output all 7 × OpenAI's; the platform's 5-minute write and OpenAI's
30-minute and 12-hour writes not compared), fit-cost 9,420 → 9,439, couples 276, Claude 55; sonnet-5.5 8 refused (its
price date 28 Sep – 19 Oct crosses the maker's cache-read change of 7 Oct, 0.20 → 0.10; S1 shows 0.7 = 7 × 0.10, the
platform's cache price before 7 Oct is not captured: not known at the run's date). The 45 costs of the five models priced with every class (opus-5,
gpt-5.4-mini, gpt-5.4-nano, grok-4.6, grok-4.7) are unchanged; every other split refusal of the source gains the
reason « rule cost-class-cannot-apply not applied … ».

Tests: `cost_class_cannot_apply_decisions` (1: the platform's cache-read 7 × the maker's, like input and output, its
5-minute write against the maker's 30-minute one not compared, 200 tokens per call < 512 → in, 29.4 / 7; negative 1:
the platform's cache-read 14 × → doubt, out; negative 1: the maker's cache-read changes before the first capture, the
platform's cache at the run's date not known → doubt, out; 2: a tier on S1 only with the fact → in; negative 2: no
fact → out, for the tier and for the cache; a split that needs no class left out enters without the fact). The
scenario `_split_scenario` writes the fact by default (`one_call`). In `cost_class_cannot_apply`, the 512 case is now
refused by condition 1 (the platform's cache-write 2 × input against the maker's 1.25 ×). Mutations: condition 1
switched off (always billed) → `cost_class_cannot_apply` and `cost_class_cannot_apply_decisions` fail; condition 2
switched off → `cost_class_cannot_apply_decisions` fails.

## Added on 5 Nov 2026 (salvo s5, integration 2)

No rule of the build changed. data/decisions.json now holds the maintainer's first headline decisions (kind headline,
D2–D31: OckBench, Context Arena, lmcouncil's cards, RVG-Bench, Epoch's two SpireClimb tables), which the setups of
data/registry point to. A build against data/registry therefore needs data/decisions.json (without a decisions file
it stops: « headline decision … but no decisions file », as before). Two tests followed: `bad_arguments_clean_errors`
gives the examples' registry an empty decisions file of its own, and `pilot_legacy_build_against_real_registry` builds
with data/decisions.json (its measure decision D1 names measures absent there: reported stale, not an error).

## Added on 9 Nov 2026 (integration 3 of salvo s5, the maintainer's decisions of 9 Nov)

- **Copies, measure by measure (`copy_of`, `copies`; rule `copy-same-runs`).** A measure that says it republishes
  another board (an accepted `restated-from` fact) and whose `same-runs-as` fact carries `held` — the measure we hold
  with the same runs (`<source id>#<measure id>`), read by the agent row by row — is a copy: `out:copy` on both axes,
  whatever lqm's republication rule finds (its threshold of 3 values no longer matters), flag `same-runs-as:<held>`.
  With `capture` (a capture of the copying source: an older snapshot of the original that shows the copied value) and
  `held` naming the source we hold newer, it is `out:copy-older-snapshot`. Step 9 of §5.2, after the campaign step; a
  status set earlier (model, effort…) stays, the rule is recorded. A `held` naming a measure that is not in the build
  leaves the copy as its own measure; a held source that is not in the findings is a validation error. Such facts take
  no part in the document-level `same-runs-as` linking (a regrade, later replaces earlier), which skips them. First
  use: lmcouncil's cards (54 rows of held runs: Epoch's tables, SimpleBench, METR v1.1, GSO, WeirdML; 5 rows of its
  Text Arena (Coding) card, Epoch's WebDev copy of 20 Aug 2026, older than our LMArena WebDev of 16 Oct), and
  benchmarklist's « Benchmark map » (36 of its 51 values; 15 pending). Test `copy_of_held_runs_counted_once` (negative
  controls: a held measure not in the build, held without restated-from, restated-from alone).
- **Per-table names (`table_matches`).** models.json names of kind `table-id` carry `table` = `<publisher>/<file
  name>`: a publisher's own id (Epoch's « Model version », LiveBench's model column) is attached for that table only,
  matched exactly, for a model fact of a source of that publisher read in a file of that name; each entry's evidence is
  the table's own row (release date, organisation) or the id's dated maker id. 73 entries: 26 Epoch names over their
  tables, LiveBench's two `claude-4-1-opus-20250805-*` ids in its two saved tables. validate.py: identity checks compare
  per table; a table-id name names its table, no route, selects nothing. Test `table_id_name_valid_in_its_table_only`
  (negative controls: another table of the publisher, the same file name of another publisher).
- **validate.py `digits_agree`: durations.** A value written as hours and minutes (« 2h42m », « about 2h40m »,
  « 3h 48m ») is checked as its minutes (162); a duration with hours accepts nothing else; minutes alone (« 75m »,
  also a million « 1.2m ») keep the digit rule beside it. Check only: the agent writes the minutes. Test
  `duration_written_in_hours_and_minutes` (negative: 160, 242, 2, 163). First use: METR's GPT-5.1-Codex-Max report,
  50 % horizon 162 minutes (setup `metr-report-gpt-5-1-codex-max-p50`, suite version not named; no effort written:
  out, recorded).
- **SpireClimb.** `epoch-spireclimb` is a linear composite of `epoch-spireclimb-sts1-a20-heart` and
  `epoch-spireclimb-sts2-a10` (weights 1/1: each spireclimb.csv row's id joins one run of each table, its score their
  mean, 8 of 8 rows of 4 Nov reproduced); the composite rule applies.
- **vocab.json:** reason codes `out:copy`, `out:copy-older-snapshot`; name kind `table-id`. **source.schema.json:**
  fact fields `held` (and `capture` for a same-runs-as fact). **models.schema.json:** name field `table`.

## Added on 9 Nov 2026 (integration 4 of salvo s5, the maintainer's decisions of 9 Nov, continued)

No rule of the build changed.
- **Decisions D32–D34** (data/decisions.json, measure decisions, both axes, out): D32, ARC Prize rows that state a
  thinking budget and a level at once (« Claude Opus 4.6 (120K, Low|Medium|High|Max) », 4 Nov and 15 Oct snapshots, 16
  measures); D33, ARC's undated « GPT-5.6 Luna (<level>) » rows of arcagi1/2, replaced by the dated pass « GPT-5.6 Luna
  2026-07-30 (<level>) » of the same payload (10 measures); D34, benchmarklist's Terminal-Bench 2.1 value (two possible
  origins, pending).
- **A copy inside one document.** The copy rule (`copy_of`, rule `copy-same-runs`) also covers a table that repeats a
  run another table of the same paper reports: `held` names the other cell's measure of the same source. First use:
  arXiv 2609.29933, Table 12's Full column (Table 1's all-images configuration, as the paper says) and Table 10's
  no-think cells (Table 1's all-images and Table 12's k=5 runs, value for value): 13 cells, each run counted once.
- The relecture of the four sources (ARC Prize 4 Nov, dubesor, arXiv 2609.29933, Epoch 4 Nov) corrected findings only;
  its log is the session's S/s5/integ4/RELECTURE.md.

## Added on 9 Nov 2026 (integration 5, the maintainer's decisions of 9 Nov on integration 4's questions)

No rule of the build changed.
- **Route records prolonged to 9 Nov (decision 1).** As on 29 Oct (4f5220d): the routes.json records ending at the
  29 Oct capture (`last-capture`) whose 29 Oct quotes are found again in today's copy of the same page (OpenRouter
  /api/v1/models: in the entry of the same id) are extended to 2026-11-09, one evidence per quote (saved copies:
  /work/.salvo14/mig/s6/ev/integ5/, SHA256SUMS). Extended 1,170 of 1,253: OpenRouter 946 (/models 906, its docs and
  route-wide records: `accepts_maker`, `level_mapping`), Claude Code 45, Codex CLI 57, Fireworks 30, Together 5, Groq
  4, mini-SWE-agent 44, Terminus-2 39. Google's thinking page now redirects to aistudio.google.com (a script shell):
  its Markdown copy (…/thinking.md.txt → aistudio.google.com/docs/thinking.md) carries the same table rows, quoted as
  Markdown rows; OpenAI's model pages are read in their Markdown copies (`.md`), whose backticks the 29 Oct quotes keep.
  Left at 29 Oct (not found again, or changed): 35 OpenRouter records of models gone from the catalogue (hermes-3,
  laguna, mercury-2, minimax-01 / m2 / m2.1, solar-pro-3 …), llama-3.1-70b-instruct's supported_parameters (changed),
  24 OpenRouter budget mappings of the Claude models that take only a budget (the sentence now reads « based on the
  request’s max_output_tokens value ( max_tokens on Chat Completions) »), 21 Claude Code records (the effort table and
  the default-effort sentence were rewritten for Fable 5.2, released 9 Nov), Terminus-2's gemini-3.1-flash-lite
  default (the Gemini 3 guide now redirects to another page), and OpenRouter's glm-5.2 xhigh (found again, but clipped
  to the model's own xhigh configuration, which models.json ends on 29 Oct). OpenRouter's `accepts_maker` record now
  runs to 9 Nov. models.json and prices.json were not prolonged (not in the decision).
- **arXiv 2609.29933, Table 1's « Sonnet » (decision 2):** the paper's reader, Claude Sonnet 4.5 (« Our readers are
  Claude Sonnet 4.5 », fact F5): the table cell, which no name resolves, is taken out of the model slot of the 24 Table 1
  measures (kept as a fact, with a note); the model is F5 → sonnet-4.5. Table 12's « Sonnet » cells are not touched.
- **Decision D35 (decision 3):** Epoch's chess_puzzles rows « gemini-3.5-flash_<level> » (15 Oct and 4 Nov snapshots,
  run 13 Oct): the alias rule gives gemini-3.6-flash, the row gives Gemini 3.5 Flash's release and Epoch's metadata its
  name, the route is not written and the logs are refused: not settled, out on both axes (6 measures). The other
  Epoch rows of the alias are either before 8 Oct (gemini-3.5-flash, archive of 1 Oct) or already unresolved (their
  run interval spans 8 Oct).
- **WinoGrande, one setup per number of shots (decision 4):** setups epoch-ext-wino-grande-0shot, -1shot, -5shot,
  -8shot, -16shot (family epoch-ext-wino-grande), each measure's Shots cell cited by a note fact (4 Nov: 103 rows;
  18 Oct: 3 rows, read in the Wayback copy of 19 Oct). Decision D36: the 42 rows of 4 Nov whose Shots is empty (37) or
  « few » (5) name no number: out on both axes.
- The relecture of Epoch 18 Oct (decision 5) corrected findings only (gso Evaluation date, surface-evolver cost and
  tokens, budgets the Notes state exactly); its log is the session's S/s6/integ5/RELECTURE.md.

## Added on 10 Nov 2026 (integration 8, the maintainer's decisions of 10 Nov)

No rule of the build changed.
- **models.json and prices.json prolonged to 10 Nov (decisions a and b).** The method of the route records (integration
  5): the records ending at the 29 Oct capture (`last-capture`) whose 29 Oct quotes are found again in today's copy of
  the same page are extended to 2026-11-10, one evidence per quote (saved copies: /work/.salvo14/mig/s6/ev/integ8/,
  SHA256SUMS). Google's pages (pricing, flex, batch, deprecations, Gemini 3 guide) are now script shells: their
  Markdoc copies (…/X.md.txt → aistudio.google.com/docs/X.md) are read as text (tags, bullets and rules dropped).
  A page reworded with the same content (same model, same levels, same price) extends the record with the new quote
  (decision b), read by hand: 27 price records (Claude Fable 5 / 5.1 rows, OpenAI's gpt-5.3-codex row with two new
  write columns, Alibaba's « No free quota », Gemini blocks whose copy writes « <= 200k tokens », Inception, StepFun,
  MiniMax and Meta pages read as live text). models.json: 261 of 262 extended; prices.json: 245 of 257 extended,
  `as_of` 2026-11-10. Changed content is a new record: 10 OpenRouter prices changed since 29 Oct get records from the
  9 Nov capture (integration 5) to 10 Nov; the old ones end on 29 Oct. Left at 29 Oct: gemini-3.1-flash-lite's default
  (the model is no longer in the thinking-level tables) and Claude Haiku 3.5's prices (the row is gone).
- **arXiv 2609.29933, Table 12's « Sonnet » (decision c).** The text introduces the study's readers (« Our readers are
  Claude Sonnet 4.5, served through a hosted API, and the open-weight Qwen3.5-{4B, 9B, 27B}, served locally », F5) and
  runs Table 12 on those same readers (« We sweep the number of retrieved pages k for the ColQwen2.5 image retriever
  across Sonnet and all three Qwen3.5 sizes on both benchmarks (Table 12) », new fact F436): same role (the reader),
  the study's own runs. As for Table 1 (integration 5), the cell leaves the model slot of the 10 Table 12 Sonnet
  measures (kept as a fact, with a note); the model is F5 → sonnet-4.5.
- **Decision D37 (decision d): the publisher's own effort hypothesis is out.** Every row where the publisher writes its
  own assumption of the effort goes out on both axes. Read in every copy of Epoch's CSVs on disk (their Notes column):
  only Epoch writes one (« Assuming medium reasoning effort », « Assuming medium based on GPT-5 being run at medium. »,
  « Medium thinking used in other GPT-5 evaluations, assuming the same here. », « Assuming default thinking token
  budget »…), and of its 21 such rows only geobench o1-2024-12-17_medium (4 Nov snapshot, 2 measures) is converted.
- **OpenAI complement (lot k-openai-3) and the fit's other models of 2610.38096.** The lot's new facts and measures are
  appended to the five sources (2611.05340 +711 facts / +472 measures, 2610.38096 +362 / +166, 2611.02028 +290 token
  facts, 2610.34435 +25 facts, 2611.03575 nothing new; no cell repeated), with its 141 proposed setups (headline
  pending). The 24 « items » facts of 2610.34435 (the N of Table 7's n/N) are attached to M241-M264. Table 9 of
  2611.05340: the « result » family t9-rs-* (lot k-openai-2, the OpenAI rows) is merged into t9-res-* (the same rows,
  lots k-google-1 and k-openai-3; the moved value facts take the res family's term and scale), and t9-rs-fa's direction
  is corrected to lower (false alarms). The integration converted itself, row by row, the rows of the fit's other
  models (Opus 5.5, Opus 5, Opus 4.8, Sonnet 5.5, Fable 5.1, Haiku 5.5, Gemini 4 Argon, Gemini 3.8 Flash) of 2610.38096's
  Supplementary Tables S2 (52 rows), S7 (26), S12 (27), S14 (13) and S33 (15): 487 measures, 86 new setups (headline
  pending), the lot's rules (Table 1 cells not repeated: S2 main-set B_u rejected and solved, S12 main-set B_u calls
  without an answer, S14 B_u first runs; run dates from Supplementary Table S1; effort « high » for every model).
- **GPT-6.1 Terra in the fit's catalogue.** data/catalog/models.json gains gpt-6.1-terra (after gpt-6.1-sol-pro). Its
  models.json record (key of integration 6) is completed from the copies we hold: the API id gpt-6.1-terra (changelog
  « Oct 26 », the OpenAI post, the model page), the OpenRouter id openai/gpt-6.1-terra (captures of 9 and 10 Nov), the
  configurations nothink, low, medium, high, xhigh and max from release (the model page: « `reasoning.effort` supports
  `none`, `low`, `medium` (default), `high`, `xhigh`, and `max`. »; Markdown copy of 10 Nov) and the default medium from
  that capture only (no earlier copy of the model page; the Wayback Machine was offline). prices.json: the maker's
  standard price, 1 / 5 / 0.05 $ per MTok, 30-minute and 12-hour writes 1.25 / 2.50, above 272K input tokens 2 / 7.5 /
  0.10 / 2.50 / 5.00: the post's release-day price (26 Oct), then the rendered pricing page (Wayback 27 Oct, 28 Oct,
  3 Nov) to the Markdown copy of 10 Nov. Its rows enter the fit by the existing rules.

## Added on 10 Nov 2026 (integration 10: one run, k measurements — a method change, before main: the maintainer's yes)

- **Rule `same-run-weight` (the maintainer, 10 Nov 2026).** When one source gives, for one run (one model, one
  configuration, one execution), k quality measurements (task scores, rates, errors, each with its direction: metrics,
  sub-scores, slices or aggregations of the same executions), they all enter the fit, each with weight 1/k: lqm
  multiplies each row's noise variance by k (model/README.md), so that together they weigh as one row.
- **One run, in the build** (§5.2 step 11, `run_ids`, after the group step): the measures in on quality of one source,
  one model@configuration and one campaign whose setups share a `run_set` (benchmarks.json, a new setup field) are one
  run. A setup held twice there means two runs: they are separated by the table row (the measures' model facts); when
  the row does not separate them, nothing is grouped (doubt: runs possibly distinct; listed in the status report's
  `run_doubts`). The run id is written in the new last column `run` of `fit-quality.csv` and `data.csv` (empty on the
  cost axis, on a legacy row, on a measure alone in its run); lqm counts k among the rows it keeps (after the composite
  and republication rules) and never takes two rows of one run for a republication of each other. A row without a run id
  has k = 1. A setup without `run_set` is a run of its own: in doubt the integration did not group (« ne regroupe pas »).
- **Headline basis `run-share`** (vocab.json): a pending setup (basis decision, no decision) whose only reason was that
  the source gives several quality measurements of the same runs enters with its own metric (evidence: one of its
  value cells). Integration 10 read the 937 pending setups whose measures pass steps 0–4 (4,901 measures): 414 →
  run-share (3,805 measures; 371 with a run set), 523 kept pending with their reason appended to the note (a copy, a
  behaviour / safety / security quantity, a count of calls, tokens, steps or actions, a latency or another system
  quantity, a difference between conditions, a headline not proven on a legacy setup, a composite whose components
  are held, a component left to the maintainer). 101 setups already headline (only-metric, judgment, ranked-by…) of
  the same runs got the run set too (e.g. arXiv 2611.06135's p1 table: F1, precision, recall, MCC, TP of one detection
  run). The per-setup list: the session's S/s7/integ10/logs/point1.log; the rules, S/s7/integ10/py/runsets.py.
- **Not changed:** the non-headline metrics of setups whose headline is designated by the source, ranked by, judged
  or decided by the maintainer (out:not-headline, « setup metric X, headline Y »: 1,225 measures) stay out — a question
  for the maintainer; the cost axis (one cost per set of spend facts, as before).
- **Checks:** precheck's « same runs under two metrics » warning skips two groups whose shared couples carry one run id
  (declared). Tests: `same_run_weight` (a run of three measurements weighs as one row: variance × 3 on each, precisions
  summing to one row's; negative control without the column: k = 1 and the identical costs taken for republications)
  and `same_run_weight_build` (grouping, separation by the row, doubt, no run id for an out measure, another source or
  a setup without run set).

## Added on 10 Nov 2026 (integration 11: the maintainer's decisions a, b, c on the rule same-run-weight)

- **Label errors (point 1).** precheck stopped on four values outside the bound their metric label states. Read from
  the sources: arXiv 2610.26538's Table 2 « Δ = both photos − baseline, MAE% points » is a difference between two
  conditions (t2-d-before-c-left pending, as its siblings since integration 10) and its Table 5 « Mean = mean of day %
  errors » a signed error, closer to zero better (t5-mean-day-error-* pending: no direction); the difference and signed
  metrics are relabelled without « % » (a label with « % » reads as bounded on 0–100, `lqm.bound`). The Table 4 error
  decomposition (t4-median-offset, t4-offset-meals) was in the fit as a score: pending. BenchLM's AA-Omniscience Index
  is signed (« -50.9% »): metric `omniscience-index (points)`, no bounds. Directions contradicted by the metric's own
  label (« Hallucination Rate », « …-lower-better », « fail-rate-pct-LOWER-IS-BETTER », « frames-lower-better ») set to
  lower (BenchLM's AA-Omniscience hallucination rows, soc-t1a / soc-t1b, rt-v1.1-audio-proofread, dpbench-*,
  coleam00-k3-trap-reliability, speedrunbench-pokemon-badge1).
- **a (the maintainer, 10 Nov 2026).** The metrics that integration 10 left out (« setup metric X, headline Y »: the
  source designates or ranks by another metric of the same runs) enter with headline basis `run-share`, weight 1/k,
  in the run set of the setup holding the designated metric in the same source (found by source, couple and metric,
  the closest setup id; one fixed by hand); except the decisions D3, D5, D6, D7 (OckBench's OckScore, Context Arena's
  AUC@1M / average / overall_score). A table whose headline was only judged (several metrics, « the first metric is
  assumed ») is read the same way. Kept out with their reason in the note: copies, behaviour / safety / system
  quantities, counts, differences (the integration 10 rules). Applied to the setups with measures reaching the
  headline step; the old headline (basis, metric) is written in the note, its evidence kept.
- **b.** The components of a table without a declared composite enter with its final score, all of one run, each 1/k:
  HABIT-Bench (arXiv 2610.24520, four domains and the macro, one run set per memory system), Book QA (arXiv 2611.00244,
  four datasets and the micro average, both conversions of Table 1, one run set per condition), Claude Battle (S, P and
  Final), Vals Index 2.2 and its Code Migration component.
- **c, rule `f1-not-components`.** When a table gives an F1 and its components precision and recall for the same run,
  the F1 alone enters; precision and recall are pending (out:not-headline), noted (arXiv 2611.06135 p1 / p2 / t5 / t5-rr,
  2611.00340 s14 / s17, 2611.02826, 2611.02484 t3, 2610.37797, 2610.37459).
- Lists: the session's S/s7/integ11/logs/point1.log, point2.log; scripts S/s7/integ11/py/.

## Added on 11 Nov 2026 (correction of the cost data: ReactBench, the maintainer's consigne of 11 Nov)

The cost fit of 10 Nov froze (R̂ 6.8, step size 5e-4, every chain stuck): two cost groups, reactbench#1.0~c4 and
#1.1~c5, shared 20 costs of 20 copied to 15 digits (reading precision d ≈ 3e-15); their common effect absorbed the
residuals and their σ went to 2.6e-9. ReactBench's page embeds three versions of one board (v1.0, v1.1, v1.2: 39
tasks × 5 trials each, facts F1309/F1310, F5/F6, F2379/F2380) that re-grade the same runs.

- **Data, decisions D39–D41** (data/decisions.json, cost axis, out; the scores stay). D39, 187 measures: a cost
  identical, value for value, to the cost of the same setup and configuration in a later version (kept: v1.2, else
  v1.1). D40, 110 measures: the Writing / Fixing costs of v1.0 and v1.1 for a configuration whose overall cost and
  tokens v1.2 repeats — v1.2 re-split the 39 tasks (write / fix 23 / 16 → 28 / 11), and 23·w + 16·f = 28·w' + 11·f'
  = 39 × overall was checked for each: the same trials, counted once in v1.2's split. D41, 45 measures: GPT-5.6 Luna,
  the same runs (identical tokens) costed 5× apart between v1.0 and v1.1, the factor of the two price lists the
  registry holds for it; the page says nothing of the price used (capture of 4 Nov, live page of 11 Nov): every Luna
  ReactBench cost out. Not touched: configurations whose cost and tokens differ between versions (re-runs: GPT-5.6
  Terra and GLM 5.2 in v1.0; Opus 5, Sonnet 5, Gemini 3.5 Flash high / low, Gemini 3.1 Pro low, Inkling Small in v1.2).
- **R1, same-runs-as between the versions of one source** (`version_runs`, called at the end of `same_runs`). Two
  versions of one source and one benchmark family are versions of one table when ≥ 2 shared couples have identical
  costs (§3's closeness test, on the costs as written, before any re-pricing) and a score differs on one of them.
  Then couple by couple: a couple whose cost is identical in two versions is one run — on quality, its measures in
  those versions and in every setup of its run set (else its family) share one run id (rule same-run-weight, k over
  all of them; nothing is superseded: the maintainer, point 3); on cost, each setup's cost counts once, in the latest
  version of the run holding an accepted cost (`out:superseded`, « same runs as … (version x of this source) »),
  also for a setup the later version re-split. A couple whose cost differs is another run and stays apart. The
  links go to the status report's `version_links`. On the data of 1548576 R1 links ReactBench only (its three
  families, five version pairs); the other sources holding two versions of one family with costs (PokeBench 21 / 22 /
  rvb4, the qiita dahatake sheets 1.0.88 / 1.0.89) share no identical cost. Test `same_runs_versions_in_one_source`
  (negative controls: one identical couple; identical scores, no regrade; a re-run couple stays two runs).
- **R2, precheck check 6 (blocking).** Two groups of the cost fit table (after lqm.load) sharing ≥ 3 couples with
  identical costs (relative gap < 1e-9) stop the fit (`!!`, exit 1), the reading precision shown (« near zero: σ can
  collapse » below 1e-6). The smoke fit becomes check 7. Test `precheck_identical_costs_block` (negative controls:
  2 identical couples; values 1e-6 apart).

## Added on 11 Nov 2026 (arbitration of the 12 cost-group pairs blocked by precheck R2)

No rule of the build changed; R2 stays blocking. Each pair was read from its findings (value, quote, URL, date):

- **Copies, cost counted once (decisions D42–D52, data/decisions.json).** D42, both axes: OpenAI's GPT-6.1 Sol post,
  GDP.pdf, GPT-6.1 Sol and GPT-6 Astra (10 measures) print Artificial Analysis's GDP-PDF runs (Astra's costs with AA's
  floating-point tail, 1.7948240999999998; 6.1 Sol's AA's rounded to 4 digits); GPT-6 Sol, whose scores differ, is not
  touched. D43, both axes: arXiv 2611.07461's Table 31 Claude Code baselines (4) print SWE Refactor Bench's Table 3
  (arXiv 2608.23564), score and cost, all eight numbers. D44, cost: datallmlab's blog of 6 Aug (3) and its evidence
  JSON of 3 Oct are the same runs (dates, tokens, prices); the later file is kept. D45, cost: the Haiku 5.5 system
  card's OSWorld strict costs (10, read from pixels) are the launch chart's runs (D1); the launch's written CSV is kept.
  D46, D47, D49, D52, both axes: OpenAI's AutomationBench charts (GPT-6.1 Sol post 10, GPT-6 Sol and Luna post 5 + 25,
  GPT-6 Astra launch 10) are
  Zapier's AutomationBench board 1.0.6 (scores agreeing on every couple to one side's rounding); the board is kept.
  D48, cost: tokensave's first measurement of 9 Oct (5) is yunany90's Qiita run (same tokens, times, lines). D50 / D51,
  cost: Vals.ai EMB and HLab, version 1 against version 1.1 (two captures, the later a declared snapshot): 9 and 3
  configurations with the same cost to 7 digits and a re-graded score; the cost counts once, in v1.1; the re-run
  configurations stay. Their scores stay: R1 joins the gradings of one source and one family as one run, and these
  versions are two sources and two families in the registry (emb / valsemb11, valshlab / valshlab-2026-10-21).
- **Copies, stated in the findings (rule copy-same-runs).** benchmarklist's Grok 4.5 ARC-AGI-2 (M14, M110, M111) and
  Grok 4.6 CursorBench 3.2 (M32–M34) cite their board (restated-from) and now carry a same-runs-as fact naming the held
  measure (ARC Prize 4 Nov M471 / M473 / M472; CursorBench 9 Sep M34 / M28 / M44): out:copy.
- **A declared coincidence (precheck `COINCIDENCES`).** AI Coding Daily (Laravel prompts through Codex CLI) and Column
  Tax's TaxCalcBench (tax returns) share GPT-6 Luna's costs at the cent ($0.01, $0.03, $0.01): two benchmarks, two
  runs. The pair of base groups and its three couples are declared with the proof; precheck reports it (`??`) and does
  not block; another identical couple, or these couples in another pair, block again. Test
  `precheck_declared_coincidence`.

## Added on 11 Nov 2026 (lighter smoke, the pending points, the `??` of precheck)

- **Smoke fit (precheck check 7).** Both axes in turn, quality then cost, 2 chains of 50 warm-up + 150 draws each;
  R̂ ≤ 2.0 on each (it only checks that the fit sets off in roughly the right direction); the message names the axis
  that stops the full fit. Test `precheck_smoke_both_axes` (sampling stubbed).
- **AutomationBench, the same runs costed twice (D53, cost).** Where OpenAI's charts (D46, D47, D49, D52) and Zapier's
  board 1.0.6 give one couple two costs beyond the rounding of the less precise (the cent): Opus 5 low–xhigh ($1.64 …
  against $0.75 …), GPT-5.6 Sol low–xhigh ($0.31 … against $0.42 …), GPT-6 Astra at every level (the Astra launch's
  $1.087119 … against $1.08 …): which price is right is not known, the cost goes out on both sides (13 Zapier
  measures; OpenAI's were out already, their reasons say so). Where the costs agree to the rounding (Opus 5 max,
  GPT-5.6 Sol max, GPT-5.6 Luna, GPT-6 Luna, GPT-6 Sol) Zapier's cost stays, counted once.
- **Decisions of kind run (`declared_runs`, after `run_ids`; decisions.schema.json).** The maintainer joins measures
  of two sources that the sources establish as one run (weight 1/k on quality, rule same-run-weight; nothing goes
  out); a stale facts hash joins nothing (reported), a measure already in a run is not re-joined (run doubt). D54:
  Vals.ai EMB (9) and HLab (4) versions 1 and 1.1, the configurations whose cost is the same to 7 digits (D50, D51;
  HLab's Sonnet 5.5 max too, $12.45943725 in both, its cost out as single-couple). D57: Artificial Analysis's
  AA-Briefcase Elo under two setups (aabriefcase, model pages of Oct; aa5-aa-briefcase, leaderboards of Nov), 44
  configurations within 1 %, one evaluation re-rated. Test `declared_run_decision` (negative controls: one measure
  out, a stale hash, a measure already in a run).
- **The `??` of precheck, read one by one.** Labels: KernelBench's peak_fraction is « achieved / peak, clamped to
  [0, infinity) » (roofline.py): metric `achieved-over-peak (unbounded)` (14 setups, facts' term); lester model arena
  round 10 counts the 24 tests passed (« 24/24 »): `pass-of-24`. One run under two metrics: scf52-oswp / scf52-osws
  (partial and strict pass of the same runs, §8.13.3) and arXiv 2604.26954's κ at j = 3 / 5 / 7 (majority votes of the
  same « j replications at temp = 1 ») share a run_set; D56 keeps the OSWorld cost once (chart B); D55 keeps
  Chartography's Fable 5.1 cost once, in the Fable 5.1 card (the Fable 5.2 card reprints it); nnakapa's two setups
  already shared a run_set (precheck now reads it). Configurations under one key, separated: new setups
  anthropic-cookbook-latency-desk-agent-fast-mode (cell 60), arcagi3-provider-adapter (providerAdapterEvaluation),
  ibragim-codex (harness Codex), oai55-t-expert-swe-internal (Expert-SWE rows held under CyberGym),
  tokensave-brickbreaker-cost-first (the first measurement of 9 Oct); nurb's benchmark revision (« nurb/evals@content-
  revision: a new revision is a new row ») is now the measures' version fact, so each revision is its own campaign.
  Out, with their reasons: D58 Bug Hunt rows the board supersedes with the mean that contains them; D59 MGATE's GPT-5.5
  « base » rows (another configuration than its Medium row, ours cannot tell what base ran); D60 UGI's grok-4.20 beta
  rows; D61 single-row variants (cookbook no caching / prefetch / bigger pages / no commentary, ibragim Oh My Pi,
  MathArena's DeepSeek Harness rows beside the board's own); D62 OpenAI's GPT-5.5 page printing the same figures in a
  second table. Declared in precheck (reported « -- declared », not `??`): `DISTINCT_RUNS` (arXiv 2609.29933 k = 10 /
  k = 20, other inputs; Mintaka's languages, other question sets) and `REPLICATES` (seeds or separate runs of one
  configuration, with their exact values: seaquest r0–r2, TestCabinet's runs, llm_chess's two runs, Playcode's four
  default runs of Gemini 3.8 Flash, nurb rows of one revision on two patch releases of Codex). Test
  `precheck_declared_twins_and_replicates` (negative controls: another value, an undeclared pair).
- **R1 guard, found by the build of this integration** (`tokens_differ`). With nurb's revisions as versions, R1 linked
  bundle_holder 0.22.2@c16e77e91b9a and 0.23.0@396cc49ef106 for Grok 4.6 low and medium (costs $0.10 / $0.12 and
  $0.27 / $0.28, close at the cent, a score differing), though each row is its own trials (3 against 6 and 5, tokens
  118,602 / 156,200 and 210,421 / 277,469). A couple whose two measures give token counts of one kind that differ
  beyond the coarser step is now two runs, whatever the costs; ReactBench's re-gradings carry identical counts. Test
  `version_runs_tokens_differ` (negative controls: identical counts, within the step, no common kind).

## Added on 11 Nov 2026 (Fable 5.2 alone in its cost groups: corrections and rules R3–R5)

The cost fit of 11 Nov mixed slowly in one direction: Claude Fable 5.2 was alone in 29 of its 30 cost groups (lqm),
its level against the other models tied by one PokeBench row (analysis ANA.md of 11 Nov). The maintainer's
corrections:

- **CursorBench (data).** The Fable 5.2 card's Figure 8.8.A (scf52-cb40, 16 measures) is Cursor's runs (§8.8,
  « Cursor measured and reported all scores independently »): restated-from F1125 and same-runs-as F1126–F1141, each
  naming the board measure read row by row (scores equal, costs within 0.03 $): `out:copy`, counted once on the board.
- **FrontierCode 2.0 (data, D63 / D64).** Cognition's five Fable 5.2 costs are 1.249–1.251 × the card's (Fable 5.1's
  price 10 / 50 $ applied to the same runs): Cognition's costs out (D63), the card's kept at the current price; the
  card's five scores out on quality (D64), the same runs' scores counted once on Cognition's board as for the other
  models of the table.
- **OpenRouter route for Fable 5.2 (data, held back).** The model page saved on 10 Nov proves OpenRouter served it from
  2026-11-09T19:49:41Z at 8 / 40 $. Entered with that date, it put 36 Fable 5.2 measures of the boards captured on
  10 Nov (ARC Prize, CursorBench, Zapier, Epoch, geotoolbox, notesbylex) out on both axes as `effort-not-established`:
  their run interval starts at the release (9 Nov 00:00), before the route served the model, and OpenRouter's own
  `accepts_maker` ends on 9 Nov (its last capture), so the route's levels cover no such run and the candidate routes
  disagree. With R3 the card's groups join without it; the entries are not in the registry.
- **R3, the route key is the price applied** (item 31; `price_key`, `route_price_vs_maker`). Effect on the data of this
  build: 6,933 cost measures go from `unknown` to `maker-api`, 1,924 from a harness chain (`claude-code/maker-api`,
  `inspect-ai/…`, …) to `maker-api`, 104 to a route's id; 29 models keep `unknown` where OpenRouter's registered price
  differs from the maker's over the price date (GPT-5.6 Sol / Terra / Luna: OpenRouter's 2 / 10 $ of Aug–Sep against
  OpenAI's 4 / 20 $ promotion; Grok 4.7's 1.6 / 4.8 $ of 23 Sep; DeepSeek, GLM, Kimi, Qwen). Cost groups whose subsets
  change: 140 joined more models, 87 split, 39 both (model pairs sharing a subset: +2,547, −5,326). The splits are the
  models whose price is known to differ, which `unknown` used to pool with every multi-route model (AA boards,
  Vals.ai, connections-oneshot, datallmlab); the joins are mostly harness chains and router-served models meeting the
  maker-API ones (ObviousBench, Vals.ai index, Terminal-Bench 4.0, IdentityBench).
- **R4, an unwritten method follows the page** (Settings, `snapshot_root`). It joins the captures of one page that all
  lack a method (10 groups by R4 alone, 41 with R3). It does not join a capture without a method to an earlier one that
  writes it (ARC Prize 11-10 against 11-04's « retail pricing », CursorBench, Zapier): those Fable 5.2 groups stay apart.
- **R5, precheck check 8 (warning).** Nothing is named on this build (Fable 5.2: 18 of its 38 groups shared at high,
  7 of 26 at low; before, 1 of 30).
- Fable 5.2 on the cost axis (lqm): 20 of its 40 groups hold another model (before 1 of 30): the card's Bcad, Chart
  N / T, HLE no tools, OSWorld, AA index, the Vals.ai boards, PokeBench, ironcurtain. Still alone: AA's per-benchmark
  boards and ARC / Zapier / CursorBench of 10 Nov (method not written in that capture), the card's Draco, HLE with
  tools and W&R (Opus 5.5 and Fable 5.1 there are lqm republications of the Fable 5.1 card), FrontierCode.
- Fit tables (lqm): quality 22,174 → 22,153 rows, cost 9,665 → 9,746 rows, 352 / 288 couples unchanged. Tests
  `cost_route_key_is_price_applied`, `cost_method_unstated_follows_page`, `precheck_isolated_couples`.

## Added on 12 Nov 2026 (integration 12: salvo s8, the maintainer's decisions of 12 Nov; no code changed)

- **Salvo s8** (lots k8-fable52, k8-conv-1, k8-conv-2; their VERIF files applied): 39 sources, 456 measures. New
  captures carry snapshot_of (Artificial Analysis model pages, CursorBench, lmcouncil); the 90 rows of the AA model pages
  of 12 Nov all bring a cost and output tokens per task that no held capture has (their scores equal the leaderboards'
  of 9 Nov: the later capture supersedes within the campaign); CursorBench's 3 new rows only (89 rows, 86 held).
  Copies linked row by row (same-runs-as with `held`): aiagentstore ← Hex DataBench (20) and OckBench (5), kingy.ai ←
  the AA model pages of 15 Oct (index to the rounding; its costs differ, noted), mpgone M21 ← AA 12 Nov, lmcouncil's
  WeirdML high / max ← Epoch's weirdml_external.
- **OpenRouter route of Fable 5.2**: the records held back on 11 Nov enter with the model page of 12 Nov as a second
  proof, valid to that capture (the price to the registry's as_of).
- **Opus 4.7 without thinking**: retort8 is « default » (effort not established, like retort49); WeirdML « no thinking »
  (lmcouncil) and Epoch's two 0.764 records are one run, counted once on lmcouncil's side with its effort; tinybird's
  rows carry a version fact by harness (results committed before 21c77839 of 17 Jun, between it and bb8f8799 of 27 Jul,
  after): each harness version is its own campaign; 40 rows without a results commit stay apart (no version).
- **D57** (decision 2): AA-Briefcase keeps its last capture only: the 143 aabriefcase measures (model pages of 15, 19
  and 21 Oct) go out on quality (kind measure; was kind run, 44 pairs at 1/k).
- **Decision 3** (a principal chosen by us): 9 headlines kept (the source states the result in that metric, quoted in
  the setup note); 10 of arXiv 2610.25078 (« the first metric is assumed ») take basis run-share (their run sets were
  already shared: no weight changes); SCBench left to the maintainer.
- **Decision 7**: the cookbook's race setup split by its levers (fast mode, prefetch, bigger pages: eight setups);
  OpenAI's GPT-5.5 page: 38 cells that repeat table 0 or the effort charts linked to the held cell (restated-from +
  same-runs-as in the same document), the Terminal-Bench 2.0 rows moved from oai55-t-browsecomp to
  oai55-t-terminal-bench-2-0.
- Lists and scripts: the session's S/s8/integ12/ (RAPPORT.md, AVANT-APRES.txt, logs/, py/).
