# Anthropic System Cards — registry & integration state

Goal: fold the **cost + quality by effort** data from the Anthropic System Cards into `raw-data.csv`, then
`python3 gen/build.py`. The cost and quality grids are **robust couple-atomic**: same-task ratios *within* a
benchmark → normalise each benchmark to the anchor `opus-4.8@medium = 1.0` (÷ anchor, or a ×0.5-weighted bridge
when absent) → **source-weighted median** for the centre, **per-side Huber ±1.5·MAD** for the band (robust,
asymmetric, centred on the median). We **never** compare raw values across benchmarks — only **within-benchmark
ratios**. Single-couple benchmarks are dropped. Haiku 4.5 = a `solo` node (no effort dial).

## Exhaustive list of System Cards (source: anthropic.com/system-cards, July 2026)

| Model | Date | Pages | Direct PDF | Priority | State |
|---|---|---|---|---|---|
| **Sonnet 5** | 2026-06-30 | 145 | https://www-cdn.anthropic.com/9e6a1044980d8c4ed85669faf9c2a8342e2e9f1e/Claude%20Sonnet%205%20System%20Card.pdf | — | ✅ **INTEGRATED** |
| **Fable 5 & Mythos 5** | 2026-06-30 | 319 | https://www-cdn.anthropic.com/d00db56fa754a1b115b6dd7cb2e3c342ee809620.pdf | ★★★ (Fable sweeps) | ✅ **INTEGRATED** |
| **Opus 4.8** | 2026-05-28 | 246 | https://www-cdn.anthropic.com/0f0c97ad20d8005706296bd92aa1c27c6b2f4f61/Claude%20Opus%204.8%20System%20Card.pdf (alt hash: 0b4915911bb0d19eca5b5ee635c80fef830a37ea.pdf) | ★★★ (Opus 4.8/4.7 sweeps → fills opus-4.7@medium) | ✅ **INTEGRATED** |
| **Opus 4.7** | 2026-04-16 | 232 | https://www-cdn.anthropic.com/037f06850df7fbe871e206dad004c3db5fd50340/Claude%20Opus%204.7%20System%20Card.pdf | ★★ | ✅ **INTEGRATED** |
| **Sonnet 4.6** | 2026-02-17 | 134 | https://www-cdn.anthropic.com/78073f739564e986ff3e28522761a7a0b4484f84.pdf | ★★ | ✅ **PROCESSED** (nothing to add) |
| **Opus 4.6** | 2026-02 | ? | https://www-cdn.anthropic.com/14e4fb01875d2a69f646fa5e574dea2b1c0ff7b5.pdf (alt: 0dd865075ad3132672ee0ab40b05a53f14cf5288.pdf, 6a5fa276ac68b9aeb0c8b6af5fa36326e0e166dd.pdf) | ★ (legacy) | ⏳ |
| **Mythos Preview** | 2026-04 | ? | page: anthropic.com/claude-mythos-preview-system-card | ☆ (research config) | ⏳ |
| Opus 4.5 | 2025-11 | ? | https://www-cdn.anthropic.com/bf10f64990cfda0ba858290be7b8cc6317685f47.pdf | ☆ legacy | — |
| Haiku 4.5 | 2025-10 | 39 | https://www-cdn.anthropic.com/7aad69bf12627d42234e01ee7c36305dc2f6a970.pdf | ★ (Haiku, no discrete effort) | ✅ **PROCESSED** (nothing to add) |
| Sonnet 4.5 | 2025-09 | ? | https://www-cdn.anthropic.com/963373e433e489a87a10c823c52a0a013e9172dd.pdf | ☆ legacy | — |
| Opus 4.1 | 2025-08 | ? | https://www-cdn.anthropic.com/9fa30625273bafdf5af82c93719d7ca606485a16.pdf | ☆ legacy | — |
| Sonnet 4 & Opus 4 | 2025-05 | ? | https://www-cdn.anthropic.com/07b2a3f9902ee19fe39a36ca638e5ae987bc64dd.pdf (alt 6be99a52..., 4263b940...) | ☆ legacy | — |
| Sonnet 3.7 | 2025-02 | ? | https://www-cdn.anthropic.com/9ff93dfa8f445c932415d335c88852ef47f1201e.pdf | ☆ legacy | — |
| Haiku 3.5 & Sonnet 3.5 | 2024-10 | ? | https://www-cdn.anthropic.com/c7822cdc35ad788ec87e14b3a9d45010f1f86c38.pdf | ☆ too old | — |
| Claude 3 | 2024-03 | ? | https://www-cdn.anthropic.com/c6a80a657af445f40e31afac050f3bf76d3b1404.pdf | ☆ | — |
| Claude 2 | 2023-07 | ? | https://www-cdn.anthropic.com/bd2a28d2535bfb0494cc8e2a3bf135d2e7523226/Model-Card-Claude-2.pdf | ☆ | — |

