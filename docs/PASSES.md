# Research log

Notes from each source pass and method change: what was searched, what was admitted or corrected,
and what moved. The measured rows themselves are in `raw-data.csv`; the method is summarised in the README
(*How the numbers are built*) and detailed in `METHODOLOGY.md`. Section headings are kept as written at the time, so figures inside an older
section describe the state after that pass, not today's.

## Fourteenth pass: Sonnet 5.5, third salvo

Five Sonnet agents on narrow axes, 30 Sep 2026 (two leaderboard lists, GitHub and Hugging Face, the English web,
the non-English web), each resumed once when it stopped after two or three minutes. Every number below was re-read
at its source before entering the data file; several agent drafts were corrected (tables read from the articles'
images, efforts taken from the configuration, groups split by task).
**__COUNTS__**

- **Admitted.**
  - *bug-hunt-bench*: Sonnet 5.5 is now a mean of three runs on all five rungs, like Opus 5.5 (tokens averaged
    from the repo's per-run metrics, which reproduce Opus 5.5's 346,678 exactly); the single `max` and `xhigh` runs of
    the twelfth pass were the first of those three and are replaced, not added.
  - *LMArena WebDev* (Code arena, Overall): a new score-only group, Elo with no cost; effort read from the arena's
    model key (`claude-sonnet-5-5-high`, `claude-opus-5-max-webdev`…), flagged unconfirmed. Five couples enter the
    fit; the thinking/non-thinking keys of older models are kept as `default`/`nothink`.
  - *Zapier AutomationBench*: the board now lists Sonnet 5.5 `xhigh` and `max` (36.83 %, \$0.48; 44.75 %, \$1.14);
    they replace the system-card digitisation of the same runs (36.9 / 44.7); `low`–`high` stay digitised.
  - *kamui/code-review-bench*: two groups where Sonnet 5.5 and Opus 5.5 ran the same skill snapshot on the same
    12 PRs × 3 trials at `high` (/ce-code-review, /thermo-nuclear review): recall and cohort cost. The built-in
    `/code-review` arms are not comparable (Sonnet 5 ran another built-in prompt; the Opus 5.5 baseline covered 10
    PRs, its gap runs have no cost).
  - *AI for Mortals* (Pat Simmons): five Claude Code `/goal` builds at `high` for Sonnet 5.5, Sonnet 5, Opus 5.5 and
    Fable 5.1, cost and tokens per build; no numeric score.
  - *note.com renkon40*: eight personal tasks, Sonnet 5.5 (`high`/`xhigh`/`max`) against Opus 5.5, blind AI judges,
    costs at list price — both tables read from the article's images; Opus 5.5's 3-minute slides (an earlier chat
    work) and its homepage with a skill (the others ran without) are kept as inactive rows.
  - *note.com claudecode_lab*: an invoice check, Sonnet 5.5 and Opus 5.5 × `low`/`medium`/`high`/`max`, 7/7
    everywhere (saturated, cost kept).
  - *qiita yama3133*: five tasks across five models; Sonnet 5.5 and Opus 5.5 at `medium`, the others at their
    Claude Code default (`default`, which is `high` for Sonnet 5 and Opus 5 in 2.1.284).
  - *qiita dahatake*: a spreadsheet engine and a SQL engine (two prompts) in GitHub Copilot CLI at `medium`, three
    runs each, hidden tests; cost in Copilot credits.
- **Already in.** ObviousBench PR #39 (Sonnet 5.5 entered from the PR's earlier head on 29 Sep; unchanged at
  `bb435cb`, still unmerged); the six Vals boards and the AA effort pages an agent reported as new.
