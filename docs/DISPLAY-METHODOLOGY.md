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
  the convergence criteria. Effort-ladder inversions (a higher rung costing or scoring less) are printed, not corrected; the rungs are *thinking off*,
  then *minimal* … *max*, and *thinking on* is compared with *thinking off* only.

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

The page shows the latest model of each family and the one before it; older ones — Fable 5, Opus 4.8, Opus 4.7,
Sonnet 4.6 — are hidden by default, and an *Older models* switch shows them (Opus 4.8 joined them on 1 Oct 2026, two
generations behind Opus 5.5; Fable 5 on 12 Nov 2026, two generations behind Fable 5.2). Hidden models leave the charts, the matrices, the frontier, the tiers and the crown: every
recommendation is computed over the models on screen, and the cheapest couple is the cheapest one on screen. The price
trend never includes them (§ 8).

## 5. The matrix

One row per model, one column per configuration: *low* … *max* always, and *thinking off*, *minimal* (before *low*)
and *thinking on* (after *max*) when a model shown has them; each cell is the cost multiple with its interval, coloured on a heat scale
(log cost, from the cheapest to the dearest couple). Rows are ordered by the expected score of the model at its highest
published effort. A model without a setting (*solo*) fills a single merged cell across all the columns; an unpublished couple
is shown as a dash. A model the catalogue flags as size-sensitive (`flag_task_size` in `data/catalog/models.json`: a verbose model,
whose cost swings widely between short and long agentic tasks) carries a *size-sensitive* tag.

A second matrix gives every couple's **value index** (§ 9) with its 16–84 % range (r ± √(h_x² + λ²·h_θ²)), same rows.
Its colours follow the data: green above 100, red below, each side scaled to the most extreme index shown (log scale).

## 6. The charts

- **Cost axis**: log₁₀ of the cost multiple.
- **Quality axis**: θ, linear above the weakest tier target θ*₁ (§ 10). Below it — couples short of today's level —
  θ is compressed three times: y = θ*₁ + (θ − θ*₁) ⁄ 3. Older and weaker models sit together at the bottom instead of
  stretching the axis; the top is not compressed. Gridlines at round expected scores (§ 3).
- One line per model through its effort ladder, in the order *thinking off*, *minimal*, *low* … *max*, *thinking on*
  (a point is labelled *no think*, *minimal*, *low* …). Optional **ovals** draw each couple's 16–84 % interval, with separate
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

What a given quality costs today, fitted on every couple of the **latest model of each family** (Fable 5.2, Opus 5.5,
Sonnet 5.5, Haiku 5.5), dominated ones included — the going rate of the models on sale, not their frontier:

    ln cost = a + λ·θ

- **Weights**: each couple by its uncertainty across the line, 1 ⁄ (h_x² + λ²·h_θ²) — both axes are uncertain
  (effective variance) —, iterated to the fixed point.
- **λ** is the market's price of quality: one more unit of θ costs e^λ times more. It is kept ≥ 0 (quality never gets
  cheaper as it rises).
- **Straight** on the latent scale: every step of quality costs the same ratio more, wherever it sits. No shape
  constant to choose.
- **Why the latest generation only**: each generation is better and cheaper per point than the one before, so a trend
  through every generation is flattened by the older, dearer couples and makes quality look cheap (on 30 Sep 2026, λ
  0.109 over every shown couple, 0.149 over the latest models, 0.236 along the effort ladders of each model). Until
  1 Oct 2026 the trend was fitted on every shown couple. It now does not move when the reader shows older models.
- The chart states its weighted R².

## 9. Value

The distance of a couple to the trend, on the cost axis:

    r = (a + λ·θ) − ln cost          positive = cheaper than the going rate

shown as the **value index** 100·e^r: 100 is the trend, 500 five times cheaper than the trend at its quality, 50
twice as dear (the header's sentence says it in words: "5.0× cheaper than the price trend"). Since the trend is a straight
line, the same gap read on the quality axis is r ⁄ λ: the couple's θ above what the trend gives for its cost, shown in
points of expected score. No reference couple: 100 is the trend itself.

## 10. Tiers: best value by task complexity

Four tiers — *Grunt work*, *Everyday tasks*, *Advanced reasoning*, *Cutting-Edge thinking* — each with a target θ*,
a window width σ and a price of quality β.

- **Targets**: θ*₁ … θ*₄ spread evenly from (1 − e)·min + e·max to (1 − e)·max + e·min of the frontier's θ (frontier
  by centres), e = 0.05. The bottom tier follows the weakest frontier couple as it rises, the top one the best; each end
  is drawn 5 % of the span inward so that no target sits on a single couple. The targets depend on the couples only
  through these two bounds.
