"""Latent quality and cost of (model, effort) couples, fused from heterogeneous public benchmarks.

For every measured row r (group b, couple c of model m, publisher s, task type t):

    f(y_r) = o_b + a_b · (θ_c + u_{s,c} + w_{s,m} + v_{c,t}) + ε_r,      ε_r ~ Student-t_ν(0, κ_r · h_r² · σ_b² + d_r²)

  f        per metric (METRIC RULES): empirical logit of a bounded score, log of an unbounded positive quantity,
           identity for an interval or unknown scale; log on the cost axis.
  θ_c      latent quality (quality axis) or log cost (cost axis) of the couple. θ sums to zero over the couples:
           no couple is a reference; the page divides by its reference couple afterwards (a display choice).
  o_b      group offset, flat. a_b group gain: quality log(a_b/σ_b) ~ N(0, s_g²) (discrimination, pooled; its zero
           mean sets the unit of θ); cost log a_b ~ N(0, s_g²) (elasticity around 1).
  σ_b      group noise, pooled: log σ_b ~ N(μ_σ, s_σ²) on the group's standardised scale (invariant to an affine change
           of the metric), μ_σ flat.
  d_r      reading precision of the value (READING PRECISION): the standard deviation of the error made in reading it
           — rounding of a printed number, resolution of a chart that was digitised, propagated through a computation —
           carried to the model's scale; known, added to the row's variance.
  h_r      shape of the sampling noise of an empirical logit, 1/(2√(q(1−q))) at the observed proportion q; 1 else.
  κ_r      variance multiplier of an early-access run, log κ ~ N(0, 1); 1 for other runs.
  u, w, v  publisher × couple (sd τ_c, τ_c ~ N⁺(0, s_τ)), publisher × model (sd ψ), couple × task type (sd ω)
           effects; composites (task type 'mixed') carry no task-type effect. A level carried by a single row is left
           out (indistinguishable from that row's noise). u and w are centred within their publisher, v within its
           task type: their mean is confounded with the free offsets of that publisher's (type's) groups.
  Priors:  θ ~ N(0, 10²); s_g, s_τ, ψ, ω, s_σ ~ half-Student-t(3, 0, 2.5); ν ~ Gamma(2, 0.1).

Estimation: Hamiltonian Monte Carlo (NUTS) on lqm.stan — nutpie on the quality axis, CmdStan (CmdStanPy) warm-started
from the previous fit on the cost axis (SAMPLER). The read-out `level` is computed in Stan for every draw; `summarise`
turns it into a centre and a per-couple interval (quasi-variances).
"""
import collections, csv, itertools, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "data"))
from catalog import COMPOSITES, FAMILY_OF, PUBLISHER_OF, UNIT_ALIASES
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


# ---------------------------------------------------------------- reading precision
PREC_FIELD = {"score": "score_prec", "cost_usd": "cost_prec"}


def rounding_sd(text):
    """Standard deviation of the rounding error of a number as written: one unit of its last decimal / √12 (an
    integer: a unit). Used when the data file gives no precision for a value."""
    t = (text or "").strip().lower().split("e")[0]
    dec = len(t.split(".")[1]) if "." in t else 0
    return 10.0 ** -dec / math.sqrt(12)


def reading_sd(r, field):
    """Reading precision δ of a value, in its own unit: the data file's column (score_prec, cost_prec) when filled,
    else the rounding of the value as written in the file."""
    try:
        d = float(r.get(PREC_FIELD[field]) or "nan")
    except ValueError:
        d = float("nan")
    return d if d == d and d >= 0 else rounding_sd(r[field])


def _other_value(r, field):
    """The row's value on the other axis, to confirm a republication: (value, precision, last-digit unit, scale)."""
    try:
        v = float(r[field])
    except (TypeError, ValueError):
        return None
    t = r[field].strip()
    return (v, reading_sd(r, field), 10.0 ** -(len(t.split(".")[1]) if "." in t else 0),
            "usd/" + UNIT_ALIASES.get(r["source"], {}).get(r["unit"], r["unit"] or "") if field == "cost_usd"
            else r["score_metric"])                                  # a cost compares only in one unit


# ---------------------------------------------------------------- data
EFFORTS = {"low", "medium", "high", "xhigh", "max", "solo"}           # 'solo': a model without an effort setting
NO_TASK_EFFECT = {"mixed", ""}


