# data/build.py: the build of the findings pipeline

This file implements the decision tree of `docs/DATA-PIPELINE.md` (§5) and writes the fit tables (§6). It also gives
legacy rows of today's raw-data.csv a pass-through path (§8). It runs over the schemas, vocabularies and validator in
`data/schema/`, and uses only the Python 3 standard library.

## Run

```
python3 data/build.py                                    # data/registry + data/findings + data/decisions.json → build/
python3 data/build.py --registry data/findings/examples/registry --findings data/findings/examples --out build/
python3 data/build.py ... --previous build-old/status-report.json   # adds the status diff (per measure and per source)
python3 data/build.py ... --cost-method-unstated out                # the setting below
python3 data/build.py ... --fit-models catalog                      # the fit's model list (default: models.json keys)
python3 data/build.py ... --no-lqm                                  # skip the lqm.load step
python3 data/build_lqm.py build/                                    # the lqm.load step alone
python3 data/legacy.py raw-data.csv OUT/findings --registry OUT/registry   # raw-data.csv → legacy findings
python3 data/tests/run.py [name-filter]                             # the tests (96, about two seconds)
python3 data/tests/acceptance.py [raw-data.csv] [--registry data/registry]   # the legacy acceptance test (≈ 20 s)
python3 data/schema/validate.py [--verbose]                          # per-file summary; registry warnings apart
python3 data/convert/precheck.py SOURCE_ID                           # names and route heads against the registry
python3 data/convert/gaps.py build/status-report.json [--registry R --findings F]   # registry gaps per source
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

## Outputs (`build/`)

| File | Content |
|---|---|
| `fit-quality.csv` | Rows `in` on quality, in today's `raw-data.csv` columns: legacy rows verbatim, then findings rows. `source` is the publisher id. `cost_usd` holds the raw cost of the same execution, which the republication check reads. |
| `fit-cost.csv` | Rows `in` on cost. The group is the quality group, with `~c<n>` added when the group has several cost subsets. The cost is at the base price; `score` is the score of the same execution. |
| `group-map.json` | Each fit group → its base group: the setup's first `legacy_groups` entry, else the setup id; a legacy row's group maps to itself. |
| `data.csv` | Every measure, including composite residuals and legacy rows: the fit columns plus `status_quality` and `status_cost`. |
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
  `cost-base-price:<rule>`, `base-last-list-price`, `cap`, `composite-residual-refused:scale`, `stale-decision:<id>`.

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
   - When the route is unknown, the candidates are `maker-api` plus every route whose entry for the model has a
     dated record overlapping the run.
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
30. `cost-uniform-factor` requires every candidate vector to be the same uniform multiple of the base. An unrepriced
    model gets its own subset when its registered prices fully cover its price dates and are uniform multiples of one
    another (a single vector counts). When no registered price covers the price date, the cost gets
    `out:cost-not-comparable`.
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

`python3 data/tests/run.py` runs 96 fixtures: 55 in run.py (the build's, the merge's `ext_*`, and the registry fix's
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

## Not implemented yet

- cost residuals of composites;
- conversion between currencies (`currency-fixed`);
- YAML and HTML tables.

**Price band (29 Oct, the maintainer).** An unrepriced cost whose price vectors over its price date differ in some
classes only (Sonnet 5.5's cache read halved on 7 Oct) is no longer out: at the latest vector its cost lies between
raw × the smallest and raw × the largest per-class ratio; the row keeps the middle, its sd grows by the band's uniform
sd, flag and rule `cost-price-band`. Vectors of different tiering stay out.