- **Window width**: σ = gap ⁄ (2·√ln 2), gap the spacing of the targets: adjacent windows cross at half weight midway
  between their targets.
- **Score**: among the frontier couples (§ 7),

      score = window(θ) × e^(β·λ·θ) ⁄ cost,   window = e^(−δ²) below the target, 1 at or above,   δ = (θ − θ*) ⁄ σ

  Above its target, a couple wins by bringing more quality than the tier is ready to pay for its extra cost. Below the
  target the window penalises the shortfall.
- **Price of quality β**: what each tier's buyer pays for one more unit of θ, as a multiple of the market's λ. Grunt
  work runs at scale and would rather pay less for a little less; cutting-edge thinking pays a premium for the last
  points. β is spread evenly **in ratio** from 1⁄4 to 4 — 0.25, 0.63, 1.59, 4 —, symmetric about the market (geometric
  mean 1): a multiplier of a price is symmetric in ratio, not in difference. With β = 1 everywhere (until 1 Oct 2026) the
  term was the couple's value against the trend for every tier, and three tiers picked the same couple. Every
  geometric spread tried from 0.5 → 2 to 0.1 → 10 gave the same four picks on 1 Oct 2026; increasing the weight of
  cost instead (cost^γ) ranks as β ⁄ γ with a softer window, so β is the only knob.
- **Cost as people perceive it**: cost enters as a ratio (log cost). Perceived price follows the ratio of prices, not
  their difference (Weber–Fechner; Monroe 1973, *Journal of Marketing Research* 10(1)): twice as dear weighs the same
  at every price. A power of the cost such as C^0.88 is not used: that exponent is the curvature of the value of gains
  and losses in prospect theory (Tversky & Kahneman 1992), measured on lotteries, not on prices.
- **Pick**: the candidate with the highest score. Two tiers may pick the same couple. A card shows the pick's value
  against the trend as its value index (§ 9).
- **Sliders**: each tier's θ*, σ and β can be moved (β from 0.1 to 10, on a log scale). θ* travels over the targets' range padded by half a gap on each
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

Every group that measured a Claude couple is listed with its verified configuration (harness, effort), its kind
(effort sweep, cross-model, cross-generation) and the Claude couples it links; the groups of other makers' couples
alone, which the fit also uses (METHODOLOGY.md §5), are not. The header counts sources, benchmarks and measurements
of the listed groups. The page's date
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
| § 10 price of quality | β from 1⁄4 to 4, even in ratio | each tier's buyer, symmetric about the market price |
| § 8 price trend's couples | latest model of each family | today's going rate; older generations would flatten it |

## 15. The head-to-head page

`claude-models-head-to-head.html`, written by `site/duels.py` from the same grids: every pair of the latest model of
each family (Fable 5.2, Opus 5.5, Sonnet 5.5, Haiku 5.5), and each of them against its predecessor. Costs are
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

## 16. The multi-site draft (models.agensse.com)

A draft, built locally only and not served: `python3 site/multisite.py` writes `out/models/` (gitignored): the
**global page** (`index.html`) and one page per model maker (`claude/`, `openai/`, `google/`, `xai/`, `deepseek/`,
`qwen/`, `glm/`, `kimi/`), with `llms.txt`, `robots.txt`, `summary.json` (per page: size, couples shown, counts,
the full answer, the effort-ladder inversions) and the icons. It reuses the Claude page — `app.js`, `body.html`,
`style.css`, the pre-render — with the per-site settings of `site/makers.json`, applied as exact replacements that
stop the build when one no longer applies. `python3 site/build.py` and the files it writes are unchanged.

- **Same rules as §§ 1–14** on every page: publication by two publishers or more, the frontier, the price trend, the
  value, the tiers and the crown, all computed **among the page's couples on screen** (the price trend excepted when
  the reader turns chips off: it stays the default view's, below). A couple is shown when it is
  published on **both** axes (the ones a chart can place); on the Claude page every cost couple has its quality.
