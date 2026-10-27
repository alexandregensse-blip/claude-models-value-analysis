# data/schema: schemas of the findings pipeline

Schemas for the files of docs/DATA-PIPELINE.md (at 9f3e7ef, 22 Oct 2026), revised after the schema review
(/work/.salvo14/review-schema/review.md). No build script yet: these files define what agents and the maintainer write.

## Files

| File | What it validates |
|---|---|
| `common.schema.json` | shared ids, real dates (`format`), `evidence`, the dated interval `{from, to, evidence}` (+ `from_basis`, `to_basis`) |
| `source.schema.json` | `data/findings/sources/<id>.json`: the source, its `captures` (Wayback / commit / fetch), `extractions` (PDF text), facts, data-file `tables`, digitised `charts` |
| `measure.schema.json` | `data/findings/measures/<source id>.json`: the facts of each measure by slot, its setup, `value_seen_in` (capture ids) |
| `models.schema.json` | `models.json`: keys, release, configurations, names per namespace, default, conversions, modes, and the name-resolution rule |
| `routes.schema.json` | `routes.json`: class, `spellings`, `name_prefixes`, level mapping, per-model ids / accepts / mapping / default |
| `benchmarks.schema.json` | `benchmarks.json`: families, setups (metric and headline metric as vocabulary terms, bounds, kind, composite) |
| `publishers.schema.json`, `prices.schema.json`, `rules.schema.json` | publisher → maker; dated prices (+ `base` marker); rules |
| `decisions.schema.json` | `data/decisions.json`: measure decisions (pinned by `facts_hash`) and setup-level headline decisions |
| `flag-map.schema.json` | `flag-map.json` (migration only): per-source cost method, legacy effort values |
| `vocab.schema.json`, `vocab.json` | closed vocabularies, each a JSON Schema at `vocab.json#/$defs/<name>` plus `x-terms` records |
| `validate.py` | schema + cross-file checks (standard library only) |

Examples (hand-converted from held data): `data/findings/examples/{sources,measures,registry}/`. (a) ObviousBench v0.2 data
file: 7 measures, fractions on `answer_pass3%`, Inspect model strings resolved by prefix, values seen in two commits.
(b) HotKV Banking77 prose post: the label "lowest effort setting", per-row judges, list-price cost, `tokens-total`.
(c) Fable 5.1 card, Chartography: the printed 86.2 % with its "max effort" label is the max measure; the four unlabeled
markers are `not-established:assumed`. The example registry holds only what they need, plus a two-entry example flag-map.

## Validate

```
python3 data/schema/validate.py                                   # data/registry + data/findings + data/decisions.json
python3 data/schema/validate.py --registry data/findings/examples/registry --findings data/findings/examples --check-files
python3 data/schema/validate.py --hash <source id>#M2               # facts_hash for a measure decision
python3 data/schema/validate.py --legacy-coverage /work/.wt-px/raw-data.csv [--flag-map F]
python3 data/schema/validate.py FILE.json ...                     # schema only (kind from folder / name)
```
Cross-file checks:
- **References:** everything referenced is registered (publishers, setups, keys, routes, namespaces, rules, headline
  decisions). Cited facts, cells and capture ids exist, and slots match fact types. One value is cited by one measure.
  The value and per-entry facts are about an entry the model facts name. The value's metric term is the setup's metric.
- **Fact form:** score facts and columns carry a metric term and a `scale`, API-id facts a namespace, thinking budgets
  their token count. A quote is required for prose, table cells, labels, code and image text, and contains the value.
  A quote in a PDF must point at the PDF's text extraction instead (NFKC matching). Read points sit on charts, with
  chart-pixel precision.
- **Registries:**
  - **Identity:** two keys of one maker serving one id over overlapping intervals fail, and so do identical display
    labels under the normalisation rule.
  - **Configurations and defaults:** `solo` only alone; defaults, `selects` and maps stay within the model's
    configurations; defaults may not overlap.
  - **Dated records:** every dated record of every registry is ordered. `to: null` only on configurations and names.
    Capture-dated bounds are days.
  - **Prices and flag-map:** at most one `base` price; flag-map bases agree with their methods.
