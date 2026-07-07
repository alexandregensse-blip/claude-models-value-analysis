# HANDOFF — what's left to do

> **Anthropic System Cards** (in progress): full list + processing method + integration state in
> [`docs/anthropic-system-cards.md`](docs/anthropic-system-cards.md). Sonnet 5 + **Opus 4.8** + **Fable 5/Mythos 5**
> cards DONE. Opus 4.8 → 3 sweeps filling the Opus 4.7 ladder. Fable 5 → 5 sweeps
> (`scfsweppro`/`scfcdiamond`/`scfdeepqa`/`scfhletools`/`scfdraco`); **Fable 5 = Mythos 5** (user-confirmed equal,
> figures plot the "Mythos 5" line). Corroboration **green 24 · yellow 1 · orange 0 · red 0**, only
> `opus-4.7@medium` yellow. Opus 4.7 DONE. Sonnet 4.6 + Haiku 4.5 processed (pre-scaling-figure era, legacy-only comparisons → nothing to integrate). **ALL current-model cards done.**


Status: data curated + verified, generator working, interactive report built (`cost-matrix.html`).
Every `@default` in the effort-assignment view has been resolved or set aside. Next passes, in priority order.

## 1. Fix the normalized matrix separability — DONE (2026-07-06)

§1 (`B`) and §2 (`M`) are **data-driven** via `gen/build.py::ratio_grid(field)` (cost_grid + quality_grid). Method (rewritten 2026-07-06 to the **robust per-benchmark** scheme — central AND band from the same estimates):
1. Per benchmark, take `log(value)` of every current `(model,effort)` couple (explicit efforts + `haiku@solo`; nothink/priceblend/default excluded). **Drop benchmarks with <2 couples** (a lone couple is circular — it only echoes the anchor).
2. Normalise each benchmark to the anchor `opus-4.8@medium=1.0` via a per-benchmark offset: `÷ anchor` when the benchmark contains it, else a **bridge** offset = MEAN residual over shared couples (the offset is a nuisance alignment term → mean, non-degenerate). Bridged benchmarks (no anchor) are **down-weighted ×0.5**.
3. Each benchmark yields one normalised estimate per couple; `central` = **source-weighted MEDIAN** of those estimates (weight = #sources ×0.5-if-bridged), anchor pinned to 1.0.
4. Band = **per-side Huber spread**, centred on the median: deviations (log est − log median) clipped to ±1.5·MAD, then lower/upper = median·exp(∓RMS of clipped neg/pos deviations). Robust (caps a wild outlier at 1.5·MAD) yet **counts** outliers (they widen their side up to the cap — unlike IQR which discards them) and **asymmetric** (captures skew). Centred on the median → the plotted dot is always inside. Single-benchmark node → degenerate `[c,c,c]` box. §1 draws these as asymmetric ovals on a **symlog quality axis** (dilated near 1.0); axis bounds come from the central points, ovals clip.
No `crossmodel_factor × effort_factor` product anywhere; ratios stay strictly within-benchmark. Injected as `__COSTGRID__`/`__QUALGRID__`; `app.js` builds `B`/`M` from it (only `intel`/`ey`/`tag` capability priors stay hand-set). **Haiku 4.5 = single `solo` node** (no effort dial — its one thinking-on point is `officeqa` at `effort=solo`, paired vs `sonnet-4.6@high`). Non-monotone quality at max (Fable, Sonnet 4.6) is the **real over-thinking inverted-U**, not an artifact — do NOT force monotonicity. `normalized.csv` is a stale legacy artifact (the live matrix no longer reads it).

## 2. Audit couple-atomic treatment end-to-end

Make sure no code path re-introduces model×effort separability:
- `normalized.csv` factor tables (the `crossmodel ÷Opus4.8` × `effort ÷medium` lines) — replace with per-couple values.
- §1 landscape curves in `gen/app.js`: `OFF5 / OFF4 / OFF3` apply **one shared effort-shape to all models** (calibrated on OSWorld). That is a separability assumption on the *quality* axis — flag it, and differentiate per model where data allows.
- Confirm the linking graph and ratio charts stay couple-atomic (they already are).

## 3. Corroborate the weakly-supported graph nodes  — PASS 1 DONE (2026-07-06)

The linking graph (§3) rings each node by independent-source count: green ≥3, yellow 2, orange 1, red 0.
After a 5-package web sweep (Sonnet agents) the corroboration is now **green 9 · yellow 8 · orange 7 · red 1** (was 8/7/6/6). Sources added:

- **Fable 5** — `simonwillison.net` gives the FIRST full effort sweep (low→max, tokens_out+$ on a trivial pelican-SVG task). Fills the 3 red Fable cells (→orange) and lifts @high→green, @max→yellow. Confound tagged `trivial-svg-1run`; note the **non-monotone high<medium** token inversion (author flags it too).
- **Sonnet 4.6 @low** — `futuresearch.ai/effort-scaling` (Deep Research Bench, low $0.27 / high $0.46, effort labelled) → @low now yellow, also strengthens @high (green, 8 src).
- **Haiku 4.5 — STRUCTURAL: modelled as a single-effort model (one merged node).** Two independent GitHub issues confirm Haiku 4.5 does **not** expose the discrete `effort` param (only continuous `thinking.budget_tokens`; `effort` → HTTP 400 `invalid_reasoning_effort`). We have **no** budget-tokens granularity for Haiku either. Since it has no effort dial, it is drawn in §3 as ONE node (`haiku-4.5@solo`, `MEFF=["solo"]`) placed off the effort gridlines with a "single operating point" label, whose ring merges **all** sources that measured Haiku in any config (10 → green). It is NOT spread across low/medium/high, and no fake `@high` node. It has no effort-ladder edges (the edge filter requires the effort to be in the model's own `MEFF`); its cross-model relationships live in §4 (e.g. `sonnet-4.6/haiku-4.5`, OfficeQA matched reasoning-high ratio) and §6 (no-think regime, cheapest anchor = 1×).
- **Opus 4.7 @medium** — still RED (the last one). Only relative data found (apiyi.com ~1.3× tokens vs low; towardsai aggregate 2.7× low→max). DataCamp gives high/xhigh $/task but its `budget_tokens` method returns 400 on 4.7 → **methodology suspect, not integrated**. Needs an absolute $/task or tokens measurement at medium.
- **@max/@high Opus·Sonnet disagreement (high σ)** — NOT arbitrated. No independent leaderboard (Terminal-Bench, Aider, Scale AI, Epoch, METR) has these 4 models with a cost/effort column yet (all trace back to Anthropic OSWorld + AA). Only anecdotal tweets (n=1–3) found, directionally siding with OSWorld (Opus ≫ Sonnet 5). Revisit in a few weeks.
- **CursorBench (HN 48736605) — VERIFIED REAL, secondary.** The earlier "could-not-reconfirm" alert was a false alarm from HN HTML rate-limiting; via the Algolia API the comment exists (maxloh, id 48747133): Fable 5 Max 72.9% @ $18.02 vs Opus 4.7 Max 64.8% @ $11.02 (same bench, both Max → 1.64×). But it is a **forum comment citing CursorBench `[0]`** — get the primary CursorBench URL before adding it to `raw-data.csv`.

### PASS 2 (2026-07-06) — CursorBench found; corroboration now **green 18 · yellow 6 · orange 1 · red 0** (25 nodes, incl. Haiku merged `@solo`)

A second Sonnet sweep (5 packages) yielded ONE integrable source, but a decisive one:

- **CursorBench (`cursor.com/cursorbench`) integrated — 24 rows.** A complete cost×effort GRID (Low/Medium/High/Extra-High/Max) for Fable 5, Opus 4.8, Opus 4.7, Sonnet 5, Sonnet 4.6 (Haiku absent). Primary page verified + corroborated to the cent by javascripthacker.com. It is a first-party/**vendor** benchmark (Anysphere bills model usage) → tagged `confound=cursor-vendor`; cost = public $/MTok × measured tokens (input/output mix hidden); single task family; not independently reproducible. Treated as one more credible first-party datapoint (peer of the Anthropic OSWorld chart), NOT a definitive arbiter. This single source **filled the last red** (`opus-4.7@medium` $2.93) and lifted almost everything to green/yellow — be aware a large chunk of the new green rests on this one vendor grid.
- **Remaining thin cells:** `opus-4.7@medium` (orange, CursorBench only — no independent absolute measurement exists; a weak gist with unconfirmed `code_gen_effort` config was rejected). 6 yellow: Fable low/medium/xhigh (CursorBench+Willison), opus-4.7 high/xhigh, sonnet-5@medium (anthropic+CursorBench).
- **@max/@high disagreement — NOT resolved, now better characterised.** CursorBench adds a 3rd/4th point to the contradictory couples and lands *between* the extremes (e.g. `opus-4.8/sonnet-5 @max`: 1.91 / 0.62 / 0.87 / **1.10**), or as an outlier (`opus-4.7/sonnet-4.6 @max` = **3.57**, CV→0.54). Conclusion reinforced: these ratios are **task-dependent, not universal constants** — exactly the couple-atomic assumption. Do NOT collapse them to a single number.
- **Leads for later (verified real, not yet extractable):** (1) **Epoch AI** `epoch.ai/models/claude-fable-5` tracks Fable per reasoning setting (max/xhigh/high) but values are JS-rendered — needs a browser or the data-explorer CSV export. (2) **LiveBench / Terminal-Bench** have Opus 4.7 @xhigh scores (no cost). (3) Nothing independent yet for `sonnet-5@medium` cost (Sonnet 5 too recent; aider.chat hasn't ingested it).
- **Dead ends confirmed:** no qualifying 2nd Fable source with real (non-illustrative) cost; no Haiku thinking-on source pairing a *current* model with cost (finds paired Haiku with legacy 4.5-gen models); no independent `sonnet-5@medium`.

When adding a source: append rows to `raw-data.csv` AND the hardcoded `GROUPS` array in `gen/app.js` (they must stay in sync — the ratio/consolidated data comes from the CSV, the §3 corroboration graph from `GROUPS`), keep the verified effort/thinking config (check paper text AND repo code — see `docs/repo-config-proof.md`), then `python3 gen/build.py`.

## Also pending

- **No-think regime analysis — CONFIRMED as a separate category (not a ladder point).** Sources proven to run without extended thinking are tagged `nothink` in `raw-data.csv`: **17 rows / 7 sources** (WorkBench, STAGE-Claw, TOBench, ianlpaterson, code-review, WildClaw, TrueFoundry). Plus **5 `default` rows** (CEO-Bench, AutomationBench, ctala, drona23, ponytail) = harness-default, thinking unstated → keep as a **3rd "unknown-thinking" bucket**, don't merge into no-think. Build a dedicated regime column/table (cheapest regime). Haiku 4.5 folds in here almost entirely (it is off the effort ladder — see above; its OfficeQA reasoning-on run survives only as a §4 matched-config ratio). Still TODO: the actual artifact section (body.html + app.js render + build.py aggregation).
- **thinking-default confound (hypothesis, to verify).** Omitting `thinking` may **enable** adaptive on Sonnet 5 but **disable** it on Opus 4.7/4.8 → a third-party harness that doesn't set `thinking` explicitly would compare "Sonnet 5 thinking" vs "Opus non-thinking", plausibly explaining part of the AA↔OSWorld contradiction on `opus-4.8/sonnet-5 @max`. Verify against Anthropic docs, then document as a `confound` on those couples.
- **Internal validation run.** Public data caps confidence at "medium-high". A single controlled run on a real workload (same tasks across models/efforts) would anchor the whole matrix.

## Working loop

```bash
# edit gen/{build.py,app.js,body.html,style.css} and/or raw-data.csv / normalized.csv
python3 gen/build.py         # regenerates cost-matrix.html
# open cost-matrix.html in a browser to check
```
The generator is the single build path — do not hand-edit `cost-matrix.html`.