- **Global page**: by default, the **current models of every maker, and the couples of older models that no other
  model of the same maker strictly beats** — no couple of another model of that maker (its own builds and modes do
  not count) both costs less and scores more, on the published centres. The frontier, the tiers and the crown are
  taken among these; *Older models* adds the beaten couples. The price trend is fitted on the current models. One hue
  per maker, its models in steps of lightness; Claude's model names carry "Claude". A model that another model of its
  maker entirely outclasses is hidden too, current or not (below).
- **Maker pages**: the maker's models in its own colours (the Claude page keeps the catalogue's), its tiers and
  crown among its own couples, its price trend on its current models; the maker's older models are hidden by default,
  as on the Claude page (§ 4).
- **Tier targets: the 20th, 40th, 60th and 80th percentiles of the couples shown** (19 Nov 2026; the maintainer:
  « j'ai l'impression que les tiers sont hyper bas maintenant, remonte le seuil de perf min pour grunt », « propose moi
  des nouveaux parametres de tiers pour mieux les centrer sur les perfs generales », then, of the proposals shown,
  « B »). On every page of the multi-site draft, and only there, the four targets θ*₁ … θ*₄ (Grunt work, Everyday
  tasks, Advanced reasoning, Cutting-Edge thinking) are the 20th, 40th, 60th and 80th percentiles of θ over **every
  couple shown on the page** (the selection and the *Older models* switch in force, the couples `couples()` gives),
  linearly interpolated between the sorted values at rank f·(n − 1). They replace the even spread between the
  frontier's bounds drawn inward (§ 10, `TIER_E`), which put the bottom tier at the weakest frontier couple. They
  depend on θ only, not on the prices. The window width keeps the rule of § 10, σ = gap ⁄ (2·√ln 2), gap now the mean
  spacing of the targets, (θ*₄ − θ*₁) ⁄ 3. β (0.25, 0.63, 1.59, 4), the score, the pick among the frontier couples,
  the fixed price trend and the promotions are unchanged. When the reader turns chips off, the targets are taken
  again on the couples shown, like the frontier; the price trend is not (below). The axis compression of § 6 still
  starts at the weakest target, θ*₁. The Claude page at the repository root keeps § 10. Applied by `site/multisite.py`
  as replacements of `tierDefaults()` and of the pages' text.