def load(path, models, field="score"):
    """Rows of the data file → groups ready for fit(). field = 'score' (quality) or 'cost_usd' (cost).

    1. Composites: a couple measured on a component of a composite (catalog.COMPOSITES) leaves the composite out.
    2. Homogeneity: a group is split by publisher, harness (without version), scale (bounded scores: bound) and, on
       the cost axis, cost unit — only rows measured under one configuration are compared.
    3. Republished numbers count once: what two groups share — all their common values, or one model's series (its
       efforts) — identical on at least two values away from the metric's bounds, is one experiment printed twice (a
       table reprinted, or a series reused in another chart next to new ones); its identical rows are kept once, in the
       larger group. Identical
       means within what separates two copies of one number: both reading precisions (2·√(δ₁² + δ₂²): two readings
       of one chart point, or of two charts drawing it) plus one unit of the last digit of each (a rounding made the
       wrong way somewhere along the publisher's pipeline). Two rows are one execution only if both their values agree, the
       score and the cost, wherever both rows carry them on one scale. One run scored with two metrics is one
       execution, whose quality is measured once: its cost identifies it, and its rows are kept once on both axes. Confirmed on both axes, the two groups must agree on every value they share but one (a miscopy), and
       on two at least; on one axis alone (the other absent or on another metric), on every value, three at least. Groups are compared within a benchmark family, and within a publisher across its families (the same
       runs reprinted under another grouping). The series must
       agree on every value the two groups share but one at most (one number miscopied): a few coincidences among
       many shared values, or equality at a bound (two runs both at 100 %), are not a republication."""
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
            ea=int("EAP-run" in (r["confound"] or "")), harness=harness_base(r["harness"]), prec=reading_sd(r, field),
            step=10.0 ** -(len(r[field].strip().split(".")[1]) if "." in r[field] else 0),
            other=_other_value(r, "score" if field == "cost_usd" else "cost_usd"),
            unit=UNIT_ALIASES.get(r["source"], {}).get(r["unit"], r["unit"] or "")))

    # --- 1. composites
    for g, spec in COMPOSITES.items():
        if g not in raw:
            continue
        measured = {x["couple"] for h in spec for x in raw.get(h, [])}
        kept = [x for x in raw[g] if x["couple"] not in measured]
        report["composite row, component measured"] += len(raw[g]) - len(kept)
        raw[g] = kept

    # --- 2. homogeneity
    by_group, family = {}, {}
    for g, rows in raw.items():
        parts = collections.defaultdict(list)
        for x in rows:
            # scale: a bounded score by its bound (a percentage and a pass rate are one scale), any other by its label
            scale = x["unit"] if field == "cost_usd" else (
                (x["kind"], bound(x["metric"])) if x["kind"] == "logit" else (x["kind"], x["metric"]))
            parts[(x["publisher"], x["harness"], scale)].append(x)
        for i, (_, xs) in enumerate(sorted(parts.items(), key=lambda kv: -len(kv[1]))):
            name = g if i == 0 else f"{g}~{i + 1}"
            by_group[name], family[name] = xs, FAMILY_OF.get(g)
        report["group split by configuration"] += len(parts) - 1 if parts else 0

    # --- 3. republications
    def close(v1, d1, s1, v2, d2, s2):
        return abs(v1 - v2) <= 2 * math.hypot(d1, d2) + s1 + s2

    def scale(metric):                                                  # a percentage and a pass rate are one scale
        return ("bounded", bound(metric)) if bound(metric) else metric

    def same(x1, x2):
        """One execution printed twice: 0 = no; 2 = both axes agree, each on one scale; 1 = one axis agrees and the
        other cannot tell (absent, or on another scale). One run scored with two metrics is one execution: its two
        scores do not compare, its cost is one. Two scores on one scale under two labels are one metric if they agree
        (a label written two ways), two metrics if they do not."""
        def agree(v1, v2, metric1, metric2, cost):
            if cost and metric1 != metric2 or not cost and scale(metric1) != scale(metric2):
                return None                                             # not on one scale: cannot tell
            if close(*v1, *v2):
                return True
            return False if cost or metric1 == metric2 else None
        a = agree((x1["raw"], x1["prec"], x1["step"]), (x2["raw"], x2["prec"], x2["step"]),
                  *((x1["unit"], x2["unit"]) if field == "cost_usd" else (x1["metric"], x2["metric"])), field == "cost_usd")
        o1, o2 = x1["other"], x2["other"]
        b = None if o1 is None or o2 is None else agree(o1[:3], o2[:3], o1[3], o2[3], field != "cost_usd")
        if a is False or b is False:
            return 0
        return 2 if a and b else 1 if a or b else 0

    def at_bound(x):
        n = bound(x["metric"]) if field != "cost_usd" else None
        return n is not None and (x["raw"] >= 0.9995 * n or x["raw"] <= 0.0005 * n)

    size = {g: len({x["couple"] for x in rows}) for g, rows in by_group.items()}
    order = sorted(by_group, key=lambda g: (-size[g], g))
    slots = collections.defaultdict(list)          # (benchmark family, couple) and (publisher, couple) → [(group, row)]
    for g in order:
        for x in by_group[g]:
            slots[("family", family[g] or g, x["couple"])].append((g, x))
            slots[("publisher", x["publisher"], x["couple"])].append((g, x))
    pairs = {}                                                          # the same two rows, met through either key
    for entries in slots.values():
        for (g1, x1), (g2, x2) in itertools.combinations(entries, 2):
            if g1 != g2 and not at_bound(x1):
                pairs[(id(x1), id(x2))] = (g1, g2, x1, x2)
    matches, shared, single = collections.Counter(), collections.Counter(), collections.Counter()
    for g1, g2, x1, x2 in pairs.values():                            # per group pair, and per model's series in it
        v = same(x1, x2)
        for k in ((g1, g2, ""), (g1, g2, x1["model"])):
            shared[k] += 1
            matches[k] += v > 0
            single[k] += v == 1
    # confirmed on both axes: all shared values but one (a miscopy) and at least two; on one axis only: all, at least 3
    series = {k for k, n in matches.items()
              if ((n >= 3 and n == shared[k]) if single[k] else (n >= 2 and n >= shared[k] - 1))}
    republished = sorted((*k, matches[k], shared[k]) for k in series)   # (group, group, model or "" = all, identical, shared)
    dropped = set()
    for g1, g2, x1, x2 in pairs.values():
        if ((g1, g2, "") in series or (g1, g2, x1["model"]) in series) and same(x1, x2) and id(x1) not in dropped:
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
                x["dy"] = x["prec"] / bound(x["metric"]) * n_steps / (n_steps + 1) / (q * (1 - q))   # delta method
            elif k == "log":
                x["y"] = math.log(v)
                x["dy"] = x["prec"] / abs(v)
            else:
                x["y"] = v
                x["dy"] = x["prec"]
        ys = [x["y"] for x in rows]
        mu = sum(ys) / len(ys)
        sd = (sum((y - mu) ** 2 for y in ys) / len(ys)) ** 0.5 if field != "cost_usd" else 1.0
        sd = sd or 1.0                                                  # a tie away from the bounds: equal couples
        for x in rows:
            x["z"] = (x["y"] - mu) / sd                                 # numerical prescale; the model is affine-invariant
            x["d"] = x["dy"] / sd                                       # reading precision on the same scale
        groups[g] = dict(rows=rows, mu=mu, sd=sd, kind=k, metric=rows[0]["metric"], family=family[g],
                         publisher=rows[0]["publisher"], task=rows[0]["task"], n_steps=n_steps)
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
        z=[x["z"] for _, x in entries], h=[x["h"] for _, x in entries], d=[x["d"] for _, x in entries],
        ea=[x["ea"] for _, x in entries],
        L1=len(levels["pub_couple"]), L2=len(levels["pub_model"]), L3=len(levels["couple_task"]),
        k1=[lvl("pub_couple", x["publisher"], x["couple"], x["task"]) for _, x in entries],
        k2=[lvl("pub_model", x["publisher"], x["couple"], x["task"]) for _, x in entries],
        k3=[lvl("couple_task", x["publisher"], x["couple"], x["task"]) for _, x in entries],
        own1=[ci[c] + 1 for _, c in levels["pub_couple"]],
        **centring(levels),
        mu=[groups[g]["mu"] for g in names],
        sd=[groups[g]["sd"] for g in names],
        P=len(P), pg=[b + 1 for b, _ in P], pw=[w for _, w in P],
        r1=[[lvl("pub_couple", groups[names[b]]["publisher"], c, groups[names[b]]["task"]) for c in couples] for b, _ in P],
        r2=[[lvl("pub_model", groups[names[b]]["publisher"], c, groups[names[b]]["task"]) for c in couples] for b, _ in P],
        r3=[[lvl("couple_task", groups[names[b]]["publisher"], c, groups[names[b]]["task"]) for c in couples] for b, _ in P],
        has_v=[int(groups[names[b]]["task"] not in NO_TASK_EFFECT) for b, _ in P],
        ptype=[1 + next(i for i, (b2, _) in enumerate(P) if groups[names[b2]]["task"] == groups[names[b]]["task"])
               for b, _ in P],
        K=GH_NODES, ghx=list(xg * math.sqrt(2)), ghw=list(wg / math.sqrt(math.pi)))
    if not P:                                                       # Stan wants a P × C array even when P = 0
        data.update(r1=np.zeros((0, len(couples)), int), r2=np.zeros((0, len(couples)), int),
                    r3=np.zeros((0, len(couples)), int))
    return data, dict(names=names, couples=couples, ci=ci, levels=levels)


