# claude-models-value-analysis

**What does each recent Claude model actually cost, at each effort level — and is paying for more effort worth it?**

A normalized **cost × model × effort** matrix for the current Claude family, fused from independent public measurements, plus a self-contained interactive report with a live value-scoring model.

Open [`index.html`](index.html) in a browser — fully self-contained (no server, no external assets), light/dark aware, with zoomable charts and live tier tuning.

**Live page:** <https://claude-models.agensse.com/>. It is served from `main`: the server checks `main` every 5 minutes and copies a whitelist of files: `index.html`, `raw-data.csv`, `robots.txt`, `sitemap.xml`, `llms.txt`, `favicon.svg`, `favicon.png`, `og-image.png` and the IndexNow key file (`b3573dbc1da690e66e9ef05b081b7abe.txt`). Nothing is built on the server, so `index.html` must be committed built, and a new file served at the root must be added to that whitelist. Exploratory blocks (value score, window tuner, full method) are collapsed by default; click to expand.

**Publishing a fork:** in `gen/build.py`, set `SITE_URL` to the fork's address (every absolute URL, the sitemap, `robots.txt`, `llms.txt` and the domain shown in the share image derive from it) and `REPO_URL` to its repository; set `BING_SITE_VERIFICATION` and `INDEXNOW_KEY` to `""` (they prove this site's ownership to Bing and IndexNow; an empty value leaves out the tag and the key file) or to your own values. Delete `b3573dbc1da690e66e9ef05b081b7abe.txt`, run `python3 gen/build.py`, and redraw the share image with the new domain (`gen/og_image.py`, needs Pillow: `uv run --no-project --with pillow python gen/og_image.py`). The author credit and the GitHub links in `gen/body.html` point to this repository (attribution, CC BY 4.0). Then e.g. GitHub Pages: *Settings → Pages → Source: Deploy from a branch → `main` / root*.

Models covered: **Fable 5.1, Fable 5, Opus 5.5, Opus 5, Opus 4.8, Opus 4.7, Sonnet 5, Sonnet 4.6, Haiku 4.5**. Base of the relative scale: **Opus 5 @high = 1.00** since 23 Sep 2026 (it was Opus 4.8 @medium up to tag `v2026.09.23` — see *Re-anchoring on Opus 5 @high* in `PASSES.md`; the git tags reproduce each earlier scale). Opus 4.7 and Sonnet 4.6 stay in the data but are hidden on the page by default (an *Older models* switch brings them back).

---

## What the report shows

1. **Consolidated landscape** — one curve per model, one point per effort, on relative cost × relative quality (both anchored at Opus 5 @high = 1.0). Optional *tier bands* shade the four usage tiers on this chart and on the Pareto view. Robust uncertainty ovals. A Pareto view isolates the non-dominated couples, fits a **price envelope** (the cost the frontier charges for a given quality), and scores every frontier couple by its signed distance to that envelope (cheaper = good value). A **tier picker** (with live q\*/σ sliders) turns the frontier into a decision: the best-value (model, effort) for four task-complexity levels, plus a crowned overall pick.
2. **Normalized matrix** — relative cost per model × effort, sorted by relative quality, each cell a weighted median (diminishing returns per source) with a robust CI.
3. **Sources** — every source that measured ≥2 couples on the same task, with its verified configuration and the couples it links (names are clickable).
4. **Method** — how the numbers and the uncertainty band are built.

## How the numbers are built

You cannot compare raw dollars across sources (task sizes differ), so:

