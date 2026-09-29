# Methodology

How the report turns public measurements into a relative cost, a relative quality and a recommendation for every
(model, effort) pair. Every number on the page is computed from the published data file by the procedure below;
nothing is entered by hand. The procedure does not depend on which models, versions or effort levels are covered;
the examples in parentheses only illustrate it.

## 1. Vocabulary

- **Couple** — a model at one effort level (*Opus 5 @high*). A model's couples, from its lowest to its highest
  effort, form its **effort ladder**. A model without an effort setting is a single couple labelled *solo*.
- **Reference couple** — the couple the page divides by to display relative values (1.0 on both axes). It is a
  display choice only: the fit does not depend on it, and changing it divides every value by a constant.
- **Row** — one published measurement of one couple: a cost, a score, or both.
- **Group** — the rows one source measured on the same task under the same configuration (a leaderboard column, a
  system-card chart, a paper's table). Only within a group are two couples directly comparable.
- **Publisher** — whoever produced the numbers. Outlets of one organisation that publish its own measurements (its
  system cards, blog charts and documentation) are one publisher; the list is kept in a table.
- **Benchmark family** — the groups that run the same benchmark: same task set, same version, same grading,
  whoever runs it and whatever the harness (Terminal-Bench 4.0 run by four sources is one family; CursorBench 3.2 and
  4.0 are two; the full and the hard subset of one benchmark are two). The mapping is kept in a table; it scopes the
  detection of republished numbers (§3) and makes a benchmark count once in the panel of §5.
- **Task type** — coding, agentic tool use, computer use, reasoning/maths, writing, or *mixed* for composite indices.

## 2. Collection

### What is recorded

One line per measurement: the group, the source, the model, the effort, the task type and complexity, the harness,
the cost unit (per task, per attempt, per run), the cost in dollars, the input and output tokens, the score and its
metric, the cache-read share, a free-text **confound** field, the reference (URL, page, file), and the **reading
precision** of the cost and of the score (§4).

### Admission

- **The same task, the same configuration.** A row belongs to a group only with the other couples its source
  measured on the same task, harness and settings. Raw dollars or scores are never compared across groups.
- **The effort is read, not assumed.** The effort level comes from the source's own configuration (a flag, a payload
  field, a documented default). A run whose effort cannot be established is recorded as *default*; a run with
  thinking disabled as *nothink*; a cost computed from list prices blended over a token mix as *priceblend*. These
  stay in the data file but outside the computation: they are not a rung of an effort ladder.
- **Primary sources only.** A number is taken from the publisher's own table, payload, chart or repository. A
  secondary quotation of a number already recorded is not a new measurement.
- **Measured spend over list price.** The cost is what the run actually spent, including cache reads and writes,
  when the source reports it; a cost estimated from token counts at list prices is flagged. A source that priced
  tokens at wrong rates is re-priced and the correction flagged. Tokens read on a chart and converted at one flat
  price are not a cost: a flat price ignores the mix of input and output tokens, which changes with the effort, and
  so bends the effort ladder; such a cost is left out and the score kept.
- **Charts are digitised and checked** against any number the same document prints in its text, and flagged; the
  resolution of every digitised chart is measured (§4).
- **Early access.** A run its source dates before the model's public release is flagged (§5: its noise is inflated
  by an estimated factor).
- **Uninformative scores.** A score stuck at the floor or the ceiling of its metric for one couple while the others
  are not (3 successes out of 657 tasks) says little and depends on how the bound is handled; such a score is left
  blank and the cost kept.
- **Flag, do not drop.** Doubts (cost basis undocumented, a fallback model served part of the run, an effort inferred
  from order, a digitised value) are written in the confound field. A source is excluded only when it breaks a rule
  above.

## 3. From rows to groups

- **One configuration per group.** A group is split when its rows differ by publisher, by harness (versions of one
  harness count as one), by scale (a score out of 25 and a score out of 36 are two scales) or, for costs, by cost
  unit. Each part is compared only with itself. Two labels a publisher uses for one quantity are one unit (vals.ai
  writes its single cost column "per test" or "per task"); the aliases are kept in a table.
