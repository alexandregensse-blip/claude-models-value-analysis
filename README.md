# claude-models-value-analysis

**What does each recent Claude model actually cost, at each effort level — and is paying for more effort worth it?**
A normalized **cost × model × effort** matrix for the current Claude family, fused from **~55 independent public measurements**, plus a self-contained interactive report.

Interactive report: open [`cost-matrix.html`](cost-matrix.html) in a browser (fully self-contained — no server, no external assets, light/dark aware, zoom/pan on the charts).

Models covered: **Fable 5, Opus 4.8, Opus 4.7, Sonnet 5, Sonnet 4.6, Haiku 4.5**. Base of the relative scale: **Opus 4.8 @medium = 1.00**.

---

## TL;DR findings

- **Cross-model cost ratios are NOT benchmark-stable** — the same model pair ranges wildly by task type (e.g. Opus 4.8 / Sonnet 4.6 ≈ 0.9× on OSWorld low–high but ≈ 2.5× at max computer-use, ≈ 1.7× on agentic AA). They are only stable *within the same source at matched effort*, which is exactly what the normalization exploits.
- **Effort → quality is mostly a plateau** on coding/agentic (gains ≤ ~1 pt from low→max, sometimes an inverted-U where high *hurts*), but **effort pays on reasoning-math** (+9–29 %). Corroborated by 8 independent effort-sweep sources.
- **Effort → cost is not monotonic** on agentic-with-retries (higher effort is sometimes *cheaper* — HAL inversions).
- **The "default effort" is not one thing.** Claude Code / API defaults are **per-model**: high for Opus 4.8 / Sonnet 5 / Sonnet 4.6 / Fable 5, **xhigh** for Opus 4.7, high→**medium** for Opus 4.6 since Claude Code v2.1.68, and Haiku 4.5 has **no effort parameter** at all.
- **Many scientific benchmarks run Claude with NO extended thinking.** Verified from paper text *and* repository source code: several 2026 papers set only `temperature` and never enable `thinking`/`effort`. On the mid-2026 raw API that means adaptive thinking is **off** for Opus 4.x / Sonnet 4.6 (Fable 5 always thinks). Those runs are a distinct **"no-think" regime**, not an unknown effort — and are set aside from the effort-assignment view.

---

## How the numbers are built (methodology)

The hard problem is that you cannot compare raw dollars across sources (task sizes differ). The pipeline:

1. **Same-task ratios only.** Keep only sources that measured ≥2 models/efforts *on the same task*; their **ratio** cancels task-size variance.
2. **Couple-atomic linking.** Each `(model, effort)` is an indivisible node. No `model × effort` separability is assumed (passing Haiku to max ≠ passing Opus to max). Nodes are placed by multiplying measured ratios along the path to the base `Opus 4.8 @medium`.
3. **Median over concurrent paths** (robust to cache/harness confounds); confidence = dispersion of the paths.
4. **Consolidated square per (pair, effort)** = the **median of the measured points at that effort** — data-driven, varies by effort (not the separable matrix).
5. **Price-derived cross-axis.** A point that exists only in tokens (or only in cost) is reproduced on the other axis via `cost_ratio = token_ratio × (price_out_A / price_out_B)`. This turns Artificial-Analysis token ratios (at max) into colored cost anchors.

### The report's sections
1. **Consolidated landscape** — intelligence vs relative cost, one curve per model with per-effort points and 2D confidence ribbons.
2. **Normalized matrix** — relative cost per model × effort, sorted by intelligence.
3. **Linking graph** — every `(model, effort)` node and the sources that connect them; colored ring = corroboration count (green ≥3 / yellow 2 / orange 1 / red 0).
4. **Assign-the-defaults ratio charts** — per model pair, stacked cost + token axes, colored by effort, grey = unresolved default; consolidated-median squares as reference; **semantic zoom** (Shift+wheel / drag / dbl-click).
5. **Criteria** with worked numeric examples · 6. **Confidence & fusion method.**

---

## The effort / thinking verification (the deep dive)

We did not trust "the source didn't say" — we verified each source's **actual run configuration**, with proof:

