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
- **Early access.** A run its source dates before the model's public release is flagged (§5: a third of the weight).
- **Uninformative scores.** A score stuck at the floor or the ceiling of its metric for one couple while the others
  are not (3 successes out of 657 tasks) says little and depends on how the bound is handled; such a score is left
  blank and the cost kept.
- **Flag, do not drop.** Doubts (cost basis undocumented, a fallback model served part of the run, an effort inferred
  from order, a digitised value) are written in the confound field. A source is excluded only when it breaks a rule
  above.

## 3. From rows to groups

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
| bounded score: a percentage, a score out of *N* (or "*k* of *N*"), an F1, a 0–4 grade, a composite published on 0–100 | empirical logit of the proportion: logit((p·n + ½)/(n + 1)), n the group's number of scoring steps |
| positive unbounded quantity with a true zero (money earned, points) | log |
| interval or unknown scale (an Elo rating, a correlation, a composite without a stated range) | none |
| lower is better (a rank) | sign flipped first |
| a label contradicted by its values (scores beyond the stated bound, like a "score out of 10" reaching 100) | treated as an unknown scale, and reported by the build |
| cost | log |

A bounded score compresses near its floor and ceiling; the logit removes that. The number of scoring steps n is one
over the group's finest observed score difference (7 for a benchmark of 7 tasks), and at most 100: a score of 0 or
100 % lands half a step inside the bounds instead of at infinity.

## 5. Fusion: one quality and one cost per couple

### Model

For every row *r* (group *b*, couple *c* of model *m*, publisher *s*, task type *t*), with *f* the transformation of §4:

    f(y_r) = o_b + a_b · (θ_c + u_{s,c} + w_{s,m} + v_{c,t}) + ε_r ,      ε_r ~ Student-t₄(0, m_r · σ_b²)

| Term | Meaning | Prior |
|---|---|---|
| θ_c | the couple's latent quality (quality axis) or log cost (cost axis) | N(0, 10²); one couple fixed at 0 to set the origin |
| o_b | the group's offset: the metric's zero, the task's difficulty, the harness level | flat |
| a_b | the group's gain: metric units per unit of θ | below |
| σ_b | the group's noise, never below the metric's resolution | quality: 1/σ; cost: log σ_b ~ N(μ_σ, s_σ²), pooled |
| u_{s,c} | the publisher's systematic effect on this couple | N(0, τ_c²); τ_c² ~ IG(2, β), β ~ Exp(mean 0.05), pooled over couples |
| w_{s,m} | the publisher's systematic effect on this model, shared by all its effort levels | N(0, ψ²), ψ² ~ IG(1, 0.01) |
| v_{c,t} | the couple's deviation on a task type; composite indices (*mixed*) carry none | N(0, ω²), ω² ~ IG(1, 0.01) |
| m_r | 3 for an early-access run, else 1 | fixed |

**Gains.**
- Quality: the discrimination d_b = a_b/σ_b is pooled across groups, log d_b ~ N(0, s_d²). A gain estimated from
  three points cannot run away, and the zero mean sets the unit of θ.
- Cost: log a_b ~ N(0, s_a²). A task's size multiplies every couple's cost, but the cost of extra effort also grows
  with the task's difficulty, so a benchmark's cost ratios can be stretched or compressed. θ is the log cost on a
  task of typical elasticity.
- Groups of one benchmark family keep their own gains. Their gains agree to about ±20 % on the current data,
  against a spread of more than an order of magnitude across benchmarks, so a benchmark run by several sources is on
  one scale; pooling those gains in a way that keeps the model's affine invariance is not implemented.
- Hyper-priors: s_d², s_a², s_σ² ~ IG(1, 0.25); μ_σ flat.

**Affine invariance.** Rescaling or shifting a group's scores leaves the result unchanged: o_b, a_b and σ_b absorb
it. This is why a score can be used without knowing which benchmark produced it.

### Weighting

No weight is chosen per source or per benchmark; each contribution follows from the model. The fixed constants are
the Student-t's 4 degrees of freedom, the ×3 variance of early-access runs, the 100-step limit of §4 and the
hyper-prior constants above.

- **Couples per group.** A group of *k* couples spends two degrees of freedom on its own offset and gain. The
  information it brings on the spacing of couples has trace d_b²·(k − 2): three couples is where a group starts to
  inform differences. A group of two couples brings their order, and a magnitude borrowed from the typical gain.
