# data/schema — schemas of the findings pipeline

Schemas for the files of docs/DATA-PIPELINE.md (draft of 22 Oct 2026, after four reviews). No build script yet: these
files define what agents and the maintainer write; the decision tree comes later.

## Files

| File | What it validates |
|---|---|
| `common.schema.json` | shared ids, dates, `evidence`, the dated interval `{from, to, evidence}` (+ `from_basis`, `to_basis`) |
| `source.schema.json` | `data/findings/sources/<id>.json`: one source snapshot, its facts, data-file `tables`, digitised `charts` |
| `measure.schema.json` | `data/findings/measures/<source id>.json`: which facts form each measure, on which setup |
| `models.schema.json` | `data/registry/models.json`: keys, release, configurations, names, default, conversions, modes |
| `routes.schema.json` | `routes.json`: route class, spellings, level mapping, per-model ids / accepted configurations / mapping / default |
| `benchmarks.schema.json` | `benchmarks.json`: families, setups (headline, bounds, direction, kind, composite) |
| `publishers.schema.json` | `publishers.json`: publisher → maker or none, legacy outlets |
| `prices.schema.json` | `prices.json`: `as_of`, dated prices per model × route × kind (standard, promotion, off-peak, batch, flex, fast) |
| `rules.schema.json` | `rules.json`: deduction and standing rules, dated, with who decided |
| `decisions.schema.json` | `data/decisions.json`: per-measure decisions pinned by `facts_hash` |
| `vocab.schema.json`, `vocab.json` | the closed vocabularies; each is a JSON Schema in `vocab.json#/$defs/<name>` plus `x-terms` records |
| `validate.py` | schema + cross-file checks (standard library only) |

Examples (hand-converted from held data, all pass): `data/findings/examples/{sources,measures,registry}/` —
(a) ObviousBench v0.2 data file (7 measures: Opus 5.5, Haiku 4.5 default and budget, GPT-5.5 none/low, Qwen3.6-27B via
OpenRouter), (b) HotKV Banking77 prose post (label "lowest effort setting", per-row judges, list-price cost), (c) the
Fable 5.1 system card's Chartography chart (p186, five read points, printed cross-check). The example registry holds only
what they need (opus-5.5, fable-5.1, haiku-4.5, gpt-5.5, qwen3.6-27b; maker-api, openrouter; three setups; Opus 5.5 prices).

## Validate

```
python3 data/schema/validate.py                                  # data/registry + data/findings + data/decisions.json
python3 data/schema/validate.py --registry data/findings/examples/registry --findings data/findings/examples --check-files
python3 data/schema/validate.py --hash <source id>#M2              # facts_hash for a decision
python3 data/schema/validate.py --legacy-coverage /work/.wt-px/raw-data.csv
python3 data/schema/validate.py FILE.json ...                    # schema only (kind from folder / name)
```
Cross-file checks: every publisher, setup, model key, route and rule registered; every fact a measure cites exists (a
cell `T1/<row>/<column>` needs its table and declared column; with `--check-files` the row and a non-empty cell in the
saved CSV); slot ↔ fact type (`vocab measure_slot`); a locator on every fact and table; a quote for prose, table-cell,
label, code and image-text facts, containing the value (`--check-files`: the quote is in the saved text file, every
reachable saved file matches its sha256); closed-vocabulary `term`s; read facts only on charts with a chart-pixel
precision; models.json identity checks (two keys of one maker serving one id over overlapping intervals, same label),
`solo` only alone, default / `selects` / conversions / route maps within the model's configurations, intervals ordered;
decisions: measures exist, a stale `facts_hash` is reported. A file that fails its schema skips its cross-file checks.
Result today: examples 13 files, 0 errors, 1 warning (HotKV headline pending). Negative control: 18 injected faults
(one per check above) all reported, exit 1.

## Vocabularies filled from the data (`vocab.json`)

- **Units**: the 187 distinct non-empty `unit` values of /work/.wt-px/raw-data.csv, with row counts, plus
  `unit_aliases.json` as `x-aliases`. **Currencies**: USD, CNY (yuan, RMB), JPY.
- **Cost methods** (from the confound flags, first match wins): `publisher-table` 621 cost rows, `library-table` 734,
  `cli-total` 478, `router-invoice` 26, `provider-invoice` 209, `tokens×list` 5,992, `unstated` 1,311; 44 rows carry only a
  subscription flag. **Not mapped: 8,420 of 17,835 cost rows** (vals.ai 2,009, matharena.ai 765, chinese-llm-benchmark 558,
  arcprize 535, anthropic-syscard 529, …; flags such as bare `cost:`, `cost-per-run`, `run-cost` say nothing of the
  method). Flags that are not methods are listed in `cost_method.x-not-methods` (repricing, price dates, currency, digitised).
- **nothink spellings**: 14 (setting / label / name), found in 1,653 of 2,763 nothink rows; **think spellings**: 8, in
  1,626 of 3,405 solo / req-enabled / req-thinking / think-unstated rows. The rest need the migration re-read.