- **Composites count once.** An index, an average or a total over several benchmarks repeats the measurements of
  its components. The components of each composite are listed from its publisher's documentation (for instance the
  ten benchmarks of the Artificial Analysis Intelligence Index v4.3, or the published formula of the Vals Index). For
  a couple measured on at least one component, the composite row is left out; a couple measured only on the
  composite keeps it, and a composite none of whose components is in the data is kept whole.
- **One execution counts once.** A run printed twice — a system card reprinting the previous card's series, the
  same run drawn on two charts, a leaderboard copying a vendor's table — is one measurement. Two rows are the same
  execution when their values agree within what separates two copies of one number: both reading precisions (§4),
  2·√(δ₁² + δ₂²), plus one unit of the last digit of each (a rounding made the wrong way somewhere along the
  publisher's pipeline). Where both rows carry a score and a cost, both must agree; one run scored with two metrics
  (partial credit and strict pass on the same trajectories) is still one execution, recognised by its cost, and a
  score written under two labels of one scale is one metric if the values agree. Two groups are compared when they
  run one benchmark family, or come from one publisher (the same runs regrouped). They share an execution when they
  agree on what they share — all their common values, or one model's series — on two values at least and on all but
  one (a miscopy); when only one axis can tell, on all of them and three at least. The execution's rows are kept
  once, on both axes, in the larger group. A few coincidences among many shared values, or two runs that both reach
  100 %, are not a republication.
- **Groups without information.** A group with a single couple says nothing about a difference, nor does a group
  whose couples all sit at the same bound (every couple at 100 %). Both stay in the data and the counts, not in the
  fit. A tie away from the bounds (two couples at 79.3 %) is information — the couples are equal — and is kept.
- **One scale per group.** A group whose rows carry metrics of different natures stops the build.

## 4. Scales

Each metric is put on a scale where a benchmark can be linear in quality. The rule reads the metric's label, never
the benchmark's identity:

| Metric | Transformation |
|---|---|
| bounded score: a percentage, a score out of *N* (or "*k* of *N*"), an F1, a 0–4 grade, a composite published on 0–100 | empirical logit of the proportion: logit(q), q = (p·n + ½)/(n + 1), n the group's number of scoring steps |
| positive unbounded quantity with a true zero (money earned, points) | log |
| interval or unknown scale (an Elo rating, a correlation, a composite without a stated range) | none |
| lower is better (a rank) | sign flipped first |
| a label contradicted by its values (scores beyond the stated bound, like a "score out of 10" reaching 100) | treated as an unknown scale, and reported by the build |
| cost | log |

**Reading precision.** Every value carries the standard deviation δ of the error made in reading it off its source,
in its own unit, added to the row's variance (§5):
- a printed number: its rounding, one unit of the last digit written in the data file / √12 (a uniform error). A
  source that prints fewer digits than the data file holds (a page rounding a table, a chart label) is not where the
  finer digits came from: the data file's own last digit counts;
- a value read off a chart, two errors in quadrature: the reading, the axis' units per pixel (recomputed by least
  squares from the chart's tick coordinates) times the chart's reading error in pixels (from an independent re-reading
  of its points: the RMS difference / √2, never below the pixel's own 1/√12, the median of the charts for a chart
  with fewer than three re-read points); and the chart's own error against the number it draws — re-plotting,
  roundings along the publisher's pipeline — estimated on the runs printed on two charts (identical printed scores
  prove the run): 0.48 % of the axis span. On a log axis both are relative (about 2 % on a digitised cost);
- a cost the collector computed from published token counts: the counts' rounding propagated (the largest relative
  rounding of the counts, conservative), added to the rounding of the result.
Converted to the model's scale by the derivative of the transformation (the logit's at the observed proportion, the
log's 1/value). The evidence — per chart the calibration and the re-read points, per source whether each value is
printed, from a data file or computed — is in `data/precision/`, checked source by source.

