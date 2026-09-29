"""Latent quality and cost of (model, effort) couples, fused from heterogeneous public benchmarks.

For every measured row r (group b, couple c of model m, publisher s, task type t):

    f(y_r) = o_b + a_b · (θ_c + u_{s,c} + w_{s,m} + v_{c,t}) + ε_r,      ε_r ~ Student-t₄(0, m_r · σ_b²)

  f        per metric (METRIC RULES): empirical logit of a bounded score, log of an unbounded positive quantity,
           identity for an interval or unknown scale; log on the cost axis.
  o_b      group offset, flat prior.
  a_b      group gain. Quality: log(a_b/σ_b) ~ N(0, s_d²) (discrimination, pooled; its zero mean sets the unit
           of θ). Cost: log a_b ~ N(0, s_a²) (elasticity, pooled around 1: θ is the log cost on a typical task).
  σ_b      group noise. Quality: Jeffreys 1/σ above the metric's resolution. Cost: log σ_b ~ N(μ_σ, s_σ²), pooled.
  θ_c      latent quality (quality axis) or log cost (cost axis) of the couple; θ ~ N(0, 10²), anchor fixed at 0.
  u_{s,c}  publisher × couple effect ~ N(0, τ_c²), τ_c² ~ IG(2, β), β ~ Exp(mean 0.05) pooled over couples.
  w_{s,m}  publisher × model effect, shared by the model's effort levels, ~ N(0, ψ²), ψ² ~ IG(1, 0.01).
  v_{c,t}  couple × task-type effect ~ N(0, ω²), ω² ~ IG(1, 0.01); composite indices (task type 'mixed') carry none.
  m_r      3 for an early-access (pre-release) run, else 1.
  Hyper-priors: s_d², s_a², s_σ² ~ IG(1, 0.25); μ_σ flat.

Estimation: Gibbs sampling. o_b is integrated out for the slice-sampling updates of log a_b and log σ_b; θ and the
effects are normal conjugates; the Student-t is a latent scale mixture; hyper-parameters have conjugate updates.
Exact moves along directions the likelihood cannot see keep the chain mixing: a global rescaling (θ and effects × λ,
gains ÷ λ), and for every effect family a shift of the couples that own an effect against it (the anchor's owner:
the anchor level against everything else). Independent chains run in parallel processes. Pure standard library.
"""
import collections, csv, itertools, math, random, re

from catalog import FAMILY_OF, PUBLISHER_OF

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


def empirical_logit(p, n):
    """logit((p·n + ½) / (n + 1)): a proportion at 0 or 1 lands half a scoring step inside the bounds."""
    q = (p * n + 0.5) / (n + 1)
    return math.log(q / (1 - q))


# ---------------------------------------------------------------- data
EFFORTS = {"low", "medium", "high", "xhigh", "max", "solo"}           # 'solo': a model without an effort setting
NO_TASK_EFFECT = {"mixed", ""}
EARLY_ACCESS_VARIANCE = 3.0


def load(path, models, field="score"):
    """Rows of the data file → groups ready for fit(). field = 'score' (quality) or 'cost_usd' (cost).

    Republished numbers count once: two groups of one family that share at least two identical values away from the
    metric's bounds are one experiment printed twice, and their identical rows are kept once, in the larger group.
    A single coincidence, or equality at a bound (two runs both at 100 %), is not a republication."""
    report = collections.Counter()
    by_group = collections.defaultdict(list)
    for r in csv.DictReader(open(path)):
        if not r["group"] or r["group"].startswith("#") or r["model"] not in models or r["effort"] not in EFFORTS:
            continue
        try:
            raw = float(r[field])
        except (TypeError, ValueError):
            continue
        metric = "usd" if field == "cost_usd" else r["score_metric"]
        if field == "cost_usd" and raw <= 0:
            continue
        by_group[r["group"]].append(dict(
            couple=f'{r["model"]}@{r["effort"]}', model=r["model"], publisher=PUBLISHER_OF.get(r["source"], r["source"]),
            task=r["task_type"], raw=raw, metric=metric, kind="log" if field == "cost_usd" else kind(metric),
            m=EARLY_ACCESS_VARIANCE if "EAP-run" in r["confound"] else 1.0))

    # --- republications
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
            slots[(FAMILY_OF.get(g, g), x["couple"])].append((g, x))
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
            if k == "logit":
                if n_steps is None:
                    n_steps = scoring_steps([y["raw"] / bound(y["metric"]) for y in rows])
                x["y"] = empirical_logit(x["raw"] / bound(x["metric"]), n_steps)
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
        groups[g] = dict(rows=rows, mu=mu, sd=sd, kind=k, metric=rows[0]["metric"], family=FAMILY_OF.get(g),
                         n_steps=n_steps,
                         floor=max((steps[0] if steps else 0.0) / sd / math.sqrt(12), 1e-3))  # noise floor: resolution
    return groups, report, sorted(republished)