- **Decisions:** stale measure decisions (the hash covers the setup, not `note`/`translation`) are reported, not applied.

`--check-files` also checks sha256 of every reachable saved copy (sources and registry evidence), quotes in text files,
CSV rows and cells, and that a value reads the same in every capture listed in `value_seen_in`. Model facts are
resolved with the name rule and reported (warning) when they give no key or several. A file that fails its schema
skips its cross-file checks.

**Result:** examples, 14 files, 0 errors, 1 warning (HotKV headline pending). The review's fault scripts: all 45 plant.py
cases reported (44 errors, the stale hash as the designed warning). plant2: a decision goes stale when its measure's
setup changes, a note edit no longer stales it, and `tokens-total` is accepted. Two plant2 cases now differ from what
they expected:
- `value_seen_in: ["W1"]`: the slot is accepted, but the capture id W1 is not defined in that source, so it is an error.
- `scale-conversion`: the example rules already hold it, so adding it again is a duplicate.

25 more planted faults for the new checks were all reported (the unresolvable model id as a warning, by design).

## Vocabularies filled from the data (`vocab.json`)

- **Units:** the 187 distinct `unit` values of /work/.wt-px/raw-data.csv, plus `unit_aliases.json`.
- **Metrics:** the 423 distinct `score_metric` values (row counts).
- **Score scales:** fraction, percent, raw.
- **Currencies:** USD, CNY, JPY.
- **Cost methods, first-match flag patterns over 17,835 cost rows:**

  | Method | Cost rows |
  |---|---|
  | `tokens×list` | 5,992 |
  | `unstated` | 1,311 |
  | `library-table` | 734 |
  | `publisher-table` | 621 |
  | `cli-total` | 478 |
  | `provider-invoice` | 209 |
  | `router-invoice` | 26 |
  | **unmapped** | **8,420** (vals.ai 2,009, matharena.ai 765, chinese-llm-benchmark 558…) |

  These are mapped source by source at migration through `flag-map.json`'s `cost_method_by_source`: evidence per
  source, `applies: unmapped | all`, optional groups. With the example entry (ObviousBench's own costing code,
  `applies: all`), 386 rows move from `tokens×list` to `library-table`. `simulated-cost` follows §5.3.2: classified
  per source.
- **Spellings:**
  - nothink: 21 spellings, found in 2,099 of 2,763 nothink rows. The review's quick wins were added. `instant` and
    `chat mode` were removed: they are names, so they belong in keys or `names.selects`.
  - think: 12 spellings, found in 1,872 of 3,405 solo/think rows.
  - `legacy_effort` says where the other legacy effort values go.
- **Flags `lqm.load` reads:** `EAP-run`, `restated-from:<Org>`, `restated-from:`, `evaluated-by:`, `vendor-reported:<Org>`,
  `as reported by <Org>`, `<Org>-reported`, plus `prev`. No `reading-sd`: the sd goes in `score_prec` / `cost_prec`.