A bounded score compresses near its floor and ceiling; the logit removes that. The number of scoring steps n is one
over the group's finest observed score difference (7 for a benchmark of 7 tasks), and at most 100: a score of 0 or
100 % lands half a step inside the bounds instead of at infinity. On the logit scale the sampling noise of a
proportion is not constant: its variance is proportional to 1/(q(1 − q)), about four times larger at 7 % or 93 % than
at 50 %. Each bounded row carries that shape, h = 1/(2√(q(1 − q))) at its observed q (1 at 50 %), so a score near a
bound weighs what it is worth.

## 5. Fusion: one quality and one cost per couple

### Model

For every row *r* (group *b*, couple *c* of model *m*, publisher *s*, task type *t*), with *f* the transformation of §4:

    f(y_r) = o_b + a_b · (θ_c + u_{s,c} + w_{s,m} + v_{c,t}) + ε_r ,      ε_r ~ Student-t_ν(0, κ_r · h_r² · σ_b² + d_r²)

| Term | Meaning | Prior |
|---|---|---|
| θ_c | the couple's latent quality (quality axis) or log cost (cost axis) | N(0, 10²), summing to zero over the couples |
| o_b | the group's offset: the metric's zero, the task's difficulty, the harness level | flat |
| a_b | the group's gain: metric units per unit of θ | below |
| σ_b | the group's noise: how far its measurements scatter beyond their reading error | log σ_b ~ N(μ_σ, s_σ²), pooled |
| h_r | the noise shape of a bounded score (§4); 1 on other scales | fixed by the data |
| d_r | the value's reading precision (§4), on the model's scale | known |
| u_{s,c} | the publisher's systematic effect on this couple | N(0, τ_c²), τ_c ~ N⁺(0, s_τ²) pooled over couples |
| w_{s,m} | the publisher's systematic effect on this model, shared by all its effort levels | N(0, ψ²) |
| v_{c,t} | the couple's deviation on a task type; composite indices (*mixed*) carry none | N(0, ω²) |
| κ_r | the variance multiplier of an early-access run (1 for other runs) | log κ ~ N(0, 1), estimated |
| ν | the Student-t's degrees of freedom: how heavy the tails of the noise are | Gamma(2, 0.1), estimated |

Every standard deviation (s_g below, s_τ, ψ, ω, s_σ) has a weakly informative half-Student-t(3, 0, 2.5) prior; μ_σ is
flat.

**No reference couple in the fit.** The θ sum to zero: the origin is the average couple, not a chosen one. The page
divides by a reference couple afterwards; that is a display choice, which changes neither the fit nor the
uncertainty of any other couple.

**Gains.**
- Quality: the discrimination a_b/σ_b is pooled across groups, log(a_b/σ_b) ~ N(0, s_g²). A gain estimated from
  three points cannot run away, and the zero mean sets the unit of θ.
- Cost: log a_b ~ N(0, s_g²). A task's size multiplies every couple's cost, but the cost of extra effort also grows
  with the task's difficulty, so a benchmark's cost ratios can be stretched or compressed. θ is the log cost on a
  task of typical elasticity.
- Groups of one benchmark family keep their own gains. Their gains agree to about ±20 % on the current data,
  against a spread of more than an order of magnitude across benchmarks, so a benchmark run by several sources is on
  one scale; pooling those gains in a way that keeps the model's affine invariance is not implemented.

**Noise.** The noise is pooled across groups on each group's standardised scale (its scores centred and divided by
their spread), which an affine change of the metric leaves unchanged. A group of two couples borrows its noise level
from the others instead of letting it run to infinity. Each value adds its own reading error: a group whose points
line up perfectly is still no more precise than it was read, and no floor on σ_b is needed.

**Effects that the data can tell apart.** An effect carried by a single row cannot be told from that row's noise
and is left out; its variance stays in the noise. The mean of a publisher's effects is indistinguishable from the
offsets of that publisher's groups, which are free, and likewise the mean of a task type's effects: the effects are
centred within their publisher (u, w) or their task type (v).