- **Not admitted.** Driftproof report 013 (every arm at Claude Code's default effort, scores as ranges); an
  avenoxai repo of creative builds without a score; a Chinese case study quoted without its author.
- **Found empty.** ARC Prize, Epoch, LiveCodeBench, Kilo, OpenRouter, SimpleBench, Aider, Terminal-Bench (2.1, 4.0),
  SWE-bench, swe-rebench, DeepSWE, OSWorld, Sonar (which has added Opus 5.5, not Sonnet 5.5 yet), Hugging Face;
  SEAL, aipricing.guru and marginlab unreachable; restatements of the launch figures in English, Japanese, Chinese
  and Korean.

__IMPACT__

## Method change: the display without a reference couple, decided on the latent scale

**Why.** The page divided every value by a reference couple (Opus 5 @high = 1.00), and several display choices leaked
into the picks: the quality axis was a symmetric log around that couple's quality (constant 0.045), and the price
curve, the tier targets and windows and the crown measured quality on it; the price curve was pulled toward the
frontier by weights 1 − d/d_max that depended on the farthest couple; the tiers added a bonus of up to +20 % that
saturated within one window width and acted as a step, and tilted cost by hand-set exponents γ = 1.20 … 0.80; the crown
was a knee along the frontier, which moves when a neighbouring rung is added.

**What** (`docs/DISPLAY-METHODOLOGY.md`).
- *No reference couple.* Cost is a multiple of the cheapest couple shown; quality is the latent quality θ, labelled
  with the expected panel score it predicts (the fit now publishes θ per couple and the panel curve θ → score).
- *Every decision on the latent scale* (log cost, θ); the display scale only draws: linear in θ, compressed three times
  below the weakest tier target (the models short of today's level grouped at the bottom).
- *Frontier with the intervals.* A couple is within reach of the frontier unless another beats it on both axes with
  probability 0.84 or more; the couples within reach are the candidates of every pick.
- *Price trend* over every couple, the trend of the models: ln cost = a + λ·θ, effective-variance weights.
- *Tiers.* Targets between (1 − e)·min + e·max and (1 − e)·max + e·min of the frontier's θ, e = 0.05; score = window ×
  e^(λθ) ⁄ cost: a smooth reward for quality above the target, no bonus constant, no γ; cost weighed in ratios, as
  people perceive prices (Weber–Fechner; a power 0.88 of cost, from prospect theory's lotteries, was considered and not
  used).
- *Crown*: the couple within reach furthest below the trend.
- *Precision.* Cost multiples to two significant digits: their Monte Carlo error is about 0.3 % (the cheapest couple's
  included), and two decimals on 18× would be noise.

**Before → after** (fit of 30 September 2026, same data; the refit publishing θ: cost 446 s, R̂ 1.0019; quality 527 s,
R̂ 1.0024; no divergence).

| | before (v2026.09.29b) | after |
|---|---|---|
| Crown | Opus 5.5 xHigh (knee) | Sonnet 5.5 high, 4.3× cheaper than the trend |
| Grunt work | Sonnet 5.5 high | Sonnet 5.5 high |
| Everyday tasks | Sonnet 5.5 high | Sonnet 5.5 high |
| Advanced reasoning | Opus 5.5 high | Opus 5.5 medium |
| Cutting-Edge thinking | Opus 5.5 xHigh | Opus 5.5 high |

Price trend λ = 0.108 (one unit of θ costs 11 % more), weighted R² 0.41. Within reach but off the frontier by centres:
Opus 5.5 low, Sonnet 5.5 xHigh, Haiku 4.5.

## Method change: reading precision, and one execution counted once

**Why.** The model had a noise floor per group (the smallest observed score difference / √12) and knew nothing of
how precisely each value had been read. Two consequences showed on the cost axis. Curves digitised off the system
cards, which line up almost perfectly, passed for the most precise sources in the data file, when a digitised value is
by construction the least precise; and the same run printed in two documents, or scored with two metrics, counted as
two sources that agreed to 0.1 % — the fit read that as near-noiseless groups, weighted them heavily and sampled them
slowly (R̂ 1.028 after 13 minutes without the floor).

**What.**
- *Reading precision per value* (`cost_prec`, `score_prec` in the data file, computed by `data/precision.py`): the
  rounding of a printed number; for a digitised value, the chart's resolution times its reading error in pixels plus
  the chart's own error against the number it draws, 0.48 % of the axis span, estimated on the runs printed on two
  charts (identical scores prove the run; their costs differ by 1.6 % RMS). About 2 % on a digitised cost, against
  0.2–0.5 % from a re-reading of one image. The model adds it to each row's variance; the noise floor goes.
- *Evidence, source by source.* 14 Sonnet agents re-measured the 55 digitised charts (tick coordinates, least-squares
  calibration recomputed and checked, re-read points, annotated images), 33 more checked where every non-digitised
  value comes from (printed, primary data file, computed) with verbatim quotes; summaries in `data/precision/`.
- *One execution counts once.* Two rows are the same execution when their values agree within both reading
  precisions plus one unit of the last digit each (a rounding made the wrong way along the publisher's pipeline);
  score and cost must both agree where both are comparable; one run scored with two metrics is one execution,
  recognised by its cost; groups are compared within a benchmark family and within a publisher. Found: HLE with and
  without tools reprinted across the Opus 5, Fable 5, Fable 5.1, Sonnet 5 and Sonnet 5.5 cards, OSWorld 2.1 scored
  twice (partial credit and strict pass) in the Sonnet 5.5 card, DeepSearchQA, AutomationBench (Zapier and the Opus 5
  card), ARC-AGI-2 (ARC Prize and the Opus 4.7 card), the AA index on two pages, OSWorld charted twice — 48 cost rows
  and 68 score rows kept once (2 and 46 before).
- *Costs that were not costs.* Four effort sweeps of the Opus 4.7 and 4.8 cards (`schleeff`, `scsweproeff`,
  `scosweff`, `scodeepqa`) read tokens on a token axis and converted them at one flat price per tier: a flat price
  ignores the input/output mix, which changes with the effort (HLE Opus 4.8 low→max: ×3.9 reconstructed against ×4.7
  measured in dollars on the other cards). The 43 costs leave the cost axis, flagged with their former value; the
  scores stay.
- *Refit.* Each axis is checked as soon as it is sampled: a stuck nutpie chain restarts the axis on CmdStan from the
  last fit's draws, too few effective draws continue the same chains within a 10-minute budget, and an unchanged axis
  is not refitted. Quality draws 4 × 12,000 (ESS 584 against the 400 required).

**Result.** Cost 416 s, R̂ 1.0036, ESS 2,345; quality 557 s, R̂ 1.0024, ESS 584; 16 minutes in all (the cost
axis no longer saturates the tree depth). Crown unchanged, Opus 5.5 xHigh (1.08× the quality of Opus 5 @high for
0.75× its cost, 0.79× before); tiers Sonnet 5.5 high / Sonnet 5.5 high / Opus 5.5 high / Opus 5.5 xHigh (Sonnet 5.5
low / high / high, Opus 5.5 high in v2026.09.29). Quality moves by −4 % (Opus 5.5) to +9 % (Haiku 4.5), cost by −12 %
(Sonnet 5.5 max) to +34 % (Haiku 4.5); Opus 4.7 max costs 18 % more without the reconstructed sweeps.

**Reported, not corrected** (to check at their source): the agents flagged 27 differences between the data file and a source, and ten more on the charts
— digitised points off by more than a marker (Opus 4.8 low on the Fable 5 card's SWE-bench Pro and
FrontierCode Diamond, Sonnet 5 low on Chartography, Opus 4.7 medium on ARC-AGI-2), boards updated since collection
(Vals Corporate Finance, Terminal-Bench 2.1), a HAL score (Opus 4.1: 61.0 against 68.0 %), roundings the wrong way.

**Checks.** Held out (1,708 scores): median error 1.96 points against 4.78 for score ratios, coverage 66 % (target
68 %). Known truth: distortion 0.071–0.091, pairs in the wrong order 0.1–0.8 %, coverage 62–77 %. Without the model
vendor: cost τ 0.988 (median move 2.4 %, largest 14.6 %, Sonnet 5.5 medium), quality τ 0.960 (0.9 %, 3.5 %). The
held-out check took 35 minutes (five full quality fits), beyond the 20-minute salvo; the others stayed within it.

## Method change: the model in Stan, without a reference couple

**Why.** The latent-quality model of v2026.09.29 ran on a hand-written Gibbs sampler and missed the convergence
standard (R̂ 1.062 on costs, 1.017 on qualities). Its intervals were measured against the reference couple, fixed
at 0: every couple carried the reference's uncertainty, the reference had none and its sibling rungs looked narrow.
The ovals drew what one new benchmark would report (noise counted twice) rather than the couple's own uncertainty,
and the value index and the price curve were smeared by the ends of those bands (⅛ each), pulling values toward
parity.

**What.**
- *Stan* (`model/lqm.stan`), sampled by nutpie (quality) and CmdStan (cost), published only with R̂ ≤ 1.01, bulk
  and tail ESS ≥ 400 and no divergence on every parameter; `model/fit-cache.json` carries the fingerprint of its
  inputs and the site refuses a stale or unconverged cache.
- *No reference couple in the fit*: θ sums to zero, the page divides afterwards. Intervals are the couple's own
  (quasi-variances, Firth & de Menezes 2004); the new-source band is still computed and stored. Price curve and value
  index use centres only.
- *Review of the model* (two independent reviewers): groups split by publisher, harness, scale and cost unit;
  composites matched to their documented components (Artificial Analysis v4.3, Vals Index formula, and others);
  the binomial shape of an empirical logit's noise; half-Student-t priors; publisher and task-type effects centred
  within their sets, effects seen in one row left out; the quality read-out integrates unknown effects
  (Gauss–Hermite); Student-t tails and the early-access multiplier estimated.
- *Writing* for the sampler, which leaves the model unchanged (checked on the log density and its gradient): noise
  centred in every group, gain centred from 20 rows, sparse products, `stanc --O1` with `STAN_NO_RANGE_CHECKS`
  (−36 % per gradient).
- *Repository* reorganised into `data/`, `model/`, `site/` and `docs/`, each with its own README.

**Result** (fit of 29 September, before the reading-precision change above): costs 491 s, R̂ 1.0074; qualities
380 s, R̂ 1.0032. Crown unchanged (Opus 5.5 xHigh).

## Method change: a latent-quality fusion model

**Why.** Relative quality was the weighted median of per-benchmark score ratios to the anchor, which assumes every
benchmark is proportional to quality with the same gain. It is not: fitting one free slope per benchmark under that
assumption gave slopes from 0.05 to 4 (10th–90th percentile), about 3 on hard benchmarks (mean score under 30 %) and
0.5 on saturated ones (70 % and above). The median of ratios therefore mixed rulers graduated differently, pulled
couples tested mostly on hard benchmarks away from the anchor, and widened the bands.

**What.** Both grids now come from one model (`gen/lqm.py`, full description in `METHODOLOGY.md`): every metric on
its natural scale (empirical logit for a bounded score, log for money, points and cost, as is for an Elo or an
unknown composite); every group with its own offset, gain and noise; one latent value per couple; publisher × couple,
publisher × model and couple × task-type effects; Student-t noise; early-access runs at a third of the weight;
Gibbs sampling, four chains in parallel, cached by a fingerprint of the data. Quality is shown as the mean predicted
score over the benchmark panel relative to the reference couple, cost as the cost on a task of typical size; the
band is what one new benchmark would report. The reference couple is a display choice.

**What goes.** Score ratios and their weighted median, the √n rule per publisher, the ×0.5 weight of bridged
benchmarks, the 0.5→1 ladder-coverage weight and the Huber band: the model's own information weighting replaces all
of them. Also removed: `ratio-ids.md` and the no-think / default regime tables, which the page no longer showed.

**Tried and set aside.**
- Showing quality as exp(κ·θ), κ the slope at the anchor: the unit depended on the anchor (×3.4 with Haiku 4.5 as
  anchor), so relative values changed with the reference.
- Showing quality as the median, over benchmarks, of predicted score ratios: it extrapolated weak couples to the floor
  of hard benchmarks they never sat.
- Pooling the gains of groups that run the same benchmark. The gains of one benchmark do agree (about ±20 %, against
  more than an order of magnitude across benchmarks), but multiplying two priors on one gain broke the sampler's
  calibration, and pooling gains in metric units breaks the model's affine invariance. Its effect on the grids was
  0.4 % (median), 2.9 % at most. Families remain, to detect republished numbers and to count a benchmark once in the
  display panel.

**Found in the data.**
- `scfrontiercode` mixes the Sonnet 5 card's digitised `score%` with Cognition's `weighted-rubric`: the rubric score
  is a 0–100 percentage and is now read as one. A group whose metrics differ in nature now stops the build.
- `nnrlog-game` (`playable-of-2`, values written as percentages) and `forgep2` (`score/10`, values reaching 100):
  labels contradicted by their values; such groups are read as unknown scales, and the build reports them.
- 46 score rows were counted twice: the same experiment reprinted in two documents, mostly Anthropic system cards
  repeating an earlier card's reference column (HLE with tools, DeepSearchQA, OSWorld). They now count once.
  Two cost rows likewise.
- Sonnet 4.6 `xhigh` is measured by one publisher, through an unverified effort mapping; a couple now needs two
  publishers to be shown.

**Review.** An agent with no context reviewed the method, the code and the data. The sampler was correct; the
display, the band (51 % of observed ratios inside it, 12 % far from the anchor) and the single-publisher couple were
not; the cost gain fixed at 1 was contradicted by the data (per-benchmark slopes 0.6–1.7); the logit clip produced
residuals of −17σ on a 7-task benchmark. All were changed as described above; the band now covers 82 % (quality)
and 80 % (cost) of the observed ratios.

**What moved, same data** (Sonnet 5.5 included). Quality, then cost, relative to Opus 5 @high:

| Couple | Quality before | Quality after | Cost before | Cost after |
|---|---|---|---|---|
| Sonnet 5.5 `low` | 0.75 | 0.81 | 0.08 | 0.11 |
| Sonnet 5.5 `high` | 0.98 | 1.00 | 0.19 | 0.22 |
| Sonnet 5.5 `max` | 1.04 | 1.08 | 1.45 | 1.80 |
| Opus 5.5 `low` | 0.98 | 0.95 | 0.17 | 0.23 |
| Opus 5.5 `high` | 1.07 | 1.09 | 0.45 | 0.48 |
| Opus 5.5 `max` | 1.13 | 1.13 | 1.51 | 2.12 |
| Fable 5.1 `max` | 1.07 | 1.07 | 2.47 | 2.97 |
| Sonnet 5 `max` | 0.79 | 0.89 | 1.10 | 1.08 |
| Sonnet 4.6 `low` | 0.52 | 0.60 | 0.24 | 0.35 |
| Haiku 4.5 | 0.57 | 0.52 | 0.13 | 0.11 |

Sonnet 5 `max` no longer falls below its `xhigh`, and Opus 4.7 `xhigh` no longer below its `high`. One ladder
inversion appears on cost, Sonnet 4.6 `high` 0.70 > `max` 0.69, inside the band. The picks: best overall Sonnet 5.5
`xhigh` → Opus 5.5 `xhigh`; grunt work Sonnet 5.5 `medium` → `low`; everyday Opus 5.5 `low` → Sonnet 5.5 `high`;
advanced reasoning Opus 5.5 `medium` → Sonnet 5.5 `high`; cutting-edge Sonnet 5.5 `xhigh` → Opus 5.5 `high`.

**Checks** (scripts in `gen/validation/`): held-out prediction error 1.9 points (median) against 4.7 for the ratio
baseline; scale distortion on synthetic data with known truth equal to the baseline's where ratios are exact and
about half otherwise; uniform calibration ranks on both axes, with a deliberately wrong prior rejected; changing the
reference couple moves values within Monte Carlo error; removing the largest publisher moves quality by 1.9 % at
most and some costs by up to 13 %.

## Thirteenth pass: Sonnet 5.5, second salvo

Eleven Sonnet agents on narrow axes, 29 Sep 2026, a few hours after the twelfth pass: re-checks of the boards that
did not carry Sonnet 5.5 yet, what the first salvo left aside at AA, Vals and in the system card, new GitHub and
Hugging Face repos, English forums, Japanese/Chinese/Korean sites, tool vendors' blogs, a second look at the repos
already followed, and an audit of every Sonnet 5 cost for a leftover \$3/\$15 price (Vals had one).
**168 → 172 sources, 481 → 491 benchmarks, 3338 → 3435 measurements.** Sonnet 5.5 now rests on 280 measurements in
122 benchmarks from 28 sources.

- **Admitted.** AA payload fields outside the index, score only (Harvey LAB, Terminal-Bench-Science, MLCR, with the
  ladders AA has). The Sonnet 5.5 card's AutomationBench sweep (fig. 8.14.6.A, digitized, its Sonnet 5 and Opus 5.5
  points within 0.3 % of `zapierab`; costs are Anthropic's, computed from Zapier's token counts), FrontierSWE's score
  printed in the card (the board's cache is stale), computingforgeeks' k3s DevOps suite (Sonnet 5.5 `low`→`max`,
  Sonnet 5, Opus 5.5; the snippet the first salvo had seen was wrong). ramen-bench (four models × five rungs, cost
  only, Claude Code's own cost with the known 2.1.283 caveat), MineBench's voxel arena (Elo, measured cost for eight
  of twelve Claude models), note.com nantokanaru_log (Sonnet 5.5 vs Opus 5.5, `high`) and tank_ai's era converter.
- **Held.** tank_ai's two blind-rank tasks (rank of 6, no cost) are kept as inactive `#` rows: a rank is ordinal, and
  the grid reads a score as higher-is-better.
- **Corrected.** `lighthouse-svg` stored a subjective rank (1 = best) as its score, so the grid read Opus 5.5's
  last place as twice Fable 5.1's second: the rank moves to `confound` and the score is left blank, as for
  Willison's ordinal SVGs. `rtk-base`'s Sonnet 5 costs are Claude Code's `total_cost_usd`, and the paper's own
  calibration (sec. 6.1) shows they sit at the \$3/\$15 "standard" rate (the \$2/\$10 "introductory" rate leaves
  +33 % unexplained): re-priced ×2/3 under the eighth-pass rule.
- **Price audit.** 99 groups with a Sonnet 5 cost and no stated price basis: no other \$3/\$15 leftover (54 confirmed
  at \$2/\$10 by code, JSON or exact arithmetic, 27 real billing, 11 without enough evidence either way). One agent read two July papers as
  proof that Sonnet 5 was actually billed \$3/\$15 until mid-July; checked at the source, neither shows it (one
  calibrates against Claude Code's own table, the other never prints the rate), so the eighth pass's reading
  stands: \$2/\$10 was the launch price, the rise to \$3/\$15 scheduled for 1 Sep was cancelled on 10 Aug. Only
  `rtk-base`, whose figures are explicitly at \$3/\$15, changes. The six new Sonnet 5 runs of the Sonnet 5.5 card
  have no stated price basis and are left as they are.
- **Found empty.** Nineteen boards re-read (ARC Prize, LMArena, Epoch, Kilo, OpenRouter, aipricing.guru, marginlab,
  Vals RSI, SEAL, LiveCodeBench, SimpleBench, Aider, Zapier, Terminal-Bench, SWE-bench and Pro, swe-rebench, DeepSWE,
  OSWorld, Sonar): none had added Sonnet 5.5 yet. Thirty-five tool vendors: availability notes or Anthropic's
  figures only (the same partner-kit sentence recurs at GitHub, Snowflake and Lovable). HN has restatements only;
  Reddit is blocked from this host and the X mirrors are down since 15 Sep. The repos already followed have not
  re-run; bug-hunt's Sonnet 5.5 replicates, ObviousBench's PR #39 and merc-bench's PR #5 are still pending.

Sonnet 5.5 (quality / cost vs Opus 5 @high): `low` 0.75 / 0.08, `medium` 0.86 / 0.08, `high` 0.98 / 0.19, `xhigh`
1.09 / 0.43, `max` 1.04 / 1.45. The frontier is Sonnet 5.5 `medium`, Opus 5.5 `low`, `medium`, Sonnet 5.5 `xhigh`, Opus
5.5 `xhigh`, `max`; the page's best value overall is now Sonnet 5.5 `xhigh`. Elsewhere Fable 5.1 `xhigh` cost
2.02 → 1.78.

## Twelfth pass: Sonnet 5.5

Sonnet 5.5 went GA on 28 Sep 2026 at the Sonnet 5 rate (\$2 / \$10 per MTok, cache read \$0.20, write \$2.50 for
5 min or \$4 for 1 h), with the five rungs `low`→`max` (`high` by default on the API, `medium` in Claude Code). Thinking
cannot be disabled: the lowest setting is `between_tools`, filed `nothink`. Five agents (Opus) searched it on
29 Sep: Anthropic's own material, AA/Vals/ARC-type boards, coding and agent boards, the repos and practitioners the
repo already follows, and the open web. **160 → 168 sources, 432 → 481 benchmarks, 2894 → 3338 measurements.**
Sonnet 5.5 rests on 247 measurements in 110 benchmarks from 23 sources.

- **Anthropic.** The launch page carries its four cost × effort charts as CSV in its payload: Terminal-Bench 4.0 joins
  `an55tb40` (the Opus 5.5 series is the same run; Sonnet 5 scores only 3–10 % there, unexplained, flagged). The
  FrontierCode, CursorBench and AA-Briefcase charts restate third-party primaries and are not ingested twice. The
  system card (148 pages) gives eight cost × effort sweeps, digitized and checked against the Opus 5.5 points already
  in the repo (≤ 0.3 % on cost): Sonnet 5.5 and Sonnet 5 join `sc55hlet`, `sc55draco`, `sc55wandr`, `sc55bcad`,
  `sc55osw`, `chartogt`/`chartogn`/`sc55chartq`; new groups for HLE without tools, OSWorld strict, BenchCAD and
  Chartography without tools. Score-only tables at `max`: SWE-bench Pro, Multilingual and Multimodal, TB-Science,
  ProgramBench, OfficeQA (and Pro), Toolathlon, GMMLU, MILU, twelve life-science evals and three health benchmarks
  (PhysicianBench and HealthBench with Sonnet 5.5's labelled ladder). OSWorld's seven unlabelled Sonnet 5.5 points
  are kept as inactive `#` rows (only `max` carries a printed score). The card's OSWorld is v2.1 (files of 10 Sep, same
  configuration as the Opus 5.5 card), so `sc55osw` is relabelled. claude.dev's hillclimbing post adds an Opus 5.5 vs
  Sonnet 5 pair at `low` (`cdhillclimb`).
- **Boards.** Artificial Analysis v4.3 (payload re-read: 252 of 253 repo rows identical) adds the whole ladder to the
  index and its ten components; the GDPval-AA and AA-Briefcase runs were on a pre-release deployment with a
  structured-output bug (launch note 3, card note 21) and are flagged early access. AA's Coding Agent Index has Sonnet
  5.5 `max` first (68.4 %, \$14.19), from an EAP endpoint, flagged. Cognition's FrontierCode JSON (both v1.1 subsets,
  five rungs; Opus 4.6 gap-filled), CursorBench 4.0 (five rungs) and LiveBench (`xhigh`, and `max` held during EAP
  per PR #59; Opus 4.6 and 4.5 gap-filled). Nothing yet on ARC Prize, LMArena, Zapier, Terminal-Bench, DeepSWE,
  swe-rebench, SWE-bench, OSWorld's board, FrontierSWE, Sonar, marginlab or aipricing.guru.
- **Vals re-read.** Twenty-one Vals boards carry Sonnet 5.5 (all at `max` but TB 2.1 at `high`; refusals fall back to
  Sonnet 5 server-side, counts in `confound`). Re-reading them showed that on 27 Sep Vals re-priced its costs while
  every score stayed put: **Sonnet 5 × 2/3 everywhere** (Vals had used \$3/\$15) and Opus 5.5 up by 2–63 %, not
  uniformly. So 24 Vals groups are rewritten from the 27–28 Sep snapshot under their existing keys (old values kept in
  `prev-cost=`/`prev-score=`), rather than added beside the old ones, which would have counted each score twice.
  Along the way: RSI Index moved to v1.1 (four campaigns), CUA-bench's Fable 5.1 cost fell from \$595.9 to \$323.8,
  the archived Vals Index v1.2 has Opus 4.7 at `high` (not `max`) and Opus 4.8 at \$7.52, ProofBench now states `max`
  for Opus 5, and missing Claude models are added (Tax Agent 4 → 10 rows). The other 26 Vals groups match.
- **Repos and practitioners already followed.** vlm-exam (six tasks, `low` and `high`), bug-hunt-bench (`xhigh`, `max`:
  57/105, above Opus 5.5 `max`, at 2.6× its cost), runebench (via OpenRouter, flagged), ObviousBench (six settings, from
  the head of the unmerged PR #39), Simon Willison's pelican (`low`→`xhigh`; `max` hit the 128k cap without an SVG and
  is omitted, as it was for Opus 5.5), Senko Rašić's three games (`xhigh`). Claude Code before 2.1.284 billed Sonnet
  5.5 on the Opus 5.5 table (about 1.2× too high): CLI-reported costs from 28 Sep are flagged.
- **New sources.** Occam bench (18 procedural tasks, three plugin arms, Sonnet 5.5 and Opus 5.5 at `medium`/`max`,
  plus Haiku 4.5 and a Sonnet 5 calibration run), KillSwitch-Bench, two note.com studies (dende2023's SLA function
  `low`→`max`; riku_techlab's relative costs against Sonnet 5), Atomic Agent, a waterslide game and a flight simulator
  (cost only), MrMerkus (saturated), Box's enterprise eval by industry (score only), CodeRabbit (Sonnet 5.5 thinking
  on/off and Sonnet 5 join the Signal group, same frozen 13 cases as the Opus 5.5 post; a 44-PR set, cost only) and
  Qiita suwa_nobu's twelve-model run (no Sonnet 5.5, taken to record it).
- **Corrections.** AA index Opus 5 `low` 40 → 39 (payload 39.35). Sonar gains six Claude models (score only but Sonnet
  5); its Opus 4.7 row held suite totals for tokens and another harness label. ObviousBench's Opus 4.6 `xhigh` row is
  removed: Inspect sent `high` (the author's audit, PR #39). bug-hunt's Opus 5.5 rows priced cache writes at the 1 h rate
  (\$8), not 5 min × 1.25 (flag fixed, costs unchanged).
- **Found empty or restated:** kingy.ai, cyberq, Vellum, orcarouter and some twenty launch articles restate
  Anthropic's, AA's or Vals' figures; arXiv has nothing yet. merc-bench's unmerged PR #5 would re-price its cache
  writes at 2×: `merc-core10` to redo once merged.

Sonnet 5.5 (quality / cost vs Opus 5 @high): `low` 0.74 / 0.08, `medium` 0.85 / 0.10, `high` 0.98 / 0.19, `xhigh`
1.09 / 0.44, `max` 1.04 / 1.54. It takes the bottom of the Pareto frontier from Haiku 4.5 (0.57 / 0.13, now dominated
by Sonnet 5.5 `low`) and its `xhigh` edges out Opus 5.5 `high` (1.07 / 0.45); the frontier is now Sonnet 5.5 `low`,
`medium`, Opus 5.5 `low`, `medium`, Sonnet 5.5 `xhigh`, Opus 5.5 `xhigh`, `max`. Its `max` rung falls below `xhigh`,
as FrontierCode, LiveBench and the card's own notes show (the ladder check flags it, left as measured). Elsewhere
Opus 5.5 `medium` 1.06 → 1.04, Sonnet 4.6 `high` 0.68 → 0.72, and Sonnet 5 `max` cost 1.29 → 1.10 (the Vals
re-pricing).

## Eleventh pass: twelve Sonnet agents, narrow axes and broad sweeps

Eight agents on narrow axes (parked leads, Hugging Face, arXiv cs.SE, arXiv cs.AI/CL/LG, Japan, China and Korea,
Western blogs, new public boards) and four broad sweeps (search queries, citation chasing, older models, task
domains), 27 Sep 2026. **138 → 160 sources, 379 → 432 benchmarks, 2772 → 2894 measurements.**

- **Boards.** SWE-bench's official Verified board (its own `#leaderboard-data` JSON, mini-SWE-agent runs with
  `instance_cost`), LMArena's agent leaderboard (median \$/task), MCPMark's legacy board, aipricing.guru's live
  cost-per-task JSON (six Claude models on 49 tasks, a rolling daily board — an earlier pass had read only its blog),
  marginlab's Claude Code tracker (daily pass rate across six Opus generations, score only), FeatherBench (seven
  Claude models; an earlier pass had rejected it on one saturated cell) and Brood War Bench (a 171-game StarCraft
  round robin; model versions inferred from the date, Sonnet's cost is the page's token estimate).
- **Papers.** VEX-Bench, EffiBench IIV, an API-vs-interface reasoning-budget study (its "low/medium/high" are
  `budget_tokens` 1024/4096/16384, filed `think-1k/4k/16k`), a requirements-quality generational sweep,
  CliffCompaction (its baselines cite other primaries, flagged), MobileCybench (Claude Code, Opus 4.8 vs Opus 5;
  refusals and early access flagged), Scoring Both Directions, a Japanese stroke-order eval, Adobe's Designer-RSI
  (eight benchmarks), FinSheet-Bench and a semantic-layer SQL study.
- **Practitioners and repos.** WhiteKUMALabo's Opus 4.6 effort × difficulty study (the two held rows gain their
  scores) and its Fable 5 vs Opus 4.8 comparison, Qiita suwa_nobu's cache-state cost sweep, NTT Data's compaction
  token counts, Claude Code Camp, jev-effort (Opus 5.5 `high` vs `max`), Simbian's cyber-defense benchmark, Box's
  per-industry Opus 5 → 5.5 accuracy, Vals' web-search board (one couple per search backend), the Terminal-Bench 2.0
  submission corpus on Hugging Face (one couple per scaffold) and retort's exp-75 (Opus 5.5 on thirteen languages
  against Opus 5).
- **Found empty:** Chinese and Korean sites (restatements of vendor numbers, or blocked), translation, tutoring and
  multilingual beyond maths. The session's WebSearch quota (200, shared by all agents) ran out mid-pass; the agents
  continued through direct APIs and fetches, and the cap is now raised for future sessions.

Opus 5.5 rests on 318 measurements in 117 benchmarks from 40 sources and still holds the frontier with Haiku 4.5:
`low` 0.98 / 0.17, `medium` 1.06 / 0.32, `high` 1.07 / 0.46, `xhigh` 1.12 / 0.75, `max` 1.13 / 1.51 (quality / cost vs
Opus 5 @high). Elsewhere no quality moves by more than 0.03 (Haiku 4.5 0.52 → 0.55); the largest cost move is Fable 5.1 `max`, 2.58 → 2.52. The ladder check still flags Sonnet 5 `xhigh` 0.87 > `max` 0.79
and Opus 4.7 `high` 0.82 > `xhigh` 0.80.

## Tenth pass: a third salvo, and the held rows re-read line by line

Eight agents (Opus, low effort) closed the gaps the ninth pass left, then three Sonnet agents turned each report's
corrections into explicit operations (delete, replace, fill) that were applied and checked for duplicate keys.
**118 → 138 sources, 272 → 379 benchmarks, 2084 → 2772 measurements.**

- **Held rows re-derived.** Every github-* group was recomputed from the committed data, every pre-eighth-pass arXiv
  paper re-read, every Vals board re-read from its payload, and the remaining leaderboards (LiveBench's CSVs,
  stet.sh, Databricks, Braintrust, Quesma, Kingy, CursorBench 3.2 via the Wayback Machine) checked. Errors fixed:
  `posttrain`'s two "Opus 4.5" rows were another vendor's model (replaced by the paper's Claude Code results);
  `skillsbench` ran in OpenHands at the highest effort and averaged two conditions into one cost (split in two, `max`);
  `slopcode` and `ceobench` held v1 values that v2 superseded; `tuabench` costs are published in its
  leaderboard JSON; several `tokens_out` columns held totals (tycho-arc3, tobench, stageclaw, predev); coderev priced
  Haiku 4.5 at the Haiku 3.5 rate; ponytail's "Opus" is Opus 4.8 with thinking off; mcptox's Opus 5 and Sonnet 5 ran
  with adaptive thinking (`default`, not `nothink`); vibe-openscad's "bare" runs send no effort (`default`); ctala is a
  rolling board at provider defaults (replaced); Databricks' Opus 4.8 is `high` and its Sonnet 5 cost was at \$3/\$15
  (re-priced). **Braintrust's T25/T50 are context sizes (25K/50K tokens), not thinking budgets**: the group is split
  by context size at `default`, and the `EMAP` alias in `gen/build.py` is gone. Refs pinned to commits throughout
  (tilth to the commit before its author withdrew the table on 19 Sep, flagged).
- **Rows the held sources already had.** retort (Opus 5 ladders from exp-55, Sonnet 5 vs 4.6 vs Opus 4.8, Opus 4.7 vs
  4.8, Fable 5.1), vibe-openscad, ObviousBench and vlm-exam ladders, retroboard's other cells, runebench and bug-hunt
  rungs, Vals boards never ingested (Code Migration, HLAB, ProgramBench, ProofBench, Time Horizon, CUA-bench,
  Terminal-Bench 2.0, Public Benefits v1, AIME, CaseLaw, MedQA, Claude Code harness variants), and LiveBench rows.
- **New sources.** The Rails team's *Agents on Rails* (two stages, public raw runs), Endor Labs' Agent Security
  League, Snorkel's Terminal-Bench+, CodeRabbit's review evals, George Liu's 10-prompt Claude Code suite (Opus 5 vs
  Opus 5.5 at five rungs), Synthorai and CyberQ (Opus 5.5 ladders, list-price estimates), Qiita's coding set, and ten
  repositories: claude-effort-bench, low-or-bust, the Dealwatch orchestration benchmark, claude-code-eco,
  effortmining, wook3024's bench, forge-benchmark, an Opus 5.5 effort comparison, effort-pick, and the weather-card
  benchmark (147 token rows across Claude Code and three Cursor harnesses). Haiku 4.5 runs sent a nominal effort are
  filed `req-<rung>`; runs with a second configuration of the same couple get their own group.
- **Not reached:** Reddit and X (every route blocked), GitLab and Kaggle search (auth), aipricing.guru and
  Brood War Bench (not opened). Unverified and flagged: `vulcanbench3` (values not found in the repo), aa-index4 (no
  archived snapshot matches), the old 24-benchmark Vals Index.

**What moved.** Opus 5.5 rests on 295 measurements in 96 benchmarks from 36 sources, and still holds the whole
frontier with Haiku 4.5 (quality / cost vs Opus 5 @high): `low` 0.98 / 0.17, `medium` 1.06 / 0.32, `high` 1.07 /
0.45, `xhigh` 1.12 / 0.75, `max` 1.13 / 1.51. The older models move most: Haiku 4.5 0.64 → 0.52 in quality, Sonnet 5
up by 0.04–0.10 per rung, Opus 4.8 up by 0.05. The ladder check flags Sonnet 5 `xhigh` 0.87 > `max` 0.79 and Opus
4.7 `high` 0.82 > `xhigh` 0.80.

## Ninth pass: a second salvo, mostly verification

Eight agents (Opus, low effort), 27 Sep 2026: four re-checked held rows against their primaries, four searched
where the eighth pass could not reach. **109 → 118 sources, 250 → 272 benchmarks, 1956 → 2084 measurements.**

- **Anthropic's own pages.** The docs page *Optimizing for cost and intelligence* carries dated internal effort
  sweeps: SWE-bench Pro (478-problem subset, Opus 5.5 low→xhigh), DeepResearch Bench II, a 370-task coding set,
  four Fable 5 research benchmarks and a corpus-defect sweep (38 rows). The claude.dev post *Spending your effort*
  gives Terminal-Bench 3.0 pass rates against median tokens per attempt, from the page's embedded data (74 tasks)
  and from its effort-curve SVG (70 tasks, with Opus 5.5); unlabelled rungs placed by order are flagged, and Opus 5's
  second "max" run (raw `max`, 52.2 %) is left out in favour of the author's effort-120 run. The cookbook's
  cost-optimization notebook adds Opus 5 and Sonnet 5 × low/medium/high (mostly saturated). All three count as one
  publisher with the system cards (`PUBLISHER` in `gen/build.py`), so √n still treats Anthropic as one source.
- **Boards.** The OSWorld 2.0 board's `estimatedCostUsd` is the 108-task suite total — divided by 108 it reproduces
  the held arXiv rows exactly; its Opus 5 ladders (two releases, output tokens) and two step-budget groups join.
  Scale's SWE-Bench Pro V2 (read from the Wayback Machine; the live page is a bot wall), Surface-Evolver-Bench,
  LLMConfBench (arXiv 2609.20666), a Vectorise MCP effort test and a Copilot SVG run from Reddit.
- **Corrections.** OpenRouter's τ²-bench and GPQA boards are rolling means, so all 13 held rows had drifted; they
  are replaced by the 27 Sep snapshot, and Fable 5.1, Opus 5.5 and Sonnet 4.6 join. harnesseval's author re-judged
  the report after 7 Sep: the seven held rows give way to the six current cells (its Opus 5 `xhigh` is gone). Also:
  swe-rebench cache shares filled in, Kilo Bench identified as Terminal-Bench 2.0 under Kilo, renchris scores 7
  briefs (not 9), PetriBench's Haiku 4.5 run, renchris's Fable 5.1 `max`, PlayCode's Opus 5.5 `max`.
- **Verified unchanged:** every Opus 5.5-card number printed in the text against its held row (ArXivMath,
  FrontierCode, Chartography, OSWorld), all arXiv groups checked for newer versions (none adds Opus 5.5 or Fable
  5.1), swe-rebench, Kilo, PlayCode. No Sonnet 5 row beyond the eighth pass's five groups needed re-pricing.
- **Not reached:** LiveBench (JS shell), stet.sh, Snowflake, Databricks, Quesma, Kingy, CursorBench 3.x, the older AA
  groups; Reddit beyond one search (login wall), X, note.com, Qiita, Chinese and Korean sites; GitLab, Kaggle.

Opus 5.5 now rests on 233 measurements in 71 benchmarks from 27 sources (quality / cost vs Opus 5 @high): `low`
0.91 / 0.17, `medium` 1.05 / 0.32, `high` 1.07 / 0.44, `xhigh` 1.13 / 0.80, `max` 1.13 / 1.49. `xhigh` is again its
highest-quality rung, and `low` the best value overall. The ladder check flags Sonnet 5 (`high` 0.78 > `xhigh` 0.77 >
`max` 0.76) and Opus 4.7 (`high` 0.77 > `xhigh` 0.76).

## Re-anchoring on Opus 5 @high

The scale had been pinned to **Opus 4.8 @medium** since the first snapshot, deliberately, so numbers stayed
comparable across releases. Three releases later that couple had become a poor reference: it sat low on the
quality axis (the whole frontier read 1.1–1.5×) and only **28 of 114** benchmarks measure it, so three quarters of
them were normalised through bridges, at half weight. **Opus 5 @high** is measured directly by **60 of 114** — the
best-linked couple in the dataset once Opus 4.7 and Sonnet 4.6 are set aside — and it is Opus 5's default effort,
the baseline Anthropic's own "40 % cheaper" claim for Opus 5.5 is stated against. The frontier now reads
0.87–1.13× in quality.

This is **not a pure rescale**. Which benchmarks are anchored directly, and which are bridged, changes with the
anchor, so the weights change and a few relations move: Opus 4.8 @medium now costs 0.57× Opus 5 @high, where the old
grid had the inverse at 1.55× (0.65×). The residual Opus 5 `xhigh` > `max` quality inversion disappears (both
1.02×) — a side effect, not a goal. The mean cost band is 2.103×. Every anchor mention on the page is generated
from one setting (`GRID_ANCHOR` in `gen/build.py`), so a future move is one line. Sections of this README written
before this change quote the old scale.

The page also gained two display switches, both off by default: **Older models** (Opus 4.7, Sonnet 4.6 — hidden
from every view and fit, exactly as if unmeasured; neither touches the frontier today) and **Tier bands** on the
Quality-vs-Cost chart (each band is the quality range where one usage tier's window outweighs its neighbours;
edges sit midway, in the chart's dilated metric, between adjacent tier centres, and follow the tier sliders).

## Eighth pass: the open network, and a price that never rose

Four parallel sweeps again (leaderboards and vendor boards, preprints, practitioners, public code), 27 Sep 2026,
this time with an open network. Everything found was taken, with its caveats written into `confound` rather than
used as a reason to leave it out: **93 → 109 sources, 199 → 250 benchmarks, 1494 → 1956 measurements**.

- **Leaderboards.** ARC Prize's `evaluations.json` carries Opus 5.5's full ladder (ARC-AGI-2: 70.1 / 87.5 / 93.3 /
  92.5 / 91.7 % for \$0.24 → \$1.85; ARC-AGI-1 scores ≥ 97.5 % flagged `gen5-saturated`, as the held Opus 5 and
  Fable 5 rows already were). **Artificial Analysis was under-read a third time**: each model payload holds score and
  cost per task for all ten index components, and the repo had two; the other seven (Terminal-Bench 4.0, SciCode,
  HLE, GDP-PDF, CritPt, AA-LCR, Omniscience) join as full ladders for Opus 5.5, Opus 5, Fable 5.1 and Sonnet 5, and
  AA-Briefcase is re-read whole (its Elo was re-anchored). AA's new Coding Agent Index (Claude Code harness, max
  only) adds three couples. **DeepSWE**'s live JSON (Datacurve) is the primary behind the Opus 5 card's figure, so it
  replaces the 20 digitized `sc5deepswe` rows; its Opus 5 series is a later run. Vals AI: CyberBench, SkillsBench, a
  whole re-read of EMB (8 Claude entries, not 2), two missed entries, and ten benchmarks never ingested (LiveCodeBench,
  MMMU, CorpFin, LegalBench, MortgageTax, TaxEval, Multimodal Index, SWE-bench, GPQA and MMLU-Pro, the last two cost
  only). Zapier re-published Opus 5.5's ladder with its fallback made explicit (+1 to +2.5 pt, +8 to +13 % cost):
  the new values replace the old. Sonar adds Opus 4.7 `high`. The Opus 5.5 launch page embeds its Terminal-Bench 4.0
  chart as data: three full ladders (`an55tb40`), production safeguards on.
- **Preprints** (eleven): PetriBench, a SWE-bench effort campaign (arXiv 2608.01347), FrontierFinance, OSWorld-Pro,
  τ^τ-Bench, ProgramDistill-300, GameLogicBench, RuBench, Kimi Code Bench 2.0, FuzzingBrain-Bench and BVB (its
  LiteLLM effort mapping and \$3-per-scene cap are flagged). None yet measures Opus 5.5 or Fable 5.1 with cost.
- **Practitioners.** nnakapa's QCD labs on Zenn (three PostgreSQL tasks, ten runs each, CLI-reconciled cost, a
  hidden-test gate): eight ladders across Opus 5, Fable 5.1, Sonnet 5, Opus 4.8, Opus 4.7 and Fable 5, two of them in
  GitHub Copilot CLI. The held `zenn-qcd` rows (lab #27) had the *medium* rung's scores on the *low* rung's costs
  and missed half the ladder; replaced. Simon Willison's pelican gist has Opus 5.5 `low`→`xhigh` token counts.
- **Public code.** MERC (six models × five rungs, n = 2, scores saturated → cost only), renchris's code-review corpus
  (Opus 5.5 low→max with Opus 5 @high in the same session; Fable 5.1 low→xhigh), kaybenleroll's plan review,
  VulcanBench's Fable 5.1 and Opus 5 ladders (fallback share flagged), RampNet's Fable legs, CalorieBench (effort
  `high` sent without thinking, so filed under `nothink`), and `retort49`'s Opus 4.8 and Opus 4.7 ladders, which sat in
  the same database. Corrections: `retort49`'s `tokens_out` held *total* tokens (blanked), RampNet's Sonnet 5 `low` F1
  follows the author's 18 Aug correction (45.6 → 46.3), bug-hunt-bench's Opus 5.5 rows carry the author's own
  not-comparable note, and the seventh pass's refs are pinned to commits.

**Sonnet 5's price.** The \$2/\$10 launch price was announced as introductory until 31 Aug, then \$3/\$15. On 10 Aug
2026 Anthropic made \$2/\$10 permanent. Some producers had already switched to \$3/\$15: both September system cards
(the Fable 5.1 card's Chartography and, read off the figure, the Opus 5.5 card's, whose Sonnet 5 points sit on the
same costs), MERC's runner and the PetriBench token pricing. Those Sonnet 5 costs are re-priced ×2/3 and flagged
(`chartogt`, `chartogn`, `sc55bcad`, `merc-core10`, `petribench`), and `PRICE_OUT` in `gen/build.py` is corrected.
Artificial Analysis, LiteLLM, vercel/eve and every source that states its rate use \$2/\$10.

**What moved.** Opus 5.5 went from 134 measurements in 48 benchmarks to 218 in 67. Its quality falls at both ends
(`low` 0.98 → 0.91, `max` 1.17 → 1.13) and its cost at `high` drops (0.51 → 0.44), so `high` becomes the best value
overall (1.07× for 0.44×) and `max` barely improves on `xhigh`. No single block does it at the ends: removing any
one of the leaderboard, preprint, practitioner, code or launch-page blocks leaves `low` and `max` within 0.01 (the
public-code block alone accounts for `medium`'s 1.06 → 1.02 in that test, before AA's components); the new independent
Opus 5.5 ladders (ARC-AGI-2, Terminal-Bench 4.0, AA's components, renchris) often peak at `high` or `xhigh`. The
effort-ladder check now flags Sonnet 5 `high` 0.78 > `xhigh` 0.74 and Opus 4.7 `high` 0.77 > `xhigh` 0.76; Opus 5's
`xhigh` > `max` inversion is gone.

## Seventh pass: a closed network, and two public repos

Four parallel sweeps (leaderboards, preprints, public code, practitioners), 27 Sep 2026. **This environment's
network policy denied almost every host the pass needed** — arxiv.org, huggingface.co, cognition.com, cursor.com,
vals.ai, artificialanalysis.ai, arcprize.org, tbench.ai, reddit, HN, Medium, dev.to — leaving GitHub and
anthropic.com. Three of the four axes could only read search-engine snippets, which fails the read-the-primary
rule, so they admitted nothing. Leads parked for an open-network re-run: ARC Prize's Opus 5.5 `high` rows
(ARC-AGI-1 98.5 % / \$0.16, ARC-AGI-2 93.3 % / \$0.41 per snippets), Artificial Analysis's new *Coding Agent
Index* (Claude Code harness), two synthorai posts on dev.to claiming measured Opus 5.5 vs Opus 5 runs,
arXiv 2608.02358 (ScrambleToolBench, a Sonnet 5 effort sweep), and vercel/eve, whose CI now targets Opus 5.5
but whose results file does not yet. No Claude model has shipped since Opus 5.5.

The public-code axis re-cloned the known repositories and admitted two, both Opus 5.5 full ladders:

- **retort experiment 74** (`retort74`, `retort74go`): one REST-CRUD task in Python and in Go, n = 3 per rung,
  cost from the CLI's own total. Requirement coverage is 1.0 in all 36 runs, so cost only, as for `retort49`.
  This reverses the second and fifth passes, which dropped exp-74 on both axes under the fyve rule; it is kept
  as its own group (CLI 2.1.280, against 2.1.197 for `retort49`).
  The ladder is a cliff, not a ramp: Python `high` → `xhigh` is 3.9×, `xhigh` → `max` another 3.4×.
- **VulcanBench CII v4** (`vulcanbench-ciiv4`): 23 legacy binary-parity tasks in Claude Code 2.1.280. The rows
  the sweep proposed were wrong in an instructive way: it averaged the harness's `api_equivalent_cost_usd`,
  which prices the token counts at the *requested* model's rates without the cache-write premium (so it differs
  even at `low`, where no fallback fired: \$2.01 against \$1.70) — and the fallback was on. The author's own table
  prices each run from Claude Code's reported total, which includes them; that table is what was taken
  (\$1.70 → \$8.75 per task, monotone). The confound stays on every row: the share of replies written by
  Opus 4.8 climbs with effort, 0 % at `low` to 48 % at `max`, so the upper rungs are a blend. The same card's
  Fable 5.1 ladder was left out — it is judged under an older protocol (v3.4 against v3.15) and priced from a
  different ledger, so it is not a matched-config comparison.

Opus 5.5 `max` cost moves 1.34× → 1.42×; mean cost band 2.303× → 2.23×. Nothing else moves by more than 0.02.

## Opus 5.5, in one line

Opus 5.5 (released 22 Sep 2026, \$4/\$20 per MTok, cache reads \$0.20) **holds the Pareto frontier** with all five
rungs; the only other point on it is Haiku 4.5 (0.11× for 0.64×), cheaper than Opus 5.5 `low` but far below it in
quality. On the current scale (Opus 5 @high = 1.00) its `high` (quality 1.07×, cost 0.44×) beats Fable 5.1 at `max`
(1.09× for 2.70×) within 0.02 in quality for a sixth of the cost, its default `medium` (1.04× for 0.32×) beats Opus 5's
default `high` for a third of its cost, and `max` (1.13× at 1.49×) now adds almost nothing over `xhigh` (1.12× at 0.78×).

| Opus 5.5 (Opus 5 @high = 1.00) | low | medium | high | xhigh | max |
|---|---|---|---|---|---|
| relative cost | 0.17 | 0.32 | 0.44 | 0.78 | 1.49 |
| relative quality | 0.91 | 1.04 | 1.07 | 1.12 | 1.13 |

These values follow the √n per-source weighting (see *Diminishing returns per source*, below). After the eighth pass
Opus 5.5 rests on **218 measurements in 67 benchmarks from 24 sources**.

**Where the numbers come from.** 95 rows across 22 groups, one day after launch. Independent primaries
already carry it: **Cognition's FrontierCode** JSON (both v1.1 subsets — the card's figures 8.4.A/B are read
straight from it, and its medium/max scores match the card's text to 0.05 pt), **Cursor's CursorBench 4.0**
table (Cursor now publishes Opus 5.5's cost itself), **Zapier AutomationBench 1.0.6**, **Artificial
Analysis** (full low→max ladder on the v4.3 index, same build as the rows already held — every existing cost
matches to the cent) — plus its per-evaluation GDPval-AA and AutomationBench-AA ladders —, the **Vals Index**
and Vals' **Terminal-Bench 2.1** (at `high`), **FrontierSWE** (62.33 for \$98.87 a run at `max`), and
**Sonar**'s Java leaderboard, whose metrics JSON carries measured tokens and pass rate on 4,444 tasks for Opus 5.5
at `medium` and `high` beside Opus 5 and Opus 4.8 at `high` (costed at list price, no cache: single-shot
generation). The remaining 55 rows are ten effort sweeps digitized from the
system card, all but three with scores printed on the chart and cross-checked to ≤ 0.07 pt by the y-axis fit:
HLE with and without tools, **ArXivMath** with and without tools, DRACO, **WANDR**, OSWorld 2.0, **BenchCAD**
and Chartography. Two markers hidden under another series were recovered from their visible fragment and flagged.

**Three join decisions.** HLE-without-tools in this card is the *same run* as the Fable 5.1 card's (identical
costs and scores for Opus 5 and Fable 5.1), so Opus 5.5 joins `scf51hlen` rather than opening a second group.
HLE-with-tools, DRACO and OSWorld differ from their Fable 5.1-card namesakes and are new runs. Chartography is
the awkward one: the costs match the Fable 5.1 card to < 0.5 % — the same transcripts — but the scores were
**re-graded** (Fable 5.1 no-tools `low` 33.8 → 36.6). Opus 5.5's costs therefore go into `chartogt`/`chartogn`,
where they meet the rest of that run's costs, and the re-graded scores form a quality-only group
(`sc55chartq`); nothing is counted twice and no two gradings are mixed.

**Under-read sources, again.** Zapier's page bundle carries **every** Claude model's effort ladder, and the
repo had taken three; Opus 4.8 (then the anchor model), Opus 4.7, Sonnet 5, Sonnet 4.6 and Haiku 4.5 join
`zapierab` — except Haiku 4.5's *score*, 0.46 % (3 of 657 tasks): a metric at its floor cannot segment models any
more than a saturated one can, so it is left blank and the cost kept, the rule already applied to saturated
harnesses (it would otherwise have dragged Haiku's quality from 0.52× to 0.16×). Artificial Analysis likewise carried Sonnet 5's full ladder plus Opus 4.8 and Sonnet 4.6 at max
on the same v4.3 build, and its per-evaluation data (cost = `weightedCostPerTask` ÷ the eval's weight, which
reproduces every stored cost to the cent) fills GDPval-AA and AutomationBench-AA from 9 rows to 46. GDPval's Elo
is re-anchored whenever a model joins (Opus 5 `max` 1735 → 1708), so that group is re-read whole from one
snapshot — which matches the Opus 5.5 card's table (1846 / 1735 / 1708) — rather than mixed. One conflict is recorded, not resolved: Zapier's board now shows Opus 5 `max` at
**\$3.05**, while the Opus 5.5 card plots the same release at \$1.27 — a jump no neighbouring rung supports.
The \$1.27 row is kept and annotated.

**Second pass, same day (four Sonnet agents: leaderboards, preprints, public code, forums — foreign-language sites
included, since they had more hours since launch).** Opus 5.5 now rests on **117 rows in 34 groups from 13 sources**.
Admitted after re-checking each primary: four public benchmark repos that added Opus 5.5 within hours —
**bug-hunt-bench** (four rungs, three replicates each; tokens and cost re-derived from the per-arm metrics to the
cent), **vlm-exam** (low/high), **ObviousBench** (full ladder; the agent had shifted the scores one rung, caught
against the `strict_pass3_accuracy` column the existing rows use) and **LiveBench** (max/xhigh, cost only as
before); six **Vals AI** benchmarks read from their payloads with `compute_effort: max` on every Claude entry —
Terminal-Bench 4.0 (Opus 5.5 had 30 of 198 attempts served by the fallback model, flagged), Vibe Code Bench
(now eight models), MedCode, SAGE, BioMysteryBench, Terminal-Bench-Science and SRE-Bench (which is binary reverse
engineering, not site reliability); and a **Qiita** write-up by Takuya that ran Opus 5.5 at medium and high beside
Opus 5 and Fable 5.1 on 19 reasoning questions × 3 runs in Claude Code, costs re-derived from recorded tokens. Its
per-question cost covers all 19 questions while the article's headline accuracy covers only the 9 hard ones, so
the combined accuracy (57 runs) is used to keep cost and score on the same task.

Rejected in that pass, beyond the general run of launch re-writes: **runebench** (its "opus55" runs are dated
18 Sep, four days before release — an early-access checkpoint, not verifiably the shipped model), **retort** exp-74
and Qiita's coding set (quality saturated at 100 %: a task that cannot separate the rungs is dropped on both axes,
the rule the fyve withdrawal set), **Classmethod** (one run per rung, no score, a non-monotone cost ladder),
**CodeRabbit** and an HN comment (no cost, or no quality), **Zenn** "ultracode" (a 16-agent swarm against a solo
agent), Vals **programbench** (every model at the floor) and **Code-Migration** (two inconsistent data blocks in
one payload). No preprint yet measures more than one effort rung of any recent Claude model, and the Chinese,
Japanese, Korean and European leaderboards publish no per-effort cost. Mean cost band now 2.155×.

The effort-ladder check's whitelist matched the documented Sonnet 4.6 `high` > `max` dip by its printed *values*,
so the re-anchoring silently un-whitelisted it; it now matches on model and rungs.

**Third pass (four Sonnet agents, 06:11 UTC).** Admitted after re-checking each payload: eight more **Vals AI**
benchmarks — Finance Agent v2, Legal Research, MedScribe, Tax Agent, Public Benefits v1.1, Vibe Code Bench 1-100
(Opus 5.5 at `xhigh` there), IOI and MysteryMechanism — read entry by entry with each model's own
`compute_effort`; Haiku 4.5 enters only where Vals ran its default configuration (Public Benefits), not its
"thinking" variant. Opus 5.5 now rests on **125 rows in 42 groups from 13 sources**. Rejected: a second read of
Cognition's v1.1 main subset (the same run as `fcodemain`, only a different score column), APEX-Accounting
(one model at one effort under four dollar caps, three of them nominal), KernelBench-CUDA (pre-release runs,
resumed sessions, inconsistent token fields), Vals ProofBench (saturated) and a round of forum posts with no
measurement. Mean cost band 2.164×.

**Two open questions, flagged rather than decided** (both since settled, below). *Early-access runs:* this morning's rule "an Opus 5.5 run
dated before 22 Sep is early access, reject" is not tenable as written — LiveBench's two rows say so explicitly
(runs of 19 Sep, "held back while the model was in EAP") and Sonar's `high` run is timestamped 21 Sep, but every
launch-day number (the system card, Cursor, Cognition, Zapier, Artificial Analysis, Vals, FrontierSWE) necessarily
comes from pre-release evaluation too. The three explicitly dated rows carry an `EAP-run` flag and stay in; runebench,
rejected on that ground alone, stays out until the rule is settled. *Source concentration:* Vals AI now supplies
15 of the groups that measure Opus 5.5 at `max`. Each is a single-rung, bridged benchmark (weight ×0.25 under the
ladder and bridge factors), but together they are the largest block behind that cell.

**Early-access rule, settled.** A run that its source dates before the model's public release carries an
`EAP-run` flag and counts for **a third** of a source in the weighted median (`EAPW = 1/3` in `ratio_grid`),
rather than being rejected. Launch-day numbers that carry no explicit pre-release date (system card, vendor
leaderboards) are not flagged. That lets **runebench** back in: Opus 5.5 at `medium` (API default, set in its run
script) and `xhigh`, both run on 18 Sep (per `jobName`), with cost and tokens summed from `tokenUsage` over the
16 skills and matching the repo's own totals. Five rows are now flagged (LiveBench ×2, Sonar `high`, runebench ×2).
Effect on Opus 5.5: cost `high` 0.41 → 0.39, `xhigh` 0.64 → 0.67; quality unchanged.

**Diminishing returns per source (method change).** Each measurement used to vote in the weighted median with a
weight that counted the sources measuring it, so a publisher with many benchmarks voted many times: behind Opus 5.5,
the Anthropic system card held 9 of the 18–22 measurements at every rung from `low` to `xhigh`, and Vals AI 15 of the
35 at `max`. Now a source with **n** measurements of a couple weighs **√n** in total, shared equally among them
(1 → 1, 4 → 2, 16 → 4), and every measurement keeps its own vote. √n is the usual scaling for n correlated
measurements: a lab with one harness brings more than one data point, but not n independent ones. Two alternatives
were simulated and set aside: merging each source into a single vote first (a lone one-benchmark source then weighed
as much as a 17-benchmark lab, and the median swung with which sources happened to measure each rung — five
effort-ladder inversions), and a log curve capped at 2 (too harsh on the large sources). A source is a
**publisher**: Anthropic's launch-blog chart (`anthropic-chart`) and its system cards (`anthropic-syscard`) are one
source. This settles the source-concentration question above.

Effect: Opus 5.5 costs more at its low rungs (0.07 → 0.11 at `low`, 0.24 → 0.32 at `medium`) — the system card, which
showed it cheapest there, no longer outweighs everyone — and scores higher everywhere; `max` is no longer dominated.
Two effort-ladder inversions remain and are left as measured: Opus 5 quality `xhigh` > `max` (1.03 > 1.02) and
Sonnet 5 quality `high` > `xhigh` (0.79 > 0.72). Sonnet 4.6's documented `high` > `max` dip no longer occurs.

**Tier windows become half bells.** A tier's window used to be a full Gaussian around its target quality q\*, so a
couple *above* the target was penalised as hard as one below: with Haiku 4.5 on the frontier, the bottom tier sat
exactly on it and picked it over Opus 5.5 `low`, which costs barely more for far more quality. Now a couple below q\*
is penalised as before, while one at or above it clears the bar and earns a small bonus that saturates fast —
1 + 0.2·(1 − e^(−Δ/(σ/2))), at most +20 % — so being better never hurts. The tier bands follow: each runs from its
tier's q\* to the next one's. Tier bands are now also available on the Pareto chart.

**Page header.** It said "95 independent measurement sources" while counting benchmarks; it now reads
**93 sources · 196 benchmarks · 1479 measurements** (current models, after the fifth pass). The `xhigh` rung is capitalised `xHigh`.

**Fourth pass (ten Haiku agents), restricted to publications at least 30 minutes after the announcement
(22 Sep 2026, 16:31 UTC): nothing admitted.** Leaderboards, code and agentic boards, GitHub, Hugging Face, arXiv,
and Chinese, Japanese/Korean, European and English-language sites were searched. What surfaced was already held
(Sonar, VLM Exam, ObviousBench, BugHuntBench, Qiita Takuya, Vals), re-cited Anthropic or Artificial Analysis figures
(Vellum, Kingy AI, Habr, pragma-code, GeekNews, note.com posts), had saturated scores (llm-challenges 100/100,
FeatherBench 28/28), or measured cost without a per-effort split (CodeRabbit, explainx, dev.to).

**Fifth pass (four Sonnet agents, then a wider second round on lesser-known sites): two new sources, one new
benchmark, one new rung — 32 measurements.** Admitted after reading each raw page or file: **Playcode**'s one-shot
MacBook SVG benchmark (19 measurements: high/xhigh/max for seven grid models, provider-billed cost, quality ordinal so
cost only; Opus 5.5 `max` left out — it spent its whole 128K output ceiling and returned nothing, a censored cost —
and Sonnet 4.6 `xhigh`, which the API rejected); **Senko Rašić**'s vibecode games (6 measurements: flight sim, voxel
and RTS, Opus 5.5 vs Opus 5 at `xhigh`, Claude-Code-reported cost, cost only); **Vals AI's RSI Index** (6
measurements, six Claude models at `max`, cost = sum of the five campaign costs, which reproduces the board's own
profile totals; the board is dated 21 Sep, so the Opus 5.5 row counts as early access); and **bug-hunt-bench**'s new
Opus 5.5 `low` rung (mean of 3, same method as its four other rungs). Rejected: Vercel's next-evals-oss (four models
at 30/31, and older models measured on 23 of the 31 tasks), nuxt-evals (no effort), retort exp-74 (saturated, as
before), Qiita Takuya's coding set (100 %), aipricing.guru (49/49), llm-stats and OpenRouter (no per-effort split), an
HN review comparison with no effort stated, and a round of re-cited launch figures across Japanese, Chinese, Korean
and European sites. Effect on Opus 5.5: `low` 0.11 → 0.13 in cost and 0.95 → 0.98 in quality (bug-hunt's new rung),
which brings Haiku 4.5 back onto the frontier.

**Rejected, one day in:** CodeRabbit (a token delta against a baseline, no cost, no per-rung tokens), Kingy AI and
most launch write-ups (they re-cite Anthropic, AA or Cursor), Simon Willison's pelican (only the failed `max` run —
128 k tokens, \$2.56, no answer — carries numbers), Kilo (effort undocumented). ARC Prize, Terminal-Bench 4.0,
Epoch AI and OpenRouter have no Opus 5.5 cost yet.