# ---------------------------------------------------------------- fit
STAN_DIR = os.path.join(os.path.dirname(HERE), ".stan")               # CmdStan, BridgeStan, venv (not in git)
INITS = os.path.join(STAN_DIR, "inits-{axis}.json")                  # last draw of each chain of the previous fit
# Compilation: stanc --O1 with STAN_NO_RANGE_CHECKS (lqm.stan is written so that --O1 keeps every vector in the fast
# struct-of-arrays form: −36 % per gradient; --O1 on a loop-by-element program can be 30× slower instead).
# Sampler per axis (validated in /work/.geom/JOURNAL.md): quality = nutpie (diagonal mass matrix adapted by Fisher
# divergence), which needs 4× fewer leapfrog steps here; cost = CmdStan NUTS started from the previous fit's last
# draws (nutpie cannot be given starting points, and random starts can leave a cost chain in a remote region).
SAMPLER = {"quality": dict(engine="nutpie", chains=4, warmup=1000, samples=20000, target_accept=0.85,
                           budget=600, extend=5000),
           "cost": dict(engine="cmdstan", chains=4, warmup=500, warmup_cold=1000, samples=4500, adapt_delta=0.9,
                        max_treedepth=10, budget=600, extend=1500)}
RESTART_RHAT = 1.05                  # above this, a chain is in another region: continuing it would not help