Current grid models: Fable 5, Opus 4.8, Opus 4.7, Sonnet 5, Sonnet 4.6, Haiku 4.5.
→ **All processed** (see the detailed sections + the summary at the bottom). Nothing high-priority remains.

## How to process a PDF (the rich data lives in the FIGURES = images)

`pdftoppm`/`pdftotext`/`pip` are unavailable in the env. Recipe that works (scratchpad):
```bash
cd <scratchpad>
curl -sL --max-time 120 -o card.pdf "<PDF_URL>"
uv pip install --target ./pylib pypdf pillow      # local install (system-site is blocked)
# text per page:
PYTHONPATH=./pylib python3 -c "import pypdf;r=pypdf.PdfReader('card.pdf');print(r.pages[N-1].extract_text())"
# extract the figures (embedded images) from a page range:
PYTHONPATH=./pylib python3 -c "import pypdf;r=pypdf.PdfReader('card.pdf');
[im.image.save(f'img/p{p+1}_{k}.png') for p in range(A,B) for k,im in enumerate(r.pages[p].images) if len(im.data)>15000]"
```
Then **Read the PNGs** (vision) and **digitize** the points (cost axis = log, read to ±10-15%). The text gives the
summary tables (scores @max); the **effort×cost figures** give the full sweeps.

## ✅ Sonnet 5 System Card — INTEGRATED (source=`anthropic-syscard`)

Config (p115): Sonnet 5 results = adaptive thinking **@max**, averaged over 5 trials (except where noted).
Rows added to `raw-data.csv`:
- **Quality scores @max** (Table 8.1.A p114 + the launch image for Opus 4.8) — groups:
  `scswebenchpro` (SWE-bench Pro 63.2/58.1/69.2), `schle-nt` (HLE no-tools 43.2/34.6/49.8),
  `scgdpval` (GDPval-AA v2 Elo 1618/1395/1615), `schealthbench` (57.8/44.2),
  + `automationbench` sonnet-5@max=13.5 added to the existing group. (models S5/S4.6/Opus4.8)
- **2 COMPLETE cost+quality effort sweeps digitized from figures** (confound `digitized-logx`):
  - `scfrontiercode` (fig 8.4.A p117) — Fable5, Opus4.8, Sonnet5 (low→max) + Sonnet4.6 (med/high/max).
    Scores: Fable 37.3/41.1/42.9/46.3/44.7; Opus4.8 25.3/26.9/30.3/34.3/31.3;
    Sonnet5 18.1/26.6/28.9/34.0/38.8; Sonnet4.6 med13.6/high15.1/max13.2.
  - `schletools` (fig 8.9.1.B p122, HLE with tools) — Sonnet5, Opus4.8, Sonnet4.6 (low→max).
    Sonnet5 36.5/47.2/52.8/54.6/57.4; Opus4.8 50.2/55.2/55.7/57.6/58.0; Sonnet4.6 34.9/46.5/49.7/(max)46.8.
  ($/task costs digitized from the log axes — see the `anthropic-syscard` rows in raw-data.csv)
- Result: cost ratio-points 82 → **119**. Quality curves monotone EXCEPT **Sonnet 4.6 @max** which dips
  (REAL inverted-U: FrontierCode 15.1→13.2, HLE 49.7→46.8 — over-thinking degrades). DO NOT "fix".

### Sonnet 5 card figures NOT yet digitized (do if needed, especially quality):
p118 CursorBench (already covered by our cursorbench source), p123 BrowseComp scaling,
p124-132 multimodal (GDP.pdf, OSWorld, ChartMuseum, CharXiv, BenchCAD), p133 GDPval by effort,
p135/137 ?, p138-139 multilingual MMLU (GMMLU/INCLUDE/MILU). A **"Mythos 5"** model appears (HLE:
low59.8/med62.6/high63.4/xhigh64.2/max64.7) = Fable's research config, **out of the current grid** → ignore.

## ✅ Opus 4.8 System Card — INTEGRATED (2026-07-06, source=`anthropic-syscard`, ref `anthropic-opus48-syscard-pNNN`)