**A method change: weight by ladder coverage.** Without it, Opus 5.5's quality came out *higher* at `xhigh`
(1.43) than at `max` (1.39), although `max` wins in 13 of the 14 benchmarks that measure both. The cause was
structural: the Vals Index measures `max` only, so it entered one cell's median and not its neighbour's. Each
benchmark's weight for a model is now multiplied by how much of that model's effort ladder it sweeps —
**×0.5 for a single rung, rising linearly to ×1 for the full ladder**. A sweep carries within-model
information that a one-rung leaderboard entry does not. The factor was set on that principle, not tuned
against the symptom: on the old data it moves the mean cost band by 0.2 % (1.828× → 1.831×). One residual
inversion is left as the data give it — **Opus 5 quality `xhigh` 1.27 vs `max` 1.26**, within noise, with
`max` ahead in 25 of the 37 benchmarks measuring both.

**The bands widened, and that is the expected direction.** Mean cost band 1.831× → 2.071× (1.964× leaving
Opus 5.5 out; both on the old Opus 4.8 @medium scale). Opus 5.5 is wide at the bottom of its ladder — its `low` band
spans 4.6× (0.05–0.23): the benchmarks disagree most about how cheap its cheapest rung is — and the new Zapier and AA ladders widen
Sonnet 5 and Haiku 4.5, whose cost cells had rested on fewer, more agreeable sources.

