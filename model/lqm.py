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
  Makers (lqm_ext2.stan, the published model): the scales s_τ, ψ, ω per model maker around common ones, and a home
  effect per maker on the rows a maker published about its own models, excluded from every read-out. lqm_ext3.stan,
  the model fitted since 30 Oct 2026, is the same model written in other coordinates: each maker's block of effects
  of a family as a realised magnitude and a direction (its header has the change of variables).

Estimation: Hamiltonian Monte Carlo (NUTS) on lqm_ext3.stan — nutpie on both axes, its chains continued in the
sampling process until the criteria are met; CmdStan (CmdStanPy) continues chains from their last draws after a stop,
and restarts a chain left in a far region from a good chain's last draw (SAMPLER, FAR). The read-out `level` is
computed in Stan for every draw; `summarise` turns it into a centre and a per-couple interval (quasi-variances).
"""
import collections, csv, itertools, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "data"))
from catalog import COMPOSITES, FAMILY_OF, PUBLISHER_OF, UNIT_ALIASES
STAN_FILE = os.path.join(HERE, os.environ.get("LQM_MODEL", "lqm_ext3") + ".stan")   # the model fitted since 30 Oct
# 2026 (the maintainer's decision): lqm_ext2.stan, the published model since 21 Oct 2026 (lqm.stan plus per-maker
# scales and home effects), reparameterised — each maker's block of effects of one family sampled as its realised
# magnitude and direction instead of the maker's scale and standard-normal effects: the same model, the same data
# block, the same names read here. LQM_MODEL=lqm_ext2: that model in lqm_ext2's coordinates; lqm: the model until
# 21 Oct; lqm_ext: an experiment
EXT = os.path.basename(STAN_FILE) in ("lqm_ext.stan", "lqm_ext2.stan", "lqm_ext3.stan")
EXT_PRESENT = os.path.basename(STAN_FILE) in ("lqm_ext2.stan", "lqm_ext3.stan")   # makers without data are not levels
LINE = {}                                                       # model key -> the model it is a build / mode of
PROVIDERS = ("anthropic", "openai", "google", "xai", "deepseek", "qwen", "glm", "kimi")


def provider(model):
    """Who makes the model (the encompassing variant gives each maker its own effect scales)."""
    head = model.split("-")[0]
    if head in ("opus", "sonnet", "haiku", "fable"): return "anthropic"
    if head in ("gpt", "o1", "o3", "o4", "chatgpt"): return "openai"
    if head == "gemini": return "google"
    if head == "grok": return "xai"
    if head.startswith(("qwen", "qwq")): return "qwen"
    return head if head in PROVIDERS else "other"


def is_home(publisher, model, confound, harness):
    """A number the model's maker published and measured about its own model: Anthropic's outlets on Claude, a maker's
    own publications (publisher = the maker), figures 'as reported by' the vendor, and a maker's number copied into
    another publication (restated-from:<the maker>). A board the maker merely quotes (evaluated-by / restated-from a
    third party) is not home."""
    p = provider(model)
    t = (confound or "") + " " + (harness or "")
    org = {"anthropic": "Anthropic", "openai": "OpenAI", "google": "Google", "xai": "xAI", "deepseek": "DeepSeek",
           "qwen": "Alibaba", "glm": "Zhipu", "kimi": "Moonshot"}.get(p, "~")
    if f"restated-from:{org}" in t:
        return True
    if "evaluated-by:" in t or "restated-from:" in t:
        return False
    if publisher == MAKER_PUBLISHER.get(p):
        return True
    return p != "anthropic" and any(k in t for k in (f"vendor-reported:{org}", f"as reported by {org}", f"{org}-reported"))


MAKER_PUBLISHER = {"anthropic": "anthropic", "openai": "openai", "google": "google", "xai": "xai", "deepseek": "deepseek",
                   "qwen": "alibaba", "glm": "zhipu", "kimi": "moonshot"}

# ---------------------------------------------------------------- metric rules
LOG_METRICS = {"best-run-cash$", "xp-x1e5"}                        # positive, unbounded, ratio scale
UNIT_BOUNDED = {"F1", "accuracy", "success"}                        # proportions written on 0–1
HUNDRED_BOUNDED = {"weighted-rubric", "BLEU", "EDM-F1", "pass@1", "pass@3", "AA-idx", "LB-global-avg", "mAP50",
                   "RHAE", "score/579-pct"}                         # scores published on 0–100 without a '%'
LOWER_IS_BETTER = {"subjective-rank-of-4", "val_bpb(lower-better)", "MSE(lower-better)", "edit-distance(lower-better)"}
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
# The configurations the build writes (data/schema/vocab.json 'configuration'), each its own couple: the model puts no
# order between them (lqm_ext3.stan). 'nothink': thinking off; 'minimal': the lowest level of a model that has one below
# 'low'; 'think': the one 'on' position of an on/off model; 'solo': a model without an effort setting. Anything else
# ('between-tools', a mode of one model recorded but not fitted; an odd label) is not in the fit.
EFFORTS = {"nothink", "minimal", "low", "medium", "high", "xhigh", "max", "think", "solo"}
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
            home=int(is_home(PUBLISHER_OF.get(r["source"], r["source"]), r["model"], r["confound"], r["harness"])),
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
        if max(ys) - min(ys) <= 1e-12 * max(1.0, abs(mu)):             # a tie away from the bounds: equal couples
            mu, sd = ys[0], 1.0                                         # (the mean of equal floats can miss them by 1e-16)
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
    model_of = {c: LINE.get(c.split("@")[0], c.split("@")[0]) for c in couples}   # builds and modes share their model
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
    if EXT:                                                         # the encompassing variant: makers and home rows
        fi = {f: i + 1 for i, f in enumerate(PROVIDERS + ("other",))}
        if EXT_PRESENT:
            here = {provider(model_of[c]) for c in couples}
            fi = {f: i + 1 for i, f in enumerate(f for f in PROVIDERS + ("other",) if f in here)}
        data.update(F=len(fi), prov_c=[fi[provider(model_of[c])] for c in couples],
                    prov2=[fi[provider(m)] for _, m in levels["pub_model"]],
                    prov3=[fi[provider(model_of[c])] for c, _ in levels["couple_task"]],
                    home=[x.get("home", 0) for _, x in entries])
    if not P:                                                       # Stan wants a P × C array even when P = 0
        data.update(r1=np.zeros((0, len(couples)), int), r2=np.zeros((0, len(couples)), int),
                    r3=np.zeros((0, len(couples)), int))
    return data, dict(names=names, couples=couples, ci=ci, levels=levels)


# ---------------------------------------------------------------- fit
STAN_DIR = os.path.join(os.path.dirname(HERE), ".stan")               # CmdStan, BridgeStan, venv (not in git)
INITS = os.path.join(STAN_DIR, "inits-{axis}.json")                  # last draw of each chain of the previous fit
RUNS = os.path.join(STAN_DIR, "runs")                                # each axis' draws on disk (RunStore)
# Compilation: stanc --O1 with STAN_NO_RANGE_CHECKS (lqm.stan is written so that --O1 keeps every vector in the fast
# struct-of-arrays form: −36 % per gradient; --O1 on a loop-by-element program can be 30× slower instead).
# Sampler per axis (validated in /work/.geom/JOURNAL.md): nutpie (diagonal mass matrix adapted by Fisher divergence),
# which needs 4× fewer leapfrog steps on quality; on the cost axis of the global data (20 Oct 2026, .salvo14/nut) it
# took 537 leapfrog steps per draw against CmdStan's ~1,000 (at the depth cap on 99.97 % of draws), no divergence
# against 5, and drew twice the effective draws per second on the slowest parameter (user's go, 20 Oct). nutpie cannot
# be given starting points, and a random start can leave a chain in a far region (FAR, far_chains): that chain alone
# restarts, on CmdStan, from the last draw of a good chain with that chain's adapted step size and metric. The chains
# are looked at for one in a far region at every check, whatever R̂ (maintainer's rule, 30 Oct 2026): every
# FAR["every"] iterations (warm-up and draws counted together), at the end of warm-up, and at every slice — not only at
# the planned draws when R̂ was high, as on 30 Oct 12:19–12:28 (cost, seed 13), when chain 5 sat at −4,600 against
# +1,800–2,000 from warm-up iteration ~150 on and would have run an hour before the check at 1,800 draws.
# Unconverged without a far chain (slow mixing included), and too few effective draws: the same chains continue by
# slices of `extend` draws, up to `extend_max` draws per chain beyond the planned ones — on nutpie within the sampling
# process (the chains run on, checked at every slice and stopped at the first that meets the criteria: no second
# warm-up, user's request of 21 Oct 2026), on CmdStan from the last state with the adapted step size and metric. Until
# 30 Oct 2026 an R̂ above 1.05 threw every draw away and sampled the axis again on CmdStan from the previous fit's last
# draws — in practice a cold start once the data's dimensions had changed: on 29–30 Oct the cost axis (R̂ 1.081 at
# 1,800 draws, its six chains in one region, one maker scale psi_f[qwen] mixing slowly between two modes) ended at
# R̂ 1.19, ESS 22, 41 divergences after the restart (maintainer's rule, 30 Oct 2026: no cold or random restart, no good
# draw thrown away). Counted in draws, not seconds: a check reads only the draws (or warm-up iterations) up to it, so a
# slow or loaded machine does not change the fit. Quality draws 4 × 3,000 at least: the effective draws per draw ranged
# from 1 % to 15 % across the fits of 30 Sep – 8 Oct (s_τ's posterior tail, which the data shortens: .salvo14/s21/ess),
# so 3,000 meet the criteria on most data and 12,000 — the 48,000 draws drawn by every fit before 8 Oct — on the worst.
# Warm-up 500 (maintainer, 30 Oct 2026; 600 from 29 Oct, 1,000 before): in the two nutpie stores with warm-up
# statistics (cost, 29 Oct seed 12 and 30 Oct seed 13) the good chains' step size settles at 0.013–0.016 by iteration
# 50 and their trajectories at 1,023 leapfrog steps (depth 10) from iteration 50 on; the metric's quality shows only in
# the draws' effective sample size per draw.
SAMPLER = {"quality": dict(engine="nutpie", chains=6, warmup=500, samples=1800, target_accept=0.9, extend=900,
                           extend_max=16200),
           "cost": dict(engine="nutpie", chains=6, warmup=500, samples=1800, target_accept=0.9, extend=900,
                        extend_max=16200)}
# The two axes run one after the other: on this shared 8-core machine the quality axis took 1,241 s beside the cost
# axis and 344 s alone (8 Oct 2026) — the chains of both compete for the same cores, so running them together saves
# no time and adds their memory.
PARALLEL_AXES = False
DIVERGENT_SHARE = 0.0003              # continuing an unconverged run is allowed up to this share of divergent draws
# A chain in a far region (maintainer's rule, 30 Oct 2026): its median log-density over its last `draws` draws (in
# warm-up: its last `warmup` iterations) lies below the median of the other chains' medians by more than max(`lp`,
# `spread` × their spread), the spread being 1.4826 × the median absolute deviation of the other chains' medians
# (robust: a second far chain among them does not widen it). Within one region a draw's log-density varies by about
# √(d/2) (d unconstrained dimensions: ≈ 55 on the cost axis' 6,128, ≈ 74 on quality's 10,842) and the chains' medians
# by far less; 300 is 4–5 of these deviations, beyond what the region's draws reach. The spread term widens the bar when
# the other chains themselves disagree (modes of different density, visited in turn). Seen: far chains 1,400 to 64,500
# below the others (cost 29 Oct seed 11: −2,900 against +2,050; seed 12: −27,300 and +450 against +1,880; quality 29–30
# Oct: −69,700 against −5,100; cost 30 Oct seed 13, warm-up: −4,600 against +1,800–2,000); the six cost chains of 29–30
# Oct, slow but in one region: medians 1,892–1,916 (the fit's report, .stan/fit-report.log; data/tests/sampler_tests.py
# checks these cases). Checked every `every` iterations from the start of warm-up (30 Oct 2026): in the warm-up of
# 30 Oct the criterion on the last 100 iterations flags chain 5 alone from iteration 67 on (29 Oct seed 12: its chains
# 4 and 5 from 80 on), and good chains too before (the first iterations' transient): the first check, at 250 (the maintainer, 30 Oct: every
# 250 iterations, two checks within the warm-up of 500), is past it.
# Within warm-up nothing clean can be done before the adaptation ends: nutpie runs the chains in one process and can
# neither stop one chain nor start one from a given point with a given step size and metric (init_mean is one point
# for every chain, jittered), and CmdStan's warm-up re-estimates the metric by its own windows (over the 100 remaining
# iterations, from one chain's 75 draws in 6,128 dimensions) — while stopping nutpie then would cut the good chains'
# adaptation too. A chain far at a warm-up check is reported; it is restarted at the end of warm-up (the first draw,
# every chain's adaptation final) if it is still far there.
# A verdict reads at least `least` draws (or warm-up iterations) of every chain, each chain's own (30 Oct 2026): fewer,
# no verdict. A single draw's log-density varies by about √(d/2) (≈ 55 on the cost axis) and the chains' single draws
# by more: in the fit of 30 Oct 14:57 the five good chains' first draws after warm-up spread over 1,714–2,069, and the
# check made right after the far chain's restart, on that one draw per chain, flagged the good chain at 1,714 (2,051
# the others' median, 337 below it > 300), which stopped the run at one draw (.stan/runs/cost-8c4130a43f050029). A
# restarted chain is a part of its own (RunStore.add): its draws, from the restart on, are all its own, as long as the
# others' after the drop, so every check after a restart reads only draws drawn since it by the restarted chain. Its
# log-density is CmdStan's lp__, the good chains' nutpie's logp: on one scale (both up to the same constant, with the
# Jacobian): the restarted chain's first draw, at its source chain's last point, has lp__ 2068.8422 and nutpie's
# logp there 2068.84218755.
FAR = dict(draws=200, warmup=100, every=250, lp=300, spread=5, least=100)


def cmdstan():
    import cmdstanpy
    path = os.environ.get("CMDSTAN") or next(
        (os.path.join(STAN_DIR, x) for x in sorted(os.listdir(STAN_DIR), reverse=True) if x.startswith("cmdstan-")), None) \
        if os.path.isdir(STAN_DIR) else None
    if path:
        cmdstanpy.set_cmdstan_path(path)
    return cmdstanpy


class Posterior:
    """Draws of every variable, in parts of equal length — one per batch of chains, each laid out (draws, chains,
    *shape) — with the sampler's statistics and each chain's adapted state (step size, inverse metric), from which the
    chains can be continued. A production fit reads its parts from disk (memory-mapped, RunStore): reading the draws
    costs the memory of the block being read, not of the whole run."""

    def __init__(self, parts, stats, adapted=None):
        self.parts = parts                                           # name → [array (draws, chains, *shape)]
        self.stats = stats                                           # divergences, max_treedepth_hits, leapfrog_mean…
        self.adapted = adapted                                       # dict(step_size=[C], inv_metric=[C][dim]) or None

    @property
    def names(self):
        return list(self.parts)

    def shape(self, name):
        """(chains, draws, *shape) of a variable."""
        p = self.parts[name]
        return (sum(x.shape[1] for x in p), p[0].shape[0], *p[0].shape[2:])

    def chains(self, name):
        """A variable's draws laid out (chains, draws, *shape): a copy, for the small variables."""
        import numpy as np
        return np.concatenate([np.swapaxes(x, 0, 1) for x in self.parts[name]], axis=0)

    def var(self, name):
        """A variable's draws, chains merged one after the other (chains · draws, *shape): a copy, for the small ones."""
        a = self.chains(name)
        return a.reshape(a.shape[0] * a.shape[1], *a.shape[2:])

    def blocks(self, name, size=256):
        """A variable's scalars `size` at a time: (index of the first, array (chains, draws, k))."""
        import numpy as np
        flat = [x.reshape(x.shape[0], x.shape[1], -1) for x in self.parts[name]]
        for s0 in range(0, flat[0].shape[2], size):
            yield s0, np.concatenate([np.swapaxes(f[:, :, s0:s0 + size], 0, 1) for f in flat], axis=0)

    def last(self, name):
        """Each chain's last draw of a variable: (chains, *shape)."""
        import numpy as np
        return np.concatenate([np.asarray(x[-1]) for x in self.parts[name]], axis=0)

    def lp(self):
        """Each chain's log-density per draw (chains, draws), or None when the draws do not carry it."""
        return self.chains("lp__") if "lp__" in self.parts else None

    def in_memory(self):
        import numpy as np
        return Posterior({v: [np.array(x) for x in p] for v, p in self.parts.items()}, dict(self.stats), self.adapted)