- **Anthropic docs** (Adaptive thinking + Effort): the `effort` default is `high` *only when adaptive thinking is active*; adaptive is always-on for Fable 5, on-by-default for Sonnet 5, **opt-in (off otherwise)** for Opus 4.6/4.7/4.8 & Sonnet 4.6, and absent for Haiku 4.5.
- **Per-source config** re-verified by reading each paper/site/repo (see `docs/source-config-consolidation.md`): corrected several mislabels (CEO-Bench = max, SlopCode/OfficeQA = high, EMB-Opus = max, SkillsBench harness = Claude Code not OpenHands, drona23 = Claude Code CLI not raw API, AutomationBench = max).
- **Repo-level proof** (`docs/repo-config-proof.md`): e.g. WorkBench `src/evals/inference.py` passes `temperature=0` and **no** `thinking`/`effort`; WildClaw `eval/run_batch.py` has `thinking: str | None = None` (off by default); OpenRouter's reasoning is off unless explicitly requested.
- **Claude Code default effort** confirmed per-model (high for Sonnet 4.6/Opus 4.8; xhigh for Opus 4.7; medium for Opus 4.6 since v2.1.68).

Result: sources proven to run **without extended thinking** (WorkBench, WildClaw, TOBench, code-review, ianlpaterson, STAGE-Claw, TrueFoundry) are tagged `nothink` and set aside; `codesota` is a list-price blend (`priceblend`), also set aside. Every remaining default was resolved.

---

## Files

| Path | What |
|---|---|
| `cost-matrix.html` | The built interactive report (self-contained; open in a browser). |
| `gen/build.py` | **Generator** — reads the data, computes ratios/IDs/consolidated medians/price-derived points, and assembles `cost-matrix.html`. Run: `python3 gen/build.py`. |
| `gen/{style.css, body.html, app.js}` | Source modules the generator bundles (CSS, HTML body, client-side SVG rendering + interactions). |
| `raw-data.csv` | ~98 measured rows (source, model, effort, task, harness, cost, tokens, score, confound, ref). The single hand-curated source of truth. |
| `normalized.csv` | Relative-cost matrix (base Opus 4.8 @medium = 1.00) + factor tables + confidence. |
| `ratio-data.json`, `ratio-ids.md` | Derived same-task ratio points + their stable IDs (regenerated by the build). |
| `docs/source-config-consolidation.md` | Verified per-source run config (harness · thinking · effort · temperature). |
| `docs/repo-config-proof.md` | Code/paper quotes proving the effort/thinking config of the "NS" sources. |
| `docs/effort-cost-matrix-findings.md` | The master research registry (all sources, digitized charts, effort multipliers, distributions, verdicts). |
| `research-logs/agent-*.md` | Raw findings from the background research agents (GitHub, blogs, leaderboards, forums, academic, gateways, recent-focus waves). |
| `research-logs/agent-config-*.md` | Raw findings from the config-verification agents. |

## Rebuild

```bash
python3 gen/build.py     # → writes cost-matrix.html
```
No dependencies beyond Python 3 standard library. The client-side chart rendering is vanilla JS/SVG (no external libraries — an Artifact CSP constraint that also makes the file trivially portable).

---

## Known limitations (read before trusting a cell)

- **`normalized.csv` is currently separable** — the cross-model factor is applied as a constant across efforts (Sonnet 4.6 = 0.60 × Opus 4.8 at every effort), so its per-effort ratios don't vary. The report's **consolidated squares avoid this** by using per-effort medians of the measured data; the matrix itself is a next-pass fix.
- **Task-type variance dominates** cross-model ratios; a single "consolidated" number hides a real spread. The linking graph and confidence bands are there to keep that honest.
- **Per-effort granularity is thin.** Most cells rest on 1–2 independent sources; only `@default`-condition anchors and the top of well-measured models reach ≥3 (see the corroboration rings).
- **Public data ceiling.** Genuine independent measurements are rare (~55); most web content re-cites Artificial Analysis / Anthropic. Confidence is capped at "medium-high"; an internal run on a real workload remains the intended final validation.
- **No-think regime** is distinct from the low→max effort ladder and is deliberately excluded from the effort-assignment view rather than forced onto it.

## Provenance

Built through an iterative human-in-the-loop analysis session: deep multi-wave source collection (background agents), a from-scratch normalization design, adversarial config verification (paper text + repository source code), and a modular artifact generator. The `research-logs/` and `docs/` folders preserve the raw evidence trail.

Data are public third-party benchmarks; this repo is an independent analysis, not affiliated with or endorsed by Anthropic. Prices reflect published rates at time of writing.