246 pages. **3 digitized effort×cost figures** (low→max sweep, log axis), each a DEDICATED group
(100% intra-figure ratios; per-tier pricing Opus $0.06/Ktok, Sonnet $0.012/Ktok = 5:1):
- **`scsweproeff`** (fig 8.2.A p196, SWE-Bench Pro, output tokens) — Opus 4.8 & Opus 4.7 low→max.
  Opus4.8 scores 63.6/66.0/67.4/69.7/69.3; Opus4.7 57.3/59.5/62.4/62.8/63.6. (Opus 4.6 legacy ignored.)
- **`schleeff`** (fig 8.10.1.B p203, HLE with tools, TOTAL tokens) — Opus4.7 43.0/48.4/53.2/55.4/54.7;
  Opus4.8 50.2/55.2/55.7/57.6/57.9. (≈ identical to the Sonnet5 card's `schletools` → confirms the same experiment.)
- **`scosweff`** (fig 8.12.6.B p222, OSWorld, output tokens) — Opus4.8 78.5/80.0/81.4/83.1/83.4;
  **Opus4.7 73.8/75.7/79.8/80.2/82.8** (absent from the `osworld`/AA group); Sonnet4.6 71.3/75.9/77.8/(max)78.4.
- Table 8.1.A p194-195 (@max scores Opus4.8 vs Opus4.7) and bars p205/p223 (DeepSearchQA, OfficeQA/Pro,
  Finance, MCP-Atlas) read but NOT added (score-only @max, marginal gain vs the 3 sweeps).
- **Result**: `opus-4.7@medium` orange→**yellow** (anthropic-syscard + cursorbench); Opus4.7 cost+quality
  ladders monotone across 3 benchmarks. Global corroboration **green 24 · yellow 1 · orange 0 · red 0** (25 nodes).
  cost-pts 119→142. (Note: the Opus 4.7 card is also `anthropic-syscard`, so it does NOT turn medium green —
  a NON-Anthropic source is needed; medium stays the only yellow.)

## ✅ Fable 5 & Mythos 5 System Card — INTEGRATED (2026-07-06, source=`anthropic-syscard`, ref `anthropic-fable5-syscard-pNNN`)

319 pages. **KEY DECISION (user-confirmed): "Fable 5 = Mythos 5 with more safety" → treat the two as EQUAL.**
The card's effort×cost figures plot the "Claude Mythos 5" line (= deployed Fable 5, within ~0.3pt due to the
safety fallback to Opus 4.8 on ~21% of Terminal-Bench trials). Equivalence evidence: the Mythos 5 line on
**FrontierCode Main** (37.3/41.1/42.9/46.3/44.7) and **CursorBench** (max 72.9%) matches EXACTLY our
`scfrontiercode`/`cursorbench` data already labelled "Fable 5". "Claude Mythos Preview" (an earlier research
config) stays OUT of grid → ignored.

**Bonus: costs read DIRECTLY in $/task on the x-axis** (no token→price conversion). Opus 4.8 is co-plotted on
each figure = anchor → Fable 5 is placed directly. 5 dedicated groups (couple-atomic, intra-figure) added as
`fable-5` + `opus-4.8`, confound `digitized-logx-mythos`:
- **`scfsweppro`** (fig 8.2.A p255, SWE-bench Pro) — Fable low→xhigh 75.0/78.2/79.6/80.4; Opus4.8 60.3/65.2/67.5/68.6.
- **`scfcdiamond`** (fig 8.4.A p257, FrontierCode Diamond) — Fable 11.5/17.8/24.0/29.3/30.9; Opus4.8 8.2/**5.9**/8.7/13.4/11.4 (med<low inversion is REAL, digitized faithfully).
- **`scfdeepqa`** (fig 8.14.3.B p270, DeepSearchQA F1) — Fable 92.0/94.1/93.6/94.5/94.2; Opus4.8 88.6/90.1/91.0/92.1/93.1.
- **`scfhletools`** (fig 8.14.1.B p267, HLE with tools) — Fable 59.8/62.6/63.4/64.2/64.5; Opus4.8 50.2/55.2/55.7/57.6/57.9 ($ costs = `schletools` ✓ confirms the digitization).
- **`scfdraco`** (fig 8.14.4.A p271, DRACO) — Fable 76.7/80.6/82.8/84.9/86.4; Opus4.8 70.2/73.3/75.1/79.0/80.6.
- **SKIPPED** (duplicates): FrontierCode Main (= `scfrontiercode`), CursorBench (= `cursorbench`).
- **Result**: all Fable 5 nodes at 3–5 independent sources (green), σ tightened; cost (1.56→5.94) and
  quality (1.18→1.33) ladders monotone. Corroboration unchanged **green 24 · yellow 1**; cost-pts 142→166.