**Affine invariance.** Rescaling or shifting a group's scores leaves the result unchanged: o_b, a_b and σ_b absorb
it, and the pooled priors act on scale-free quantities (the discrimination, the standardised noise). This is why a
score can be used without knowing which benchmark produced it.

### Weighting

No weight is chosen per source or per benchmark; each contribution follows from the model. The fixed constants are
the 100-step limit of §4 and the prior constants above; the tails of the noise and the down-weighting of early-access
runs are estimated.

- **Couples per group.** A group of *k* couples spends two degrees of freedom on its own offset and gain. The
  information it brings on the spacing of couples grows with d_b²·(k − 2): three couples is where a group starts to
  inform differences. A group of two couples brings their order, and a magnitude borrowed from the typical gain.
- **Discrimination.** The factor d_b² makes a saturated or noisy benchmark weigh little; within a group, a score near
  a bound weighs less through h_r.
- **Publishers.** However many groups a publisher contributes, its weight on a couple stays below what its own
  systematic effects allow (τ_c² per couple, ψ² shared across a model's effort levels): a diminishing return that
  follows from the correlation between one publisher's measurements.
- **Task types.** θ is a random-effects mean over the task types the couple was measured on: a couple measured on
  several types does not inherit one type's advantage; a couple measured on a single type keeps it, shrunk.
- **Early access.** Its variance multiplier κ is estimated from how far early-access runs sit from the rest.

### Estimation

The model is written in Stan (`model/lqm.stan`); the data preparation of §2–§4 is in `model/lqm.py`. It is sampled with
the No-U-Turn sampler, a Hamiltonian Monte Carlo method (Hoffman & Gelman 2014; Betancourt 2017).

- **Writing.** How a model is written changes how fast the sampler explores it, not what it estimates. Each group's
  noise log σ_b is written in centred form, and its gain log a_b in centred form when the group has at least 20
  rows, non-centred otherwise (Papaspiliopoulos, Roberts & Sköld 2007; Betancourt & Girolami 2015). Effects are
  centred and mapped to rows by sparse matrix products, so that Stan's optimiser (`stanc --O1`) keeps every vector in
  its fast memory layout. These choices were made one at a time against the simplest form, and each was checked to
  leave the log density and its gradient unchanged.
- **Samplers.** Quality: nutpie (Seyboldt et al.), whose adaptation of the mass matrix needs about four times fewer
  steps here, 4 chains × (1,000 warm-up + 16,000 draws), target acceptance 0.85. Cost: CmdStan, 4 chains × (500
  warm-up + 4,500 draws), target acceptance 0.9, each chain started from the last draw of the previous fit (1,000
  warm-up iterations when there is none). A chain left in another region restarts its axis on CmdStan from the
  previous fit's draws; too few effective draws continue the same chains, adding draws rather than starting again,
  within a budget of 10 minutes per axis; an axis whose data and model are unchanged is not refitted.
- **Where it runs.** The fit runs on the maintainer's machine (`model/fit.py`) and only its results are published
  (`model/fit-cache.json`, with a fingerprint of the data, the model and its settings); building the page does not need
  Stan. The fitting environment is pinned in `model/requirements-fit.txt`.

A fit is published only if, on every parameter and read-out, the rank-normalised split R̂ is at most 1.01, the bulk
and tail effective sample sizes are at least 400 (Vehtari et al. 2021), and no transition diverged; the build
refuses one that misses any of them. The Monte Carlo error of every displayed value is stored with it, and must stay
below half of its last displayed digit, so that a refit with another seed changes no visible figure.

### Fixed values

Every constant the procedure sets by hand, in one place. None is tuned to the data.

| Where | Value | Why |
|---|---|---|
| §3 republication | identical within 2·√(δ₁² + δ₂²) + one last digit each; on ≥ 2 values and all shared but one (≥ 3 and all when one axis alone can tell) | two copies of one number differ by their reading errors and a rounding; a few coincidences are not a reprint |
| §4 logit | ½ step added, at most 100 scoring steps | a 0 or 100 % score lands half a step inside the bounds |
| §4 reading precision | printed: last digit / √12; chart: reading error in pixels ≥ 1/√12 | the standard deviation of a uniform rounding error; the chart's own error is estimated, not set |
| §5 priors | θ ~ N(0, 10²); every standard deviation ~ half-Student-t(3, 0, 2.5); ν ~ Gamma(2, 0.1); log κ ~ N(0, 1) | weakly informative (Gelman 2006; Bürkner 2017; Juárez & Steel 2010) |
| §5 effects | a level carried by one row is left out | it cannot be told from that row's noise |
| §5 panel read-out | 9 Gauss–Hermite nodes | exact to far below the Monte Carlo error |
| §5 publication | measured by ≥ 2 publishers | one publisher's figures cannot be cross-checked |
| §5 intervals | 16–84 % (± 1 standard deviation for a normal law) | the usual width for comparing many points on one chart |
| §5 convergence | R̂ ≤ 1.01, ESS ≥ 400, no divergence | Vehtari et al. 2021 |
| §5 writing | gain centred from 20 rows | a sampling choice: the model is the same either way |
| §7 quality axis | symmetric log around parity, constant 0.045 | display only |
| §9 price curve | k on the grid {0.1 … 3}; weight 1 − d/d_max | see §9 |
| §11 tiers | 4 tiers; cost exponents 1.20, 1.05, 0.95, 0.80; bonus above target capped at +20 % | see §11 |
| §12 crown | Gaussian weight of width 10 around parity | nearly flat, see §12 |

### Software and references

- Stan 2.40 (CmdStan) and CmdStanPy 1.3 — Stan Development Team, *Stan Modeling Language*, <https://mc-stan.org>.
- nutpie 0.16, through BridgeStan 2.9 — <https://github.com/pymc-devs/nutpie>, <https://github.com/roualdes/bridgestan>.
- ArviZ 1.3 for R̂, ESS and Monte Carlo errors — <https://www.arviz.org>.
- NumPy for the read-outs computed outside Stan and the quasi-variances.
- Vehtari, Gelman, Simpson, Carpenter & Bürkner (2021), *Rank-normalization, folding, and localization: an improved
  R̂ for assessing convergence of MCMC*, Bayesian Analysis 16(2).
- Hoffman & Gelman (2014), *The No-U-Turn Sampler*, JMLR 15; Betancourt (2017), *A Conceptual Introduction to
  Hamiltonian Monte Carlo*, arXiv:1701.02434.
- Papaspiliopoulos, Roberts & Sköld (2007), *A general framework for the parametrization of hierarchical models*,
  Statistical Science 22(1); Betancourt & Girolami (2015), *Hamiltonian Monte Carlo for Hierarchical Models*.
- Firth & de Menezes (2004), *Quasi-variances*, Biometrika 91(1).
- Gelman (2006), *Prior distributions for variance parameters in hierarchical models*, Bayesian Analysis 1(3);
  Bürkner (2017), *brms: An R package for Bayesian multilevel models using Stan*, JSS 80(1); Juárez & Steel (2010),
  *Model-based clustering of non-Gaussian panel data based on skew-t distributions*, JBES 28(1) (the Gamma(2, 0.1)
  prior on ν).
- Gelman et al. (2020), *Bayesian Workflow*, arXiv:2011.01808 (the model was built and checked stage by stage).

### Output

- **Relative quality** — the couple's expected score averaged over the benchmark panel, divided by the reference
  couple's. The panel is every group with a bounded score, each benchmark family counting once. The expected score
  on a panel group is the group's fitted curve at the couple's θ plus its effects there: the publisher and task-type
  effects the data contain for this couple, and, for those they do not, the average over their distribution
  (Gauss–Hermite quadrature). It reads: *if every couple sat every benchmark of this report as its publisher ran it,
  this couple's average score would be this multiple of the reference couple's.*
- **Relative cost** — exp(θ_c − θ_reference): the cost ratio on a task of typical elasticity.
- **Centre** — the posterior median of the couple's read-out, divided by the reference couple's: changing the
  reference divides every value by the same constant.
- **Interval** (16–84 %) — the couple's own uncertainty, as a quasi-standard error (Firth & de Menezes 2004): one
  half-width per couple, fitted so that for any two couples √(q_i + q_j) reproduces the 16–84 % spread of their
  difference across the posterior draws. Two couples compare through their two intervals, whichever the reference;
  the reference couple has its own interval like any other. The approximation error is reported (§ Checks); it errs
  on the wide side for neighbouring rungs of one model, whose difference is known more precisely than two separate
  intervals suggest.
- **New-source interval** (16–84 %) — what one new source would report for the couple on the same read-out: a new
  publisher and task-type effect drawn from their laws. It measures how much sources disagree about the couple.
- **Publication** — a couple is shown only when at least two publishers measured it. The others stay in the fit and
  in the data file.

### Checks

Scripts in `model/validation/` reproduce each check. ⟨Figures of the final fit: to be filled in.⟩

- **Held-out prediction** (`heldout.py`). One fifth of the percentage scores removed, the model refitted, the
  removed scores predicted, five times; compared with a score-ratio baseline (per-benchmark ratios to the reference,
  weighted median across benchmarks); share of removed scores inside their 16–84 % predictive interval (target 68 %).
- **Known truth** (`synthetic.py`). Synthetic scores on the real design with known qualities, under benchmarks
  proportional to quality (where score ratios are exact by construction), logistic, and a mix of logistic, Elo,
  power and saturating shapes: distortion of the recovered scale, share of couple pairs in the wrong order, and share
  of pairs whose true difference lies in the 16–84 % posterior interval and in the quasi-standard-error interval
  (target 68 % for both).
- **Sensitivity** (`compare.py`). Removing the largest publisher: how far the values move.
- **Effort ladders.** At build time, any couple scoring or costing less than the rung below it is reported. The
  report is printed, not corrected: an inversion inside the interval is left as the data give it.

## 6. The matrix

One row per model, one column per effort, the cell = relative cost with its interval. Rows are ordered by the model's
relative quality at its highest published effort. A model without effort levels fills a single merged cell; an
unpublished couple is shown as n/a.

## 7. The landscape chart

- **Cost axis**: log₁₀ of the relative cost.
- **Quality axis**: a symmetric log around parity, T(Q) = sign(Q − 1)·ln(1 + |Q − 1| / 0.045). It dilates the
  crowded band near the reference and compresses the sparse tails; every distance in quality below is measured in T.
- One curve per model through its effort ladder. Optional ovals draw each couple's 16–84 % interval (cost × quality).

## 8. Pareto frontier

A couple is **dominated** when another couple costs no more and scores no less, and is strictly better on one of
the two (centres compared). The frontier is the set of non-dominated couples, ordered by cost.

The reader can hide older models (a display switch). Hidden models leave the frontier, the price curve, the tiers
and the crown as well as the charts: every recommendation is computed over the models on screen.

## 9. Price curve

What a given quality typically costs, fitted on **every** shown couple, dominated ones included:

    log₁₀(cost) = g(u) = α + β·u + γ·(e^{k·u} − 1)/k ,   u = T(Q) − T_min ,   β ≥ 0, γ ≥ 0

- **Monotone by construction.** g′(u) = β + γ·e^{k·u} ≥ 0 everywhere, so the price of quality never falls as quality
  rises, extrapolation included. The exponential term lets the curvature grow near the quality ceiling, where cost
  rises sharply; k → 0 gives a quadratic. k is chosen on a grid {0.1 … 3} by weighted least squares; α, β, γ by
  constrained weighted least squares (the active set of β ≥ 0, γ ≥ 0).
- **Weight by distance to the frontier.** d = log₁₀(cost) − log₁₀(cost of the cheapest couple offering at least this
  quality), 0 on the frontier. Each couple weighs 1 − d/d_max: a frontier couple fully, the farthest couple not at
  all, linearly in between. Equal weights would let strictly dominated couples steer the curve; the frontier alone
  would discard the measurements that populate the middle.
- **Centres only.** Each couple enters at its centre. Smearing a point over its interval through the non-linear T
  and g would shift it toward parity: a bias, not an uncertainty.

## 10. Value index

The distance of a couple to the price curve, in log-cost:

    G = g(T(Q))                                           what the curve charges for this quality
    C = log₁₀(cost)                                       what the couple costs
    r = G − C                                             positive = cheaper than the going rate
    value index = 100 · 10^(r − r_reference)

The index is a ratio: 100 is the reference couple, 350 means 3.5 times its value for money, 45 means 0.45 times; it
is unbounded above. The reference's residual is read from the full set of couples, so the scale holds even when the
reference is not on the frontier. A frontier couple can score below 100: being non-dominated does not make it good
value for what it delivers.

## 11. Tiers: best value by task complexity

Four tiers, from routine throughput work to research-grade problems.

- **Targets.** The four target qualities q*₁…q*₄ are spread evenly in T across the frontier's quality span, from its
  weakest to its strongest couple, so they move with the models.
- **Window width.** σ = gap / (2·√ln 2), gap being the spacing of the targets in T: adjacent windows cross at half
  weight midway between their targets, so the four windows partition the axis.
- **Half-bell window.** With δ = (T(Q) − T(q*))/σ, a couple's weight is e^(−δ²) below the target and
  1 + 0.2·(1 − e^(−2δ)) at or above it: falling short is penalised, clearing the bar earns a bonus that saturates at
  +20 %, so being better never hurts.
- **Cost sensitivity.** Tier *i* ranks frontier couples on weight × 10^(G − γ_i·C), with γ = 1.20, 1.05, 0.95, 0.80
  from the lowest to the highest tier: cost weighs more than proportionally on throughput work, less on
  research-grade work. Only the selection is tilted; a card shows the neutral value index (γ = 1).
- **Pick.** The frontier couple with the highest tier score. Sliders move the targets and widths; the defaults are
  the data-derived values above.

## 12. The crown

The best overall pick is the frontier couple that stands out most from its neighbours. Along the frontier ordered by
cost, its **prominence** is 2·r_n − r_(n−1) − r_(n+1), the endpoints getting 0: a second difference of the distance
to the price curve, a knee in value. The crown is the most prominent couple, weighted by a Gaussian of width 10 in T
around parity (nearly flat); its card shows its value index.

## 13. Sources table and counts

Every group is listed with its verified configuration (harness, effort), its kind (effort sweep, cross-model,
cross-generation) and the couples it links. The header counts sources, benchmarks and measurements. The page's date
moves only when its content (text, figures, data) changes.

## 14. Limits

- One latent quality per couple, averaged over task types; the ranking can differ on a single task type.
- Which couples a source chooses to measure is not random. Free offsets absorb the level of the tasks chosen and
  the task-type effect their type; a selection on another axis would not be corrected.
- The panel of §5 is the benchmarks of this report: adding benchmarks can move relative quality even for couples
  they do not measure, because every couple is read on the same panel.
- A couple measured by few, disagreeing publishers keeps a wide interval, and its centre can move by several percent
  when one publisher is added or removed.
- Republished numbers are detected within a benchmark family and within a publisher; a reprint by another publisher
  under an unrelated group, or one that changed every value beyond a rounding, would count twice.
  Composites are matched to their components from their publisher's documentation; an undocumented composite would
  count its components twice.
- Costs are what each source measured at the prices of its day; a price change a source did not report is not
  corrected, and the data file has no measurement date to apply one systematically.
- The cost of the largest models rests heavily on their vendor's system cards; removing that publisher moves some
  costs by more than 10 %.
- Differences smaller than the intervals — two neighbouring rungs, a crown between two close couples — are ties.