def _f64(path, shape):
    """A float64 file of the given shape, memory-mapped read-only (an empty array in memory: mmap needs a byte)."""
    import numpy as np
    shape = tuple(int(x) for x in shape)
    return np.zeros(shape) if math.prod(shape) == 0 else np.memmap(path, dtype=np.float64, mode="r", shape=shape)


class RunStore:
    """One axis' draws on disk, from the first draw until the axis is next fitted (RUNS/<axis>-<key>): a run stopped
    at any point — out of memory, container restarted — resumes from what is written, and an axis whose sampling
    inputs are unchanged (sampling_key) is summarised again without sampling.

      manifest.json   the key; the variables' shapes; the parts — per part its engine, chains, planned and kept draws
                      per chain, sampler statistics (in total and per chain), each chain's adapted state, the seeds of
                      its segments, its directory; a part planned from given starting points (`start`) has no draw yet;
      p<k>/<var>.f64  part k's draws of the variable, float64 laid out (draws, chains, *shape): continuing the chains
                      appends to the end of the file; the log-density is the variable lp__;
      seg/            the sampling run in progress (nutpie's store or CmdStan's CSV files) and seg.json, what it is.
    The manifest is written last, atomically. A file longer than the manifest says is cut back before it is written
    to, so committing a segment again after a stop changes nothing."""

    def __init__(self, path, key=None):
        import json, shutil
        self.path = path
        self.manifest = dict(key=key, shapes={}, parts=[])
        try:
            m = json.load(open(os.path.join(path, "manifest.json")))
            if m.get("key") == key:
                self.manifest = m
            else:
                shutil.rmtree(path)
        except (OSError, ValueError):
            pass
        os.makedirs(path, exist_ok=True)
        self.seg = os.path.join(path, "seg")

    @property
    def parts(self):
        return self.manifest["parts"]

    def _save(self):
        import json
        tmp = os.path.join(self.path, "manifest.json.tmp")
        with open(tmp, "w") as f:
            json.dump(self.manifest, f)
        os.replace(tmp, os.path.join(self.path, "manifest.json"))

    def dir(self, k):
        """Part k's directory."""
        return os.path.join(self.path, self.parts[k].get("dir", f"p{k}"))

    def reset(self):
        import shutil
        for k in range(len(self.parts)):
            shutil.rmtree(self.dir(k), ignore_errors=True)
        self.manifest.update(shapes={}, parts=[])
        self._save()

    def plan(self, k, draws):
        """Part k is to reach `draws` per chain (more draws for the same chains)."""
        self.parts[k]["planned"] = draws
        self._save()

    def add(self, engine, chains, planned, adapted, start, **record):
        """A new part with no draw yet: `chains` chains to be sampled from the starting points `start` with the adapted
        state `adapted`, without warm-up, up to `planned` draws (the far chains' restart, _run)."""
        self.parts.append(dict(engine=engine, chains=chains, planned=planned, draws=0, seeds=[], adapted=adapted,
                               start=start, stats=dict(divergences=0, max_treedepth_hits=None if engine == "nutpie" else 0,
                                                       leapfrog_sum=0.0, chain=_no_chain_stats(engine, chains)),
                               dir=f"p{len(self.parts)}", **record))
        self._save()

    def drop(self, k, chains):
        """Part k without the given chains (indices within the part), their draws discarded: the kept chains' draws are
        copied into a new directory, the manifest switched to it at once, then the old directory removed — a stop at
        any point leaves either the part as it was or the part without the chains."""
        import numpy as np, shutil
        p = self.parts[k]
        keep = [c for c in range(p["chains"]) if c not in set(chains)]
        if not keep or len(keep) == p["chains"]:
            raise ValueError(f"part {k}: dropping {chains} of {p['chains']} chains")
        old, new = self.dir(k), os.path.join(self.path, f"p{k}-{len(p.get('dropped', [])) + 1}")
        shutil.rmtree(new, ignore_errors=True)
        os.makedirs(new)
        for v, shape in self.manifest["shapes"].items():
            src = _f64(os.path.join(old, v + ".f64"), (p["draws"], p["chains"], *shape))
            with open(os.path.join(new, v + ".f64"), "wb") as f:
                step = max(1, int(5e7 // max(1, p["chains"] * math.prod(shape) * 8)))     # ≈ 50 MB at a time
                for d0 in range(0, p["draws"], step):
                    f.write(np.ascontiguousarray(np.asarray(src[d0:d0 + step])[:, keep]).tobytes())
        s = p["stats"]
        ch = {key: None if x is None else [x[c] for c in keep] for key, x in s["chain"].items()}
        p["stats"] = dict(divergences=sum(ch["divergences"]), leapfrog_sum=sum(ch["leapfrog_sum"]),
                          max_treedepth_hits=None if ch["max_treedepth_hits"] is None else sum(ch["max_treedepth_hits"]),
                          chain=ch)
        if p["adapted"] is not None:
            p["adapted"] = {key: [x[c] for c in keep] for key, x in p["adapted"].items()}
        p.setdefault("dropped", []).append(dict(chains=sorted(set(chains)), draws=p["draws"]))
        p.update(chains=len(keep), dir=os.path.basename(new))
        self._save()
        shutil.rmtree(old, ignore_errors=True)

    def posterior(self, only=None):
        """The kept draws, memory-mapped; `only` = the index of one part."""
        ks = range(len(self.parts)) if only is None else [only]
        P = [self.parts[k] for k in ks]
        parts = {v: [_f64(os.path.join(self.dir(k), v + ".f64"), (self.parts[k]["draws"], self.parts[k]["chains"],
                                                                *shape)) for k in ks]
                 for v, shape in self.manifest["shapes"].items()}
        add = lambda key: None if all(p["stats"].get(key) is None for p in P) else sum(p["stats"].get(key) or 0 for p in P)
        stats = dict(divergences=add("divergences"), max_treedepth_hits=add("max_treedepth_hits"),
                     leapfrog_mean=round(sum(p["stats"]["leapfrog_sum"] for p in P)
                                         / max(1, sum(p["draws"] * p["chains"] for p in P)), 1))
        adapted = None if any(p["adapted"] is None for p in P) else dict(
            step_size=[s for p in P for s in p["adapted"]["step_size"]],
            inv_metric=[m for p in P for m in p["adapted"]["inv_metric"]])
        return Posterior(parts, stats, adapted)

    def begin(self, **info):
        """Opens a segment: info = engine, seed, chains, draws (planned), part (None: a new part), adapted."""
        import json, shutil
        shutil.rmtree(self.seg, ignore_errors=True)
        os.makedirs(self.seg)
        with open(os.path.join(self.seg, "seg.json"), "w") as f:
            json.dump(info, f)
        return self.seg

    def pending(self):
        return os.path.exists(os.path.join(self.seg, "seg.json"))

    def commit(self):
        """Moves the segment in progress, finished or stopped part-way, into its part. Returns the draws per chain it
        added (0 when nothing usable was written: stopped during warm-up)."""
        import json, shutil
        info = json.load(open(os.path.join(self.seg, "seg.json")))
        read = (_read_nutpie if info["engine"] == "nutpie" else _read_cmdstan)(self.seg, info)
        n = 0
        if read is not None:
            shapes, write = read
            k = info.get("part")
            new = k is None
            part = dict(engine=info["engine"], chains=info["chains"], planned=info["draws"], draws=0, seeds=[],
                        stats=dict(divergences=0, max_treedepth_hits=None if info["engine"] == "nutpie" else 0,
                                   leapfrog_sum=0.0, chain=_no_chain_stats(info["engine"], info["chains"])),
                        adapted=None, dir=f"p{len(self.parts)}") if new else self.parts[k]
            k = len(self.parts) if new else k
            d0 = part["draws"]
            where = os.path.join(self.path, part["dir"]) if new else self.dir(k)
            os.makedirs(where, exist_ok=True)
            files = {}
            try:
                for v, shape in shapes.items():
                    path = os.path.join(where, v + ".f64")
                    f = open(path, "r+b" if os.path.exists(path) else "w+b")
                    f.truncate(d0 * part["chains"] * math.prod(shape) * 8)
                    f.seek(0, 2)
                    files[v] = f
                n, stats, adapted = write(files)
                missing = [v for v, s in self.manifest["shapes"].items() if v not in shapes and math.prod(s)]
                if n and missing:
                    raise RuntimeError(f"segment without the variables {missing}")
            finally:
                for f in files.values():
                    f.close()
            if n:
                self.manifest["shapes"].update({v: list(s) for v, s in shapes.items()})
                part["draws"] = d0 + n
                part["planned"] = max(part["planned"], part["draws"])   # a run that continued itself, then stopped
                for key in ("divergences", "max_treedepth_hits"):
                    part["stats"][key] = None if stats.get(key) is None else (part["stats"].get(key) or 0) + stats[key]
                part["stats"]["leapfrog_sum"] += stats["leapfrog_sum"]
                ch = part["stats"]["chain"]                          # per chain: a far chain's draws can be dropped
                for key, x in stats["chain"].items():
                    ch[key] = None if x is None else [a + b for a, b in zip(ch[key] or [0] * len(x), x)]
                part["adapted"] = part["adapted"] or adapted
                part["seeds"].append(info["seed"])
                if info.get("far"):                                  # the far chains that stopped the run (_grow):
                    part["far_seen"] = info["far"]                   # _run restarts them
                    part["far_seen_at"] = info.get("far_at")
                if new:
                    self.parts.append(part)
                self._save()
        shutil.rmtree(self.seg, ignore_errors=True)
        return n


def _no_chain_stats(engine, chains):
    """A part's sampler statistics per chain before its first draw."""
    return dict(divergences=[0] * chains, max_treedepth_hits=None if engine == "nutpie" else [0] * chains,
                leapfrog_sum=[0.0] * chains)


def _nutpie_written(g, root, done=False):
    """Draws per chain that every chain of nutpie's store has written for good: all of a finished run; of a run in
    progress or stopped, the chunks written but the last (which a stop may have cut)."""
    post, ss = g["posterior"], g["sample_stats"]
    arrays = [post[v] for v in post.array_keys()] + [ss["n_steps"], ss["step_size"], ss["logp"]]   # always
    # written: zarr skips a chunk equal to the fill value (`diverging` all False), which then reads as that value
    return min(a.shape[1] if done else _chunks_kept(root, a) for a in arrays if a.size)


def _chunks_kept(root, a):
    """Iterations per chain of a (chains, iterations, …) array of nutpie's store written for good in every chain: the
    chunks written but the last (which a stop may have cut)."""
    d = os.path.join(root, a.path, "c")
    out = []
    for c in range(a.shape[0]):
        have = set(os.listdir(os.path.join(d, str(c)))) if os.path.isdir(os.path.join(d, str(c))) else set()
        j = 0
        while str(j) in have:
            j += 1
        out.append(max(0, j - 1) * a.chunks[1])
    return min(out)


def _nutpie_warmup_written(g, root, done=False):
    """Warm-up iterations per chain of nutpie's store written for good: all of them once the run is finished or has
    written draws (nutpie writes the last, partial chunk of warm-up when the draws begin: the archived store of 29 Oct
    seed 12), else the chunks written but the last."""
    a = g["warmup_sample_stats"]["logp"]
    if done or _nutpie_written(g, root) > 0:
        return a.shape[1]
    return _chunks_kept(root, a)


class _NutpieDraws(Posterior):
    """The first n draws of every chain of nutpie's store, read block by block from disk while the run goes on: what
    diagnostics() needs to check a run that continues itself."""

    def __init__(self, g, n):
        import numpy as np
        self.g, self.n, post = g, n, g["posterior"]
        self.parts = {v: None for v in post.array_keys()}
        ss = g["sample_stats"]
        self.stats = dict(divergences=int(np.asarray(ss["diverging"][:, :n]).sum()), max_treedepth_hits=None,
                          leapfrog_mean=round(float(np.asarray(ss["n_steps"][:, :n], dtype=np.float64).mean()), 1))
        self.adapted = None

    def shape(self, name):
        a = self.g["posterior"][name]
        return (a.shape[0], self.n, *a.shape[2:])

    def lp(self):
        import numpy as np
        return np.asarray(self.g["sample_stats"]["logp"][:, :self.n], dtype=np.float64)

    def blocks(self, name, size=256):
        import numpy as np
        a = self.g["posterior"][name]
        rest = math.prod(a.shape[3:]) if a.ndim > 3 else 1
        if a.ndim == 2:
            yield 0, np.asarray(a[:, :self.n], dtype=np.float64)[:, :, None]
            return
        rows = max(1, size // rest)
        for i0 in range(0, a.shape[2], rows):
            x = np.asarray(a[:, :self.n, i0:i0 + rows], dtype=np.float64)
            yield i0 * rest, x.reshape(x.shape[0], x.shape[1], -1)


def _read_nutpie(seg, info):
    """nutpie's store in seg/store, finished or stopped: (shapes, write) or None. write(files) appends the kept draws
    of every variable and returns (draws per chain, statistics, adapted state). A stopped run keeps, for every chain,
    the draws of the chunks written before the stop but the last (which the stop may have cut), and the shortest
    chain sets the length of all: a chain's state at any draw is a valid point to continue it from."""
    import numpy as np, zarr
    root = os.path.join(seg, "store")
    try:
        g = zarr.open_group(root, mode="r")
        post, ss = g["posterior"], g["sample_stats"]
    except Exception:
        return None
    n = _nutpie_written(g, root, info.get("done"))
    n = min(n, info.get("stop", n))                                  # a run that continued itself: up to its last check
    if n == 0:
        return None
    C = ss["diverging"].shape[0]
    adapted = None
    try:                                                             # nutpie records the mass matrix while it adapts
        w = g["warmup_sample_stats"]["mass_matrix_inv"]              # (NaN once frozen): the last finite one is final
        inv = []
        for c in range(C):
            m = np.asarray(w[c])                                     # (rows never written read as fill values)
            f = (np.isfinite(m) & (m > 0)).all(axis=1).nonzero()[0]
            inv.append(m[f[-1]].tolist())
        adapted = dict(step_size=[float(x) for x in np.asarray(ss["step_size"][:, n - 1])], inv_metric=inv)
    except (KeyError, IndexError):
        pass
    shapes = {v: tuple(post[v].shape[2:]) for v in post.array_keys()}
    shapes["lp__"] = ()                                              # the log-density, as CmdStan's lp__ (FAR)

    def write(files):
        for v, shape in shapes.items():
            a, size = ss["logp"] if v == "lp__" else post[v], max(1, C * math.prod(shape) * 8)
            step = max(1, int(5e7 // size))                          # ≈ 50 MB at a time
            for d0 in range(0, n, step):
                x = np.asarray(a[:, d0:min(n, d0 + step)], dtype=np.float64)
                files[v].write(np.ascontiguousarray(np.swapaxes(x, 0, 1)).tobytes())
        div = np.asarray(ss["diverging"][:, :n]).sum(axis=1)
        leap = np.asarray(ss["n_steps"][:, :n], dtype=np.float64).sum(axis=1)
        stats = dict(divergences=int(div.sum()), max_treedepth_hits=None, leapfrog_sum=float(leap.sum()),
                     chain=dict(divergences=[int(x) for x in div], max_treedepth_hits=None,
                                leapfrog_sum=[float(x) for x in leap]))
        return n, stats, adapted
    return shapes, write


def _read_cmdstan(seg, info, block=200):
    """CmdStan's CSV files in seg, finished or stopped: (shapes, write) or None. The chains' files are read side by
    side, one draw of each at a time, up to the last draw complete in every file; the adapted step size and inverse
    metric come from the files' comments (or from seg.json for a continuation, which adapts nothing)."""
    import glob, numpy as np
    chain = lambda p: int(re.search(r"_(\d+)\.csv$", p).group(1)) if re.search(r"_(\d+)\.csv$", p) else 1
    csvs = sorted(glob.glob(os.path.join(seg, "*.csv")), key=chain)   # one chain: no _<n> (a far chain's restart)
    if len(csvs) != info["chains"]:
        return None
    handles = [open(p) for p in csvs]
    header, notes = None, [[] for _ in csvs]
    for i, h in enumerate(handles):
        for line in h:
            if not line.startswith("#"):
                if not line.endswith("\n"):
                    return None
                header = header or line.strip().split(",")
                break
        else:
            return None
    col = {c: i for i, c in enumerate(header)}
    idx = collections.defaultdict(list)
    for i, c in enumerate(header):
        if not c.endswith("__") or c == "lp__":                     # the parameters, and the log-density (FAR)
            name, *ix = c.split(".")
            idx[name].append((tuple(int(x) - 1 for x in ix), i))
    shapes, order = {}, {}
    for name, ix in idx.items():
        shape = tuple(max(t[d] for t, _ in ix) + 1 for d in range(len(ix[0][0])))
        pos = np.empty(math.prod(shape), int)
        for t, i in ix:
            pos[np.ravel_multi_index(t, shape) if shape else 0] = i
        shapes[name], order[name] = shape, pos
    max_depth = info.get("max_treedepth", 10)

    def rows(h, notes_c):
        for line in h:
            if line.startswith("#"):
                notes_c.append(line)
                continue
            if not line.endswith("\n"):
                return
            x = np.array(line.split(","), dtype=np.float64)
            if x.size != len(header):
                return
            yield x

    def write(files):
        n, C = 0, len(csvs)
        div, hits, leap = np.zeros(C, int), np.zeros(C, int), np.zeros(C)
        its = [rows(h, notes[c]) for c, h in enumerate(handles)]
        while True:
            buf = []
            for _ in range(block):
                try:
                    buf.append([next(it) for it in its])
                except StopIteration:
                    break
            if not buf:
                break
            X = np.asarray(buf)                                      # (k, chains, columns)
            for v, pos in order.items():
                files[v].write(np.ascontiguousarray(X[:, :, pos]).reshape(X.shape[0], X.shape[1], *shapes[v]).tobytes())
            div += X[:, :, col["divergent__"]].sum(axis=0).astype(int)
            hits += (X[:, :, col["treedepth__"]] >= max_depth).sum(axis=0)
            leap += X[:, :, col["n_leapfrog__"]].sum(axis=0)
            n += X.shape[0]
            if len(buf) < block:
                break
        for h in handles:
            h.close()
        adapted = info.get("adapted")
        if adapted is None:
            try:
                step, inv = [], []
                for c in range(len(csvs)):
                    t = "".join(notes[c])
                    step.append(float(re.search(r"# Step size = ([^\n]+)", t).group(1)))
                    m = re.search(r"# Diagonal elements of inverse mass matrix:\n# ([^\n]+)", t)
                    inv.append([float(x) for x in m.group(1).split(",")])
                adapted = dict(step_size=step, inv_metric=inv)
            except AttributeError:
                adapted = None
        return n, dict(divergences=int(div.sum()), max_treedepth_hits=int(hits.sum()), leapfrog_sum=float(leap.sum()),
                       chain=dict(divergences=[int(x) for x in div], max_treedepth_hits=[int(x) for x in hits],
                                  leapfrog_sum=[float(x) for x in leap])), adapted
    return shapes, write


def _last_draws(post):
    """Last draw of each chain, parameters only: where each chain stands."""
    import numpy as np
    params = [v for v in post.names if v in _param_names()]
    last = {v: post.last(v) for v in params}
    chains = post.shape(params[0])[0]
    out = [{v: np.asarray(last[v][c]).tolist() for v in params} for c in range(chains)]
    for d in out:                                                    # θ and the makers' sum-to-zero vectors must sum
        _centre(d)                                                   # to zero within 1e-8 (CSV draws: 6 digits)
    return out


def _centre(d):
    """The sum-to-zero vectors of a starting point re-centred (Stan refuses one whose sum exceeds 1e-8 in size)."""
    for v in _sum_to_zero_names():
        if v in d and d[v]:
            m = sum(d[v]) / len(d[v])
            d[v] = [t - m for t in d[v]]
    return d


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


def _sum_to_zero_names():
    """The parameters declared sum_to_zero_vector (θ and the makers' zd; in lqm_ext2.stan also zf_tau, zf_psi,
    zf_omega, which lqm_ext3.stan recovers as transformed parameters)."""
    txt = open(STAN_FILE).read()
    block = txt[txt.index("\nparameters {"):txt.index("\ntransformed parameters {")]
    return {m.group(1) for m in re.finditer(r"sum_to_zero_vector\[\w+\]\s+(\w+);", block)}


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
        _centre(d)                                                   # re-centre the sum-to-zero vectors
    return inits[:chains]


def far_chains(lp):
    """The chains left in a far region (FAR), from their log-densities lp (chains, draws or warm-up iterations): each
    chain's median over its last FAR["draws"] (the caller passes the last FAR["warmup"] warm-up iterations) against the median and spread of the other chains' medians. The chain of highest median is
    never far, so at least one chain is good."""
    import numpy as np
    if lp is None or len(lp) < 2:
        return []
    m = np.nanmedian(np.asarray(lp, dtype=np.float64)[:, -FAR["draws"]:], axis=1)
    out = []
    for c in range(len(m)):
        o = np.delete(m, c)
        ref = np.median(o)
        if ref - m[c] > max(FAR["lp"], FAR["spread"] * 1.4826 * np.median(np.abs(o - ref))):
            out.append(c)
    return out


def _far(lp):
    """far_chains once every chain has FAR["least"] draws (or warm-up iterations) of its own in lp; before, no verdict
    ([])."""
    if lp is None or len(lp) < 2 or lp.shape[1] < FAR["least"]:
        return []
    return far_chains(lp)


def _is_mark(warmup, n):
    """Whether n draws per chain end a far check (FAR["every"] iterations, warm-up and draws counted together)."""
    return n > 0 and (warmup + n) % FAR["every"] == 0


def _checks(warmup, planned, top, extend):
    """The checks of a nutpie run that continues itself, in order, as (draws per chain, kind); draws ≤ 0 stand for
    warm-up iteration warmup + draws:
      'warm-up'         every FAR["every"] iterations within warm-up: a far chain is reported (FAR: no clean restart
                        before the adaptation ends);
      'end of warm-up'  at the first draw, on the last FAR["warmup"] warm-up iterations: a far chain stops the run;
      'far'             every FAR["every"] iterations after warm-up, on the last FAR["draws"] draws: likewise;
      'slice'           at planned, planned + extend, …, top: a far chain, the criteria met or too many divergent draws
                        stop the run."""
    e = FAR["every"]
    out = {i - warmup: "warm-up" for i in range(e, warmup, e)}
    out.update({d: "far" for d in range(e - warmup % e, top, e)})
    out[1] = "end of warm-up"
    k = planned
    while True:
        out[k] = "slice"
        if k >= top:
            break
        k = min(top, k + extend)
    return sorted(out.items())


def _new_seed():
    """A fresh seed for a fit (maintainer, 30 Oct 2026: each fit draws its own, printed and recorded in its run's
    manifest and in fit-cache.json, from which the fit can be drawn again): below 2³¹, so that the seeds derived for
    CmdStan's segments (seed + 10⁶ + …) stay below its limit of 2³² − 1."""
    import secrets
    return secrets.randbelow(2 ** 31)


def sampling_key(data, axis, st):
    """What one axis' draws depend on, the seed apart: the Stan program, the axis' data, the sampler's settings and the
    code that samples (the functions below, the pinned environment). An axis whose key is unchanged is summarised again
    from its stored draws instead of being sampled again, and a run stopped part-way resumes from them. The seed is
    drawn by the run that opens the store and kept in its manifest (fit): a stored run, stopped or finished, goes on
    with its own seed, and a new launch with a new seed neither makes it stale nor changes the seed it resumes with."""
    import hashlib, inspect, json
    h = hashlib.sha256()
    h.update(open(STAN_FILE, "rb").read())
    h.update(json.dumps(dict(axis=axis, data=data, st=st, converged=CONVERGED, far=FAR, divergent=DIVERGENT_SHARE),
                        sort_keys=True, default=lambda a: a.tolist()).encode())
    for f in (Posterior, _f64, RunStore, _chunks_kept, _nutpie_written, _nutpie_warmup_written, _read_nutpie,
              _read_cmdstan, _last_draws, _centre, _inits, fit, _run, _sample, _grow, _checks, _is_mark, far_chains,
              _far, diagnostics, converged):
        h.update(inspect.getsource(f).encode())
    req = os.path.join(HERE, "requirements-fit.txt")
    if os.path.exists(req):
        h.update(open(req, "rb").read())
    return h.hexdigest()


def fit(groups, axis="quality", seed=None, settings=None, keep=False, save_inits=True, log=None):
    """Sample the posterior of one axis with its validated sampler (SAMPLER). Returns (Posterior, maps); the seed used
    is in post.stats["seed"]. The production fit keeps its draws on disk (keep: RUNS/<axis>-<sampling key>) and its
    last draws as the next warm start (save_inits); checks and experiments sample into a temporary store and get their
    draws in memory. seed: None draws a fresh one (_new_seed); a stored run of the same key keeps the seed it was
    started with, whatever is given.

    The run is checked against the validity criteria (CONVERGED); no good draw is ever thrown away (rule of 30 Oct
    2026):
      * a chain left in a far region (far_chains, looked at every FAR["every"] iterations, at the end of warm-up and at
        every slice, whatever R̂) loses its draws and restarts on CmdStan (the only engine that takes starting points per
        chain), without warm-up, from the last draw of a good chain with that chain's adapted step size and metric, up
        to the length of the others; the good chains are kept. Once per run: a chain far again stops the run,
        unconverged. A chain far during warm-up is restarted at the end of warm-up (FAR);
      * otherwise too few effective draws add draws: the SAME chains continue (no new warm-up) by slices of `extend`
        draws, up to `extend_max` per chain beyond the planned ones — on nutpie in the sampling process itself, on
        CmdStan from the last state with the adapted step size and metric — while at most DIVERGENT_SHARE of the draws
        diverged.
    A run stopped part-way (memory, restart) resumes from its stored draws: each chain continues on CmdStan from its
    last stored draw, with its adapted step size and metric, up to the draws planned."""
    import shutil, tempfile
    st = dict(SAMPLER[axis], **(settings or {}))
    data, maps = stan_data(groups, axis)
    say = log or (lambda *a: None)
    if keep:
        key = sampling_key(data, axis, st)
        path = os.path.join(RUNS, f"{axis}-{key[:16]}")
        for old in (os.listdir(RUNS) if os.path.isdir(RUNS) else []):            # an older key's draws are stale
            if old.startswith(axis + "-") and os.path.join(RUNS, old) != path:
                shutil.rmtree(os.path.join(RUNS, old), ignore_errors=True)
        store = RunStore(path, key)
    else:
        store = RunStore(tempfile.mkdtemp(prefix="lqm-run-"))
    if store.manifest.get("seed") is None:
        store.manifest["seed"] = _new_seed() if seed is None else int(seed)
        store._save()
        say(f"{axis}: seed {store.manifest['seed']} (new run)")
    else:
        say(f"{axis}: seed {store.manifest['seed']} (the stored run's)")
    seed = store.manifest["seed"]
    try:
        post = _run(store, data, axis, st, seed, say)
        if not keep:
            post = post.in_memory()
    finally:
        if not keep:
            shutil.rmtree(store.path, ignore_errors=True)
    if save_inits:
        _save_inits(post, axis)
    return post, maps


def _run(store, data, axis, st, seed, say):
    import time
    t0 = time.time()
    resumed = 0

    def segment(engine, s, draws, part=None, inits=None, adapted=None, grow=False, chains=None):
        chains = chains or st["chains"]
        seg = store.begin(engine=engine, seed=s, chains=chains, draws=draws, part=part, adapted=adapted,
                          max_treedepth=st.get("max_treedepth", 10))
        _sample(data, axis, dict(st, engine=engine, chains=chains), s, seg, inits=inits, adapted=adapted, draws=draws,
                grow=grow, say=lambda m: say(f"{axis}: {m}"))
        return store.commit()

    def complete():
        """Every part short of its planned draws continues its chains on CmdStan, without warm-up: from their last
        draws, or from the part's starting points when it has none yet (a far chain's restart). A part behind the
        others first catches up with them; parts of one length go from one far check (_is_mark) to the next and stop
        at the first that finds a chain in a far region, which _run's loop then restarts."""
        while True:
            P = store.parts
            todo = [k for k, p in enumerate(P) if p["draws"] < p["planned"]]
            if not todo:
                return
            d = min(P[k]["draws"] for k in todo)
            ahead = [p["draws"] for p in P if p["draws"] > d]
            e = FAR["every"]
            for k in [k for k in todo if P[k]["draws"] == d]:
                p = store.parts[k]
                to = min(min(ahead), p["planned"]) if ahead else min(d + e - (st["warmup"] + d) % e, p["planned"])
                if p["adapted"] is None:
                    raise RuntimeError(f"part {k} cannot be continued: no adapted state")
                inits = _last_draws(store.posterior(only=k)) if p["draws"] else p["start"]
                if not segment("cmdstan", seed + 1_000_000 + 1000 * k + len(p["seeds"]), to - p["draws"], part=k,
                               inits=inits, adapted=p["adapted"], chains=p["chains"]):
                    raise RuntimeError(f"part {k}: its continuation wrote no draw")
            n = {p["draws"] for p in store.parts}
            if (len(n) == 1 and _is_mark(st["warmup"], min(n))
                    and any(p["draws"] < p["planned"] for p in store.parts)
                    and _far(store.posterior().lp())):
                return

    def restart(post, far):
        """The far chains' draws dropped; each far chain restarts on CmdStan from the last draw of a good chain (the
        good chains in turn) with that chain's adapted step size and metric: a new part, sampled up to the length of
        the others (rule of 30 Oct 2026: no cold or random start, the good chains' draws kept)."""
        good = [c for c in range(post.shape("lp__")[0]) if c not in far]
        src = [good[j % len(good)] for j in range(len(far))]
        last = _last_draws(post)
        p0 = store.parts[0]
        n, at = p0["draws"], p0.pop("far_seen_at", None) or f"draw {p0['draws']}"
        p0.pop("far_seen", None)
        store.drop(0, far)
        store.plan(0, n)
        store.add("cmdstan", len(far), n, dict(step_size=[post.adapted["step_size"][g] for g in src],
                                               inv_metric=[post.adapted["inv_metric"][g] for g in src]),
                  [last[g] for g in src], far=far, source=src, at=at)
        complete()

    if store.pending():                                              # a run stopped part-way: keep what it wrote
        resumed = store.commit()
        say(f"{axis}: resumed a stopped run, {resumed} draws per chain recovered")
    if any(p["adapted"] is None and p["draws"] < p["planned"] for p in store.parts):
        store.reset()                                                # stopped too early to be continued
    complete()
    if not store.parts:
        segment(st["engine"], seed, st["samples"], grow=st["engine"] == "nutpie")
        complete()
    # A far chain is looked at first, whatever R̂ (30 Oct 2026): its divergent draws go with it. A few divergent draws
    # (≤ 0.03 % (user, 20 Oct): 5 of 18,000 on the cost axis of 20 Oct 2026) do not forbid continuing the chains, nor
    # does a high R̂ without a far chain (slow mixing). A run stopped early by a far chain draws its planned draws first.
    # Right after a restart the chains have one draw each (a far chain found at the end of warm-up): no verdict on it
    # (_far: FAR["least"]); the parts go on together on CmdStan, from one far check to the next, to the planned draws.
    stopped = None                                                   # why the sampling ended
    while True:
        post = store.posterior()
        p = store.parts[0]
        far = p.get("far_seen") if len(store.parts) == 1 and p.get("far_seen") else _far(post.lp())
        if far:
            if len(store.parts) > 1 or post.adapted is None:         # once per run, and only from an adapted state
                stopped = (f"chain(s) {far} in a far region at draw {p['draws']}, not restarted "
                           + ("(a far chain was restarted already)" if len(store.parts) > 1 else "(no adapted state)"))
                say(f"{axis}: {stopped}: the run stops, unconverged")
                for k in range(len(store.parts)):
                    store.plan(k, store.parts[k]["draws"])
                break
            restart(post, far)
            say(f"{axis}: chain(s) {far} in a far region ({store.parts[1]['at']}) restarted from good chains' last "
                f"draws, {time.time() - t0:.0f} s")
            continue
        extra = p["draws"] - st["samples"]                           # draws beyond the planned ones
        if extra >= 0 and extra % st["extend"] == 0 or extra >= st["extend_max"]:     # a slice: the criteria
            diag, _ = diagnostics(post)
            say(f"{axis}: {p['draws']} draws/chain {time.time() - t0:.0f} s, R̂ {diag['rhat_max']}, ESS "
                f"{diag['ess_bulk_min']}/{diag['ess_tail_min']}, divergences {diag['divergences']}")
            if converged(diag) or diag["divergences"] > DIVERGENT_SHARE * diag["draws"]:
                stopped = "criteria met" if converged(diag) else "too many divergent draws to continue"
                break
        if post.adapted is None or extra >= st["extend_max"]:
            stopped = "no adapted state to continue from" if post.adapted is None else \
                f"{st['extend_max']} draws per chain beyond the planned ones, unconverged"
            break
        # the same chains, continued (a nutpie run continued itself: here only after a stop) to the next slice — a run
        # stopped by a far chain between slices (or before the planned draws) goes on to the slice it stopped short of
        to = st["samples"] + min(st["extend_max"], (extra // st["extend"] + 1) * st["extend"] if extra >= 0 else 0)
        for k in range(len(store.parts)):                            # every part to the same length
            store.plan(k, to)
        complete()
    p = store.parts[0]
    ext = -(-(p["draws"] - st["samples"]) // st["extend"]) if p["draws"] > st["samples"] else 0
    post.stats.update(extensions=ext, engine=st["engine"], resumed=resumed, seed=seed, stopped=stopped,
                      far_restarted=len(store.parts[1]["far"]) if len(store.parts) > 1 else 0,
                      far_at=store.parts[1].get("at") if len(store.parts) > 1 else None)
    return post


def _sample(data, axis, st, seed, seg, inits=None, adapted=None, draws=None, grow=False, say=None):
    """One sampling run, written into the segment directory seg (nutpie's store, or CmdStan's CSV files). adapted =
    the chains' step sizes and inverse metrics: continue them without warm-up. grow (nutpie): the chains run on past
    the planned draws, by slices of `extend` up to `extend_max` more, checked as _grow says on the draws up to each
    check, and stop at the first check that ends the run; seg.json records the draws kept (`stop`) and the far chains
    that stopped it (`far`, `far_at`)."""
    import json, numpy as np
    if st["engine"] == "nutpie" and adapted is None:
        import nutpie
        from nutpie import zarr_store
        os.environ.setdefault("BRIDGESTAN", os.path.join(STAN_DIR, "bridgestan-2.9.0"))
        cm = nutpie.compile_stan_model(filename=STAN_FILE, extra_stanc_args=["--O1"],
                                       extra_compile_args=["STAN_NO_RANGE_CHECKS=true"]).with_data(
            **{k: (np.asarray(v) if isinstance(v, list) else v) for k, v in data.items()})
        os.makedirs(os.path.join(seg, "store"), exist_ok=True)
        planned = draws or st["samples"]
        top = planned + st["extend_max"] if grow else planned
        run = nutpie.sample(cm, draws=top, tune=st["warmup"], chains=st["chains"],     # draws go to disk as they come
                            cores=min(st["chains"], os.cpu_count() or 1), seed=seed, progress_bar=False,
                            target_accept=st["target_accept"], store_mass_matrix=True, blocking=not grow,
                            zarr_store=zarr_store.LocalStore(os.path.join(seg, "store")))
        stop, far, at = top, [], None
        if grow:
            try:
                stop, far, at = _grow(run, os.path.join(seg, "store"), st["warmup"], planned, top, st["extend"], say)
            except BaseException:
                run.cancel()                                         # no sampler left running behind the error
                raise
        info = json.load(open(os.path.join(seg, "seg.json")))
        with open(os.path.join(seg, "seg.json"), "w") as f:         # finished: every chunk is whole (or kept to stop)
            json.dump(dict(info, done=stop == top, stop=stop, draws=stop, far=far, far_at=at), f)
        return
    cs = cmdstan()
    model = cs.CmdStanModel(stan_file=STAN_FILE, stanc_options={"O1": True}, cpp_options={"STAN_NO_RANGE_CHECKS": True})
    common = dict(data=data, chains=st["chains"], parallel_chains=min(st["chains"], os.cpu_count() or 1), seed=seed,
                  max_treedepth=st.get("max_treedepth", 10), show_progress=False, output_dir=seg)
    if adapted is not None:                                          # continuation: no warm-up, adaptation frozen
        model.sample(**common, inits=inits, iter_warmup=0, iter_sampling=draws, adapt_engaged=False,
                     step_size=adapted["step_size"], inv_metric=[np.asarray(m) for m in adapted["inv_metric"]])
        return
    if inits is None and axis in ("cost", "quality"):
        inits = _inits(axis, st["chains"])
    if inits:                                                        # a stale warm start (the data's dimensions
        try:                                                         # changed) fails at once: test it on 1 iteration
            model.sample(data=data, chains=1, iter_warmup=1, iter_sampling=1, inits=inits[0], seed=seed,
                         show_progress=False)
        except (RuntimeError, ValueError):
            inits = None
    model.sample(**common, inits=inits or None, iter_warmup=st["warmup"] if inits else st["warmup_cold"],
                 iter_sampling=draws or st["samples"], adapt_delta=st["adapt_delta"])


def _grow(run, root, warmup, planned, top, extend, say=None):
    """A nutpie run in progress (non-blocking) checked at the points of _checks — every FAR["every"] iterations,
    warm-up included, at the end of warm-up and at planned, planned + extend, …, top draws per chain — each once every
    chain has written up to it, on what was written up to it. A chain in a far region (far_chains, whatever R̂: rule of
    30 Oct 2026) stops the run, for _run to restart it — from the end of warm-up on; within warm-up it is reported (no
    clean restart before the adaptation ends: FAR). At a slice the run also stops when the criteria are met or too many
    draws diverged; an R̂ above the criteria alone runs on. Returns (draws per chain kept, the far chains that stopped
    the run, where they were found)."""
    import time, numpy as np, zarr
    say = say or (lambda *a: None)

    def finished():
        try:
            return run.is_finished
        except TimeoutError:                                         # nutpie 0.16: "not finished" raises
            return False

    def warm_lp(g, i):                                               # the last FAR["warmup"] warm-up iterations up to i
        return np.asarray(g["warmup_sample_stats"]["logp"][:, max(0, i - FAR["warmup"]):i], dtype=np.float64)
    for d, kind in _checks(warmup, planned, top, extend):
        while True:                                                  # wait until every chain has written up to d
            fin = finished()
            try:
                g = zarr.open_group(root, mode="r")
                n = _nutpie_written(g, root, fin)
                warm = "warmup_sample_stats" in g
                w = _nutpie_warmup_written(g, root, fin) if warm and d <= 0 else 0
            except Exception:
                n, w, warm = 0, 0, True
            there = (not warm or w >= warmup + d) if d <= 0 else n >= d
            if there or fin:
                break
            time.sleep(15)
        if not there:                                                # the run ended short (an error): wait() raises it
            run.wait()
            return n, [], None
        if kind in ("warm-up", "end of warm-up") and not warm:       # a store without its warm-up
            continue
        if kind == "warm-up":
            far = _far(warm_lp(g, warmup + d))
            if far:
                say(f"chain(s) {far} in a far region at warm-up iteration {warmup + d}: restarted at the end of warm-up "
                    "if still far there")
            continue
        if kind == "end of warm-up":
            far, at = _far(warm_lp(g, warmup)), f"end of warm-up (its last {FAR['warmup']} iterations)"
        else:
            draws = _NutpieDraws(g, d)
            far, at = _far(draws.lp()), f"draw {d} (iteration {warmup + d})"
            if not far and kind == "slice":
                if d >= top:
                    run.wait()
                    return top, [], None
                diag, _ = diagnostics(draws)
                if converged(diag) or diag["divergences"] > DIVERGENT_SHARE * diag["draws"]:
                    if not finished():
                        run.abort()
                    return d, [], None
        if far:
            if not finished():
                run.abort()
            return d, far, at
    run.wait()
    return top, [], None


def sample_once(data, axis, st, seed):
    """One sampling run in a temporary store, its draws in memory (the pre-fit smoke test)."""
    import shutil, tempfile
    store = RunStore(tempfile.mkdtemp(prefix="lqm-run-"))
    try:
        seg = store.begin(engine=st["engine"], seed=seed, chains=st["chains"], draws=st["samples"], part=None,
                          adapted=None, max_treedepth=st.get("max_treedepth", 10))
        _sample(data, axis, st, seed, seg)
        store.commit()
        return store.posterior().in_memory()
    finally:
        shutil.rmtree(store.path, ignore_errors=True)


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


def level_new(draws, data, rng, chunk=None):
    """What one NEW source would report for each couple, per posterior draw (draws × couples, log scale): fresh
    publisher × couple (sd τ_c), publisher × model (sd ψ) and, per task type of the panel, couple × task-type (sd ω)
    effects, read on the same panel as `level` (quality) or added to θ (cost). Computed here rather than in Stan, where
    it was the costliest generated quantity; checked against the former Stan version (same deterministic part to
    1e-15 for given deviates, same quantiles within Monte Carlo error)."""
    import numpy as np
    theta, tau = np.asarray(draws["theta"]), np.asarray(draws["tau"])
    D, C = theta.shape
    psi = np.asarray(draws["psiC"]) if "psiC" in draws else np.asarray(draws["psi"])[:, None] * np.ones((1, C))
    om = np.asarray(draws["omegaC"]) if "omegaC" in draws else np.asarray(draws["omega"])[:, None] * np.ones((1, C))
    if data["cost"]:
        return (theta + rng.normal(size=(D, C)) * tau + rng.normal(size=(D, C)) * psi
                + rng.normal(size=(D, C)) * om)
    pg = np.asarray(data["pg"], int) - 1
    pw = np.asarray(data["pw"], float)
    mu, sd = np.asarray(data["mu"])[pg], np.asarray(data["sd"])[pg]
    hv = np.asarray(data["has_v"], int).astype(bool)
    ptype = np.asarray(data["ptype"], int) - 1
    reps = np.unique(ptype)                                          # one fresh task-type effect per task type
    P = len(pw)
    chunk = chunk or max(1, min(500, int(2.5e7 // (C * P))))     # draws per block: a few (draws, C, P) arrays of
    out = np.empty((D, C))                                           # 200 MB each (500 on the published data)
    for d0 in range(0, D, chunk):
        sl = slice(d0, min(D, d0 + chunk))
        d = theta[sl].shape[0]
        zv = np.zeros((d, C, P))
        zv[:, :, reps] = rng.normal(size=(d, C, len(reps)))
        zu, zw = rng.normal(size=(d, C)), rng.normal(size=(d, C))
        vt = np.where(hv, zv * om[sl][:, :, None], 0.0)[:, :, ptype]               # (d, C, P)
        o, a = np.asarray(draws["o"])[sl][:, pg], np.asarray(draws["a"])[sl][:, pg]
        lat = (theta[sl] + zu * tau[sl] + zw * psi[sl])[:, :, None] + vt
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
    V = np.empty(len(I))
    for b in range(0, len(I), 256):                                  # by blocks of pairs: draws × pairs is large
        D = L[:, I[b:b + 256]] - L[:, J[b:b + 256]]
        V[b:b + 256] = ((np.quantile(D, hi, axis=0) - np.quantile(D, lo, axis=0)) / 2) ** 2
    V = np.maximum(V, 1e-12)
    lq = np.log(np.maximum(np.array([np.median(V[(I == c) | (J == c)]) / 2 for c in range(C)]), 1e-12))
    for _ in range(500):                                             # Gauss–Newton on log q
        q = np.exp(lq)
        s = q[I] + q[J]
        res = np.log(s) - np.log(V)
        wI, wJ = q[I] / s, q[J] / s                                  # the Jacobian has two entries per pair: its
        A = np.diag(np.bincount(I, wI * wI, C) + np.bincount(J, wJ * wJ, C))      # normal equations are built
        np.add.at(A, (I, J), wI * wJ); np.add.at(A, (J, I), wI * wJ)              # without it (pairs × couples
        g = -(np.bincount(I, wI * res, C) + np.bincount(J, wJ * res, C))         # is 430 MB at 476 couples)
        step = np.linalg.lstsq(A, g, rcond=None)[0]
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
    Ln = level_new({k: post.var(k) for k in ("theta", "o", "a", "tau", "psi", "omega", "psiC", "omegaC") if k in post.names}, data,
                   np.random.default_rng(seed))
    diag, mcse_level = diagnostics(post)
    out = {c: dict(centre=float(np.median(L[:, i])), half=float(math.sqrt(q[i])),
                   new_source=[float(np.quantile(Ln[:, i], lo)), float(np.quantile(Ln[:, i], hi))],
                   mcse=float(mcse_level[i]), publishers=len(pubs[c]), published=len(pubs[c]) >= min_publishers)
           for c, i in maps["ci"].items()}
    diag.update(qv_error_max=round(qv_max, 4), qv_error_median=round(qv_med, 4))
    if not data["cost"]:                                             # quality: the latent scale θ itself, on which the
        import arviz as az                                           # page decides, and its reading as a panel score
        T = post.var("theta")
        qt, _, _ = quasi_variances(T, lo, hi)
        x = post.chains("theta")
        mt = np.atleast_1d(az.mcse(az.from_dict({"posterior": {"x": x.reshape(x.shape[0], x.shape[1], -1)}}),
                                   method="median")["x"].values)
        for c, i in maps["ci"].items():
            out[c]["theta"] = [float(np.median(T[:, i])), float(math.sqrt(qt[i])), float(mt[i])]
        diag["panel_curve"] = panel_curve(post, data, float(T.min()), float(T.max()))
    return out, diag


def panel_curve(post, data, lo, hi, n=41):
    """Expected panel score (share of each benchmark's bound, panel-weighted) of a couple of latent quality θ, with no
    couple-specific effect: [[θ, score], …] over [lo, hi], posterior median at each θ. The page labels its θ axis
    with it; decisions stay on θ."""
    import numpy as np
    pg = np.asarray(data["pg"], int) - 1
    pw = np.asarray(data["pw"], float)
    mu, sd = np.asarray(data["mu"])[pg], np.asarray(data["sd"])[pg]
    o, a = post.var("o")[:, pg], post.var("a")[:, pg]
    return [[round(float(t), 4), round(float(np.median(_expit(mu + sd * (o + a * t)) @ pw / pw.sum())), 5)]
            for t in np.linspace(lo, hi, n)]


def _num(x, digits):
    """x rounded, or None when it is not finite (R̂ of a run stopped after a few draws): JSON has no NaN or infinity."""
    return round(x, digits) if math.isfinite(x) else None


def diagnostics(post):
    """Rank-normalised split R̂, bulk and tail ESS (Vehtari et al. 2021, as computed by ArviZ) over every scalar of
    every variable; Monte Carlo error of each `level`; sampler statistics."""
    import numpy as np, arviz as az
    worst, rh_max, eb_min, et_min = [], 1.0, float("inf"), float("inf")
    for name in post.names:                                          # a block of scalars at a time: bounded memory
        if name.endswith("__") or math.prod(post.shape(name)) == 0:  # lp__: read by far_chains, not a criterion
            continue
        lv = []
        for s0, x in post.blocks(name):
            keep = [k for k in range(x.shape[2]) if np.ptp(x[:, :, k]) > 0]
            if not keep:
                continue
            dt = az.from_dict({"posterior": {"x": x[:, :, keep]}})
            rh = np.atleast_1d(az.rhat(dt)["x"].values); eb = np.atleast_1d(az.ess(dt, method="bulk")["x"].values)
            et = np.atleast_1d(az.ess(dt, method="tail")["x"].values)
            rh = np.where(np.isfinite(rh), rh, np.inf)               # too few draws (a run stopped early): R̂ and ESS
            eb, et = (np.where(np.isfinite(z), z, 0.0) for z in (eb, et))   # undefined, read as unconverged
            rh_max, eb_min = max(rh_max, float(rh.max())), min(eb_min, float(eb.min()))
            et_min = min(et_min, float(et.min()))
            worst = sorted(worst + [(float(r), f"{name}[{s0 + keep[k] + 1}]") for k, r in enumerate(rh)], reverse=True)[:5]
            if name == "level":
                lv.append((rh, eb, np.atleast_1d(az.mcse(dt, method="median")["x"].values)))
        if name == "level" and not lv:                               # every draw alike (a single draw)
            mcse_level = np.full(math.prod(post.shape(name)[2:]), np.nan)
            level = dict(rhat_max_level=None, ess_bulk_min_level=0, mcse_max_level=None)
        elif name == "level":
            rh, eb, mcse_level = (np.concatenate(z) for z in zip(*lv))
            level = dict(rhat_max_level=_num(float(rh.max()), 4), ess_bulk_min_level=int(eb.min()),
                         mcse_max_level=_num(float(np.max(mcse_level, initial=-np.inf)), 5))
    worst = [n for _, n in worst]
    C, n = post.shape("level")[:2]
    eb_min, et_min = (0 if not math.isfinite(x) else x for x in (eb_min, et_min))   # no scalar read at all
    return dict(rhat_max=_num(rh_max, 4), ess_bulk_min=int(eb_min), ess_tail_min=int(et_min), **level,
                worst_rhat=worst, draws=int(C * n), **post.stats), mcse_level


# Validity: R̂ ≤ 1.01 and bulk/tail ESS ≥ 400 on every parameter (Vehtari et al. 2021), no divergence. The stability of
# the displayed figures (Monte Carlo error of each value below half its last displayed digit) depends on the display
# precision and is checked by the build, value by value.
CONVERGED = dict(rhat=1.01, ess=400)


def converged(diag):
    return (diag["rhat_max"] is not None and diag["rhat_max"] <= CONVERGED["rhat"]    # None: too few draws to tell
            and diag["ess_bulk_min"] >= CONVERGED["ess"] and diag["ess_tail_min"] >= CONVERGED["ess"]
            and diag["divergences"] == 0)


def predict(post, maps, groups, rows, thin=4, seed=0):
    """Posterior predictive of rows the fit did not see, in groups it did. Each row: dict(group, couple, publisher,
    task, h=1, d=reading precision on the group's scale). Returns per row (mean of the expected value f⁻¹ scale, list of predictive draws of f(y)) where known
    effects are used and unknown ones drawn from their distribution; the noise is Student-t_ν(σ_b·h)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    V = {k: post.var(k)[::thin] for k in ("theta", "o", "a", "sigma", "z1", "z2", "z3", "tau", "psi", "omega", "nu",
                                           "psi2", "omega3", "psiC", "omegaC", "deltaC") if k in post.names}
    if "psi2" in V:                                                  # the encompassing variant: scales per maker
        V["psi"], V["omega"] = V["psiC"], V["omegaC"]
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
    W = centred(V["z2"] * (V["psi2"] if "psi2" in V else V["psi"][:, None]), cs["set2"])
    Vt = centred(V["z3"] * (V["omega3"] if "omega3" in V else V["omega"][:, None]), cs["set3"])
    sc = lambda v, c: V[v][:, c] if V[v].ndim == 2 else V[v]        # a scale per couple (variant) or one for all
    out = []
    for x in rows:
        b, c = bi[x["group"]], ci[x["couple"]]
        G = groups[x["group"]]
        lat = V["theta"][:, c].copy()
        k = li["pub_couple"].get((x["publisher"], x["couple"]))
        lat += U[:, k] if k is not None else rng.normal(0, 1, D) * V["tau"][:, c]
        k = li["pub_model"].get((x["publisher"], x["couple"].split("@")[0]))
        lat += W[:, k] if k is not None else rng.normal(0, 1, D) * sc("psi", c)
        if x["task"] not in NO_TASK_EFFECT:
            k = li["couple_task"].get((x["couple"], x["task"]))
            lat += Vt[:, k] if k is not None else rng.normal(0, 1, D) * sc("omega", c)
        if "deltaC" in V and x.get("home"):
            lat += V["deltaC"][:, c]
        m = V["o"][:, b] + V["a"][:, b] * lat
        noise = np.sqrt((V["sigma"][:, b] * x.get("h", 1.0)) ** 2 + x.get("d", 0.0) ** 2) * rng.standard_t(V["nu"])
        out.append((G["mu"] + G["sd"] * m, G["mu"] + G["sd"] * (m + noise)))
    return out