- **Other vocabularies:**
  - fact types now include `tokens-total`, rule ids `scale-conversion`, and reason codes `out:saturated` (lqm.load's
    saturated group);
  - makers now include `other` (never a publisher's maker), with `display_prefixes`;
  - capture kinds.

## Added for the build (22 Oct)

The build is described in data/BUILD.md. It added these terms:
- fact types `run-score` (slot `runs`, mean-of-runs) and `tokens-in-per-request` (long-context tiers);
- the fact field `run`;
- score scale `counts` (percent-from-counts);
- reason code `out:value-not-established`;
- JSON tables, whose `where` is a JSON path (`$`, `.key`, `['key']`, `[n]`, `[*]`), now read by validate.py.
- the legacy path (migration): fact type `legacy-row`, fact form `legacy`, measure slot `legacy`, the source's `legacy`
  block, and the reason codes `legacy:in` / `legacy:out:<why>`;
- a decision on a missing measure is now a warning (reported, not applied).
- after the ObviousBench pilot (23 Oct): `reasoning-included-in-out` takes a boolean term; a table column carries its
  own precision; a computed fact (`level: computed`, `rule`, `inputs`) stands for a derived cell; `run-date-convention`
  (with its `pattern`) and `price-tier` facts; `legacy_ref` on a converted measure; price-tables.json (pinned price
  tables, price-tables.schema.json); validate.py prints a summary per file, registry warnings apart (data/BUILD.md).

## Added at the merge of the registry parts (23 Oct)

The wave-1/2 parts (data/registry/parts/, reports in /work/.salvo14/mig/<part>/report.md) were merged into data/registry/
(/work/.salvo14/mig/merge/report.md). They needed:
- **vocab.json:** metric `none` (cost-only setups: metric and headline `none`); configuration `between-tools` (Sonnet
  5.5's `thinking: {type: between_tools}`, with `regex` for its setting line; x-terms `in_fit: false` at first, so the
  build gave `out:effort-not-established`; `in_fit: true` since 26 Oct, the coordinator's decision: it is in the fit like
  every configuration of a model's list); price classes `cache-write-30m`, `cache-write-12h`
  (OpenAI); rule ids `configurations-per-model`, `cost-method-unstated-single`, `base-price-retired-last-list`,
  `base-price-charged-never-applied` (standing: the decisions of DATA-PIPELINE §4 prices and §9).
- **benchmarks.schema.json:** `headline.level` (`written` / `not-established:assumed`); composite components are a setup
  id or `{name, setup}` with `setup: null` for a component the registry does not hold (weights keyed by the name; never
  present, so a residual always covers it); `linear: true | false | "unknown"` (unknown: no residual).
- **prices.schema.json:** `configurations` on an entry: the configurations the price applies to (Qwen3-8B thinking
  output 2.1, non-thinking 0.7); absent = all. Base: at most one per model and configuration; entries of one model,
  route, kind and currency that overlap in time may not share a configuration. The build re-prices with the entries of
  the measure's configuration.
- **routes.schema.json:** `names_case_insensitive`. **Rule:** in a namespace whose route sets it (`huggingface`, the
  Hugging Face namespace: repository ids `Org/Name`), an API id matches a registered name casefolded, after the route's
  prefix (`hf/`) is stripped; the identity check compares those names casefolded too. Every other namespace stays
  exact (case-sensitive). With namespace `prefix`, a head no route lists (`qwen/`) leaves the route unknown, and the
  rest, then the whole value, are tried in every namespace, the Hugging Face one included.
- **common.schema.json:** publisher ids may contain spaces and parentheses (two raw-data.csv sources do).
- **validate.py:** a quote in a saved HTML page is also looked for in its raw source (data embedded in a script: the
  2024 Anthropic pricing pages carry their prices in a Next.js payload); the checks above. **build.py:** the same name
  rule, component objects, `linear` read as `is True`, prices per configuration, `in_fit: false` terms out.
- One `maker-api` route for every maker's own API (the id models.json conversions, names with route null and the base
  price use); the part's per-maker routes are folded into it, their spellings and prefixes kept.
- Tests: 4 more (`ext_*`: named component and linear unknown, price per configuration, Hugging Face names,
  between-tools), each failing when its change is removed.

## Added at the registry fix (26 Oct)

The gap parts (gaps-keys, gaps-prices, gaps-openrouter, gaps-configdates, gaps-configdates-routes) were merged and the
registry review's must-fix items fixed (/work/.salvo14/mig/registry-fix/report.md). data/registry now validates with
`--check-files`: 0 errors. Schema changes:
- **common.schema.json:** a default may carry `setting` (`thinking` · `effort`; absent = the whole call). validate.py
  checks overlaps per side: the whole call and `thinking` answer for a call that sends nothing, `effort` for a call
  that turns thinking on.
- **routes.schema.json:** `via` (the next step: a route id) on `level_mapping`, on the route-wide `mapping` (new) and on
  a model entry's `accepts`, `mapping` and `default`; `maker` and `models` on the route-wide records. validate.py checks
  that `via` is a registered route other than the route itself, `maker` a vocabulary maker, `models` registered keys,
  and a route-wide mapping's result one of each listed model's configurations.
- **models.schema.json:** the configuration list may be empty (configurations not established: every measure
  out:effort-not-established).
- **vocab.json:** `between-tools` `in_fit: true` (the coordinator: in the fit like every configuration of a model's
  list).

## Choices where the document left freedom

1. **Fields on facts:**
   - `form`: decides the quote rule.
   - `file`: which saved copy.
   - `term`: the vocabulary entry a verbatim value stands for (score → metric, unit, currency, cost basis and
     method, a budget's tokens, a route id).
   - `scale`, `namespace`, `table` / `chart`, `precision`.
2. **Fields on sources:** `captures`, `extractions` (agents save a PDF's text with its sha256), `charts`, `published`.
3. **Measures:**
   - They gain the slots the tree reads: `route` (the only slot the route chain reads), `harness` (a setup field),
     `mode`, `early_access`, `aggregation`, `setup`, `evaluated_by`, `component_of`, `other`.
   - A cell is cited as `T1/<row key>/<column>`. A column may state two facts: Inspect's
     `openrouter/qwen/qwen3.6-27b` is a route and an API id.
4. **Name resolution (models.schema.json):** no substring or fuzzy match.
   - An API id carries its `namespace` (a route id, or `prefix`). The longest `name_prefixes` entry of that route is
     stripped once, then the id must match a name registered under that namespace exactly (casefolded in a namespace
     with `names_case_insensitive`: the Hugging Face one).
   - With `prefix`, the head up to `/` names the route. An unknown head means the route is unknown: the rest, then the
     whole value, is tried in every candidate route, and exactly one key must result.
   - Display names are compared under N: NFKC, casefold, separators as spaces, the leading maker spellings dropped ('Anthropic', 'Claude': 'Haiku 5.5' is 'Claude Haiku 5.5'), Unicode hyphens as separators, no space between a word and its version ('Qwen 3.6' is 'Qwen3.6').
     A label carrying the configuration is not a model-name fact.
5. **Headlines:** a headline is a metric term compared with the setup's metric. It is the benchmark's own designation;
   when publishers of one setup disagree, a headline decision settles it (`kind: headline`, optionally per publisher).
6. **Hashes and ids:** global measure id `<source id>#M<n>`. `facts_hash` = SHA-256 of the canonical JSON of measure,
   setup, slots and cited facts (cells: the table record and the file's sha256).
7. **Configurations:** `think-<budget>` carries `budget_min` / `budget_max`.
8. **Publisher ids** are today's catalog spellings. `vocab.json` stays in `data/schema/` (the document says
   `data/registry/`); moving it means updating the `$ref`s.

## Still open (not decided here)

1. **HotKV headline:** the post designates none and ranks by none, so it needs a headline decision. Its couples are also
   judged on different item sets (926 vs 935) by different judges.
2. **Dating by captures only:**
   - The Haiku 4.5 and Qwen3.6-27B defaults do not cover their runs, so they come out `out:effort-not-established`.
   - Opus 5.5 is priced on 21 Oct only, so HotKV's 11 Oct list prices give `out:cost-not-comparable`.
   - Earlier Wayback captures need saving.
3. **A harness on the route chain that routes.json does not list** (Inspect): behaviour unstated (identity?).
4. **"Unmapped cost method → `unstated` / `unknown`" for phase 1:** acceptable? (4,371 of the 8,420 unmapped rows are
   in today's fit.)
5. **Evidence still from OpenRouter:** Haiku 4.5's release and Qwen3.6-27B's configurations (marked in the evidence).
6. **Earlier commits not saved:** the commits that first carried ObviousBench rows (64d435e for Opus 5.5) are not saved,
   so `value_seen_in` lists only 855ee80 and 222d955.
7. **Fable chart, other models:** Fable 5 (84.2 %) and Opus 5 (83.0 %) at max are printed on the same page. Adding them
   gives the max-effort couples a group of 3.

## Added on 27 Oct

- the source field `decimal_mark` (a decimal comma, data/BUILD.md); counts scores in the source's language (validate.py COUNTS).
