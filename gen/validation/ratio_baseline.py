"""Baseline for the validation scripts: the score-ratio consolidation (per-benchmark ratio to a reference couple,
weighted median across benchmarks, √n per publisher, ×0.5 for bridged benchmarks, 0.5→1 by effort-ladder coverage,
×1/3 for early-access runs, Huber band). Kept only to compare the fusion model against."""
import csv, math


def eff(e):
    return e


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def ratio_grid(field, path, models, anchor):
    """Couple-atomic ROBUST grid for a measured field (cost_usd or score). Each (model,effort) node gets a value
    RELATIVE to GRID_ANCHOR (opus-5@high)=1.0, built ONLY from within-benchmark ratios (never a cross-benchmark value
    comparison). Central value AND uncertainty band come from the SAME per-benchmark estimates:

      1. Per benchmark, take log(value) of every current (model,effort) couple — explicit efforts + haiku@solo
         (haiku has no effort dial); nothink/priceblend/default excluded. Benchmarks with <2 couples are dropped
         (a lone couple is circular — it can only echo the anchor).
      2. Normalise each benchmark to the anchor via a per-benchmark offset:
           - anchor present  → offset = log(anchor)               (divide by the anchor directly)
           - anchor absent   → BRIDGE offset = MEAN residual (log value − global g) over its shared couples;
                               such bridged benchmarks are down-weighted ×0.5 (indirect anchoring).
         The offset is a nuisance alignment term → MEAN (non-degenerate), not median.
      3. Each benchmark then yields one normalised estimate per couple = exp(log value − offset), with
         weight = (0.5 if bridged) × ladder coverage × (1/3 if the run is early access), where ladder coverage runs
         linearly from 0.5 (the benchmark measures one rung of that model) to 1.0 (it sweeps the model's full ladder).
         DIMINISHING RETURNS PER SOURCE: a source (= publisher) with n measurements of a couple weighs √n in total,
         shared among them, so a lab publishing 16 benchmarks with one harness counts 4, not 16. Every measurement
         keeps its own vote. The global g[couple] is the weighted MEDIAN of those estimates (robust to
         task-complexity outliers); the anchor is pinned to 0 each pass. Iterate.
      4. central = exp(g[couple]) = weighted median; band = **per-side Huber spread**, centred on the median:
         deviations (log estimate − log median) are clipped to ±1.5·MAD, then the lower/upper band = median·exp(∓RMS
         of the clipped negative/positive deviations). This is robust (a wild outlier is capped at 1.5·MAD) yet
         still COUNTS outliers (they widen their side up to the cap — unlike IQR which discards them), and it is
         ASYMMETRIC (captures skew). Centred on the median → the plotted dot is always inside the band. A
         single-benchmark node gets a degenerate [c,c,c] box. Haiku 4.5 → one 'solo' node (no effort ladder)."""
    import math, collections
    CUR = set(models)                                            # 9 current models
    EFFOK = {"low","medium","high","xhigh","max","solo"}     # 'solo' = haiku 4.5 (no discrete effort)
    ANCHOR = anchor
    rows = [r for r in csv.DictReader(open(path))
            if r["group"] and not r["group"].startswith("#")]
    bench = collections.defaultdict(dict)                    # benchmark → couple → log(value)
    srcs  = collections.defaultdict(lambda: collections.defaultdict(set))
    eap   = collections.defaultdict(lambda: collections.defaultdict(set))   # sources whose run was early access
    PUBLISHER = {"anthropic-chart": "anthropic-syscard", "anthropic-docs": "anthropic-syscard",   # one publisher = one source
                 "anthropic-cookbook": "anthropic-syscard", "claude-dev-blog": "anthropic-syscard"}  # (Anthropic's own evals)
    for r in rows:
        if r["model"] not in CUR: continue
        r["source"] = PUBLISHER.get(r["source"], r["source"])
        e, c = eff(r["effort"]), num(r[field])
        if e in EFFOK and c and c > 0:
            n = f'{r["model"]}@{e}'; bench[r["group"]][n] = math.log(c); srcs[r["group"]][n].add(r["source"])
            if "EAP-run" in r["confound"]: eap[r["group"]][n].add(r["source"])
    for b in [b for b in bench if len(bench[b]) < 2]: del bench[b]   # drop single-couple (circular) benchmarks
    couples = set(c for cv in bench.values() for c in cv)
    def bridged(b): return ANCHOR not in bench[b]
    NRUNG = {"sonnet-4.6":4, "haiku-4.5":1}                  # rungs each model exposes (default: 5, low→max)
    def ladder(b, c):                                        # share of the model's effort ladder this benchmark sweeps:
        m = c.split("@")[0]; n = NRUNG.get(m, 5)             # 0.5 for a single rung → 1.0 for the full ladder
        k = sum(1 for x in bench[b] if x.split("@")[0] == m)
        return 1.0 if n == 1 else 0.5 + 0.5*(k-1)/(n-1)
    EAPW = 1/3                                               # an early-access (pre-release) run counts for a third
    def wt(b, c, s): return (EAPW if s in eap[b][c] else 1.0) * (0.5 if bridged(b) else 1.0) * ladder(b, c)
    def cap(n):     return math.sqrt(n)                      # DIMINISHING RETURNS: a source's n measurements of a couple
    def votes(c, o):                                         # weigh √n in total (1 → 1, 4 → 2, 10 → 3.2, 36 → 6),
        per = collections.defaultdict(list)                  # shared among them; each keeps its own vote in the median
        for b, cv in bench.items():
            if c in cv:
                for s in srcs[b][c]: per[s].append((cv[c]-o[b], wt(b, c, s)))
        return [(x, w*cap(len(v))/len(v)) for v in per.values() for x, w in v]
    def wmedian(pairs):                                      # weighted median of [(value, weight), ...]
        pairs = sorted(pairs); W = sum(w for _, w in pairs)
        if W == 0: return pairs[len(pairs)//2][0]
        acc = 0.0
        for v, w in pairs:
            acc += w
            if acc >= W/2: return v
        return pairs[-1][0]
    g = {c: 0.0 for c in couples}
    for _ in range(800):                                     # alternate offsets (mean) / values (weighted median)
        o = {b: (cv[ANCHOR] if not bridged(b) else sum(cv[c]-g[c] for c in cv)/len(cv)) for b, cv in bench.items()}
        ng = {c: wmedian(votes(c, o)) for c in couples}
        a = ng[ANCHOR]; g = {c: ng[c]-a for c in couples}    # pin anchor to 1.0 (log 0)
    o = {b: (cv[ANCHOR] if not bridged(b) else sum(cv[c]-g[c] for c in cv)/len(cv)) for b, cv in bench.items()}
    def cell(n):
        if n not in couples: return None
        E = votes(n, o)
        med = wmedian(E); c = math.exp(med)                                # central = weighted median (unchanged)
        if len(E) < 2: return [round(c,2), round(c,2), round(c,2)]         # single benchmark → degenerate box
        s   = 1.4826 * wmedian([(abs(l-med), w) for l, w in E]) or 1e-9    # robust scale (MAD)
        cap = 1.5 * s                                                      # Huber: clip each deviation to ±1.5·MAD
        neg = [(max(l-med,-cap), w) for l, w in E if l < med]             # per-side RMS of the CLIPPED deviations →
        pos = [(min(l-med, cap), w) for l, w in E if l > med]             # asymmetric band that COUNTS outliers but caps them
        lo  = c*math.exp(-(sum(w*d*d for d,w in neg)/sum(w for _,w in neg))**0.5) if neg else c
        hi  = c*math.exp( (sum(w*d*d for d,w in pos)/sum(w for _,w in pos))**0.5) if pos else c
        return [round(c,2), round(lo,2), round(hi,2)]                      # band centred on the median → dot always inside
    ORD = {"fable-5.1":["low","medium","high","xhigh","max"],"fable-5":["low","medium","high","xhigh","max"],
           "opus-5.5":["low","medium","high","xhigh","max"],"opus-5":["low","medium","high","xhigh","max"],
           "opus-4.8":["low","medium","high","xhigh","max"],
           "sonnet-5.5":["low","medium","high","xhigh","max"],
           "sonnet-5":["low","medium","high","xhigh","max"],"opus-4.7":["low","medium","high","xhigh","max"],
           "sonnet-4.6":["low","medium","high","max"]}
    out = {}
    for m, es in ORD.items():
        out[m] = {e: cell(f"{m}@{e}") for e in es if cell(f"{m}@{e}")}
    hk = cell("haiku-4.5@solo")          # Haiku 4.5 = single node, no effort dial
    if hk: out["haiku-4.5"] = {"solo": hk}
    return out

