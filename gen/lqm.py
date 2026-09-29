"""Latent quality and cost of (model, effort) couples, fused from heterogeneous public benchmarks.

For every measured row r (group b, couple c of model m, publisher s, task type t):

    f(y_r) = o_b + a_b · (θ_c + u_{s,c} + w_{s,m} + v_{c,t}) + ε_r,      ε_r ~ Student-t_ν(0, κ_r · h_r² · σ_b²)

  f        per metric (METRIC RULES): empirical logit of a bounded score, log of an unbounded positive quantity,
           identity for an interval or unknown scale; log on the cost axis.
  θ_c      latent quality (quality axis) or log cost (cost axis) of the couple. θ sums to zero over the couples:
           no couple is a reference; the page divides by its reference couple afterwards (a display choice).
  o_b      group offset, flat. a_b group gain: quality log(a_b/σ_b) ~ N(0, s_g²) (discrimination, pooled; its zero
           mean sets the unit of θ); cost log a_b ~ N(0, s_g²) (elasticity around 1).
  σ_b      group noise, never below the metric's resolution. Quality: Jeffreys 1/σ. Cost: log σ_b ~ N(μ_σ, s_σ²).
  h_r      shape of the sampling noise of an empirical logit, 1/(2√(q(1−q))) at the observed proportion q; 1 else.
  κ_r      variance multiplier of an early-access run, log κ ~ N(0, 1); 1 for other runs.
  u, w, v  publisher × couple (sd τ_c, τ_c ~ N⁺(0, s_τ)), publisher × model (sd ψ), couple × task type (sd ω)
           effects; composites (task type 'mixed') carry no task-type effect. A level carried by a single row is left
           out (indistinguishable from that row's noise). u and w are centred within their publisher, v within its
           task type: their mean is confounded with the free offsets of that publisher's (type's) groups.
  Priors:  θ ~ N(0, 10²); s_g, s_τ, ψ, ω, s_σ ~ half-Student-t(3, 0, 2.5); ν ~ Gamma(2, 0.1).

Estimation: Hamiltonian Monte Carlo (Stan, NUTS) on lqm.stan, run through CmdStanPy. The read-out `level` is computed
in Stan for every draw; `summarise` turns it into a centre and a per-couple interval (quasi-variances).
"""
import collections, csv, itertools, math, os, re

from catalog import COMPOSITES, FAMILY_OF, PUBLISHER_OF

HERE = os.path.dirname(os.path.abspath(__file__))
STAN_FILE = os.path.join(HERE, "lqm.stan")

# ---------------------------------------------------------------- metric rules
LOG_METRICS = {"best-run-cash$", "xp-x1e5"}                        # positive, unbounded, ratio scale
UNIT_BOUNDED = {"F1", "accuracy", "success"}                        # proportions written on 0–1
HUNDRED_BOUNDED = {"weighted-rubric", "BLEU", "EDM-F1", "pass@1", "pass@3", "AA-idx", "LB-global-avg", "mAP50",
                   "RHAE", "score/579-pct"}                         # scores published on 0–100 without a '%'
LOWER_IS_BETTER = {"subjective-rank-of-4"}
MAX_STEPS = 100                                                     # finest scoring step assumed: 1 point in 100


def bound(metric):
    """Upper bound of a bounded score, or None."""
    if metric in LOG_METRICS or metric in LOWER_IS_BETTER:
        return None
    if "%" in metric or metric in HUNDRED_BOUNDED or (metric.endswith("x100") and not metric.startswith("kendall")):
        return 100.0
    if metric in UNIT_BOUNDED:
        return 1.0
    if metric == "equiv0-4":
        return 4.0
    m = re.fullmatch(r"[a-z]+/(\d+)", metric) or re.fullmatch(r"[a-z-]+-of-(\d+)", metric)   # 'recall/13', 'playable-of-2'
    return float(m.group(1)) if m else None


def kind(metric):
    return "logit" if bound(metric) else ("log" if metric in LOG_METRICS else "identity")