- Table 8.1 p252 (@xhigh/max scores) and other bars read but not added (score-only, marginal gain).

## ✅ Opus 4.7 System Card — INTEGRATED (2026-07-06, source=`anthropic-syscard`, ref `anthropic-opus47-syscard-pNNN`)

232 pages. Compares Opus 4.7 vs Opus 4.6 (legacy) + GPT/Gemini — **Sonnet 4.6 absent** from the figures (except
DeepSearchQA). Only Opus 4.7 (+ Sonnet 4.6 on one figure) is in-grid. **N.B. this card is also `anthropic-syscard`
→ it CANNOT turn `opus-4.7@medium` green** (same source); it tightens σ. 2 groups added:
- **`scoarc`** (fig 8.11.A p213, ARC-AGI-2, $ cost direct) — Opus 4.7 low→max 61.9/66.0/68.0/75.8 (no xhigh).
- **`scodeepqa`** (fig 8.8.3.B p200, DeepSearchQA TTC, total tokens→$ 5:1) — Opus 4.7 80.6/86.0/88.6/88.1/89.9 +
  **Sonnet 4.6** 82.9/87.6/89.7/90.7 (the card's only real in-grid pair).
- **SKIPPED**: HLE p197 (fig 8.8.1.B) = Opus 4.7 ONLY, values 43.0/48.4/53.2/55.4/54.7 = EXACT duplicate of `schleeff`.
- **Result**: Opus 4.7 ladders monotone, σ tightened; corroboration unchanged **green 24 · yellow 1**; cost-pts 166→170.

## ✅ Sonnet 4.6 & Haiku 4.5 System Cards — PROCESSED, NOTHING TO ADD (2026-07-06)

Both cards **predate** the test-time-compute (effort×cost) figure era and only compare against **legacy**
out-of-grid models → no in-grid couple-atomic edge is possible. Verified:
- **Sonnet 4.6** (2026-02, 134 p): Table 2.1.A compares Sonnet 4.6 vs Opus 4.6/4.5, Sonnet 4.5, Gemini 3 Pro,
  GPT-5.2 — **no in-grid partner**, no cost column, no effort-scaling figure. `sonnet-4.6` is already green on all
  its efforts via osworld/schletools/cursorbench/scosweff/scodeepqa/futuresearch.
- **Haiku 4.5** (2025-10, 39 p): a safety card; compares vs Haiku 3.5, Sonnet 4.5, Opus 4.1 (legacy); Haiku has
  no effort dial (`solo` node); no cost. `haiku-4.5@solo` is already green.

## ✅ ALL current-model System Cards are processed
Sonnet 5 · Opus 4.8 · Fable 5/Mythos 5 · Opus 4.7 (integrated) + Sonnet 4.6 · Haiku 4.5 (nothing to add).
Final state: corroboration **green 24 · yellow 1 · orange 0 · red 0**; cost-pts 170. The only yellow
(`opus-4.7@medium`) will turn green only via a **NON-Anthropic** source measuring opus-4.7@medium with cost
(none exists to date — see HANDOFF). Legacy cards (Opus 4.6/4.5/4.1, Sonnet 4.5/4/3.7, Claude 3/2) = out of scope.
For each card: same recipe (one group per benchmark, source `anthropic-syscard`, explicit effort, digitized
costs `digitized-logx`, never a raw cross-benchmark value — ratios only).

## Project-state reminders (see also HANDOFF.md)
- 2 data-driven grids via `gen/build.py::ratio_grid(field)`: `cost_grid()` = ratios of `cost_usd`,
  `quality_grid()` = ratios of `score`. Injected as `__COSTGRID__`/`__QUALGRID__` in app.js.
- §1 landscape: X = relative cost, Y = relative quality (**symlog axis dilated near 1.0**), **oval = Huber ±1.5·MAD**
  (asymmetric, centred on the median) per point; hover to reveal. Haiku excluded from §1.
- §3 GROUPS generated from the CSV (`groups_data()`). §6 no-think regime. Dedicated Pareto.
- Corroboration (current): 0 red; `opus-4.7@medium` = the only yellow (2 sources: anthropic-syscard + cursorbench).
- Branch `task/improve`. Build: `python3 gen/build.py` → `cost-matrix.html`.