def cmdstan():
    import cmdstanpy
    path = os.environ.get("CMDSTAN") or next(
        (os.path.join(STAN_DIR, x) for x in sorted(os.listdir(STAN_DIR), reverse=True) if x.startswith("cmdstan-")), None) \
        if os.path.isdir(STAN_DIR) else None
    if path:
        cmdstanpy.set_cmdstan_path(path)
    return cmdstanpy


class Posterior:
    """Draws of every variable (chains merged, draws × shape), with the per-chain layout kept for diagnostics, and the
    sampler's adapted state of each chain (step size, inverse metric), from which the chains can be continued."""

    def __init__(self, arrays, stats, adapted=None):
        self.arrays = arrays                                         # name → array (chains, draws, *shape)
        self.stats = stats                                           # divergences, max_treedepth_hits, step sizes…
        self.adapted = adapted                                       # dict(step_size=[C], inv_metric=[C][dim]) or None

    def var(self, name):
        a = self.arrays[name]
        return a.reshape(a.shape[0] * a.shape[1], *a.shape[2:])

    def extend(self, more):
        """The same chains, continued by `more` (same number of chains, draws appended)."""
        import numpy as np
        n0, n1 = (next(iter(p.arrays.values())).shape[1] for p in (self, more))
        arrays = {v: np.concatenate([self.arrays[v], more.arrays[v]], axis=1) for v in self.arrays if v in more.arrays}
        stats = dict(self.stats)
        for k in ("divergences", "max_treedepth_hits"):
            stats[k] = None if self.stats.get(k) is None and more.stats.get(k) is None else \
                (self.stats.get(k) or 0) + (more.stats.get(k) or 0)
        stats["leapfrog_mean"] = round((self.stats["leapfrog_mean"] * n0 + more.stats["leapfrog_mean"] * n1) / (n0 + n1), 1)
        return Posterior(arrays, stats, more.adapted or self.adapted)