## Fable 5.1, in one line

Fable 5.1 is the first release that moves the frontier **down and to the right at once**: it holds five of the
eight Pareto-frontier couples — **all five of its rungs are on the frontier** — and it owns everything above
quality 0.73×. Its `low` (quality 1.11×, cost 0.66×) beats Fable 5 at `max` (1.19× for 4.81×) on
quality-per-dollar by a wide margin, and costs a third of the Opus 4.8 anchor it is measured against. Its
price per token is unchanged from Fable 5 — the whole gain is fewer tokens for the same work, plus a 75 % cut
on cache reads.

Where it does *not* win is the top of its own ladder: `xhigh` and `max` cost 2.52× and 3.70× for 1.24× and
1.26× quality, so the usual advice inverts — on Fable 5.1 the cheap rungs are the interesting ones.

## A pricing fact that affects rows across the repo

Three independent repositories reconcile, to the cent, on the same finding: **Claude Code runs bill the
one-hour cache-write bucket at 2× input** — \$20/MTok on Fable 5.1, \$10/MTok on Opus 5 — not the five-minute
1.25× rate. `tsumegobench` reconciles four of five runs exactly on that basis; `harnesseval`'s committed
`costUSD` values reconcile exactly at \$20/MTok and come out ~28 % low at \$12.50; and it is the documented
mechanism behind `runebench`'s own admitted 12–15 % undercount on two Opus 5 cells. Any figure elsewhere that
prices a Claude Code run at 1.25 × cache-write is low by roughly 10–15 %. Fable 5.1's cache **read** is
confirmed at \$0.25/MTok in all three.

