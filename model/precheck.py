#!/usr/bin/env python3
"""Checks run before a fit, so that a data error does not cost a full fit (model/fit.py runs them first).

  1. Label against values (blocking): a score above the bound its metric label states ('playable-of-2' holding 100,
     'score/10' holding 100) is a transcription error; the fit would read the group on the wrong scale.
  2. Same runs under two metrics (warning): two groups of one publisher sharing 3 or more couples, not already
     recognised as republications, whose costs agree within 1 % on every shared couple (the same runs cost the same
     whatever the metric), or, without costs, whose scores do, are probably one set of runs counted twice; they are
     merged or told apart by hand.
  3. A fraction above 1 (warning): a metric labelled as a fraction (of a peak, of a reference) whose values exceed 1
     is not bounded; it is read as is, and the label should say so.
  4. Smoke fit (blocking, model/fit.py --smoke): a short fit of the quality axis (4 chains × 500 + 500) takes about
     three minutes; a chain left in another region shows there as R̂ far above 1. Above SMOKE_RHAT the full fit is
     not started.

Run from the repository root:  .stan/venv/bin/python model/precheck.py"""
import collections, csv, itertools, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(ROOT, "data")]
import lqm

SMOKE_RHAT = 1.5
DUP_REL = 0.01


def rows(path=os.path.join(ROOT, "raw-data.csv")):
    with open(path, newline="") as f:
        return [r for r in csv.DictReader(l for l in f if not l.startswith("#")) if not r["group"].startswith("#")]


def label_errors(data):
    out = []
    for r in data:
        try:
            s = float(r["score"])
        except ValueError:
            continue
        b = lqm.bound(r["score_metric"])
        if b is not None and not 0 <= s <= b:
            out.append(f"{r['group']} {r['model']}@{r['effort']}: {s:g} outside 0–{b:g} ({r['score_metric']})")
    return out


def twin_metrics(data):
    """Pairs of groups of one publisher, 3 or more shared couples, not already recognised as republications, whose
    costs agree within DUP_REL on every shared couple (the same runs cost the same, whatever the metric), or, without
    costs, whose scores do."""
    from catalog import MODEL_ORDER
    known = set()
    for field in ("cost_usd", "score"):
        known |= {frozenset(p[:2]) for p in lqm.load(os.path.join(ROOT, "raw-data.csv"), MODEL_ORDER, field=field)[2]}
    by = collections.defaultdict(lambda: collections.defaultdict(dict))
    for r in data:
        for col in ("cost_usd", "score"):
            try:
                by[(r["source"], r["group"])][col][f"{r['model']}@{r['effort']}"] = float(r[col])
            except ValueError:
                pass
    gap = lambda x, y: abs(x - y) / max(abs(x), abs(y), 1e-9)
    out = []
    for (s1, g1), (s2, g2) in itertools.combinations(sorted(by), 2):
        if s1 != s2 or frozenset((g1, g2)) in known:
            continue
        a, b = by[(s1, g1)], by[(s2, g2)]
        cost = set(a["cost_usd"]) & set(b["cost_usd"])
        score = set(a["score"]) & set(b["score"])
        if len(cost) >= 3 and all(gap(a["cost_usd"][c], b["cost_usd"][c]) < DUP_REL for c in cost):
            out.append(f"{g1} / {g2} ({s1}): same cost on {len(cost)} shared couples")
        elif len(cost) < 3 and len(score) >= 3 and all(gap(a["score"][c], b["score"][c]) < DUP_REL for c in score):
            out.append(f"{g1} / {g2} ({s1}): same score on {len(score)} shared couples, no cost to tell them apart")
    return out


def fraction_above_one(data):
    out = collections.defaultdict(list)
    for r in data:
        try:
            s = float(r["score"])
        except ValueError:
            continue
        if "fraction" in r["score_metric"].lower() and s > 1:
            out[(r["group"], r["score_metric"])].append(s)
    return [f"{g} ({m}): {len(v)} values above 1, up to {max(v):g}" for (g, m), v in sorted(out.items())]


def smoke(seed=11):
    """Short quality fit; returns (R̂ max, worst parameters)."""
    from catalog import MODEL_ORDER
    groups, _, _ = lqm.load(os.path.join(ROOT, "raw-data.csv"), MODEL_ORDER, field="score")
    data, _ = lqm.stan_data(groups, "quality")
    post = lqm._sample(data, "quality", dict(lqm.SAMPLER["quality"], warmup=500, samples=500), seed)
    diag, _ = lqm.diagnostics(post)
    return diag["rhat_max"], diag["worst_rhat"]


def main(run_smoke=False):
    data = rows()
    errors, twins = label_errors(data), twin_metrics(data)
    for e in errors:
        print("!! label contradicted by value:", e)
    for t in twins:
        print("?? same runs under two metrics?", t)
    for f in fraction_above_one(data):
        print("?? fraction above 1:", f)
    if errors:
        return 1
    if run_smoke:
        rhat, worst = smoke()
        print(f"smoke fit (quality, 4 × 500 + 500): R̂ max {rhat} · worst {worst[:4]}")
        if rhat > SMOKE_RHAT:
            print(f"!! a chain is in another region (R̂ > {SMOKE_RHAT}): the full fit is not started")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(run_smoke="--smoke" in sys.argv[1:]))