# ---------------------------------------------------------------- sampler
def slice_sample(logf, x0, rng, w=1.0, m=20):
    """Univariate slice sampler with stepping out and shrinkage (Neal 2003)."""
    y = logf(x0) - rng.expovariate(1.0)
    lo = x0 - w * rng.random()
    hi = lo + w
    j = int(m * rng.random())
    k = m - 1 - j
    while j > 0 and logf(lo) > y:
        lo -= w
        j -= 1
    while k > 0 and logf(hi) > y:
        hi += w
        k -= 1
    while True:
        x1 = lo + (hi - lo) * rng.random()
        if logf(x1) > y:
            return x1
        if x1 < x0:
            lo = x1
        else:
            hi = x1


NU = 4.0                                            # Student-t degrees of freedom
THETA_VAR = 100.0                                   # θ ~ N(0, 10²)
EFFECTS = ("pub_couple", "pub_model", "couple_task")


def _structure(groups, anchor):
    names = sorted(groups)
    entries = [(b, x) for b, g in enumerate(names) for x in groups[g]["rows"]]
    couples = sorted({x["couple"] for _, x in entries})
    ci = {c: i for i, c in enumerate(couples)}
    model_of = [c.split("@")[0] for c in couples]
    keys = {"pub_couple": lambda x: (x["publisher"], x["couple"]),
            "pub_model": lambda x: (x["publisher"], x["model"]),
            "couple_task": lambda x: None if x["task"] in NO_TASK_EFFECT else (x["couple"], x["task"])}
    levels = {e: sorted({keys[e](x) for _, x in entries if keys[e](x) is not None}) for e in EFFECTS}
    li = {e: {k: i for i, k in enumerate(levels[e])} for e in EFFECTS}
    # owner of a level = the couples it shifts together: one couple, or all couples of one model
    owner = {"pub_couple": lambda k: (k[1],), "pub_model": lambda k: tuple(c for c in couples if c.split("@")[0] == k[1]),
             "couple_task": lambda k: (k[0],)}
    owners = {}
    for e in EFFECTS:
        grp = collections.defaultdict(list)
        for i, k in enumerate(levels[e]):
            grp[owner[e](k)].append(i)
        owners[e] = [(tuple(ci[c] for c in own), idx) for own, idx in grp.items()]
    rows = []
    for b, x in entries:
        eff = [li[e].get(keys[e](x), -1) if keys[e](x) is not None else -1 for e in EFFECTS]
        # [group, couple, z, m, λ, effect indices…, precision on θ scale, (z − o)/a]
        rows.append([b, ci[x["couple"]], x["z"], x["m"], 1.0, eff, 0.0, 0.0])
    return names, couples, ci, model_of, levels, owners, rows