This does not change what the repo stores — the numbers here are taken as each source publishes them — but it
explains a slice of the spread between sources, and it is why `runebench`'s two mispriced Opus 5 cells were
omitted rather than silently corrected: the `cacheWriteTokens` needed to fix them are never committed.

## Sixth pass: a source the repo already had, read only a third of the way

The most valuable thing this pass found was not new. `cognition.com/data/frontiercode-leaderboard/data.json`
has been in the repo since the third scan, and it publishes **two board versions × eight Claude models × five
effort rungs × two task subsets**. The repo had taken three models. Filling that in adds Opus 4.8, Sonnet 5,
Opus 4.7 and Sonnet 4.6 to both v1.1 subsets, and opens the v1 extended subset as a group of its own.

The structural win is the anchor. `fcodemain` and `scf51fcode` had no Opus 4.8 @medium, so both were *bridged*
groups — anchored indirectly through shared couples and down-weighted ×0.5. They now carry the anchor
directly, at full weight.

It also settled a double-count. `scfrontiercode` was digitized off the Sonnet 5 card's p117 chart, and it **is**
FrontierCode v1 main: across the ten Opus 4.8 and Sonnet 4.6 couples the scores agree with the primary to
within 0.03 points, which no chart-reading produces by chance. The costs do not agree nearly as well — 0.2–3.4 %
on Fable 5 and Opus 4.8, but **8–11 % on Sonnet 4.6**, whose points sit exactly where a log x-axis compresses
hardest. Those thirteen rows are replaced by the primaries and re-attributed to Cognition. Sonnet 5 stays from
the card, which is the only place it was run on that suite.