def _from_cmdstan(mcmc, max_depth=10):
    import numpy as np
    arrays = {}
    for name in mcmc.metadata.stan_vars:
        x = mcmc.stan_variable(name)                                 # (chains·draws, *shape), chain-major
        arrays[name] = x.reshape(mcmc.chains, -1, *x.shape[1:])
    sm = mcmc.method_variables()
    adapted = dict(step_size=[float(x) for x in mcmc.step_size], inv_metric=np.asarray(mcmc.inv_metric).tolist()) \
        if mcmc.inv_metric is not None else None
    return Posterior(arrays, dict(
        divergences=int(np.sum(sm["divergent__"])), max_treedepth_hits=int(np.sum(sm["treedepth__"] >= max_depth)),
        leapfrog_mean=round(float(np.mean(sm["n_leapfrog__"])), 1)), adapted)


def _from_nutpie(trace):
    import numpy as np
    post, ss = trace["posterior"], trace["sample_stats"]
    arrays = {v: np.asarray(post[v].values) for v in post.data_vars}
    adapted = dict(step_size=[float(x) for x in ss["step_size"].values[:, -1]],
                   inv_metric=np.asarray(ss["mass_matrix_inv"].values[:, -1]).tolist()) \
        if "mass_matrix_inv" in ss else None
    return Posterior(arrays, dict(divergences=int(ss["diverging"].values.sum()), max_treedepth_hits=None,
                                  leapfrog_mean=round(float(ss["n_steps"].values.mean()), 1)), adapted)


def _last_draws(post):
    """Last draw of each chain, parameters only: where each chain stands."""
    import numpy as np
    params = [v for v in post.arrays if v in _param_names()]
    chains = next(iter(post.arrays.values())).shape[0]
    out = [{v: np.asarray(post.arrays[v][c, -1]).tolist() for v in params} for c in range(chains)]
    for d in out:                                                    # θ must sum to zero to machine precision
        if "theta" in d:
            m = sum(d["theta"]) / len(d["theta"])
            d["theta"] = [t - m for t in d["theta"]]
    return out


def _save_inits(post, axis):
    """Last draw of each chain, for the next fit of this axis (a warm start: same model, slightly different data).
    Saved after every production fit, whatever the engine, so that a later fit can start CmdStan in the right region
    (random starts can leave a chain far away: seen on the cost axis, and on the quality axis of a held-out fold)."""
    import json
    json.dump(dict(inits=_last_draws(post)), open(INITS.format(axis=axis), "w"))


def _param_names():
    """Names declared in the parameters block of lqm.stan."""
    txt = open(STAN_FILE).read()
    block = txt[txt.index("\nparameters {"):txt.index("\ntransformed parameters {")]
    return {m.group(1) for m in re.finditer(r"\s(\w+);", block)}


def _inits(axis, chains):
    """Warm-start inits if the previous fit's parameters still fit the current data's dimensions, else None."""
    import json
    try:
        inits = json.load(open(INITS.format(axis=axis)))["inits"]
    except (OSError, ValueError, KeyError):
        return None
    if len(inits) < chains:
        return None
    for d in inits:                                                  # CSV draws are rounded (6 significant digits):
        if "theta" in d:                                             # re-centre θ, which must sum to zero exactly
            m = sum(d["theta"]) / len(d["theta"])
            d["theta"] = [t - m for t in d["theta"]]
    return inits[:chains]