def scoring_steps(proportions):
    """Number of scoring steps n of a bounded group: 1 / its finest observed difference, capped at MAX_STEPS."""
    diffs = [abs(p - q) for p, q in itertools.combinations(sorted(set(proportions)), 2)]
    step = min(diffs) if diffs else 1.0 / MAX_STEPS
    return min(1.0 / step, MAX_STEPS) if step > 0 else MAX_STEPS


def empirical_q(p, n):
    """(p·n + ½) / (n + 1): a proportion at 0 or 1 lands half a scoring step inside the bounds."""
    return (p * n + 0.5) / (n + 1)


def harness_base(h):
    """A harness without its version numbers: patch releases of one harness are one configuration."""
    return re.sub(r"[-_ ]?v?\d+(\.\d+){1,3}(-r\d+)?", "", (h or "").strip())


# ---------------------------------------------------------------- data
EFFORTS = {"low", "medium", "high", "xhigh", "max", "solo"}           # 'solo': a model without an effort setting
NO_TASK_EFFECT = {"mixed", ""}


def load(path, models, field="score"):
    """Rows of the data file → groups ready for fit(). field = 'score' (quality) or 'cost_usd' (cost).

    1. Composites: a couple measured on a component of a composite (catalog.COMPOSITES) leaves the composite out.
    2. Homogeneity: a group is split by publisher, harness (without version), scale (bounded scores: bound) and, on
       the cost axis, cost unit — only rows measured under one configuration are compared.
    3. Republished numbers count once: two groups of one family that share at least two identical values away from
       the metric's bounds are one experiment printed twice; their identical rows are kept once, in the larger group.
       A single coincidence, or equality at a bound (two runs both at 100 %), is not a republication."""
    report = collections.Counter()
    raw = collections.defaultdict(list)
    for r in csv.DictReader(open(path)):
        if not r["group"] or r["group"].startswith("#") or r["model"] not in models or r["effort"] not in EFFORTS:
            continue
        try:
            val = float(r[field])
        except (TypeError, ValueError):
            continue
        metric = "usd" if field == "cost_usd" else r["score_metric"]
        if field == "cost_usd" and val <= 0:
            continue
        raw[r["group"]].append(dict(
            couple=f'{r["model"]}@{r["effort"]}', model=r["model"], publisher=PUBLISHER_OF.get(r["source"], r["source"]),
            task=r["task_type"] or "", raw=val, metric=metric, kind="log" if field == "cost_usd" else kind(metric),
            ea=int("EAP-run" in (r["confound"] or "")), harness=harness_base(r["harness"]), unit=r["unit"] or ""))

    # --- 1. composites
    for g, spec in COMPOSITES.items():
        if g not in raw:
            continue
        pubs = {x["publisher"] for x in raw[g]}
        parts = spec if spec != "publisher" else [h for h in raw if h not in COMPOSITES
                                                  and {x["publisher"] for x in raw[h]} & pubs]
        measured = {x["couple"] for h in parts for x in raw.get(h, [])}
        kept = [x for x in raw[g] if x["couple"] not in measured]
        report["composite row, component measured"] += len(raw[g]) - len(kept)
        raw[g] = kept

    # --- 2. homogeneity
    by_group, family = {}, {}
    for g, rows in raw.items():
        parts = collections.defaultdict(list)
        for x in rows:
            scale = x["unit"] if field == "cost_usd" else (x["kind"], bound(x["metric"]))
            parts[(x["publisher"], x["harness"], scale)].append(x)
        for i, (_, xs) in enumerate(sorted(parts.items(), key=lambda kv: -len(kv[1]))):
            name = g if i == 0 else f"{g}~{i + 1}"
            by_group[name], family[name] = xs, FAMILY_OF.get(g)
        report["group split by configuration"] += len(parts) - 1 if parts else 0

    # --- 3. republications
    def same(x1, x2):
        n = bound(x1["metric"]) if field != "cost_usd" else None
        tol = 5e-4 * n if n else 5e-4 * max(abs(x1["raw"]), abs(x2["raw"]))
        return abs(x1["raw"] - x2["raw"]) <= tol

    def at_bound(x):
        n = bound(x["metric"]) if field != "cost_usd" else None
        return n is not None and (x["raw"] >= 0.9995 * n or x["raw"] <= 0.0005 * n)

    size = {g: len({x["couple"] for x in rows}) for g, rows in by_group.items()}
    slots = collections.defaultdict(list)                               # (family, couple) → [(group, row)]
    for g in sorted(by_group, key=lambda g: (-size[g], g)):
        for x in by_group[g]:
            slots[(family[g] or g, x["couple"])].append((g, x))
    matches = collections.Counter()
    for entries in slots.values():
        for (g1, x1), (g2, x2) in itertools.combinations(entries, 2):
            if g1 != g2 and same(x1, x2) and not at_bound(x1):
                matches[(g1, g2)] += 1
    republished = {pair for pair, n in matches.items() if n >= 2}
    dropped = set()
    for entries in slots.values():
        for (g1, x1), (g2, x2) in itertools.combinations(entries, 2):
            if (g1, g2) in republished and same(x1, x2) and id(x1) not in dropped:
                dropped.add(id(x2))

    # --- groups
    groups = {}
    for g, rows in by_group.items():
        rows = [x for x in rows if id(x) not in dropped]
        report["republished row"] += len(by_group[g]) - len(rows)
        if not rows:
            continue
        if all(x["kind"] == "logit" for x in rows) and any(not 0 <= x["raw"] <= bound(x["metric"]) for x in rows):
            report["label contradicted by values: unknown scale"] += 1   # scores beyond the stated bound
            for x in rows:
                x["kind"] = "identity"
        kinds = {x["kind"] for x in rows}
        if len(kinds) > 1:
            raise ValueError(f"group {g} mixes metric kinds {sorted({x['metric'] for x in rows})}")
        k = kinds.pop()
        if len({x["couple"] for x in rows}) < 2:
            report["group with one couple"] += 1                     # no information on a difference
            continue
        if len({x["raw"] for x in rows}) == 1 and all(at_bound(x) for x in rows):
            report["group saturated at a bound"] += 1                # every couple at 0 % or 100 %: no difference
            continue
        n_steps = None
        for x in rows:
            v = -x["raw"] if x["metric"] in LOWER_IS_BETTER else x["raw"]
            x["h"] = 1.0
            if k == "logit":
                if n_steps is None:
                    n_steps = scoring_steps([y["raw"] / bound(y["metric"]) for y in rows])
                q = empirical_q(x["raw"] / bound(x["metric"]), n_steps)
                x["y"] = math.log(q / (1 - q))
                x["h"] = 0.5 / math.sqrt(q * (1 - q))
            elif k == "log":
                x["y"] = math.log(v)
            else:
                x["y"] = v
        ys = [x["y"] for x in rows]
        mu = sum(ys) / len(ys)
        sd = (sum((y - mu) ** 2 for y in ys) / len(ys)) ** 0.5 if field != "cost_usd" else 1.0
        sd = sd or 1.0                                                  # a tie away from the bounds: equal couples
        steps = sorted({round(abs(p - q), 9) for p in ys for q in ys if p != q})
        for x in rows:
            x["z"] = (x["y"] - mu) / sd                                 # numerical prescale; the model is affine-invariant
        groups[g] = dict(rows=rows, mu=mu, sd=sd, kind=k, metric=rows[0]["metric"], family=family[g],
                         publisher=rows[0]["publisher"], task=rows[0]["task"], n_steps=n_steps,
                         floor=max((steps[0] if steps else 0.0) / sd / math.sqrt(12), 1e-3))  # noise floor: resolution
    return groups, report, sorted(republished)


