# Display methodology

How the page turns the fitted values of every (model, effort) couple into what the reader sees: the charts, the
frontier, the price trend, the value of each couple, the four tiers and the crown. The fit itself — how each couple's
cost and quality are estimated from the measurements — is in `METHODOLOGY.md`. Everything here runs in the browser from
`site/app.js`, on the values that `site/grids.py` reads from `model/fit-cache.json`, and is pre-rendered at build time
so that readers without JavaScript see the same conclusions.

## 1. From the fit to the page

- **Values.** For each couple the fit gives, on each axis, a centre (posterior median) and a quasi-standard error
  (the half-width of the couple's own 16–84 % interval, `METHODOLOGY.md` § Output): the log of the cost on a task of
  typical size, and the latent quality θ, on the model's logit scale. Both are reference-free: the fit's latent values
  sum to zero.
- **No reference couple.** No couple divides the others, in the fit or on the page. Cost is shown as a multiple of the
  cheapest couple on screen; quality is shown as the **expected panel score** of its θ (§ 2).
- **Every decision is taken on the latent scale**: log cost and θ. The frontier, the price trend, the tier targets and
  windows, the picks and the crown never depend on how the axes are drawn.
- **Publication.** A couple is on the page only if at least two publishers measured it; the others stay in the fit,
  in the fit cache and in the data file.
- **Monte Carlo stability.** Each value's Monte Carlo error is carried with it; the build reports any value whose
  error exceeds half of its last displayed digit (§ 3; the cheapest couple's error included in every cost multiple).
- **Build refusals.** The page is not built from a fit that no longer matches its inputs (fingerprint) or that missed
  the convergence criteria. Effort-ladder inversions (a higher rung costing or scoring less) are printed, not corrected.

## 2. The expected panel score

θ has no unit of its own. The fit also publishes a **panel curve**: for a couple of latent quality θ, with no effect of
its own, the score it is expected to reach averaged over the benchmark panel (each benchmark's share of its bound, with
the panel weights of `METHODOLOGY.md`), posterior median, on 41 points spanning every couple's θ. The page reads it
linearly in logit between its points. It **labels** θ — axis ticks, cards, tables — and takes no part in a decision.
It is monotone, so it never changes an order.

A couple's own panel read-out in the fit (`level`, which includes its publisher and task-type effects) can differ
slightly from the curve at its θ; the page uses the curve, so that a couple's label always matches its place on the axis.

## 3. Formatting

- Cost: a multiple of the cheapest couple, two significant digits — one decimal below 10, none above (`1.8×`, `18×`) —
  in cards, tables, the matrix and the chart ticks (round values 1, 2, 5 per decade). Finer digits would be noise: the
  Monte Carlo error of a multiple is about 0.3 % (the cheapest couple's included) and its interval about ±10 %.
- Quality: an expected score in %, one decimal (`65.8 %`); chart gridlines every 5 points (every 10 when they fall
  closer than 16 px apart on screen; in the compressed low end, a line closer than 16 px to the previous one is
  skipped).
- Value index: an integer, 100 = the price trend (`500`, `85`).

## 4. Older models

Opus 4.7 and Sonnet 4.6 are hidden by default; an *Older models* switch shows them. Hidden models leave the charts,
the matrix, the frontier, the price trend, the tiers and the crown: every recommendation is computed over the models on
screen, and the cheapest couple is the cheapest one on screen.

## 5. The matrix

One row per model, one column per effort; each cell is the cost multiple with its interval, coloured on a heat scale
(log cost, from the cheapest to the dearest couple). Rows are ordered by the expected score of the model at its highest
published effort. A model without effort levels (Haiku 4.5, *solo*) fills a single merged cell; an unpublished couple
is shown as a dash.

A second matrix gives every couple's **value index** (§ 9) with its 16–84 % range (r ± √(h_x² + λ²·h_θ²)), same rows.
Its colours follow the data: green above 100, red below, each side scaled to the most extreme index shown (log scale).

## 6. The charts

- **Cost axis**: log₁₀ of the cost multiple.
- **Quality axis**: θ, linear above the weakest tier target θ*₁ (§ 10). Below it — couples short of today's level —
  θ is compressed three times: y = θ*₁ + (θ − θ*₁) ⁄ 3. Older and weaker models sit together at the bottom instead of
  stretching the axis; the top is not compressed. Gridlines at round expected scores (§ 3).
- One line per model through its effort ladder. Optional **ovals** draw each couple's 16–84 % interval, with separate
  radii on each side; the axes always span the ovals, so turning them on does not rescale the chart.
- Optional **tier bands** shade the quality range each tier owns: from its target up to the next one; the outer bands
  extend half a gap beyond the first and last targets.

## 7. Pareto frontier

A couple is **dominated** when another costs no more and scores no less, and is strictly better on one of the two
(centres compared). The frontier is the set of non-dominated couples, ordered by cost; it is drawn as a line, and its
couples are the **candidates** of every pick (§ 10, § 11). A couple beaten on both axes by another is not a candidate,
however close: a "within reach" rule (not beaten with probability 0.84) was used on 30 Sep 2026 and withdrawn the same
day, since it let a couple strictly beaten by another be picked.

## 8. Price trend

What a given quality typically costs, fitted on **every** shown couple, dominated ones included — the trend of the
models, not their frontier:

    ln cost = a + λ·θ

- **Weights**: each couple by its uncertainty across the line, 1 ⁄ (h_x² + λ²·h_θ²) — both axes are uncertain
  (effective variance) —, iterated to the fixed point.
- **λ** is the market's price of quality: one more unit of θ costs e^λ times more. It is kept ≥ 0 (quality never gets
  cheaper as it rises).
- **Straight** on the latent scale: every step of quality costs the same ratio more, wherever it sits. No shape
  constant to choose.
- The chart states its weighted R².

## 9. Value

The distance of a couple to the trend, on the cost axis:

    r = (a + λ·θ) − ln cost          positive = cheaper than the going rate

shown as the **value index** 100·e^r: 100 is the trend, 500 five times cheaper than the trend at its quality, 50
twice as dear (the header's sentence says it in words: "5.0× cheaper than the price trend"). Since the trend is a straight
line, the same gap read on the quality axis is r ⁄ λ: the couple's θ above what the trend gives for its cost, shown in
points of expected score. No reference couple: 100 is the trend itself.

## 10. Tiers: best value by task complexity

Four tiers — *Grunt work*, *Everyday tasks*, *Advanced reasoning*, *Cutting-Edge thinking* — each with a target θ*
and a window width σ.

- **Targets**: θ*₁ … θ*₄ spread evenly from (1 − e)·min + e·max to (1 − e)·max + e·min of the frontier's θ (frontier
  by centres), e = 0.05. The bottom tier follows the weakest frontier couple as it rises, the top one the best; each end
  is drawn 5 % of the span inward so that no target sits on a single couple. The targets depend on the couples only
  through these two bounds.
- **Window width**: σ = gap ⁄ (2·√ln 2), gap the spacing of the targets: adjacent windows cross at half weight midway
  between their targets.
- **Score**: among the frontier couples (§ 7),

      score = window(θ) × e^(λ·θ) ⁄ cost,   window = e^(−δ²) below the target, 1 at or above,   δ = (θ − θ*) ⁄ σ

  e^(λθ) ⁄ cost is the couple's value against the trend (e^(r + a)): above its target, a couple wins by bringing more
  quality than the trend charges for its extra cost — a smooth reward, with no bonus constant. Below the target the
  window penalises the shortfall.
- **Cost as people perceive it**: cost enters as a ratio (log cost). Perceived price follows the ratio of prices, not
  their difference (Weber–Fechner; Monroe 1973, *Journal of Marketing Research* 10(1)): twice as dear weighs the same
  at every price. A power of the cost such as C^0.88 is not used: that exponent is the curvature of the value of gains
  and losses in prospect theory (Tversky & Kahneman 1992), measured on lotteries, not on prices.
- **Pick**: the candidate with the highest score. Two tiers may pick the same couple. A card shows the pick's value
  against the trend as its value index (§ 9).
- **Sliders**: each tier's θ* and σ can be moved. θ* travels over the targets' range padded by half a gap on each
  side; σ from a quarter to three times its default.

## 11. The crown

The best overall pick is the frontier couple that sits **furthest below the price trend** (largest r, § 9): the
most quality for its cost against the going rate. Its card shows its value index, and its note both readings of the
same gap — e^r times cheaper than the trend at its quality, and r ⁄ λ above the trend at its cost, in points of
expected score. It does not depend
on its neighbours on the frontier.

## 12. Text read without the charts

- The header's sentence names the crown with its value against the trend and its expected score.
- `llms.txt` states the crown, the pick of every tier and the highest measured quality.
- The tier cards, the crown, the Pareto blocks, the tables and the source counts are pre-rendered at build time
  (`site/prerender.js`, Node, no dependency); the browser redraws everything on load.

## 13. Sources table and counts

Every group is listed with its verified configuration (harness, effort), its kind (effort sweep, cross-model,
cross-generation) and the couples it links. The header counts sources, benchmarks and measurements. The page's date
moves only when its content (text, figures, data) changes.

## 14. Constants

| Where | Value | Why |
|---|---|---|
| § 1 publication | ≥ 2 publishers | one publisher's figures cannot be cross-checked |
| § 2 panel curve | 41 points, linear in logit between them | labels only |
| § 6 low-end compression | 3×, below the weakest tier target | display only: older models grouped, the top left as it is |
| § 8 price trend | straight line in (θ, ln cost), effective-variance weights | the trend of every couple; no shape constant |
| § 10 targets | e = 0.05 | ends drawn inward by 5 % of the frontier's span |
| § 10 windows | σ = gap ⁄ (2·√ln 2) | adjacent windows cross at half weight midway |

## 15. The head-to-head page

`claude-models-head-to-head.html`, written by `site/duels.py` from the same grids: every pair of the latest model of
each family (Fable 5.1, Opus 5.5, Sonnet 5.5, Haiku 4.5), and each of them against its predecessor. Costs are
multiples of the cheapest couple shown on the main page (older models of § 4 left out), scores the expected panel
score of § 2.

- **At each shared effort level**, axis by axis (not the two-axis probability of § 7): one couple is cheaper, or
  higher, when the normal law on the difference of the two centres, with the two quasi-standard errors, puts it
  ahead with probability ≥ 0.84; otherwise the two are level within the uncertainty.
- **Match**: for the best-scoring couple of one model, the cheapest couple of the other that it does not out-score
  at 0.84 (it reaches the same quality within the uncertainty, or more). None: the other model's best is given.
  A match near the threshold can flip with a refit.
- Ratios read as on the main page: "3.5× cheaper", "1.6× dearer". A model flagged size-sensitive (§ 5) keeps its
  note.