- **Discrimination.** The factor d_b² makes a saturated or noisy benchmark weigh little.
- **Publishers.** However many groups a publisher contributes, its weight on a couple stays below what its own
  systematic effects allow (τ_c² per couple, ψ² shared across a model's effort levels): a diminishing return that
  follows from the correlation between one publisher's measurements.
- **Task types.** θ is a random-effects mean over the task types the couple was measured on: a couple measured on
  several types does not inherit one type's advantage; a couple measured on a single type keeps it, shrunk.
- **Early access.** Three times the noise variance, a third of the weight.

### Estimation

Gibbs sampling in pure Python. The offset o_b is integrated out for the slice-sampling updates of log a_b and log σ_b;
θ, the effects and o are normal conjugates; the Student-t is a latent scale mixture; the hyper-parameters have
conjugate updates. Several directions are invisible or nearly invisible to the likelihood, and plain coordinate
updates cross them slowly; the sampler moves along them exactly: a global rescaling of θ and the effects against the
gains; for each effect, the couples it belongs to against the effect; the level of every other couple against the
group offsets; and, for the couple fixed at 0, its own effects and the other effort levels of its model against the
rest. The remaining invisible directions — a publisher's effects against the offsets of its groups, a task type's
effects against the offsets of the groups of that type — are held by their priors. Four independent chains of 6,000
sweeps (2,000 discarded, one draw in two kept) run in parallel; the Gelman–Rubin R̂ across chains is reported for
every couple. The fitted grids are cached with a fingerprint of the data, the model and its settings, so the page is
refitted only when one of them changes.

### Output

- **Relative quality** — the couple's mean predicted score over the benchmark panel divided by the reference
  couple's. The panel is every group with a bounded score, each benchmark family counting once; a predicted score is
  the group's fitted curve at the couple's θ. It reads: *if every couple sat every benchmark of this report, this
  couple's average score would be this multiple of the reference couple's.* It is computed exactly for every
  posterior draw, so changing the reference couple divides every value by a constant.
- **Relative cost** — exp(θ_c − θ_reference): the cost ratio on a task of typical elasticity.
- **Centre** — the posterior median.
- **Band** (16–84 %) — the ratio couple ÷ reference couple that **one new benchmark** would report: a benchmark
  drawn from the panel (quality) or from the cost groups (cost) with its own gain, level and noise, a new publisher and
  a new task type, drawn for both couples (a publisher's model effect is shared when both are the same model). It
  answers "what would an independent new measurement say". The credible interval of the centre, much narrower, is
  kept in the output.
- **Publication** — a couple is shown only when at least two publishers measured it. The others stay in the fit and
  in the data file.

### Checks

Scripts in `validation/` reproduce each check.

- **Held-out prediction** (`heldout.py`). One fifth of the percentage scores removed, the model refitted, the
  removed scores predicted, five times (1,795 scores): median error 1.9 points against 4.7 for a score-ratio
  baseline (per-benchmark ratios to the reference, weighted median across benchmarks), 90th percentile 8.6 against
  16.9.
- **Known truth** (`synthetic.py`). Synthetic scores on the real design with known qualities, under benchmarks
  proportional to quality (where score ratios are exact by construction), logistic, and a mix of logistic, linear,
  power and saturating shapes. The distortion of the recovered scale (RMS error after the best change of unit,
  relative to the spread of the truth) is the same as the ratio baseline's where ratios are exact (0.059 against
  0.054) and about half of it otherwise (logistic 0.13 against 0.30, mixed 0.08 against 0.15); both put fewer than
  2 % of couple pairs in the wrong order.
- **Sampler** (`sbc.py`). Simulation-based calibration on both axes, on a design with two-couple groups, publishers
  measuring several effort levels of one model, task types including composites, and Student-t noise: the ranks of
  the true values are uniform (quality χ² = 11.6, cost χ² = 10.1, 240 ranks each, 5 % critical value 16.9), and a
  fit with a deliberately wrong prior is rejected (χ² = 354). A fit that ignores the publisher × model effect is not
  detected by this test: that effect moves θ too little for the ranks to show it.
- **Reference couple** (`anchor_invariance.py`). Fitting with another couple fixed at 0 and dividing back moves the
  values by 0.6 % (median) and 2.3 % at most, the size of the Monte Carlo error of those runs.
- **Band** (`band_coverage.py`). Share of the ratios actually observed in the data (couple ÷ reference couple, same
  group) inside the 16–84 % band: 82 % for quality (81 % for couples far from the reference), 80 % for cost. The band
  is slightly conservative.
- **Sensitivity** (`compare.py`). Removing the largest publisher (a quarter to a third of all rows): quality moves by
  0.7 % (median) and 1.9 % at most, Kendall τ = 0.98; cost moves by 5.5 % (median) and 13 % at most (the costs of the
  largest models rest heavily on that publisher's system cards), Kendall τ = 0.97.
- **Monte Carlo error.** Two independent runs of two short chains (2,500 sweeps) differ by 0.2 % (median) and 1.7 %
  at most on quality, 1.1 % and 3.6 % on cost; the published fit uses four chains of 6,000 sweeps.
- **Effort ladders.** At build time, any couple scoring or costing less than the rung below it is reported. The
  report is printed, not corrected: an inversion inside the band is left as the data give it.

## 6. The matrix

One row per model, one column per effort, the cell = relative cost with its band. Rows are ordered by the model's
relative quality at its highest published effort. A model without effort levels fills a single merged cell; an
unpublished couple is shown as n/a.

## 7. The landscape chart

- **Cost axis**: log₁₀ of the relative cost.
- **Quality axis**: a symmetric log around parity, T(Q) = sign(Q − 1)·ln(1 + |Q − 1| / 0.045). It dilates the
  crowded band near the reference and compresses the sparse tails; every distance in quality below is measured in T.
- One curve per model through its effort ladder. Optional ovals draw each couple's band (cost × quality, asymmetric).

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
- **Uncertainty.** Each couple enters as five samples: its centre (½) and its four band extremities — cost low, cost
  high, quality low, quality high (⅛ each).

## 10. Value index

The distance of a couple to the price curve, in log-cost:

    G = ¾·g(T(Q)) + ⅛·g(T(Q_low)) + ⅛·g(T(Q_high))      what the curve charges for this quality
    C = ¾·log₁₀(cost) + ⅛·log₁₀(cost_low) + ⅛·log₁₀(cost_high)      what the couple costs
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
- A couple measured by few, disagreeing publishers keeps a wide band, and its centre can move by several percent
  when one publisher is added or removed.
- Republished numbers are detected within a family; a reprint filed under an unrelated group would count twice.
- The cost of the largest models rests heavily on their vendor's system cards; removing that publisher moves some
  costs by more than 10 %.
- Differences smaller than the band — two neighbouring rungs, a crown between two close couples — are ties.