- **lqm flags**: `EAP-run`, `restated-from:<Org>`, `restated-from:`, `evaluated-by:`, `vendor-reported:<Org>`, `as reported
  by <Org>`, `<Org>-reported`, `prev`, with the `<Org>` spellings of `lqm.is_home` (`maker` vocabulary).
- Fact types, levels, reason codes (every `in:`/`out:` code the document names), route classes, configuration ids,
  anomaly types, rule ids: as the document lists them.

## Choices where the document left freedom

1. Facts gained `form` (decides the quote rule), `file` (which saved copy, required when there are several), `term`
   (the vocabulary entry a verbatim value stands for: unit, currency, cost basis, cost method; a route id), `table` /
   `chart` links and `precision`. Sources gained `charts` (calibration of read points) and `published` (the default run
   upper bound needs it).
2. Measures gained the slots the tree reads but §3's example omits: `route`, `harness`, `mode`, `early_access`,
   `aggregation`, `setup`, `evaluated_by`, `component_of`, `other`. A data-file cell is cited as `T1/<row key>/<column>`.
3. Global measure id `<source id>#M<n>`; `facts_hash` = SHA-256 of the canonical JSON of the cited facts (cells: the table
   record and the file's sha256).
4. A model whose thinking takes any budget lists `think-<budget>` with `budget_min` / `budget_max`. `to: null` = no end
   known; `from_basis` / `to_basis` record release / stated / capture.
5. One `maker-api` route for every maker; routes carry `spellings` so route facts without a term resolve.
6. A headline chosen by decision may name `decision: null` while pending (warning; the tree then gives `out:not-headline`).
7. Publisher ids = today's catalog spellings (`anthropic`, `github-obviousbench`), so `lqm.load`'s maps keep resolving.
8. `vocab.json` sits here, as the task asked (the document puts it in `data/registry/`); moving it means updating the
   `$ref`s. Unknown fields are refused everywhere (`unevaluatedProperties: false`).

## Contradictions, gaps and open questions (not decided here)

1. **Chart sweeps without labels**: the Fable 5.1 chart (p186) has no effort label on its markers; today's rows give
   low…max in cost order. No fact type or rule maps a marker's rank to a level, so the example records the rank as
   `not-established:absent` and its five measures fall to `out:effort-not-established` as the tree is written.
2. **The same card contradicts itself**: p184 "max effort enabled in all runs" vs the p186 sweep "at various effort
   levels". Which value a measure takes when a point is both printed (86.2 %) and read (86.18) is not stated; the example
   cites the read point and keeps the printed one under `other`.
3. **A harness value "default"** (ObviousBench `reasoning_effort: default`): typed `no-effort-sent` from the repo's line
   "provider default when no setting was sent". This choice decides Haiku 4.5 (step 7 → `nothink`) vs `unstated`.
4. **Dating by captures only**: with one saved capture a default or price covers one day (Haiku 4.5 default, Opus 5.5
   price: 21 Oct only), so earlier runs are not covered. Following §4 strictly, more Wayback captures must be saved first.
5. **Unknown route** (ObviousBench's `anthropic-fallback/`): §5.1 step 6 evaluates "every candidate route", but which
   routes are candidates is not defined.
6. **Score scale**: the ObviousBench file gives fractions (0.958333) for a percent metric; no rule converts a fraction
   (`percent-from-counts` is for counts).
7. **No fact type for total tokens** (input + output in one figure: HotKV, today's `tokens-total-only`).
8. **HotKV headline**: the post designates none and ranks by none: needs a maintainer decision.
9. **Cost methods**: `library-table` (litellm, runcost) is added from the flags, not in the document's list; approve or
   fold it. `simulated-cost` (511 OpenAI launch rows, also flagged `list-price-cost`) looks like a `source-estimate`
   (a level question), not a method.
10. **§6 `reading-sd`** is not a flag: `lqm.reading_sd` reads the `score_prec` / `cost_prec` columns. `lqm.is_home` also
    reads the `harness` column.
11. **Publisher maps**: §6 says `group-map.json` serves publishers and unit aliases, but `PUBLISHER_OF` and
    `UNIT_ALIASES` are keyed by source, not group (review 4's B4 leftover).
12. **Levels**: the introduction says every certainty level is computed by the build, while §2 has agents write a
    fact's `level`. Encoded as two vocabularies: `level` (fact, agent) and `field_level` (measure field, build).
13. **"Earliest capture carrying the measure's value"** (run upper bound) cannot be encoded per measure: sources list
    Wayback URLs but not which capture carries which value.
14. **Small text slips**: the header says three reviews (four exist); §8 says Haiku 4.5 has 375 `solo` rows, §9 says 373.
15. **Example evidence to replace**: Haiku 4.5's release date and Qwen3.6-27B's configurations come from OpenRouter
    captures, not the maker's pages (marked in their `note`/`evidence`).