| | before | after |
|---|---|---|
| mean cost band | 2.016× | **1.811×** |
| Sonnet 4.6 `low` | 3.36× | **1.19×** |
| Sonnet 4.6 `medium` | 1.83× | **1.08×** |
| Sonnet 4.6 `max` | 2.33× | 1.89× |
| Opus 4.7 `xhigh` | 1.53× | **1.16×** |
| Sonnet 5 `max` | 3.48× | 3.37× |

Two boards were also read from their own payloads rather than their rendered pages: **CursorBench 4.0**, a
harder suite shipped 10 Sep on which Fable 5.1 at `max` falls from 73.4 % to 51.8 % (the fifteen Claude points
are in the chart's `aria-label` attributes), and the four missing **Terminal-Bench 4.0** effort rungs, which
also yielded exact figures for two rows the repo stored rounded to two significant figures. Fable 5.1 scores
57.88 % at both `xhigh` and `max` there — 191 of 330 trials each, a real tie rather than a misread row.

## The leads this pass left open, closed

Every lead the sweeps flagged as "worth revisiting" was chased down rather than carried forward. Most died,
and recording *why* is the point — a lead that is merely unresolved gets re-opened every pass.

- **`uhyo/react-profession-bench`** was the most promising: an explicit rubric, a fixed judge, unsaturated
  scores across thirteen specs. It has no cost data at all. Its tree holds 199 files and not one mentions
  cost, tokens or usage, and the two most recent reports (Fable 5.1, Opus 5) never name a price. Not a
  source to watch — a source with nothing to measure.
- **arXiv 2602.22953** (General Agent Evaluation) reads its cost-efficiency appendix in real dollars, but the
  only Claude model in it is **Opus 4.5**, outside this lineage, and "effort" appears in the paper only as
  prose. **arXiv 2604.26954** turns out to evaluate OpenAI and Google models exclusively.
- **`SammyTourani/road-to-52`** quotes per-task dollars, all carrying `measured_by_us: false` and sourced
  from the ARC Prize leaderboard this repo already ingests. Secondary citation of an admitted source.
- **Harvey's Legal Agent Benchmark** states no effort setting anywhere, so its rows could only ever be
  `default`, and its two in-scope models (Opus 4.7, Sonnet 4.6) form a pair already covered. Digitizing its
  Figure 3 — whose labels are outlined vector paths — would have bought nothing.
- **Terminal-Bench 2.1 can no longer be verified.** Every leaderboard route on tbench.ai now serves the 4.0
  dataset byte-for-byte, including `/terminal-bench/2.1`. The six `tb21` rows are from a board that is gone;
  they are flagged as such rather than silently trusted or silently dropped.
- **morphllm.com** answered 429 to every route and every client tried.

One lead paid off. **frontierswe.com** publishes mean reward and mean cost per trial over 170 runs for Fable
5.1, Opus 5 and Fable 5 on a 34-task ultra-long-horizon suite, and its v2 write-up states the setting the
leaderboard page does not: *"We evaluate each model at its maximum reasoning effort."* That makes them `max`
rungs rather than unlabelled runs, which is what lets them into the grid. Its cost basis is undocumented, so
they carry the same flag the Terminal-Bench rows carry. The Kilo leaderboard payload also turned out to hold
measured output-token counts for the seven Claude rows already ingested from it, which the repo had left empty.

## What this pass rejected, and why it matters

Three candidate blocks were dropped after checking them against their sources, and the reasons generalise:

- **Vals AI's RSI Index** (25 rows) — two failures at once. The published table does not match the rows
  proposed from it: one model's figures had been duplicated onto a second model on two of the five tasks, which
  is what an "identical to the decimal" coincidence usually turns out to be. And the benchmark runs actual
  training jobs while documenting nothing about what its \$200–\$2900 per task covers. If that figure includes
  GPU spend, the ratio stops measuring the model, which is the one thing every row here has to measure.
- **Token counts alongside the CursorBench 4.0 figures** — the costs and scores are exact, but the token counts
  offered with them appear nowhere on the page. Cost and score were kept; the tokens were dropped.
- **PinchBench** — neither the board nor its repo states whether its cost is metered spend or list price ×
  tokens. That is the same gap that keeps BenchLM and llm-stats out.

- **fyve.co.jp — admitted, then withdrawn.** Five per-task Claude Code sweeps, cost read from the tool's own
  `modelUsage.costUSD`. Its checklist scores were saturated (7/7, 8/8, 3/3), so only the costs were taken.
  That was not careful enough. The rows moved Fable 5.1 `low` from 0.66× to 0.91× and **inverted the effort
  ladder**: `low` came out dearer than `medium`. The underlying data was never the problem — in all seventeen
  benchmarks that measure both rungs, `medium` costs 1.20–1.54× what `low` costs, without exception. The
  artifact is structural: fyve ran `low` and `high` but never `medium`, on three single-run toy tasks with no
  anchor, so `low` and `medium` ended up consolidated over different benchmark sets and their medians stopped
  being comparable. A saturated score and a task too small to segment effort are the same defect on both axes;
  the cost side is no safer than the quality side. Withdrawn.

Two genuinely new sources survive, both small: an AIME effort contrast (arXiv 2608.16956, whose `sonnet-5`
high-vs-omitted pair is the first measurement here of what *omitting* the effort parameter costs), and
`vercel/eve`'s committed benchmark results — plus frontierswe.com, below. The thin-third-party-field problem
is unchanged: three weeks after Fable 5.1 shipped, the field is still mostly vendors and leaderboards.

**`gen/build.py` now prints an effort-ladder check on every build.** Within a model, a higher rung costing
less than a lower one is almost never a measurement — it means the two couples were consolidated over
different benchmark sets. One documented exception is whitelisted: Sonnet 4.6's quality falls after `high`,
which the Sonnet 5 card prints itself. Anything else is flagged loudly. This inversion reached a published
commit and a pushed tag before a reader caught it by eye; the check is so that the next one cannot.

## Third scan: the blocked sources, opened

The four axes of the second salvo left five sources unread, each blocked by JavaScript-only rendering or
repeated HTTP 429s. A targeted scan opened four of them, and two of those changed data already in the repo
rather than only adding to it.

**Cognition's FrontierCode leaderboard** publishes its data at
`cognition.com/data/frontiercode-leaderboard/data.json`, reachable by reading the fetch URL out of the page's
Next.js chunks. Two consequences. The Fable 5.1 card's figure 8.4.A **is** that board's Extended subset — the
digitisation matched the primary to within 0.5 %, so those fifteen rows were replaced with exact values and
re-attributed to Cognition instead of being counted twice. And FrontierCode has **no "\$ per completed task"
metric at all**: its cost field is *"the mean USD spend per rollout"*, so every secondary source quoting
\$2.68 / \$3.51 / \$5.84 under that name is quoting per-rollout Extended figures under a wrong label. The real
trap is subset mixing — `main` (100 tasks) and `extended` (150) are separate groups here.

**CursorBench 3.2** turned out to be the single most valuable source in the matrix: a complete 3 × 5 matrix —
all three models at all five rungs — on one suite, with measured tokens and a stated method (*"published
per-million-token pricing applied to the tokens it used on each task"*). It is now the backbone of the Fable 5.1
effort curve in place of the system card. It also corrected the one value flagged as uncertain when it was
digitised: `opus-5@low`, read off an occluded hollow marker at 2.285/63.70, is really 2.55/62.8.

**ARC Prize's \$3.12 vs \$4.49 was never a conflict** — they are the `xhigh` and `max` rungs, both scoring
90.0 % on ARC-AGI-2. Per-effort costs sit in the page payload, so Fable 5.1's five rungs now complete the
`arcagi1` / `arcagi2` groups that already held Fable 5 and Opus 5.

**Terminal-Bench 4.0**, read from its RSC payload, answers a question in the negative: no effort rungs have
been added. Every Claude row is still `max`, while the schema carries the other rungs for other vendors — a
real absence, not a limitation. It also corrected a mistake introduced here: the Snorkel mirror's
2.7 B / 6.5 B / 3.8 B are *total* tokens; output is 63.1 M / 66.0 M / 58.6 M.

**Artificial Analysis shipped three mutually incomparable index scales in seven days** — the 1 Sep launch
article, v4.2 on the 4th, v4.3 on the 7th (Terminal-Bench 2.1 → 4.0, AutomationBench-AA added, run totals
differ). Each is its own group, and the launch-article rows carry a note that their scores do not cross the
rebaseline. Any figure citing Fable 5.1 at index 66 or \$3.76/task is stale.

Reddit, unreachable in the previous salvo, was opened through an Anubis-challenged redlib mirror. It yielded
one admissible row set out of fourteen candidates, and confirmed the dominant forum failure mode: spend
reported with no quality result, or rate-card arithmetic presented as measurement. The most useful find was
elsewhere — **Simon Willison's five-rung Fable 5.1 sweep**, whose shape is the point: `low`, `medium` and
`high` all land at ~\$0.10–0.13 for ~2 k output tokens, then `xhigh` jumps 14× and `max` 25×. The effort ladder
is not a ramp; it is a cliff between `high` and `xhigh`.

**OpenHands Index** was reached through its REST API and rejected outright: no effort dimension in the schema,
and a cache stale since 1 Sep that leaves two of the three target models absent.

## The second salvo: coverage bought, bands not tightened

Four parallel sweeps — public leaderboards, preprints, public code, practitioner write-ups — restricted to
Fable 5.1, Fable 5 and Opus 5. Twelve sources were admitted out of roughly forty examined.

The richest vein was **public code**: benchmark harnesses whose result files are committed to the repo that
produced them. ObviousBench (inspect-ai, 144 items × 3 epochs), bug-hunt-bench (105 planted bugs, blind
judge), roboflow/vlm-exam (133 identical images), harnesseval (six PRs common to every cell), vibe-openscad
and nurb-benchmarks all publish measured tokens or the CLI's own metered cost alongside an explicit
`--effort` / `output_config.effort` setting. Add Terminal-Bench 4.0's Harbor index, Kingy AI's 30-case
gateway run, and three preprints: **SWE Refactor Bench** (arXiv 2608.23564, 20 whole-repository migrations,
measured API spend), **QuoteBench** (2608.13547, provider-reported output tokens across three models' full
ladders, the anchor included) and **AI4AI-Bench** (2608.20318, measured exploration spend).

**Where a harness's metric saturates, the score is left blank and only the cost is kept.** vibe-openscad
scores 7/7 in every cell, nurb-benchmarks 1.0000, Kingy 30/30 with a stated 0.0-point difference. Entering a
flat metric would tell the quality grid that every effort rung is identical — the same reason the Zenn 3/3
sweep was excluded in the fourth pass. The datasets that genuinely separate quality by effort are
ObviousBench (Fable 5.1 pass@3 0.861 → 0.993), bug-hunt-bench (29 → 33 → 43 fixes of 105), vlm-exam and
harnesseval.

**Result: coverage, not precision.** Fable 5.1 went from 39 rows / 4 sources / 9 benchmarks to **68 / 11 /
18**, and the independent measurements pull its cost well below what the vendor sweeps alone implied —
`xhigh` 4.08× → 2.52×, `max` 5.63× → 4.14×. The mean cost band nonetheless *widened*, 1.856× → 1.973×, with
10 couples narrower and 18 wider. Sonnet 5 was the exception and tightened where it was worst
(`max` 3.60 → 3.46, `xhigh` 2.74 → 2.40, `high` 2.11 → 1.99). For a model six days old this is the expected
order of events: the spread is discovered first and narrowed later.

**No academic paper reports cost or tokens for Fable 5.1.** Of 13,013 arXiv abstracts from 20 Jul – 8 Sep
2026 and 1,135 full texts machine-scanned, exactly one mentions the model and it publishes no cost table.
Every Fable 5.1 cost figure in existence today is vendor or leaderboard material.

Two calibration facts worth recording, both from papers that were otherwise rejected. QuoteBench measured
what the *unset* effort field actually does: **Opus 5's unset arm behaves like `medium`**, Opus 4.8's like
`xhigh`. And arXiv 2608.16956 confirms against Anthropic's documentation that **Fable 5's omitted effort maps
to `high`**. The repo holds a large number of `default` rows (thinking unstated) that sit outside the effort
grid; these two facts are the beginning of a case for placing some of them, but that is a method change and
has not been applied.

Rejections worth recording, because they are the shape of the field: **Terminal-Bench 3.0** varies the
harness per row (mini-SWE-agent for Opus 5, Claude Code for Fable 5), so it is not a matched-config ratio.
**CodeRabbit** published a real Fable 5.1 low-vs-high sweep and disqualified it in one sentence — *"this
evaluation did not record reliable input and output token totals"*. **Cognition's** FrontierCode teardown is
the best-instrumented cost measurement found anywhere (every LLM call across 3,000 sessions parsed) and never
states the effort setting. **BenchLM**, **llm-stats** and the entire Japanese blog corpus price from the rate
card. **Aider's** leaderboard has no model newer than Opus 4. And the widely-cited Lance Martin thread turns
out to be a pointer at CursorBench 3.2.0 with no numbers of its own.

Two conflicts are recorded rather than resolved: Terminal-Bench 4.0's official board gives Fable 5.1 57.9 %
and Fable 5 44.5 % where Anthropic's launch page says 55.8 % / 42.0 % (different runs); and ARC Prize
publishes ARC-AGI-2 for Fable 5.1 at \$3.12/task on X but \$4.49/task on its own results page, at the same
score. Neither is guessed at.

Two sub-axes remain genuinely unswept: **Reddit** is unreachable from this environment, and **Cognition's
FrontierCode** leaderboard and Devin blog — probably the single best cross-model cost source for these three
models — returned JS-only pages and repeated HTTP 429s.

## Chartography, and a pass that widened the bands

The sixth pass added one benchmark: **Chartography** from the Fable 5.1 card (p186) — Fable 5.1, Fable 5,
Opus 5 and Sonnet 5, five efforts each, cost per task in real dollars. The figure overlays two curves per
model, solid for with-tools and dashed for without, in the same colour; they were separated by sampling the
segment between every pair of markers and measuring what fraction of it carries the series colour (≈1.0 solid,
≈0.7 dashed). The Opus 4.8 series was joined in from the **Opus 5** card's copy of the same figure (p171),
which makes the benchmark *anchored* rather than bridged.

That join was checked before it was made, and the check turned up something worth recording. Opus 5 appears in
both cards' versions of this figure and matches to within 0.3 % on all five efforts — the same run, on the same
cost scale, so joining is safe. **Sonnet 5, however, has identical scores in the two cards but costs in a
constant 1.502× ratio** — exactly 15/10. The Fable 5.1 card (1 Sep) priced Sonnet 5 at the \$3/\$15 rate that had
been scheduled for 1 Sep; the Opus 5 card priced it at \$2/\$10. That increase never happened: Anthropic made the
\$2/\$10 price permanent on 10 Aug 2026 (pricing page, footnote 3: the increase "will not occur"). Sonnet 5 is taken
from p186 and **re-priced ×2/3** (eighth pass), which puts it back on the Opus 5 card's scale, never mixed across the two.

The **without-tools** curves are kept in the data but held out of the effort grid, labelled `nt-*`. Stripping
the tools from a benchmark that needs them is a regime change, not an effort setting — the same reason
`nothink` is already excluded. The numbers say so plainly: without tools the anchor costs almost nothing, so
Fable 5.1 at max comes out at **27.6×** the anchor against 5.4× everywhere else.

**This pass widened the intervals rather than narrowing them:** mean cost band 1.856× → 1.938×, 15 couples
wider against 9 narrower, and Fable 5.1's centres moved a long way (`xhigh` 4.08 → 2.53, `max` 5.63 → 4.46).
Chartography is a short multimodal task, and on it Fable 5.1 is far cheaper relative to the anchor than on the
long agentic benchmarks that make up most of the set. With only nine benchmarks carrying Fable 5.1, one
divergent-but-real measurement moves it. That is the honest reading: the band was narrow because the coverage
was narrow, and this is what task-type variance looks like when you sample a new corner of it. The measurement
was kept — dropping a verified vendor sweep because it widens a band would be choosing the data to fit the
conclusion.

## What the fifth pass changed, and what it did not

This pass went after the *intervals* rather than after new models. The diagnostic first: of the 35 (model, effort)
couples, the widest cost bands were Sonnet 4.6 `low` (4.05× between the band's ends), Sonnet 5 `max` (3.78×) and
Sonnet 4.6 `medium` (2.06×) — the Sonnet family, plus every `low` rung. Haiku 4.5 was worse than any of them: it
rests on **one** benchmark, so its band is degenerate rather than wide.

The most useful find was not a new source but an old one read badly. The `cursorbench` and `scfrontiercode`
groups are the two effort sweeps in the **Sonnet 5 system card** (p118 and p117), and they had been entered by
eye: costs rounded to one decimal, and Sonnet 4.6's high/max scores recorded as 48.8/49.0 when the chart prints
**48.2/47.5** — a curve that falls after `high`, entered as one that rises. Re-digitizing both (X-axis fit
residual 0.2 px, scores taken from the printed labels) corrected 42 rows. Added on top: the Opus 4.7 card's
OSWorld-by-effort figure (p209, output tokens × price, three models × four efforts) and two Artificial Analysis
model-page rows (Opus 4.8 and Sonnet 5 at max) that complete `aa-index4`.

The result is honest rather than flattering: the mean cost band narrowed only from 1.854× to 1.826×, with **15
couples narrower and 13 wider**. The targets moved the right way — Sonnet 4.6 `low` 4.05×→3.40×, `medium`
2.06×→1.73×, `max` 2.37×→2.09×, Sonnet 5 `max` 3.78×→3.60×, Opus 4.8 `max` 1.82×→1.73× — while several Fable 5
bands widened. That widening is the point: the old rounded values understated the spread between benchmarks, so
those bands were not narrow, they were wrong.

Four candidate sources were examined and **rejected**, for reasons worth recording:

- **BenchLM** quotes cost from published list prices and assumed token counts, not measured spend.
- **HAL (Princeton)** and **swe-rebench** publish cost *and* score on the same task, but neither has ingested
  any model newer than Sonnet 4.5 / Fable 5 — swe-rebench lists no Haiku 4.5 and no Fable 5.1 at all.
- The **Opus 4.8 card's** DeepSearchQA (p206) and DRACO (p209) effort figures plot *total* tokens, not output
  tokens. Turning that into a cost ratio assumes both models share an input/output mix, which is the same kind
  of assumption that gets list-price sources excluded here — so they were left out.
- The **Haiku 4.5 system card** contains no cost-versus-effort figure at all.

## Haiku 4.5 stops being a single point

Haiku carried 44 rows with a cost, and exactly **one** of them reached the grid. The rest were labelled
`default` — thinking unstated — and the grid admits only the explicit effort rungs plus the `solo` node.

But `default` is not a configuration choice on Haiku: the API rejects `output_config.effort` on it, so a
`default` run **is** its only configuration, which is precisely what `solo` denotes. Those 22 rows are now
labelled `solo` (`nothink` and the ARC Prize `think-*` budget ladder stay distinct, since those are genuinely
different regimes). Haiku goes from one benchmark to six — `officeqa`, `ceobench`, `automationbench`, `ctala`,
`drona23`, `ponytail` — and the correction is large:

| | before (1 benchmark) | after (6 benchmarks) |
|---|---|---|
| relative cost | 0.50 (degenerate band) | **0.24** [0.17, 0.30] |
| relative quality | 0.59 (degenerate band) | **0.58** [0.36, 0.80] |

The single arXiv measurement had overstated Haiku's cost by a factor of two, and the degenerate band displayed
that as certainty. Haiku now sits on the Pareto frontier and takes the grunt-work tier, which is where a cheap
small model belongs and which the report could not show while one measurement stood in for six.

**The caveat, stated rather than hidden:** in five of those six groups Haiku's partner runs at `high` or `max`,
so the ratio compares Haiku-in-its-only-configuration against another model pushed hard. That is the Haiku
exception `comparisons()` already applies on the ratio side, and it is why the quality band is so wide
([0.36, 0.80]) — the six benchmarks genuinely disagree about Haiku. Read the cost figure as *what Haiku costs
relative to models being run properly*, not as a matched-effort comparison, which is not available for a model
with no effort dial.

## A note on double-counting, from this pass

The CursorBench 3.2.0 figure in the Fable 5.1 system card is **the same measurement** as the `cursorbench32`
rows already ingested from Cursor's own leaderboard: five couples matched to within 0.1 %. Admitting it as a
new group would have counted one benchmark twice and doubled its weight in the source-weighted median. It was
folded into the existing group instead, which is what the extra couples (Fable 5 at low/medium/high, Opus 5 at
low/medium, and all five Fable 5.1 rungs) are doing there. The same check cleared HLE, DRACO and OSWorld: each
system card re-runs them, and the numbers differ enough between cards to be genuinely independent runs.

Artificial Analysis needed the mirror-image care. Its launch article and its per-model pages report the
Intelligence Index on **different builds** — Fable 5.1 at max scores 66 for \$3.76/task in the article and 57 for
\$10,816 per suite on the model page. Mixing them would have compared two different tasks, so they are two
groups (`aa-index-pertask3`, `aa-index4`), never one.

## A correctness note from the fourth pass

**Haiku 4.5 has no effort dial** — the API rejects `output_config.effort` on it (it predates the
dial and uses `budget_tokens`). Sonnet 4.6 has no `xhigh` either; that level arrived with Opus 4.7.
The ingest scripts now refuse any `(model, effort)` pair the API does not expose, which is what
caught the one real data-integrity problem of the pass: two sources report an "effort sweep" on
Haiku 4.5, which cannot be what it says it is. Their measurements are kept under `req-*` effort
labels that cannot feed the effort grid, flagged `effort-flag-unsupported-on-haiku`.

Haiku 4.5 therefore stays a single `solo` node in the grid, by design and not by omission. What
ARC Prize contributes for it is a **thinking-budget** ladder (none / 1K / 8K / 16K / 32K), labelled
`think-*` — a real and useful axis, but a different one from the effort dial.