# ---------------------------------------------------------------- Stan data
EFFECTS = ("pub_couple", "pub_model", "couple_task")
GH_NODES = 9                                                        # Gauss–Hermite nodes of the panel read-out


def panel(groups, names):
    """Benchmarks a quality is read on: every group with a bounded score, each family counting once."""
    count = collections.Counter(groups[g]["family"] for g in names if groups[g]["kind"] == "logit")
    return [(b, 1.0 / count[groups[g]["family"]] if groups[g]["family"] else 1.0)
            for b, g in enumerate(names) if groups[g]["kind"] == "logit"]


def centring(levels):
    """Centring sets of the effects: publisher for u and w, task type for v (see lqm.stan)."""
    out = {}
    for n, e, pos in ((1, "pub_couple", 0), (2, "pub_model", 0), (3, "couple_task", 1)):
        keys = sorted({k[pos] for k in levels[e]})
        idx = {k: i + 1 for i, k in enumerate(keys)}
        out[f"S{n}"], out[f"set{n}"] = len(keys), [idx[k[pos]] for k in levels[e]]
    return out


def stan_data(groups, axis):
    """The model's data block, plus the index maps needed to read its output."""
    import numpy as np
    names = sorted(groups)
    entries = [(b, x) for b, g in enumerate(names) for x in groups[g]["rows"]]
    couples = sorted({x["couple"] for _, x in entries})
    ci = {c: i for i, c in enumerate(couples)}
    model_of = {c: c.split("@")[0] for c in couples}
    key = {"pub_couple": lambda s, c, t: (s, c),
           "pub_model": lambda s, c, t: (s, model_of[c]),
           "couple_task": lambda s, c, t: None if t in NO_TASK_EFFECT else (c, t)}
    # an effect level carried by a single row cannot be told apart from that row's noise: it is left out
    count = {e: collections.Counter(key[e](x["publisher"], x["couple"], x["task"]) for _, x in entries) for e in EFFECTS}
    levels = {e: sorted(k for k, n in count[e].items() if k is not None and n >= 2) for e in EFFECTS}
    li = {e: {k: i + 1 for i, k in enumerate(levels[e])} for e in EFFECTS}     # 1-based; 0 = none

    def lvl(e, s, c, t):
        k = key[e](s, c, t)
        return li[e].get(k, 0) if k is not None else 0

    P = panel(groups, names) if axis == "quality" else []
    xg, wg = np.polynomial.hermite.hermgauss(GH_NODES)
    data = dict(
        N=len(entries), G=len(names), C=len(couples), cost=int(axis == "cost"),
        grp=[b + 1 for b, _ in entries], cpl=[ci[x["couple"]] + 1 for _, x in entries],
        z=[x["z"] for _, x in entries], h=[x["h"] for _, x in entries], ea=[x["ea"] for _, x in entries],
        L1=len(levels["pub_couple"]), L2=len(levels["pub_model"]), L3=len(levels["couple_task"]),
        k1=[lvl("pub_couple", x["publisher"], x["couple"], x["task"]) for _, x in entries],
        k2=[lvl("pub_model", x["publisher"], x["couple"], x["task"]) for _, x in entries],
        k3=[lvl("couple_task", x["publisher"], x["couple"], x["task"]) for _, x in entries],
        own1=[ci[c] + 1 for _, c in levels["pub_couple"]],
        **centring(levels),
        noise_floor=[groups[g]["floor"] for g in names], mu=[groups[g]["mu"] for g in names],
        sd=[groups[g]["sd"] for g in names],
        P=len(P), pg=[b + 1 for b, _ in P], pw=[w for _, w in P],
        r1=[[lvl("pub_couple", groups[names[b]]["publisher"], c, groups[names[b]]["task"]) for c in couples] for b, _ in P],
        r2=[[lvl("pub_model", groups[names[b]]["publisher"], c, groups[names[b]]["task"]) for c in couples] for b, _ in P],
        r3=[[lvl("couple_task", groups[names[b]]["publisher"], c, groups[names[b]]["task"]) for c in couples] for b, _ in P],
        has_v=[int(groups[names[b]]["task"] not in NO_TASK_EFFECT) for b, _ in P],
        K=GH_NODES, ghx=list(xg * math.sqrt(2)), ghw=list(wg / math.sqrt(math.pi)))
    if not P:                                                       # Stan wants a P × C array even when P = 0
        data.update(r1=np.zeros((0, len(couples)), int), r2=np.zeros((0, len(couples)), int),
                    r3=np.zeros((0, len(couples)), int))
    return data, dict(names=names, couples=couples, ci=ci, levels=levels)