- **Outclassed models go into the older models** (the maintainer, 19 Nov 2026: « ensuite tu places dans older models
  tous les modeles qui sont entierement moins bons et plus cher qu'un autre modele du meme fabricant. genre quand un
  modele est entierement surclasse par un autre fait par la meme boite, tu le mets en older models »). A model A is
  **entirely outclassed** when one model B of the same maker dominates **every** couple of A shown on the page with
  at least one of its own couples: B's couple costs no more and scores no less, and is strictly better on one of the
  two, on the values the frontier uses (ln cost and θ, the tolerance of `frontier()`: 1e-9). No other threshold. A
  is then hidden by default, as an older model, and the *Older models* switch shows it again — on every maker page
  and on the global page (where B is a model of A's maker), whatever its family says, **a current model included**:
  an outclassed current model also leaves the price trend's couples, so the trend does not move when the reader
  shows the older models. The page's builder (`outclassed()` in `site/multisite.py`) writes the outclassed models of
  each page, each with every model that outclasses it, in `out/models/summary.json`. `families` in `site/makers.json`: per catalogue key its family, `current` (the latest
  model of its family: the trend's couples, always shown on the global page) and `hidden` (hidden by default on its
  maker's page). `python3 site/import_families.py` fills it from the families salvo (`families.tsv` per maker, with
  the makers' pages as evidence): current = status `current`; an unknown status, or "not a model", is not current;
  shown on the maker's page = current, or followed by a current key (the latest model and the one before); a line
  that is not current follows its model. `family_overrides` holds a user decision the files do not carry (Gemini 3.1
  Pro current beside Gemini 4 Argon; 19 Nov 2026: GPT-6.1 Terra current in place of GPT-5.6 Terra, Gemini 4 Hydrogen
  in place of Gemini 3.8 Flash, and the statuses that follow). The catalogue's later keys (GPT-6.1 Terra, Gemini 4
  Carbon and Hydrogen, Qwen4 Max and its preview, GPT-5 Chat) have entries citing the registry's sheets; a model
  whose succession no source writes (Qwen4 Max) is shown and not current. Claude's keys are not there: the Claude maker page follows the Claude page — its
  models, labels and colours from the catalogue (`display_order`), current = `CURRENT` and hidden = `LEGACY` of
  `site/duels.py`, and the page's own generation card. A catalogue key with no family entry is shown and not current.
- **Charts: points only** (the maintainer, 19 Nov 2026: « quand ya autant de modeles, on voit rien sur le graphique.
  enleve les lignes pour ne laisser que le nuage de point et tu enleve les labels de point pour n'afficher que ceux de
  la frontiere pareto ou au sruvol du point a la souris. enleve la liste des modeles de la legende. »). On every page
  of the multi-site draft, the landscape and the Pareto chart place each couple as a point and draw no line between
  couples (no effort ladder); the reading aids that join no two couples stay: the Pareto frontier, the price trend,
  a price variant's dotted line to its own couple. Only the couples of the page's Pareto frontier are labelled, in
  text on the chart, "model · effort" (the maintainer, 19 Nov 2026: « j'aime pas du tout les pastilles numerotees et
  la liste een dessous du graphique »; the numbered badges, their leader lines and the lists under the charts of
  3573edb are gone): small (11 px on screen at every width, redrawn when the window is resized), in the muted ink,
  without background or frame. Each label goes to the first free spot beside its point, nearest first (12 positions
  around it, starting up-left — the side of the frontier no couple can occupy —, on 4 rings 4 px apart), whose box,
  with a 1.5 px margin, overlaps no other label, no point (the largest mark, 6.5 units, and the margin) and no line of
  the chart (the frontier, a variant's dotted line), inside the plot. A label set off its point — placed beyond the
  first ring — is joined to it by a short leader line, thin (0.8 px) and muted, from the point's edge to 1 px short of
  the label's box (the maintainer, 19 Nov 2026: « tu as enleve les petits traits »); a spot is then free only if that
  line crosses no other leader line and passes over no other label, and no leader line already drawn crosses the
  label. The placement is otherwise that of b704bd0. A label that finds no free spot is not shown:
  its point reads on hover. The width of a label is the browser's measure of its text (0.6 em a character where none
  is available, as in the pre-render). The landscape, the Pareto chart and the tier tuner (whose frontier marks name
  their couple on hover or tap, without number) follow the same rules. Hovering or tapping any point, or a label,
  shows the tooltip (model · effort, cost, score) at a fixed size on screen. The legends list no model: they keep
  the symbols (hollow points, price variants, the labels), the frontier, the trend, the dominated couples. The
  Claude page at the repository root keeps its curves, labels and legend.
- **Head of the page** (the maintainer, 19 Nov 2026: « maintenant en haut de page ya des boutons et des filtres ca fait
  super moche. le titre doit etre en haut pourquoi il est en dessous des filtres ? »), top to bottom: a plain text
  navigation (links to the global page and the eight maker pages, the current page in bold, no button); the title
  and its subtitle, with nothing between the navigation and them; the line of sources, the introduction; the
  draft banner; the crown and the tier cards; then the selection bar, just above the first chart.
- **Selection bar** (the maintainer, 19 Nov 2026: « je voudrais pouvoir selectionner les fabricants pour choisir ce qui
  s'affiche »): one plain line just above the first chart, which sticks to the top of the window only once scrolled
  past (never above the title on load); it scrolls sideways when it does not fit (on a phone). Fine chips with a light
  outline and a small dot of the maker's (or model's) colour: on the global page one per maker, on a maker page one
  per model shown (its builds and modes with it), *All* first and *Older models* last on the same line. Everything
  is on by default. A chip turned off removes its couples from every chart and every table (the sources table and
  the counts included); the frontier, its labels and the tier targets are taken again on the couples shown, as the
  *Older models* switch does on the Claude page.
  **The price trend does not move with the selection** (the maintainer, 19 Nov 2026: « desactiver un fabricant ne
  doit pas recalculer la tendance des prix »): it stays the trend of the default view — every couple of the page's
  current models that are not outclassed, all makers and models on —, whatever the chips; what reads against the
  trend reads against that fixed trend: the crown, the "× cheaper than the trend", the value matrix and the tiers. A
  selection the page cannot draw is refused (its last chip is locked): the tiers need two frontier couples. The
  selection is kept in the address (`#makers=openai,google`, `#models=…`: the chips shown that are on; no address
  when all are), so a link shares it.
- **Links between the pages**: the published build links the clean addresses (`/`, `/openai/`, no `index.html`);
  `python3 site/multisite.py --local-links` links each page's file (`../openai/index.html`), for a copy opened from the
  disk, where a folder link shows the folder.
- **Lines** (the catalogue's `line`: a dated build, a preview, OpenAI's Pro mode): separate couples of one model,
  each with its own effort ladder. They share the model's colour; the first is drawn with filled points, the others
  with hollow points. Chart labels, tooltips and table rows give the full name ("DeepSeek V4.1 Flash 1017 build",
  "GPT-6 Astra Pro").
- **Sources table**: the groups that measured at least one couple shown on the page, with those couples; sources
  are counted by publisher (`data/catalog/publishers.json`). A group without a verified configuration note shows "—".
  The Claude page at the repository root still lists every Claude couple a group measured, efforts outside the fit
  included, so its counts are larger.
- **Price variants** (a promotion, an off-peak rate): the published cost (data/build.py) is the list price without
  promotion (DeepSeek at its peak rate). Read from the registry's dated price records (`price_variants` in
  `site/makers.json`: `data/registry/prices.json`, kinds `promotion` and `off-peak`, the fit catalogue's models; the
  maintainer, 16 Nov 2026): a record is a variant of every couple of its model (of its configurations, when it lists
  them) when it is in force — an end the maker states not past, or seen at the model's last capture on its route and
  currency, or no end —, its route is that of the model's base price (`base_price` of `data/build.py`, the price the
  published cost is at), and **every tariff** (input, output, cache, long-context tiers) is in **one ratio** to the
  base price on the same classes (a record with no classes and a stated factor applies it to all). Any other record
  is not shown; `out/models/price-variants.json` lists every record read with its outcome. The mock
  `site/price_variants.mock.json` is no longer read.
