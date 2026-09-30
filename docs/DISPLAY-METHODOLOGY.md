# Display methodology

How the page turns the fitted values of every (model, effort) couple into what the reader sees: the relative values,
the charts, the frontier, the price curve, the value index, the four tiers and the crown. The fit itself — how each
couple's cost and quality are estimated from the measurements — is in `METHODOLOGY.md`. Everything here runs in the
browser from `site/app.js`, on the grids that `site/grids.py` reads from `model/fit-cache.json`, and is pre-rendered at
build time so that readers without JavaScript see the same conclusions. This file describes the page as published;
choices under discussion are listed at the end and are not applied.

## 1. From the fit to the grids

- **Values.** The fit gives each couple a centre and a quasi-standard error on the log scale, reference-free
  (`METHODOLOGY.md` § Output). `site/grids.py` turns them into a cost grid and a quality grid:
  value = exp(centre − centre_reference), interval = value × exp(∓ quasi-standard error), i.e. the couple's own
  16–84 % interval.
- **Reference couple.** Opus 5 @high (`site/config.py`, `GRID_ANCHOR`). It divides every value, so it reads 1.00 on
  both axes and 100 on the value index. It is a display choice: the fit does not depend on it.
- **Publication.** A couple is on the page only if at least two publishers measured it; the others stay in the fit,
  in the fit cache and in the data file.
- **Monte Carlo stability.** Each value's Monte Carlo error, the reference's included, is carried with it; the build
  reports any value whose error exceeds half of its last displayed digit.
- **Build refusals.** The page is not built from a fit that no longer matches its inputs (fingerprint) or that missed
  the convergence criteria. Effort-ladder inversions (a higher rung costing or scoring less) are printed, not corrected.

## 2. Formatting

- Relative cost and quality: two decimals (`1.08×`, `0.75×`) in cards, tables and the matrix.
- Chart tick labels: two decimals below 1, one below 10, none above (`0.25×`, `2.5×`, `25×`), on round values 1, 2, 5
  per decade.
- Value index: an integer.

## 3. Older models

Opus 4.7 and Sonnet 4.6 are hidden by default; a *Older models* switch shows them. Hidden models leave the charts,
the matrix, the frontier, the price curve, the tiers and the crown: every recommendation is computed over the models
on screen.

## 4. The matrix

One row per model, one column per effort; each cell is the relative cost with its interval, coloured on a heat scale.
Rows are ordered by the model's relative quality at its highest published effort. A model without effort levels
(Haiku 4.5, *solo*) fills a single merged cell; an unpublished couple is shown as a dash.

## 5. The charts