def fit(groups, anchor, axis="quality", sweeps=5000, burn=1500, thin=2, seed=7, fixed=None):
    """One Gibbs chain. axis = 'quality' or 'cost'. `fixed` pins hyper-parameters (keys 'sd2', 'sa2',
    'tau2', 'psi2', 'om2', 'm_sig', 's2_sig'); it exists only for simulation-based calibration."""
    fixed = fixed or {}
    cost = axis == "cost"
    rng = random.Random(seed)
    names, couples, ci, model_of, levels, owners, rows = _structure(groups, anchor)
    nG, nC = len(names), len(couples)
    nL = {e: len(levels[e]) for e in EFFECTS}
    iA = ci[anchor]
    by_group, by_couple = collections.defaultdict(list), collections.defaultdict(list)
    by_level = {e: collections.defaultdict(list) for e in EFFECTS}
    for r in rows:
        by_group[r[0]].append(r)
        by_couple[r[1]].append(r)
        for j, e in enumerate(EFFECTS):
            if r[5][j] >= 0:
                by_level[e][r[5][j]].append(r)
    level_couple = [ci[k[1]] for k in levels["pub_couple"]]            # τ² is per couple
    floor = [groups[g]["floor"] for g in names]

    th = [0.0] * nC
    ef = {e: [0.0] * nL[e] for e in EFFECTS}
    o, sg, a = [0.0] * nG, [0.5] * nG, [0.5 if not cost else 1.0] * nG
    sd2, sa2 = fixed.get("sd2", 1.0), fixed.get("sa2", 0.16)
    tau2 = [fixed.get("tau2", 0.05)] * nC
    beta = 0.05
    psi2, om2 = fixed.get("psi2", 0.05), fixed.get("om2", 0.05)
    m_sig, s2_sig = fixed.get("m_sig", math.log(0.1)), fixed.get("s2_sig", 1.0)

    def var(e, k):
        return tau2[level_couple[k]] if e == "pub_couple" else (psi2 if e == "pub_model" else om2)

    def X(r):
        x = th[r[1]]
        for j, e in enumerate(EFFECTS):
            if r[5][j] >= 0:
                x += ef[e][r[5][j]]
        return x

    def gain_prior(b, l):                                             # −log prior density of log a_b
        return (0.5 * l * l / sa2) if cost else (0.5 * (l - math.log(sg[b])) ** 2 / sd2)

    draws = []
    for it in range(sweeps):
        # ---- group gain, noise, offset (o integrated out for a and σ; moments scale as 1/σ²)
        for b in range(nG):
            R = by_group[b]
            xs = [X(r) for r in R]
            ws = [r[4] / r[3] for r in R]
            W1 = sum(ws)
            mx = sum(w * x for w, x in zip(ws, xs)) / W1
            my = sum(w * r[2] for w, r in zip(ws, R)) / W1
            Pxx = Pxy = Pyy = 0.0
            for w, r, x in zip(ws, R, xs):
                dx, dy = x - mx, r[2] - my
                Pxx += w * dx * dx; Pxy += w * dx * dy; Pyy += w * dy * dy
            s2 = sg[b] ** 2

            def log_post_gain(l):
                A = math.exp(l)
                return -0.5 * (Pyy - 2 * A * Pxy + A * A * Pxx) / s2 - gain_prior(b, l)
            a[b] = math.exp(slice_sample(log_post_gain, math.log(a[b]), rng))
            A = a[b]
            rss1 = Pyy - 2 * A * Pxy + A * A * Pxx

            def log_post_noise(l):
                if l < math.log(floor[b]):
                    return -1e300
                if cost:
                    prior = 0.5 * (l - m_sig) ** 2 / s2_sig
                else:
                    prior = 0.5 * (math.log(A) - l) ** 2 / sd2
                return -len(R) * l - 0.5 * rss1 * math.exp(-2 * l) - 0.5 * (math.log(W1) - 2 * l) - prior
            sg[b] = math.exp(slice_sample(log_post_noise, math.log(max(sg[b], floor[b] * 1.0001)), rng))
            o[b] = rng.gauss(my - A * mx, sg[b] / math.sqrt(W1))

        # ---- θ and effects: normal conjugates on the θ scale
        for r in rows:
            b = r[0]
            r[6] = r[4] / (r[3] * sg[b] * sg[b]) * a[b] * a[b]
            r[7] = (r[2] - o[b]) / a[b]
        for c in range(nC):
            if c == iA:
                continue
            P, N = 1.0 / THETA_VAR, 0.0
            for r in by_couple[c]:
                P += r[6]; N += r[6] * (r[7] - X(r) + th[c])
            th[c] = rng.gauss(N / P, P ** -0.5)
        for j, e in enumerate(EFFECTS):
            vec = ef[e]
            for k in range(nL[e]):
                P, N = 1.0 / var(e, k), 0.0
                for r in by_level[e][k]:
                    P += r[6]; N += r[6] * (r[7] - X(r) + vec[k])
                vec[k] = rng.gauss(N / P, P ** -0.5)

        # ---- Student-t scale mixture
        for r in rows:
            b = r[0]
            e_ = r[2] - o[b] - a[b] * X(r)
            r[4] = rng.gammavariate((NU + 1) / 2, 2.0 / (NU + e_ * e_ / (r[3] * sg[b] ** 2)))

        # ---- hyper-parameters
        if cost:
            ls = [math.log(x) for x in sg]
            if "m_sig" not in fixed:
                m_sig = rng.gauss(sum(ls) / nG, (s2_sig / nG) ** 0.5)
            if "s2_sig" not in fixed:
                s2_sig = 1.0 / rng.gammavariate(1.0 + nG / 2, 1.0 / (0.25 + sum((x - m_sig) ** 2 for x in ls) / 2))
            if "sa2" not in fixed:
                sa2 = 1.0 / rng.gammavariate(1.0 + nG / 2, 1.0 / (0.25 + sum(math.log(x) ** 2 for x in a) / 2))
        elif "sd2" not in fixed:
            ss = sum(math.log(a[b] / sg[b]) ** 2 for b in range(nG))
            sd2 = 1.0 / rng.gammavariate(1.0 + nG / 2, 1.0 / (0.25 + ss / 2))
        if "tau2" not in fixed:
            per = collections.defaultdict(list)
            for k, x in enumerate(ef["pub_couple"]):
                per[level_couple[k]].append(x)
            for c in range(nC):
                us = per[c]
                tau2[c] = 1.0 / rng.gammavariate(2.0 + len(us) / 2, 1.0 / (beta + sum(x * x for x in us) / 2))
            beta = rng.gammavariate(1.0 + 2.0 * nC, 1.0 / (1.0 / 0.05 + sum(1.0 / t for t in tau2)))
        if "psi2" not in fixed and nL["pub_model"]:
            psi2 = 1.0 / rng.gammavariate(1.0 + nL["pub_model"] / 2, 1.0 / (0.01 + sum(x * x for x in ef["pub_model"]) / 2))
        if "om2" not in fixed and nL["couple_task"]:
            om2 = 1.0 / rng.gammavariate(1.0 + nL["couple_task"] / 2, 1.0 / (0.01 + sum(x * x for x in ef["couple_task"]) / 2))

        # ---- exact moves along directions the likelihood cannot see
        def log_post_scale(l):                                        # θ, effects × λ; gains ÷ λ; α − log λ
            lam2 = math.exp(2 * l)
            val = (nC - 1 + sum(nL.values())) * l                      # Jacobian of the rescaling
            val -= 0.5 * lam2 * sum(t * t for t in th) / THETA_VAR
            for e in EFFECTS:
                val -= 0.5 * lam2 * sum(x * x / var(e, k) for k, x in enumerate(ef[e]))
            if cost:
                val -= 0.5 * sum((math.log(x) - l) ** 2 for x in a) / sa2
            else:
                val -= 0.5 * sum((math.log(a[b] / sg[b]) - l) ** 2 for b in range(nG)) / sd2
            return val
        lam = math.exp(slice_sample(log_post_scale, 0.0, rng, w=0.3))
        th = [t * lam for t in th]
        for e in EFFECTS:
            ef[e] = [x * lam for x in ef[e]]
        a = [x / lam for x in a]
        # Owners against their effects. For an owner set S of couples and its levels K in effect family e:
        #   anchor ∉ S: θ_c + δ (c ∈ S), effect_k − δ (k ∈ K)
        #   anchor ∈ S: effect_k + δ (k ∈ K), θ_c + δ (c ∉ S), o_b − a_b·δ; then θ_c + δ (c ∈ S, c ≠ anchor),
        #               effect_k − δ, the anchor's rows that carry the effect entering the likelihood
        # δ | rest is normal: the effects' prior, θ's prior, and the rows of S that do not carry an effect of K.
        for j, e in enumerate(EFFECTS):
            vec = ef[e]
            for S, K in owners[e]:
                Kset = set(K)
                with_anchor = iA in S
                P = sum(1.0 / var(e, k) for k in K)
                N = sum(vec[k] / var(e, k) for k in K) * (-1.0 if with_anchor else 1.0)
                if with_anchor:
                    others = [c for c in range(nC) if c not in S]
                    P += len(others) / THETA_VAR
                    N -= sum(th[c] for c in others) / THETA_VAR
                else:
                    P += len(S) / THETA_VAR
                    N -= sum(th[c] for c in S) / THETA_VAR
                for c in S:
                    for r in by_couple[c]:
                        if r[5][j] not in Kset:
                            y = (r[2] - o[r[0]]) / a[r[0]] - X(r)
                            w = r[4] / (r[3] * sg[r[0]] ** 2) * a[r[0]] ** 2
                            P += w; N += w * (-y if with_anchor else y)
                d = rng.gauss(N / P, P ** -0.5)
                if with_anchor:
                    for k in K:
                        vec[k] += d
                    Sset = set(S)
                    th = [t if c in Sset else t + d for c, t in enumerate(th)]
                    o = [o[b] - a[b] * d for b in range(nG)]
                    # the reference couple's siblings in S against the effect: θ_c + δ (c ∈ S, c ≠ reference),
                    # effect_k − δ; the reference couple's own rows that carry the effect see −δ
                    rest = [c for c in S if c != iA]
                    if rest:
                        P = sum(1.0 / var(e, k) for k in K) + len(rest) / THETA_VAR
                        N = sum(vec[k] / var(e, k) for k in K) - sum(th[c] for c in rest) / THETA_VAR
                        for c in rest:
                            for r in by_couple[c]:
                                if r[5][j] not in Kset:
                                    y = (r[2] - o[r[0]]) / a[r[0]] - X(r)
                                    w = r[4] / (r[3] * sg[r[0]] ** 2) * a[r[0]] ** 2
                                    P += w; N += w * y
                        for r in by_couple[iA]:
                            if r[5][j] in Kset:
                                y = (r[2] - o[r[0]]) / a[r[0]] - X(r)
                                w = r[4] / (r[3] * sg[r[0]] ** 2) * a[r[0]] ** 2
                                P += w; N -= w * y
                        d = rng.gauss(N / P, P ** -0.5)
                        for c in rest:
                            th[c] += d
                        for k in K:
                            vec[k] -= d
                else:
                    for c in S:
                        th[c] += d
                    for k in K:
                        vec[k] -= d
        # the level of every other couple against every offset: θ_{c≠A} + δ, o_b − a_b·δ. Only the reference
        # couple's rows see it (their residual moves by +δ); δ | rest is normal.
        P = (nC - 1) / THETA_VAR
        N = -sum(t for c, t in enumerate(th) if c != iA) / THETA_VAR
        for r in by_couple[iA]:
            y = (r[2] - o[r[0]]) / a[r[0]] - X(r)
            w = r[4] / (r[3] * sg[r[0]] ** 2) * a[r[0]] ** 2
            P += w; N -= w * y
        d = rng.gauss(N / P, P ** -0.5)
        th = [t if c == iA else t + d for c, t in enumerate(th)]
        o = [o[b] - a[b] * d for b in range(nG)]
        if it >= burn and (it - burn) % thin == 0:
            draws.append(dict(th=th[:], a=a[:], sg=sg[:], o=o[:], ef={e: ef[e][:] for e in EFFECTS},
                              tau2=tau2[:], psi2=psi2, om2=om2, sd2=sd2, sa2=sa2))
    return dict(axis=axis, couples=couples, ci=ci, model_of=model_of, names=names, levels=levels,
                groups=groups, anchor=anchor, draws=draws, chains=[len(draws)])


