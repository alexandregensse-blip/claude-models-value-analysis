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
metric, the cache-read share, a free-text **confound** field, and the reference (URL, page, file).

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
  tokens at wrong rates is re-priced and the correction flagged.
- **Charts are digitised and checked** against any number the same document prints in its text, and flagged.
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
- **Republished numbers count once.** Two groups of one family that share at least two identical values away from
  the metric's bounds (within 0.05 % of the scale, or of the value for unbounded metrics) are the same experiment
  printed twice — a system card reprinting the previous card's reference column is the typical case. Their identical
  rows are kept once, in the larger group. A single coincidence, or two runs that both reach 100 %, is not a
  republication. Detection is scoped to families.
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

A bounded score compresses near its floor and ceiling; the logit removes that. The number of scoring steps n is one
over the group's finest observed score difference (7 for a benchmark of 7 tasks), and at most 100: a score of 0 or
100 % lands half a step inside the bounds instead of at infinity. On the logit scale the sampling noise of a
proportion is not constant: its variance is proportional to 1/(q(1 − q)), about four times larger at 7 % or 93 % than
at 50 %. Each bounded row carries that shape, h = 1/(2√(q(1 − q))) at its observed q (1 at 50 %), so a score near a
bound weighs what it is worth.

## 5. Fusion: one quality and one cost per couple

### Model

For every row *r* (group *b*, couple *c* of model *m*, publisher *s*, task type *t*), with *f* the transformation of §4:

    f(y_r) = o_b + a_b · (θ_c + u_{s,c} + w_{s,m} + v_{c,t}) + ε_r ,      ε_r ~ Student-t_ν(0, κ_r · h_r² · σ_b²)

| Term | Meaning | Prior |
|---|---|---|
| θ_c | the couple's latent quality (quality axis) or log cost (cost axis) | N(0, 10²), summing to zero over the couples |
| o_b | the group's offset: the metric's zero, the task's difficulty, the harness level | flat |
| a_b | the group's gain: metric units per unit of θ | below |
| σ_b | the group's noise, never below the metric's resolution | log σ_b ~ N(μ_σ, s_σ²), truncated at the resolution, pooled |
| h_r | the noise shape of a bounded score (§4); 1 on other scales | fixed by the data |
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
from the others instead of letting it run to infinity.

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

Hamiltonian Monte Carlo with the No-U-Turn sampler, in Stan (`gen/lqm.stan`, CmdStan run through CmdStanPy);
the data preparation of §2–§4 is in `gen/lqm.py`. ⟨Parametrisation and settings: to be written once fixed.⟩ The fit
runs on the maintainer's machine (`gen/fit.py`) and only its results are published (`gen/fit-cache.json`, with a
fingerprint of the data, the model and its settings); building the page does not need Stan.

A fit is published only if, on every parameter and read-out, the rank-normalised split R̂ is at most 1.01 and the bulk
and tail effective sample sizes at least 400 (Vehtari et al. 2021), no transition diverged, and the Monte Carlo error
of every displayed value is below half its display rounding (0.0025 on the log scale), so that a refit with another
seed changes no visible figure. The build refuses a fit that misses one of them.

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

Scripts in `gen/validation/` reproduce each check. ⟨Figures to be measured on the final fit.⟩

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
- Republished numbers are detected within a family; a reprint filed under an unrelated group would count twice.
  Composites are matched to their components from their publisher's documentation; an undocumented composite would
  count its components twice.
- Costs are what each source measured at the prices of its day; a price change a source did not report is not
  corrected, and the data file has no measurement date to apply one systematically.
- The cost of the largest models rests heavily on their vendor's system cards; removing that publisher moves some
  costs by more than 10 %.
- Differences smaller than the intervals — two neighbouring rungs, a crown between two close couples — are ties.