def fit(groups, axis="quality", seed=7, settings=None, output_dir=None, save_inits=True, log=None):
    """Sample the posterior of one axis with its validated sampler (SAMPLER). Returns (Posterior, maps). The production
    fit keeps its last draws as the next warm start (save_inits); checks and experiments must not overwrite them.

    The run is checked against the validity criteria (CONVERGED) and, within the axis' time budget:
      * a chain left in a remote region (R̂ > RESTART_RHAT) restarts the axis on CmdStan from the previous fit's last
        draws (the only engine that takes starting points per chain);
      * otherwise too few effective draws continue the SAME chains (last state, adapted step size and metric, no new
        warm-up) by slices until the criteria hold or the budget is spent — draws are added, never thrown away."""
    import time
    say = log or (lambda *a: None)
    t0 = time.time()
    st = dict(SAMPLER[axis], **(settings or {}))
    data, maps = stan_data(groups, axis)
    post = _sample(data, axis, st, seed, output_dir)
    diag, _ = diagnostics(post)
    say(f"{axis}: {st['engine']} {time.time() - t0:.0f} s, R̂ {diag['rhat_max']}, ESS {diag['ess_bulk_min']}/"
        f"{diag['ess_tail_min']}, divergences {diag['divergences']}")
    if diag["rhat_max"] > RESTART_RHAT and st["engine"] == "nutpie":
        st = dict(SAMPLER["cost"], **{k: st[k] for k in ("chains",)}, engine="cmdstan")
        post = _sample(data, axis, st, seed + 1, output_dir, inits=_inits(axis, st["chains"]))
        diag, _ = diagnostics(post)
        say(f"{axis}: restarted on CmdStan {time.time() - t0:.0f} s, R̂ {diag['rhat_max']}, ESS {diag['ess_bulk_min']}/"
            f"{diag['ess_tail_min']}")
    per_draw = (time.time() - t0) / max(1, next(iter(post.arrays.values())).shape[1])    # seconds per draw per chain
    k = 0
    while not converged(diag) and diag["divergences"] == 0 and diag["rhat_max"] <= RESTART_RHAT \
            and post.adapted is not None:
        n = min(st["extend"], int((st["budget"] - (time.time() - t0)) / per_draw * 0.8))
        if n < st["extend"] // 4:
            break
        k += 1
        post = post.extend(_sample(data, axis, dict(st, engine="cmdstan"), seed + 10 + k, output_dir,
                                   inits=_last_draws(post), adapted=post.adapted, draws=n))
        diag, _ = diagnostics(post)
        say(f"{axis}: continued +{n} draws/chain {time.time() - t0:.0f} s, R̂ {diag['rhat_max']}, "
            f"ESS {diag['ess_bulk_min']}/{diag['ess_tail_min']}")
    post.stats.update(extensions=k, engine=st["engine"])
    if save_inits:
        _save_inits(post, axis)
    return post, maps


def _sample(data, axis, st, seed, output_dir=None, inits=None, adapted=None, draws=None):
    """One sampling run. adapted = the chains' step sizes and inverse metrics: continue them without warm-up."""
    import numpy as np
    if st["engine"] == "nutpie" and adapted is None:
        import nutpie
        os.environ.setdefault("BRIDGESTAN", os.path.join(STAN_DIR, "bridgestan-2.9.0"))
        cm = nutpie.compile_stan_model(filename=STAN_FILE, extra_stanc_args=["--O1"],
                                       extra_compile_args=["STAN_NO_RANGE_CHECKS=true"]).with_data(
            **{k: (np.asarray(v) if isinstance(v, list) else v) for k, v in data.items()})
        trace = nutpie.sample(cm, draws=draws or st["samples"], tune=st["warmup"], chains=st["chains"],
                              cores=min(st["chains"], os.cpu_count() or 1), seed=seed, progress_bar=False,
                              target_accept=st["target_accept"], store_mass_matrix=True)
        return _from_nutpie(trace)
    cs = cmdstan()
    model = cs.CmdStanModel(stan_file=STAN_FILE, stanc_options={"O1": True}, cpp_options={"STAN_NO_RANGE_CHECKS": True})
    common = dict(data=data, chains=st["chains"], parallel_chains=min(st["chains"], os.cpu_count() or 1), seed=seed,
                  max_treedepth=st.get("max_treedepth", 10), show_progress=False, output_dir=output_dir)
    if adapted is not None:                                          # continuation: no warm-up, adaptation frozen
        mcmc = model.sample(**common, inits=inits, iter_warmup=0, iter_sampling=draws, adapt_engaged=False,
                            step_size=adapted["step_size"],
                            inv_metric=[np.asarray(m) for m in adapted["inv_metric"]])
        return _from_cmdstan(mcmc, st.get("max_treedepth", 10))
    if inits is None and axis in ("cost", "quality"):
        inits = _inits(axis, st["chains"])
    if inits:                                                        # a stale warm start (the data's dimensions
        try:                                                         # changed) fails at once: test it on 1 iteration
            model.sample(data=data, chains=1, iter_warmup=1, iter_sampling=1, inits=inits[0], seed=seed,
                         show_progress=False)
        except (RuntimeError, ValueError):
            inits = None
    mcmc = model.sample(**common, inits=inits or None, iter_warmup=st["warmup"] if inits else st["warmup_cold"],
                        iter_sampling=draws or st["samples"], adapt_delta=st["adapt_delta"])
    return _from_cmdstan(mcmc, st.get("max_treedepth", 10))