def _chain(args):
    return fit(*args[0], **args[1])["draws"]


def fit_chains(groups, anchor, axis="quality", chains=4, sweeps=5000, burn=1500, thin=2, seed=7, processes=None):
    """Independent chains (seeds seed … seed + chains − 1) in parallel processes; draws pooled, chains kept apart
    for the convergence diagnostic."""
    import multiprocessing as mp
    jobs = [((groups, anchor), dict(axis=axis, sweeps=sweeps, burn=burn, thin=thin, seed=seed + i)) for i in range(chains)]
    with mp.get_context("fork").Pool(processes or min(chains, mp.cpu_count())) as pool:
        parts = pool.map(_chain, jobs)
    F = fit(groups, anchor, axis=axis, sweeps=0)
    F["draws"] = [d for p in parts for d in p]
    F["chains"] = [len(p) for p in parts]
    return F


# ---------------------------------------------------------------- reading the posterior
def quantile(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    f = int(k)
    return xs[f] if f + 1 >= len(xs) else xs[f] + (xs[f + 1] - xs[f]) * (k - f)


def rhat(F, index):
    """Split-free Gelman–Rubin R̂ of θ[index] across chains."""
    chunks, i = [], 0
    for n in F["chains"]:
        chunks.append([d["th"][index] for d in F["draws"][i:i + n]])
        i += n
    if len(chunks) < 2:
        return float("nan")
    m, n = len(chunks), min(len(c) for c in chunks)
    means = [sum(c[:n]) / n for c in chunks]
    grand = sum(means) / m
    B = n * sum((x - grand) ** 2 for x in means) / (m - 1)
    Wv = sum(sum((x - mu) ** 2 for x in c[:n]) / (n - 1) for c, mu in zip(chunks, means)) / m
    return math.sqrt(((n - 1) / n * Wv + B / n) / Wv) if Wv > 0 else float("nan")


def panel(F):
    """Benchmarks a quality is read on: every group with a bounded score, each family counting once."""
    out = []
    count = collections.Counter(F["groups"][g]["family"] for g in F["names"] if F["groups"][g]["kind"] == "logit")
    for b, g in enumerate(F["names"]):
        G = F["groups"][g]
        if G["kind"] == "logit":
            out.append((b, 1.0 / count[G["family"]] if G["family"] else 1.0))
    return out


def _sigmoid(z):
    return 1.0 / (1.0 + math.exp(-max(min(z, 50.0), -50.0)))


def _score(G, o_b, a_b, x, eps=0.0):
    """Predicted proportion of group G for a couple at latent position x (θ plus effects), with residual eps."""
    return _sigmoid(G["mu"] + G["sd"] * (o_b + a_b * x + eps))


def _t4(rng):
    return rng.gauss(0, 1) / math.sqrt(rng.gammavariate(2.0, 0.5))


def summarise(F, lo=0.16, hi=0.84, every=4, seed=3, min_publishers=2):
    """Per couple, relative to the anchor.

    Quality: value = mean predicted score over the benchmark panel ÷ the anchor's (a ratio of expected scores, exact
    for every draw). Cost: value = exp(θ), the cost ratio on a task of typical elasticity.
    credible = 16–84 % credible interval of that value.
    band     = 16–84 % predictive interval of the ratio one NEW benchmark would report: a benchmark drawn from the
               panel (quality) or from the cost groups (cost) with its gain, level and noise; a new publisher (u, w);
               a new task type (v); each drawn for the couple and for the anchor, the model-level publisher effect
               shared when both are the same model.
    published = measured by at least `min_publishers` publishers."""
    rng = random.Random(seed)
    D = F["draws"][::every]
    iA = F["ci"][F["anchor"]]
    cost = F["axis"] == "cost"
    names, groups = F["names"], F["groups"]
    P = panel(F) if not cost else [(b, 1.0 / (collections.Counter(groups[g]["family"] for g in names)[groups[g]["family"]]
                                              if groups[g]["family"] else 1.0)) for b, g in enumerate(names)]
    Wtot = sum(w for _, w in P)
    cum = list(itertools.accumulate(w for _, w in P))
    pubs = collections.defaultdict(set)
    for g in names:
        for x in groups[g]["rows"]:
            pubs[x["couple"]].add(x["publisher"])
    model_of = F["model_of"]

    def draw_group():
        u = rng.random() * Wtot
        lo_, hi_ = 0, len(cum) - 1
        while lo_ < hi_:
            mid = (lo_ + hi_) // 2
            if cum[mid] < u:
                lo_ = mid + 1
            else:
                hi_ = mid
        return P[lo_][0]

    out = {}
    for c, i in F["ci"].items():
        centre, pred = [], []
        for d in D:
            if cost:
                centre.append(d["th"][i])
            else:
                num = sum(w * _score(groups[names[b]], d["o"][b], d["a"][b], d["th"][i]) for b, w in P)
                den = sum(w * _score(groups[names[b]], d["o"][b], d["a"][b], 0.0) for b, w in P)
                centre.append(math.log(num / den))
            # one new benchmark
            b = draw_group()
            G = groups[names[b]]
            same_model = model_of[i] == model_of[iA]
            w_c = rng.gauss(0, d["psi2"] ** 0.5)
            w_a = w_c if same_model else rng.gauss(0, d["psi2"] ** 0.5)
            x_c = d["th"][i] + rng.gauss(0, d["tau2"][i] ** 0.5) + w_c + rng.gauss(0, d["om2"] ** 0.5)
            x_a = 0.0 + rng.gauss(0, d["tau2"][iA] ** 0.5) + w_a + rng.gauss(0, d["om2"] ** 0.5)
            if i == iA:
                pred.append(0.0)
                continue
            e_c, e_a = d["sg"][b] * _t4(rng), d["sg"][b] * _t4(rng)
            if cost:
                pred.append(d["a"][b] * (x_c - x_a) + e_c - e_a)
            else:
                pred.append(math.log(_score(G, d["o"][b], d["a"][b], x_c, e_c) / _score(G, d["o"][b], d["a"][b], x_a, e_a)))
        out[c] = dict(value=math.exp(quantile(centre, 0.5)),
                      credible=(math.exp(quantile(centre, lo)), math.exp(quantile(centre, hi))),
                      band=(math.exp(quantile(pred, lo)), math.exp(quantile(pred, hi))),
                      publishers=len(pubs[c]), published=len(pubs[c]) >= min_publishers, rhat=rhat(F, i))
    return out
