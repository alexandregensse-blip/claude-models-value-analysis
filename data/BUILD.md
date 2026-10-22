# data/build.py: the build of the findings pipeline

This file implements the decision tree of `docs/DATA-PIPELINE.md` (§5) and writes the fit tables (§6). It runs over the
schemas, vocabularies and validator in `data/schema/`, and uses only the Python 3 standard library.

## Run

```
python3 data/build.py                                    # data/registry + data/findings + data/decisions.json → build/
python3 data/build.py --registry data/findings/examples/registry --findings data/findings/examples --out build/
python3 data/build.py ... --previous build-old/status-report.json   # adds the status diff
python3 data/build.py ... --cost-method-unstated out                # the setting below
python3 data/build.py ... --fit-models catalog                      # the fit's model list (default: models.json keys)
python3 data/build.py ... --no-lqm                                  # skip the lqm.load step
python3 data/build_lqm.py build/                                    # the lqm.load step alone
python3 data/tests/run.py [name-filter]                             # the tests (39, under a second)
```

The build runs in five steps:

1. **Validate.** It runs `validate.py`'s checks, with `--check-files` unless `--no-check-files` is given. Errors in the
   registries, the vocabulary or the decisions stop the build, and so does a file that fails its schema. An error that
   belongs to one source, fact or measure does not stop it: the measures it concerns get `out:no-proof`.
2. **Fields.** For each measure it computes the run-date interval, the model, the configuration, the campaign, the
   value on the setup's scale, and the cost at the base price.
3. **Statuses.** Each measure gets a status per axis. Decisions are applied first; after that, the first step that
   fails gives the status.
4. **Outputs.** The tables and reports listed below.
5. **lqm.load step.** Unless `--no-lqm` is given, `data/build_lqm.py` imports `model/lqm.py` unchanged, runs `lqm.load`
   on each fit table and compares the rows it keeps with its input, matching on (group, couple, value). It writes the
   outcome back into the report and into `data.csv`:
   - dropped by the composites rule → `out:composite`;
   - dropped by the republication rule → `out:republished`;
   - left alone in a split part → `out:single-couple` / `out:cost-single-couple`;
   - in a saturated group → `out:saturated`.

## Outputs (`build/`)

| File | Content |
|---|---|
| `fit-quality.csv` | Measures `in` on quality, in today's `raw-data.csv` columns. `source` is the publisher id. `cost_usd` holds the raw cost of the same execution, which the republication check reads. |
| `fit-cost.csv` | Measures `in` on cost. The group is the quality group, with `~c<n>` added when the group has several cost subsets. The cost is at the base price; `score` is the score of the same execution. |
| `group-map.json` | Each fit group → its base group: the setup's first `legacy_groups` entry, else the setup id. |
| `data.csv` | Every measure, including composite residuals: the fit columns plus `status_quality` and `status_cost`. |
| `status-report.json` | Per measure: status and reason detail per axis, every computed field with its level, the facts and rules used, the flags, the fit rows and the lqm outcome. Also the counts per reason, the stale decisions, the validation warnings and errors, and the diff against `--previous`. |

The fit tables carry these confound flags:
- `EAP-run`;
- `restated-from:<Org>` when the fact names a maker, else `restated-from:<value>`;
- `vendor-reported:<Org>` for an `evaluated-by` fact naming the model's maker, else `evaluated-by:<value>`;
- `prev=<value> (<measure>)` on a row that replaced an earlier one;
- the build's own flags, which `lqm` ignores: `cost-method-assumed-single`, `cost-unrepriced`,
  `cost-base-price:<rule>`, `cap`, `stale-decision:<id>`.

## Settings

| Setting | Values | Effect |
|---|---|---|
| `cost_method_unstated` (`--cost-method-unstated`) | `single-per-table` (default) · `out` | A cost with no `cost-method` fact. `single-per-table`: each table, chart or prose block of a source counts as one method of its own (`unstated[<source>/<table>]`), never mixed with another source's, and the row is flagged `cost-method-assumed-single`. `out`: the cost gets `out:cost-not-comparable`. **The maintainer has not decided.** |
| `--fit-models` | a file, `catalog`, or omitted | The model list used by step 10 (≥ 2 couples) and passed to `lqm.load`. |
| `class-ratios.json` (`--class-ratios`) | optional registry file | Feeds `cost-class-ratio`. It has no schema yet: `{"ratios": [{"model", "change": <date>, "classes": {cls: {factor, sd}}, "setups": {setup: cls}, "measures": {ref: cls}}]}`. It applies to a cost whose price date ends before `change`. Without the file, the class-ratio step never fires. |