1. **Same-task ratios only.** Keep sources that measured ≥2 `(model, effort)` couples *on the same task*; their ratio cancels task-size variance.
2. **The `(model, effort)` couple is atomic** — no `model × effort` separability is assumed.
3. **Per-benchmark normalisation → weighted median, diminishing returns per source.** Within each benchmark, divide by the anchor (Opus 5 @high) or bridge through shared couples; weight each measurement ×0.5 if bridged, ×0.5→1 by how much of the model's effort ladder it sweeps, and ×⅓ for a run dated before the model's release (early access). A source (one publisher) with n measurements of a couple weighs **√n** in total, shared among them; each cell is the weighted median across all measurements.
4. **Robust CI** — a per-side Huber spread (deviations clipped to ±1.5·MAD): robust to an outlier benchmark yet still widened by it.

Value scores add a second layer, all computed client-side from the grids: a price-envelope fit (`log₁₀ cost = g(quality)`), a signed cost-distance score, its local prominence along the frontier, and the tier picks — all **uncertainty-aware** (each couple enters as its centre plus its four CI extremities).

## Files

| Path | What |
|---|---|
| `index.html` | The built interactive report (self-contained; open in a browser). |
| `gen/build.py` | **Generator** — reads the data, computes the grids, and assembles `index.html`. Run: `python3 gen/build.py`. |
| `gen/{style.css, body.html, app.js}` | Source modules the generator bundles (CSS, HTML body, client-side SVG rendering + interactions). |
| `gen/prerender.js` | Runs `app.js` at build time in Node (fake DOM) so the conclusions, tables and counts are in the served HTML for crawlers that do not run JavaScript. |
| `PASSES.md` | Research log: every source pass and method change, with what it admitted, corrected and moved. |
| `raw-data.csv` | The measured rows (source, model, effort, task, harness, cost, tokens, score, confound, ref) — the single source of truth. |
| `ratio-ids.md` | Stable IDs for the same-task ratio points (regenerated by the build). |
| `gen/content-date.json` | Fingerprint and date of the last change to the page's content (text, figures, data), written by the build: the "Updated" date, JSON-LD `dateModified` and the sitemap `lastmod` move only when the content changes, not on a code, style or icon change. Commit it with the rebuilt page. |
| `robots.txt`, `sitemap.xml`, `llms.txt`, `b3573dbc1da690e66e9ef05b081b7abe.txt` | Root files for search engines and AI assistants, written by the build from the same data as the page (the last one is the public IndexNow key). |
| `favicon.svg`, `favicon.png`, `og-image.png` | Icon (SVG for browsers, 96 × 96 PNG for Google Search, redrawn by `gen/favicon_png.py` when the SVG changes) and share image; `gen/og_image.py` redraws the latter (rerun on a title change). |
| `LICENSE`, `LICENSE-DATA` | MIT for the code, CC BY 4.0 for the data and the report text. |

## Versions

Each snapshot is tagged by its design date, so a past state of the analysis can be reproduced exactly:

| Tag | Date | Scope |
|---|---|---|
| `v2026.07.07` | 7 Jul 2026 | Fable 5, Opus 4.8/4.7, Sonnet 5/4.6, Haiku 4.5 — 268 measured rows |
| `v2026.08.01` | 1 Aug 2026 | adds **Opus 5** (system card of 24 Jul 2026, plus Artificial Analysis, Vals AI, swe-rebench and CursorBench) — 428 measured rows |
| `v2026.08.01b` | 1 Aug 2026 | third research pass — adds the **Vals Index** composite (6 of 7 models, same suite) and **OSWorld 2.0** (arXiv 2606.29537, real USD/task) — 439 measured rows |
| `v2026.08.17` | 17 Aug 2026 | fourth research pass — 6 parallel source sweeps (leaderboards, papers, repos, forums, blogs, vendors). Adds **ARC Prize** (`costPerTask` per model × effort, served in JSON side-files), **Terminal-Bench 2.1** (explicit `reasoning_effort` + 88–96 % cache), independent **Opus 5 effort sweeps** in real dollars (latitude, Zenn), **stet.sh** (5 rungs on two models, cache-aware), and 40+ other sources — 687 measured rows, 71 sources, 131 comparison groups |
| `v2026.09.08` | 8 Sep 2026 | adds **Fable 5.1** (released 1 Sep 2026) and a second research salvo. Six cost × effort sweeps digitized from the Fable 5.1 system card (FrontierCode 1.1 Extended, CursorBench 3.2.0, HLE with and without tools, DRACO, OSWorld 2.0), plus **Chartography** — a 4-model × 5-effort sweep read by separating the solid and dashed curves, anchored by joining the Opus 4.8 series from the Opus 5 card. Re-digitizes the two Sonnet 5 card sweeps the repo had only read approximately (**CursorBench**, **FrontierCode v1**), correcting 42 rows and Sonnet 4.6's high/max scores. **Haiku 4.5** gains a real interval: its `default` runs are its only configuration, so they are labelled `solo`, taking it from 1 benchmark to 6 and halving its measured cost. Twelve new third-party sources — Terminal-Bench 4.0, ObviousBench, bug-hunt-bench, vlm-exam, harnesseval, vibe-openscad, nurb-benchmarks, Kingy AI, Artificial Analysis, the current Vals Index, and three preprints (SWE Refactor Bench, QuoteBench, AI4AI-Bench) — 955 measured rows, 81 sources, 153 comparison groups |
| `v2026.09.08b` | 8 Sep 2026 | third scan — targeted at the sources the previous salvo could not read. Opens **Cognition's FrontierCode** JSON (which turns out to be the source behind the Fable 5.1 card's figure 8.4.A, so those rows are replaced with exact primaries), **CursorBench 3.2** in full (a complete 3 × 5 matrix that becomes the backbone of the Fable 5.1 effort curve), **Zapier AutomationBench**, **ARC Prize** per-effort costs, **AA Intelligence Index v4.3**, **Firecrawl**'s 57-run study, Simon Willison's five-rung Fable 5.1 sweep, and eight further sources. Resolves the ARC \$3.12/\$4.49 conflict (they are `xhigh` and `max`) and records that Claude Code bills cache-write at 2 × input — 1050 measured rows, 90 sources, 168 comparison groups |
| `v2026.09.21` | 21 Sep 2026 | sixth pass — five parallel source sweeps (leaderboards, preprints, public code, forums, vendors). The find is not a new source but an under-read one: **Cognition's FrontierCode JSON carries eight Claude models and the repo had ingested three**, so Opus 4.8, Sonnet 5, Opus 4.7 and Sonnet 4.6 join both v1.1 subsets and the v1 extended subset opens as its own group. The same JSON proves `scfrontiercode` — digitized off the Sonnet 5 card — *is* FrontierCode v1 main, and its Sonnet 4.6 costs were 8–11 % off; those rows are replaced with primaries. Adds **CursorBench 4.0** (a harder suite shipped 10 Sep) and the four missing **Terminal-Bench 4.0** effort rungs, both re-extracted from their own payloads. Mean cost band **2.016× → 1.811×**: Sonnet 4.6 `low` 3.36× → 1.19×, `medium` 1.83× → 1.08×, Opus 4.7 `xhigh` 1.53× → 1.16× — 1149 measured rows, 93 sources, 174 comparison groups |
| `v2026.09.23` | 23 Sep 2026 | adds **Opus 5.5** (released 22 Sep 2026): six primaries (Cognition FrontierCode JSON, CursorBench 4.0, Zapier AutomationBench, Artificial Analysis v4.3 plus its GDPval-AA / AutomationBench-AA ladders, Vals Index and Terminal-Bench 2.1, FrontierSWE), **Sonar**'s Java leaderboard (measured tokens, new source) and ten system-card sweeps (HLE ± tools, ArXivMath ± tools, DRACO, WANDR, OSWorld 2.0, BenchCAD, Chartography). Zapier and AA were under-read: Opus 4.8, Opus 4.7, Sonnet 5, Sonnet 4.6 and Haiku 4.5 ladders added. **Method change**: each benchmark's weight for a model scales with the share of that model's effort ladder it sweeps (×0.5 one rung → ×1 full ladder). Opus 5.5 holds the whole Pareto frontier — 1390 measured rows, 94 sources, 183 comparison groups |
| `v2026.09.23b` | 23 Sep 2026 | **re-anchored on Opus 5 @high** (measured directly by 60 of 114 benchmarks against 28 for Opus 4.8 @medium; the frontier now reads 0.87–1.13× in quality — not a pure rescale, see *Re-anchoring on Opus 5 @high* in `PASSES.md`). Page: *Older models* (Opus 4.7, Sonnet 4.6) and *Tier bands* display switches, both off by default. Second Opus 5.5 source pass (four agents, every candidate re-checked at its primary): bug-hunt-bench, vlm-exam, ObviousBench, LiveBench, seven Vals AI benchmarks, a Qiita reasoning run — Opus 5.5 on 117 rows, 34 groups, 13 sources, still the whole frontier — 1444 measured rows, 95 sources, 190 comparison groups |
| `v2026.09.23c` | 23 Sep 2026 | *Uncertainty ovals* become a display switch, off by default, on both charts (the axes still span the oval extents, so toggling does not rescale). Third Opus 5.5 source pass: eight more Vals AI benchmarks (Finance Agent v2, Legal Research, MedScribe, Tax Agent, Public Benefits, Vibe Code Bench 1-100, IOI, MysteryMechanism) — Opus 5.5 on 125 rows, 42 groups; its `max` rung is now dominated by its own `xhigh`. Early-access runs flagged, not removed, pending a rule — 1490 measured rows, 95 sources, 198 comparison groups |
| `v2026.09.23d` | 23 Sep 2026 | **Method**: a source's n measurements of a couple weigh √n together (one publisher = one source: Anthropic's blog chart and system cards merged); early-access runs count for a third, and runebench's Opus 5.5 runs return. **Tiers**: half-bell windows (only a shortfall below the target is penalised; a small saturating bonus above), tier bands follow and are also on the Pareto chart. Header counts sources, benchmarks and measurements; `xHigh` capitalisation. Fourth pass (ten agents, post-release publications only): nothing admitted. Fifth pass: Playcode MacBook SVG, Senko Rašić's vibecode games, Vals RSI Index, bug-hunt-bench Opus 5.5 `low`. Opus 5.5 holds the frontier at every rung, with Haiku 4.5 — 93 sources, 196 benchmarks, 1479 measurements |
| `v2026.09.27` | 27 Sep 2026 | seventh to eleventh source passes (four agent salvos plus a closed-network pass; details in `PASSES.md`). Adds ARC Prize's Opus 5.5 ladder, seven more Artificial Analysis index components, DeepSWE's primary JSON, the Anthropic docs and claude.dev effort sweeps, SWE-bench's official board, LMArena's agent board and some sixty other sources; every held github, arXiv and Vals row re-derived from its primary, with errors corrected (posttrain, skillsbench, slopcode, ceobench, token totals, effort labels). **Sonnet 5 re-priced at \$2/\$10** wherever a source had used \$3/\$15 (the increase never happened). Braintrust's T25/T50 turn out to be context sizes, not effort. Research log moved to `PASSES.md`. Opus 5.5 holds the frontier with Haiku 4.5; `low` is the best value — 160 sources, 432 benchmarks, 2894 measurements |