# ---------------------------------------------------------------- fit
def cmdstan():
    import cmdstanpy
    path = os.environ.get("CMDSTAN") or next(
        (os.path.join(d, x) for d in [os.path.join(os.path.dirname(HERE), ".stan")] if os.path.isdir(d)
         for x in sorted(os.listdir(d), reverse=True) if x.startswith("cmdstan-")), None)
    if path:
        cmdstanpy.set_cmdstan_path(path)
    return cmdstanpy


def fit(groups, axis="quality", chains=4, warmup=1000, samples=1000, seed=7, parallel=None, adapt_delta=0.9,
        max_treedepth=10, output_dir=None):
    """Sample the posterior. Returns the CmdStanMCMC object and the index maps."""
    cs = cmdstan()
    data, maps = stan_data(groups, axis)
    model = cs.CmdStanModel(stan_file=STAN_FILE)
    mcmc = model.sample(data=data, chains=chains, parallel_chains=parallel or min(chains, os.cpu_count() or 1),
                        iter_warmup=warmup, iter_sampling=samples, seed=seed, adapt_delta=adapt_delta,
                        max_treedepth=max_treedepth, show_progress=False, output_dir=output_dir)
    return mcmc, maps


# ---------------------------------------------------------------- reading the posterior
def quantile(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    f = int(k)
    return xs[f] if f + 1 >= len(xs) else xs[f] + (xs[f + 1] - xs[f]) * (k - f)


def quasi_variances(L, lo=0.16, hi=0.84):
    """Quasi-variances (Firth & de Menezes 2004) of the columns of L (draws × couples), fitted on robust spreads.

    For every pair (i, j), V_ij = ((q_hi − q_lo)/2)² of L_i − L_j across draws: the squared half-width of the
    16–84 % interval of the difference (a variance for a normal law, robust to heavy tails). q ≥ 0 minimises
    Σ (log(q_i + q_j) − log V_ij)², so that q_i + q_j reproduces V_ij for every pair. Returns (q, worst relative
    error of √(q_i + q_j) against √V_ij, median relative error)."""
    import numpy as np
    L = np.asarray(L)
    C = L.shape[1]
    I, J = np.triu_indices(C, 1)
    D = L[:, I] - L[:, J]
    V = ((np.quantile(D, hi, axis=0) - np.quantile(D, lo, axis=0)) / 2) ** 2
    V = np.maximum(V, 1e-12)
    lq = np.log(np.maximum(np.array([np.median(V[(I == c) | (J == c)]) / 2 for c in range(C)]), 1e-12))
    for _ in range(500):                                             # Gauss–Newton on log q
        q = np.exp(lq)
        s = q[I] + q[J]
        res = np.log(s) - np.log(V)
        Jm = np.zeros((len(I), C))
        Jm[np.arange(len(I)), I] = q[I] / s
        Jm[np.arange(len(I)), J] = q[J] / s
        step = np.linalg.lstsq(Jm, -res, rcond=None)[0]
        lq += step
        if np.max(np.abs(step)) < 1e-10:
            break
    q = np.exp(lq)
    rel = np.abs(np.sqrt((q[I] + q[J]) / V) - 1)
    return q, float(rel.max()), float(np.median(rel))


def summarise(mcmc, maps, groups, lo=0.16, hi=0.84, min_publishers=2):
    """Per couple, on the log scale: centre = posterior median of `level`; half = quasi-standard error (the
    half-width of a 16–84 % interval that makes any two couples comparable); published = measured by at least
    `min_publishers` publishers. Ratios to a reference couple are exp(centre − centre_ref), each couple keeping its
    own interval. Also returns the convergence diagnostics."""
    import numpy as np
    L = mcmc.stan_variable("level")                                  # draws × couples
    q, qv_max, qv_med = quasi_variances(L, lo, hi)
    pubs = collections.defaultdict(set)
    for g in groups.values():
        for x in g["rows"]:
            pubs[x["couple"]].add(x["publisher"])
    out = {c: dict(centre=float(np.median(L[:, i])), half=float(math.sqrt(q[i])), publishers=len(pubs[c]),
                   published=len(pubs[c]) >= min_publishers)
           for c, i in maps["ci"].items()}
    return out, diagnostics(mcmc, qv_max, qv_med)


def diagnostics(mcmc, qv_max=None, qv_med=None):
    """Rank-normalised split R̂ and bulk/tail ESS over every parameter and read-out (Vehtari et al. 2021), from
    CmdStan's stansummary; divergent transitions and saturated trees."""
    s = mcmc.summary()
    s = s[[not i.startswith("lp__") for i in s.index]]
    col = {c.lower(): c for c in s.columns}
    rh, eb, et = s[col["r_hat"]], s[col.get("ess_bulk", "ESS_bulk")], s[col.get("ess_tail", "ESS_tail")]
    lvl = s[[i.startswith("level[") for i in s.index]]
    d = mcmc.diagnose() or ""
    div = int(sum(mcmc.divergences)) if mcmc.divergences is not None else None
    tree = int(sum(mcmc.max_treedepths)) if mcmc.max_treedepths is not None else None
    return dict(rhat_max=round(float(rh.max()), 4), ess_bulk_min=int(eb.min()), ess_tail_min=int(et.min()),
                rhat_max_level=round(float(lvl[col["r_hat"]].max()), 4),
                ess_bulk_min_level=int(lvl[col.get("ess_bulk", "ESS_bulk")].min()),
                divergences=div, max_treedepth_hits=tree, draws=int(mcmc.draws().shape[0] * mcmc.chains),
                worst_rhat=list(rh.sort_values(ascending=False).index[:5]),
                qv_error_max=None if qv_max is None else round(qv_max, 4),
                qv_error_median=None if qv_med is None else round(qv_med, 4))


CONVERGED = dict(rhat=1.01, ess=400)


def converged(diag):
    return (diag["rhat_max"] <= CONVERGED["rhat"] and diag["ess_bulk_min"] >= CONVERGED["ess"]
            and diag["ess_tail_min"] >= CONVERGED["ess"] and diag["divergences"] == 0)


def predict(mcmc, maps, groups, rows, thin=4, seed=0):
    """Posterior predictive of rows the fit did not see, in groups it did. Each row: dict(group, couple, publisher,
    task, h=1). Returns per row (mean of the expected value f⁻¹ scale, list of predictive draws of f(y)) where known
    effects are used and unknown ones drawn from their distribution; the noise is Student-t_ν(σ_b·h)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    V = {k: mcmc.stan_variable(k)[::thin] for k in ("theta", "o", "a", "sigma", "z1", "z2", "z3", "tau", "psi", "omega", "nu")}
    D = len(V["o"])
    names, ci, levels = maps["names"], maps["ci"], maps["levels"]
    bi = {g: i for i, g in enumerate(names)}
    li = {e: {k: i for i, k in enumerate(levels[e])} for e in EFFECTS}
    own1 = np.array([ci[c] for _, c in levels["pub_couple"]], dtype=int)
    cs = centring(levels)

    def centred(E, sets):
        sets = np.asarray(sets)
        for k in np.unique(sets):
            E[:, sets == k] -= E[:, sets == k].mean(axis=1, keepdims=True)
        return E
    U = centred(V["z1"] * V["tau"][:, own1], cs["set1"]) if len(own1) else np.zeros((D, 0))
    W = centred(V["z2"] * V["psi"][:, None], cs["set2"])
    Vt = centred(V["z3"] * V["omega"][:, None], cs["set3"])
    out = []
    for x in rows:
        b, c = bi[x["group"]], ci[x["couple"]]
        G = groups[x["group"]]
        lat = V["theta"][:, c].copy()
        k = li["pub_couple"].get((x["publisher"], x["couple"]))
        lat += U[:, k] if k is not None else rng.normal(0, 1, D) * V["tau"][:, c]
        k = li["pub_model"].get((x["publisher"], x["couple"].split("@")[0]))
        lat += W[:, k] if k is not None else rng.normal(0, 1, D) * V["psi"]
        if x["task"] not in NO_TASK_EFFECT:
            k = li["couple_task"].get((x["couple"], x["task"]))
            lat += Vt[:, k] if k is not None else rng.normal(0, 1, D) * V["omega"]
        m = V["o"][:, b] + V["a"][:, b] * lat
        noise = V["sigma"][:, b] * x.get("h", 1.0) * rng.standard_t(V["nu"])
        out.append((G["mu"] + G["sd"] * m, G["mu"] + G["sd"] * (m + noise)))
    return out