- **Cost axis**: log₁₀ of the relative cost.
- **Quality axis**: a symmetric log around parity (the reference's quality),

      T(Q) = sign(Q − 1) · ln(1 + |Q − 1| / 0.045)

  It dilates the band near the reference and compresses both tails. Every distance in quality used below (price
  curve, tier targets and windows, crown) is measured in T.
- One line per model through its effort ladder. Optional **ovals** draw each couple's 16–84 % interval, with separate
  radii on each side (the interval is asymmetric on the relative scale); the axes always span the ovals, so turning
  them on does not rescale the chart.
- Optional **tier bands** shade the quality range each tier owns: band edges midway, in T, between adjacent targets;
  the outer bands extend half a gap beyond the first and last targets.

## 6. Pareto frontier

A couple is **dominated** when another couple costs no more and scores no less, and is strictly better on one of the
two (centres compared). The frontier is the set of non-dominated couples, ordered by cost.

## 7. Price curve

What a given quality typically costs, fitted on **every** shown couple, dominated ones included:

    log₁₀(cost) = g(u) = a + b·u + c·(e^{k·u} − 1)/k ,   u = T(Q) − T_min ,   b ≥ 0, c ≥ 0

- **Monotone by construction**: g′(u) = b + c·e^{k·u} ≥ 0, so the price of quality never falls as quality rises,
  extrapolation included; the exponential term lets the slope grow near the ceiling. k is chosen on the grid {0.1,
  0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3} by weighted least squares; a, b, c by constrained weighted least
  squares (the active set of b ≥ 0, c ≥ 0).
- **Weight by distance to the frontier**: d = log₁₀(cost) − log₁₀(cost of the cheapest couple offering at least this
  quality), 0 on the frontier; each couple weighs 1 − d/d_max (a frontier couple fully, the farthest couple not at all).
- **Centres only**: each couple enters at its centre.

## 8. Value index

The distance of a couple to the price curve, in log-cost:

    G = g(T(Q))        what the curve charges for this quality
    C = log₁₀(cost)    what the couple costs
    r = G − C          positive = cheaper than the going rate
    value index = 100 · 10^(r − r_reference)

A ratio: 100 is the reference couple, 350 means 3.5 times its value for money, 45 means 0.45 times. The reference's
residual is read from all couples, so the scale holds even when the reference is off the frontier.

## 9. Tiers: best value by task complexity

Four tiers — *Grunt work*, *Everyday tasks*, *Advanced reasoning*, *Cutting-Edge thinking* — each with a target
quality q*, a window and a cost sensitivity γ.

- **Targets**: q*₁…q*₄ spread evenly in T from the frontier's weakest couple to its strongest, so they move with the
  models.
- **Window width**: σ = gap / (2·√ln 2), gap the spacing of the targets in T: adjacent windows cross at half weight
  midway between their targets.
- **Window**: with δ = (T(Q) − T(q*)) / σ, a couple weighs e^(−δ²) below its target and 1 + 0.20·(1 − e^(−2δ)) at or
  above it: a shortfall is penalised, clearing the bar earns a bonus that saturates at +20 %.
- **Score**: weight × 10^(G − γ·C), with γ = 1.20, 1.05, 0.95, 0.80 from the lowest tier to the highest (cost weighs
  more than proportionally on routine work, less on research-grade work).
- **Pick**: the frontier couple with the highest score. A card shows the neutral value index (γ = 1).
- **Sliders**: each tier's q* and σ can be moved. q* travels over the frontier's quality range padded by half a gap in
  T on each side; σ from a quarter to three times its default.

## 10. The crown

The best overall pick is the frontier couple that stands out most from its neighbours. Along the frontier ordered by
cost, its **prominence** is 2·r_n − r_(n−1) − r_(n+1) (the endpoints get 0): a second difference of the distance to
the price curve, a knee in value. The crown is the most prominent couple, weighted by a Gaussian of width 10 in T
around parity (nearly flat); its card shows its value index.

## 11. Text read without the charts

- The header's sentence names the crown with its relative quality and cost.
- `llms.txt` states the crown, the pick of every tier and the highest measured quality.
- The tier cards, the crown, the Pareto blocks, the tables and the source counts are pre-rendered at build time
  (`site/prerender.js`, Node, no dependency); the browser redraws everything on load.

## 12. Sources table and counts

Every group is listed with its verified configuration (harness, effort), its kind (effort sweep, cross-model,
cross-generation) and the couples it links. The header counts sources, benchmarks and measurements. The page's date
moves only when its content (text, figures, data) changes.

## 13. Constants

| Where | Value | Why |
|---|---|---|
| §1 reference couple | Opus 5 @high | a display divisor |
| §1 publication | ≥ 2 publishers | one publisher's figures cannot be cross-checked |
| §5 quality axis | symmetric log around parity, constant 0.045 | display |
| §7 price curve | k on the grid {0.1 … 3}; weight 1 − d/d_max | see §7 |
| §9 tiers | 4 tiers; γ = 1.20, 1.05, 0.95, 0.80; bonus +20 %, rate 2 per σ | see §9 |
| §10 crown | Gaussian of width 10 in T around parity | nearly flat |

## 14. Under discussion (not applied)

Reviewed on 30 September 2026. Where the choices above carry an assumption of their own:

- **The quality scale T leaks into decisions.** It is a display choice (a constant, centred on the reference), yet
  the price curve, the tier targets and windows and the crown measure quality in T: changing the constant or the
  reference changes the picks. Proposed: decisions on log Q (the natural scale of a ratio); the display scale stays a
  free, display-only choice — log above today's level, compressed below it (older models grouped, the top left
  uncompressed).
- **No reference couple on the page.** Proposed: quality as a share of the best couple, cost as a multiple of the
  cheapest frontier couple; the value index as a distance to the going rate rather than a ratio to one couple.
- **Tier targets.** Chosen: bounds (1 − e)·min + e·max and (1 − e)·max + e·min of the frontier's quality, e = 0.05.
- **Price curve.** It should describe the trend of the models, not the frontier: the weights 1 − d/d_max pull it
  toward the frontier and depend on the farthest couple. Proposed: fitted on every couple shown, weighted by its
  interval, in log Q, same monotone form. On the current data it is almost straight in log–log: 1 % more quality
  costs about 4.3 % more.
- **Bonus.** The +20 % saturates within one σ, so it acts as a step and outweighs the value differences between
  neighbouring couples. Proposed: a smooth reward, score = malus × Q^λ ⁄ C, λ the slope of the trend at the tier's
  target (d ln C ⁄ d ln Q): a couple wins when it brings more quality than the trend charges for its extra cost. No
  constant to set. On the current data: Sonnet 5.5 high for the first three tiers (it sits furthest below the trend,
  3.5 times cheaper), Opus 5.5 high for the last.
- **Frontier.** Centres only: a couple beaten by a hair leaves the frontier although the intervals overlap. A
  frontier at 84 % probability would put Haiku 4.5 and Opus 5.5 low back on it.
- **Crown.** The knee depends on the frontier's neighbours (adding a rung can move it) and never picks an endpoint;
  the alternative is the best value on the frontier (today Sonnet 5.5 high rather than Opus 5.5 xHigh).

A mock-up of the proposal compares the current and proposed charts and picks.