- **A promotion is the price in force** (the maintainer, 19 Nov 2026: « je vois que les promotion ne sont pas prises
  en compte dans les annotations et les scores / pareto »). A promotion kept above (every tariff in one ratio, no
  stated end past) is the price the couple sells at today, for everyone: on the multi-site pages it **replaces the
  list price wherever the page decides** — the Pareto frontier and its labels, the "× cheaper than the trend", the
  crown and the tiers, the price trend (its couples at their price in force), the outclassed models (above), the
  beaten couples of the global page, the cost shown in the tables and what is ranked on it; the cost axis counts from
  the cheapest couple at its price in force. Two promotions in force on one couple: the lower price. Display: the
  couple's filled point is at the promotional price; its **list price** stays visible as a hollow diamond joined by
  the dotted line (the other way round from an off-peak rate); its label, its tooltip, the tier cards, the crown, the
  answer and the tables say the promotion and its end ("Gemini 4 Carbon · High · promo until 30 Nov"), or "promo,
  seen 16 Nov" when no end is known (a record seen at the model's last capture), with the list price under the cost
  and the value index at the list price in the value matrix. **The page checks the end itself**: it is static and
  stays online after a promotion ends, so on load it compares the reader's date with the stated end; a promotion
  past its end goes back to the list price, and every decision above — the outclassed models, the older models, the
  trend's couples included — is taken again on that day (the pre-render is done at the build date;
  `promotions_in_force` in `summary.json`). An **off-peak rate** holds at some hours only, not for everyone: it
  changes nothing — a hollow diamond at the list price × its ratio, joined by a dotted line, in the tooltip and under
  the cost and the value index, and never in the frontier, the trend, the tiers or the crown.
- **Draft**: every page carries a banner and a `noindex` tag while `draft` in `site/makers.json` is set (the pages
  are not published). An empty `draft` removes both and writes the sitemap.
- **A fit that no longer matches its inputs** stops the build, as on the Claude page. `--stale-fit` builds a local
  preview from it anyway — the couples and values of the last fit, the sources table from today's data — and says so
  in the banner; it is never the published build.