# ---------------------------------------------------------------- reading the posterior
def quantile(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    f = int(k)
    return xs[f] if f + 1 >= len(xs) else xs[f] + (xs[f + 1] - xs[f]) * (k - f)


def _expit(x):
    import numpy as np
    out = np.empty_like(x)
    neg = x < 0
    e = np.exp(x[neg]); out[neg] = e / (1 + e)
    out[~neg] = 1 / (1 + np.exp(-x[~neg]))
    return out


def level_new(draws, data, rng, chunk=500):
    """What one NEW source would report for each couple, per posterior draw (draws × couples, log scale): fresh
    publisher × couple (sd τ_c), publisher × model (sd ψ) and, per task type of the panel, couple × task-type (sd ω)
    effects, read on the same panel as `level` (quality) or added to θ (cost). Computed here rather than in Stan, where
    it was the costliest generated quantity; checked against the former Stan version (same deterministic part to
    1e-15 for given deviates, same quantiles within Monte Carlo error)."""
    import numpy as np
    theta, tau = np.asarray(draws["theta"]), np.asarray(draws["tau"])
    psi, om = np.asarray(draws["psi"]), np.asarray(draws["omega"])
    D, C = theta.shape
    if data["cost"]:
        return (theta + rng.normal(size=(D, C)) * tau + rng.normal(size=(D, C)) * psi[:, None]
                + rng.normal(size=(D, C)) * om[:, None])
    pg = np.asarray(data["pg"], int) - 1
    pw = np.asarray(data["pw"], float)
    mu, sd = np.asarray(data["mu"])[pg], np.asarray(data["sd"])[pg]
    hv = np.asarray(data["has_v"], int).astype(bool)
    ptype = np.asarray(data["ptype"], int) - 1
    reps = np.unique(ptype)                                          # one fresh task-type effect per task type
    P = len(pw)
    out = np.empty((D, C))
    for d0 in range(0, D, chunk):
        sl = slice(d0, min(D, d0 + chunk))
        d = theta[sl].shape[0]
        zv = np.zeros((d, C, P))
        zv[:, :, reps] = rng.normal(size=(d, C, len(reps)))
        zu, zw = rng.normal(size=(d, C)), rng.normal(size=(d, C))
        vt = np.where(hv, zv * om[sl][:, None, None], 0.0)[:, :, ptype]            # (d, C, P)
        o, a = np.asarray(draws["o"])[sl][:, pg], np.asarray(draws["a"])[sl][:, pg]
        lat = (theta[sl] + zu * tau[sl] + zw * psi[sl][:, None])[:, :, None] + vt
        out[sl] = np.log(_expit(mu + sd * (o[:, None, :] + a[:, None, :] * lat)) @ pw / pw.sum())
    return out


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
        lq += np.clip(step, -1, 1)                                   # damped: a step never multiplies q by more than e
        if np.max(np.abs(step)) < 1e-10:
            break
    else:
        raise RuntimeError("quasi-variances did not converge")
    q = np.exp(lq)
    rel = np.abs(np.sqrt((q[I] + q[J]) / V) - 1)
    return q, float(rel.max()), float(np.median(rel))


def summarise(post, maps, groups, data, lo=0.16, hi=0.84, min_publishers=2, seed=0):
    """Per couple, on the log scale: centre = posterior median of `level`; half = quasi-standard error (the
    half-width of a 16–84 % interval that makes any two couples comparable); new_source = 16–84 % interval of what one
    new source would report for the couple (`level_new`); mcse = Monte Carlo error of the centre; published =
    measured by at least `min_publishers` publishers. Ratios to a reference couple are exp(centre − centre_ref), each
    couple keeping its own interval. Also returns the convergence diagnostics."""
    import numpy as np
    L = post.var("level")                                            # draws × couples
    q, qv_max, qv_med = quasi_variances(L, lo, hi)
    pubs = collections.defaultdict(set)
    for g in groups.values():
        for x in g["rows"]:
            pubs[x["couple"]].add(x["publisher"])
    Ln = level_new({k: post.var(k) for k in ("theta", "o", "a", "tau", "psi", "omega")}, data,
                   np.random.default_rng(seed))
    diag, mcse_level = diagnostics(post)
    out = {c: dict(centre=float(np.median(L[:, i])), half=float(math.sqrt(q[i])),
                   new_source=[float(np.quantile(Ln[:, i], lo)), float(np.quantile(Ln[:, i], hi))],
                   mcse=float(mcse_level[i]), publishers=len(pubs[c]), published=len(pubs[c]) >= min_publishers)
           for c, i in maps["ci"].items()}
    diag.update(qv_error_max=round(qv_max, 4), qv_error_median=round(qv_med, 4))
    return out, diag


def diagnostics(post):
    """Rank-normalised split R̂, bulk and tail ESS (Vehtari et al. 2021, as computed by ArviZ) over every scalar of
    every variable; Monte Carlo error of each `level`; sampler statistics."""
    import numpy as np, arviz as az
    worst, rh_max, eb_min, et_min = [], 1.0, float("inf"), float("inf")
    for name, a in post.arrays.items():
        if a.size == 0:
            continue
        x = a.reshape(a.shape[0], a.shape[1], -1)
        keep = [k for k in range(x.shape[2]) if np.ptp(x[:, :, k]) > 0]
        if not keep:
            continue
        dt = az.from_dict({"posterior": {"x": x[:, :, keep]}})
        rh = np.atleast_1d(az.rhat(dt)["x"].values); eb = np.atleast_1d(az.ess(dt, method="bulk")["x"].values)
        et = np.atleast_1d(az.ess(dt, method="tail")["x"].values)
        rh_max, eb_min, et_min = max(rh_max, float(rh.max())), min(eb_min, float(eb.min())), min(et_min, float(et.min()))
        worst += [(float(r), f"{name}[{keep[k] + 1}]") for k, r in enumerate(rh)]
        if name == "level":
            mcse_level = np.atleast_1d(az.mcse(dt, method="median")["x"].values)
            level = dict(rhat_max_level=round(float(rh.max()), 4), ess_bulk_min_level=int(eb.min()),
                         mcse_max_level=round(float(mcse_level.max()), 5))
    worst = [n for _, n in sorted(worst, reverse=True)[:5]]
    return dict(rhat_max=round(rh_max, 4), ess_bulk_min=int(eb_min), ess_tail_min=int(et_min), **level,
                worst_rhat=worst, draws=int(post.var("level").shape[0]), **post.stats), mcse_level


# Validity: R̂ ≤ 1.01 and bulk/tail ESS ≥ 400 on every parameter (Vehtari et al. 2021), no divergence. The stability of
# the displayed figures (Monte Carlo error of each value below half its last displayed digit) depends on the display
# precision and is checked by the build, value by value.
CONVERGED = dict(rhat=1.01, ess=400)


def converged(diag):
    return (diag["rhat_max"] <= CONVERGED["rhat"] and diag["ess_bulk_min"] >= CONVERGED["ess"]
            and diag["ess_tail_min"] >= CONVERGED["ess"] and diag["divergences"] == 0)


def predict(post, maps, groups, rows, thin=4, seed=0):
    """Posterior predictive of rows the fit did not see, in groups it did. Each row: dict(group, couple, publisher,
    task, h=1, d=reading precision on the group's scale). Returns per row (mean of the expected value f⁻¹ scale, list of predictive draws of f(y)) where known
    effects are used and unknown ones drawn from their distribution; the noise is Student-t_ν(σ_b·h)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    V = {k: post.var(k)[::thin] for k in ("theta", "o", "a", "sigma", "z1", "z2", "z3", "tau", "psi", "omega", "nu")}
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
        noise = np.sqrt((V["sigma"][:, b] * x.get("h", 1.0)) ** 2 + x.get("d", 0.0) ** 2) * rng.standard_t(V["nu"])
        out.append((G["mu"] + G["sd"] * m, G["mu"] + G["sd"] * (m + noise)))
    return out