## Interpretations

These are the places where the spec left room. Items marked **(method)** are method questions put to the maintainer;
the build does one thing for now and can be changed.

**Proof and reading**
1. A table cell is read from its saved CSV. If the file is unreachable, its sha256 does not match, or the table is not
   CSV, the measure gets `out:no-proof`. JSON, YAML and HTML tables are not read yet.
2. A value or cost that cannot be read as a number gets `out:no-proof`.

**Run date**

3. A `run-date` fact that cannot be parsed is ignored, and the default bounds stand. Several `run-date` facts give
   [earliest day, latest day]. Stated bounds that contradict each other give the wider interval, with the level
   `contradictory`.
4. The commit date is taken from the capture of that commit. When the source has no publication date, no capture and
   no commit, the upper bound is the harvest.
5. **Early access (method).** A configuration dated from the release (`from_basis: release`) covers an early-access
   run. Without this, no early-access run could ever have a configuration. Records dated by captures are not extended
   this way, and an alias's `serves` intervals are always date-checked.

**Model**

6. A `mode` fact that matches no registered mode leaves the model not established. "A route that cannot separate the
   mode" is read as any router on the chain, because routes.json has no field for it.

**Route chain**

7. Route facts resolve by their term, then the prefix head, then a route's spellings.
   - A chain that names only harnesses counts as route unknown.
   - After a router, `maker-api` is added to the chain; after a reseller, host or self-hosted route it is not.
   - A reseller uses the maker's defaults, with conversions dated under its own route id.
   - When the route is unknown, the candidates are `maker-api` plus every route whose entry for the model has a
     dated record overlapping the run.
8. **Undocumented steps (method).** A non-maker step that documents nothing covering the run (no mapping, `accepts` or
   `level_mapping`) leaves the configuration not established. It is not assumed to be identity. This also applies to
   step 7 through a harness. It is README open item 3 (Inspect).

**Configuration**

9. Settings resolve in this order:
   - level ids, and `x-high` / `extra high`;
   - vocab spellings of kind `setting`, tried on the value and, for a table cell, on `<column>: <value>` (so a
     `reasoning_effort` cell `none` gives `nothink`);
   - `key: value` lines;
   - a number → `scalar-<n>`;
   - `adaptive`, `auto`, `dynamic`, `default` or `enabled` → not established;
   - anything else → not recognised.
10. Labels resolve in this order:
    - vocab spellings of kind `label` (nothink spellings before think spellings);
    - a single level id left after dropping {effort, level, setting, reasoning, the, at}.

    `label-to-ladder` maps lowest / least / minimum to the lowest level and highest / maximum / most to the highest.
    **(method)** "Lowest" is `ambiguous` when `nothink` is also in the model's list (thinking off, or the lowest
    level). `think` is never on the ladder.
11. A `config-history` fact takes its interval from the first two ISO dates in its `where`, and that interval must
    cover the run.
12. Only configurations that are established are compared for contradictions. The one exception, "the more specific
    statement of the same call", is `no-effort-sent` together with a name's `selects` or a thinking-on/off fact that
    gives `think` / `nothink`.
13. Budgets within 5 % are clustered per model across the build; the cluster takes the name of its smallest budget.

**Value**

14. **(method)** A value whose level is `not-established` (other than contradictory) gets `out:estimate`: no reason
    code fits it better.
15. `mean-of-runs` is not implemented, because no slot holds per-run values: a `failure` always gives
    `out:failed-run`. The `partial` exception ("scored as wrong") is found in the fact's text, since no fact field
    carries it.
16. **Uninformative (method).** A score counts as uninformative when it is exactly equal to a bound of the setup,
    and some but not all couples of the group sit at a bound. A group where every couple is at a bound is left to
    lqm's saturated rule.
17. Scale conversion takes the target scale from the setup's `bounds`: upper 100 → percent, upper 1 → fraction. A
    `raw` score is left as it is.

**Campaigns**

18. Replacement happens only between measures that passed steps 0–5, and only across sources: two measures of one
    couple in one source both stay. Sources are ordered by publication date, else earliest capture, else harvest.