The notes behind each version — every source pass, what it admitted, rejected or corrected, and each method
change — are in [`PASSES.md`](PASSES.md).

## Rebuild

```bash
python3 gen/build.py     # → writes index.html
```

No dependencies beyond the Python 3 standard library and Node.js (any recent version, no npm package), which the build uses to pre-render the page's text. The client-side rendering is vanilla JS/SVG (no external libraries), which keeps the file trivially portable.

## Limitations

- **Task-type variance dominates** cross-model ratios; a single consolidated number hides a real spread, which is why every cell carries a CI.
- **Per-effort granularity is thin** — most cells rest on a few independent sources.
- **Public-data ceiling** — genuine independent measurements are scarce; confidence is capped at medium-high. An internal run on a representative workload remains the intended final validation.
- **Fable 5.1 no longer leans on the vendor**, three weeks after launch. It went from 39 rows to **125**, and Anthropic's own system card is now 30 of them — under a quarter, against 25 of 39 at launch. Twenty-one other sources carry it, the substantial ones being Cognition's FrontierCode (both subsets, both board versions), Cursor's CursorBench 3.2 *and* 4.0, Artificial Analysis, Terminal-Bench 4.0 and ARC Prize. Six of the digitized card sweeps were **cross-checked against numbers printed in the card's own text or on the launch page** (FrontierCode 63.6 % at medium, CursorBench 73.4/70.5/70.0, HLE 65.0/63.8/63.6 and 60.9/57.8/56.6, OSWorld 77.9/72.9/75.4) and matched to within 0.05 points, which is the calibration check the method calls for. What has *not* improved is the independent-community side: the write-ups measuring cost and quality on one task are still nearly all vendors and leaderboards.
- **Opus 5 still leans on the vendor**, though less than at first: 60 of its 125 rows come from Anthropic's own system cards (seven same-task effort sweeps, digitized from the published charts). Seven independent groups now cover it — Artificial Analysis (a full low→max sweep of the Intelligence Index, with cost *and* output tokens; plus AA-Briefcase and the per-task index), Vals AI (a five-tier sweep on Vibe Code Bench, plus the Vals Index composite), swe-rebench and CursorBench 3.2 — which pulled its cost interval at low effort from [0.38, 0.97] to [0.42, 0.51]. Expect further tightening as third-party runs accumulate.
- **The third-party field is thin for each model's first weeks.** Six days after Fable 5.1 shipped, only three independent groups had published cost *and* quality on the same task (Artificial Analysis, Vals AI, Cursor); the ARC Prize leaderboard, SWE-bench Pro and Terminal-Bench all had scores but no measured spend, and the launch write-ups reproduce Anthropic's or AA's figures rather than running their own. Expect Fable 5.1's intervals to tighten as third-party runs accumulate, as Opus 5's did.
- **The third-party field looked close to exhausted** for the Claude 5 generation before this release. A systematic sweep on 1 Aug 2026 across preprints (arXiv/HAL/OpenReview), public leaderboards, community write-ups and agent-tooling vendors found only two admissible additions. Most candidates fail the same-task rule in one of three ways: scores published without cost (Epoch AI, Scale SEAL, ARC Prize, Harvey, most arXiv evaluations), cost quoted as list price rather than measured spend (llm-stats FrontierCode), or cost and quality reported on *different* tasks (Composio). Two further sources were deliberately excluded rather than admitted: ARC Prize, because the widely-quoted $0.70/$2.06 per task appears only in secondary summaries and not on the results page itself; and a Zenn effort sweep of Opus 5, because its quality saturated at 3/3 on a toy task and its cost covered output tokens only — admitting it would have flattened Opus 5's quality curve with a measurement taken in a complexity regime the model does not segment.

Data are public third-party benchmarks; this repo is an independent analysis, not affiliated with or endorsed by Anthropic. Prices reflect published rates at time of writing.

## Licence and citation

The code (`gen/`) is under the [MIT licence](LICENSE); the data (`raw-data.csv`), the derived grids and the report text are under [CC BY 4.0](LICENSE-DATA): reuse them freely, with attribution. The third-party measurements keep their publishers' own terms; each row cites its source.

Cite as: Alexandre Gensse, *Claude cost vs quality: Fable, Opus, Sonnet, Haiku compared*, <https://claude-models.agensse.com/>, with the version tag or the date shown on the page.