19. **Rating boards (method).** Rating boards and run boards are treated the same way: within a campaign the later
    value replaces the earlier, and a new version starts a new campaign for both kinds. "Rating boards always" is read
    as no more than that.
20. A stated `same-runs-as` names the other source by its id or one of its URLs, and links measures within one
    benchmark family. **(method)** It counts as proven when ≥ 2 shared couples have identical costs (§3's closeness
    test) and at least one score differs. When the scores are identical too, the case is left to lqm's republication
    rule. The earlier measure's cost goes out only when the later measure has an accepted cost.
21. **Composite residuals (method).** A composite residual is computed only for a linear composite with no
    normalisation:
    - the weights are normalised to sum to 1, and the residual is (C − Σ present ŵ·c) / Σ missing ŵ, the weighted
      mean of the missing components;
    - components come from the same publisher, each at its latest snapshot;
    - the residual's group is the residual setup × publisher × the composite's source;
    - cost residuals are not computed: in phase 1, `lqm.load` drops the composite's cost row.

**Cost**

22. Measures citing the same cost facts in one source are one cost measure. It is carried by the measure on the
    headline metric (else the first); the others copy its status and are counted once.
23. The basis comes from the `cost-basis` fact, else from the method's basis, else `unknown`. A missing currency puts
    the cost in a part `?` and blocks repricing; it is not, by itself, out.
24. The price date:
    - `publisher-table` is treated as "a source that recomputes at its current price": the price date is the capture
      dates of `value_seen_in`, else the harvest;
    - a stated date is the first date found in a `price-table` fact.
25. The base price is the entry marked `base`, else the standard maker-API price in force on `as_of`. There is no
    automatic "last list price" fallback: the schema's `base` marker exists for that case.
26. "The publisher's own figure at the base price" means that every price that could have applied over the price date
    equals the base price.
27. `cost-delta-on-source` applies when:
    - exactly one price vector applies over the price date;
    - tokens are given per class;
    - the usage and spend units agree.

    The tolerance is one unit of the cost's last digit, plus the largest relative rounding of the token counts × the
    computed cost. `tokens-reasoning` is tried both added to output and not, unless `reasoning-included-in-out` is
    stated. Long-context tiers are ignored.
28. `cost-uniform-factor` requires every candidate vector to be the same uniform multiple of the base. An unrepriced
    model gets its own subset when its registered prices fully cover its price dates and are uniform multiples of one
    another (a single vector counts). When no registered price covers the price date, the cost gets
    `out:cost-not-comparable`.
29. In the partition, the route key is the single candidate chain, else `unknown`.

**Fit tables and groups**

30. A group is named:
    - by its setup id;
    - plus `@<publisher>` only when the setup has several publishers in the build;
    - plus `#<campaign>` only when the setup has several campaigns;
    - for cost groups, plus `~c<n>` only when the quality group has several cost subsets.

    This keeps today's names for legacy rows.
31. `data.csv` holds every measure:
    - its `effort` is the configuration, or its level when not established;
    - its `model` is `?<verbatim>` when not established;
    - a cost-only measure has a blank quality status, and a measure with no cost has a blank cost status;
    - rows are in the report's order (no extra column).
32. A decision `in` overrides every step, including the group step, and its couple counts in its group. A headline
    decision with a `publisher` decides for that publisher's measures.
33. In the lqm step:
    - `COMPOSITES` and `FAMILY_OF` are resolved through `group-map.json` inside the process, and benchmarks.json
      composites are added;
    - rows that `lqm.load` filters out before its rules (effort not in `lqm.EFFORTS`: `nothink`, `minimal`, `think`)
      are recorded as `lqm_outcome` only, because that method change is pending in lqm.py;
    - a dropped row is attributed to the composites rule if a component group measured its couple, to republication
      if its group is in lqm's republished list, and otherwise to saturated or single-couple.
34. Precision:
    - printed: the step / √12 (the precision's `step`, else the last written digit);
    - chart-pixel: the given `sd`, or blank when none is given;
    - exact: 0.

## Not implemented yet

- `mean-of-runs` and `percent-from-counts`;
- long-context price tiers;
- cost residuals of composites;
- conversion between currencies (`currency-fixed`): a cost is repriced only in its base price's currency;
- non-CSV tables.
