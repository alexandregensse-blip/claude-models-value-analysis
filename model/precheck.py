#!/usr/bin/env python3
"""Checks run before a fit, so that a data error does not cost a full fit (model/fit.py runs them first).

  1. Label against values (blocking): a score above the bound its metric label states ('playable-of-2' holding 100,
     'score/10' holding 100) is a transcription error; the fit would read the group on the wrong scale.
  2. Same runs under two metrics (warning): two groups of one publisher sharing 3 or more couples, not already
     recognised as republications nor declared one run's measurements (the build's column `run`, rule same-run-weight), whose costs agree within 1 % on every shared couple (the same runs cost the same
     whatever the metric), or, without costs, whose scores do, are probably one set of runs counted twice; they are
     merged or told apart by hand.
  3. A fraction above 1 (warning): a metric labelled as a fraction (of a peak, of a reference) whose values exceed 1
     is not bounded; it is read as is, and the label should say so.
  4. Memory (blocking): the fit's peak memory, estimated from the last measured peak of each axis
     (model/memory-peaks.json) scaled by the rows and draws it will hold now, summed when the two axes run at the same
     time, must stay under 90 % of the container's limit (cgroup memory.max); otherwise the full fit is not started —
     a fit killed for memory after 45 minutes loses them all.
  5. One couple twice in a group, discordant (warning): two rows of one model@effort in one group and one setup
     (harness, metric, unit) whose costs differ by more than DUP_COST_RATIO, or whose scores differ by more than
     DUP_SCORE_SHARE of the scale, are probably two builds or two configurations under one key (20 Oct 2026: ARC
     Prize's dated and undated GPT-5.6 Luna, costs 5× apart, left the cost fit at R̂ 2.0 after an hour). Replicates of
     one configuration agree; these do not.
  6. Identical costs in two cost groups (blocking): two groups of the cost fit table (after lqm.load, whose
     republication rule keeps a copy once) sharing COPY_MIN (3) or more couples whose costs are identical (relative gap
     < COPY_REL, 1e-9) are one set of runs whose cost would count twice; the rule that should have recognised them
     (the build's same-runs-as, lqm's republications) did not. A fortiori with a reading precision near zero (a cost
     copied to 15 digits): the pair's common effect absorbs the residuals, the groups' σ goes to 0 and the whole cost
     axis freezes (fit of 10 Nov 2026: ReactBench v1.0 / v1.1, the same runs re-graded, 20 identical costs of 20,
     d ≈ 3e-15, R̂ 6.8 after 7.7 h). The full fit is not started. A coincidence proven from the sources (runs of two
     different benchmarks, costs rounded to the cent) is declared pair by pair in COINCIDENCES, with the couples it
     covers and its proof; it is then reported, not blocking, as long as the identical couples are exactly those.
  7. Smoke fit (blocking, model/fit.py --smoke): a short fit of each axis in turn, quality then cost, SMOKE_CHAINS (2)
     chains of SMOKE_WARMUP (50) warm-up iterations and SMOKE_DRAWS (150) draws (the maintainer, 11 Nov 2026: it only
     checks that the fit sets off roughly in the right direction; it was 6 × (500 + 500) on quality alone). A chain
     left in another region shows there as R̂ far above 1. Above SMOKE_RHAT (2.0) on either axis the full fit is not
     started, and the message names the axis that stopped it.

Checks 1, 2, 3 and 5 read the build's data.csv (data/build/, the rows in the fit on either axis); 2, 4, 6 and 7 run lqm.load
on the fit tables (fit-quality.csv, fit-cost.csv) through the build's group map, as model/fit.py does.

Run from the repository root:  .stan/venv/bin/python model/precheck.py [--smoke]"""
import collections, csv, itertools, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(ROOT, "data")]
import lqm, build_lqm

DATA = os.path.join(build_lqm.BUILD, "data.csv")             # the build's public data file: every measure, its status

# The smoke fit (the maintainer, 11 Nov 2026): each axis, 2 chains of 50 warm-up + 150 draws; it only checks that the
# fit sets off roughly in the right direction, hence a loose threshold, applied to each axis.
SMOKE_RHAT = 2.0
SMOKE_CHAINS = 2
SMOKE_WARMUP = 50
SMOKE_DRAWS = 150
SMOKE_AXES = ("quality", "cost")
DUP_REL = 0.01
MEMORY_PEAKS = os.path.join(HERE, "memory-peaks.json")
MEMORY_SHARE = 0.9


def in_fit(r):
    """A data.csv row the fit reads: `in` on either axis (a legacy row: `legacy:in`)."""
    return any((r.get(k) or "").startswith(("in", "legacy:in")) for k in ("status_quality", "status_cost"))


def rows(path=DATA):
    """The rows of the build's data.csv that the fit reads (in on either axis): an out measure is not read by the fit,
    and its errors do not stop it. Groups are data.csv's (the quality group; a cost subset's fit group adds '~c<n>')."""
    with open(path, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(l for l in f if not l.startswith("#"))
                if r["group"] and not r["group"].startswith("#") and in_fit(r)]


def data_group(fit_group):
    """A fit table's group (lqm's split '~2' and the cost subset '~c1' included) → its data.csv group."""
    return re.sub(r"(~c\d+)?(~\d+)?$", "", fit_group)


def load(axis):
    """lqm.load on the axis' fit table through the build's group map, as model/fit.py reads it."""
    from catalog import MODEL_ORDER
    return build_lqm.load_table(lqm, axis, MODEL_ORDER)


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
    for axis in ("cost", "quality"):                                 # the fit tables' republications, on data.csv's groups
        known |= {frozenset(map(data_group, p[:2])) for p in load(axis)[2]}
    by = collections.defaultdict(lambda: collections.defaultdict(dict))
    run = collections.defaultdict(dict)                              # the build's declared runs (rule same-run-weight)
    for r in data:
        if r.get("run"):
            run[(r["source"], r["group"])][f"{r['model']}@{r['effort']}"] = r["run"]
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
        ra, rb = run[(s1, g1)], run[(s2, g2)]
        if ra and rb and all(ra.get(c) and ra.get(c) == rb.get(c) for c in set(ra) & set(rb)) and set(ra) & set(rb):
            continue                                                 # one run's two measurements, declared: 1/k each
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


COPY_REL = 1e-9
COPY_MIN = 3
# Coincidences proven from the sources (arbitration of the R2 pairs, the maintainer's consigne of 11 Nov 2026): the two
# base groups (the fit group without its build subset ~c<n> or lqm split ~<n>), the identical couples, the proof. A
# declaration covers that pair and exactly those couples: another identical couple, or the same couples in another
# pair, block again.
COINCIDENCES = [
    dict(groups=("aicodingdaily-main", "taxcalc-ty25-notool"),
         couples=("gpt-6-luna@high", "gpt-6-luna@max", "gpt-6-luna@medium"),
         proof="two benchmarks, two runs: AI Coding Daily's Laravel projects run through Codex CLI (« 34 | GPT-6-Luna "
               "(High) | 53.04 | $0.01 | 03:51 | | Codex CLI », avg cost per prompt) and Column Tax's TaxCalcBench TY25 "
               "returns run by its own harness (« gpt-6-luna | high | 50×1/50 | 4.00% », cost per return $0.01); the "
               "costs are printed to the cent, GPT-6 Luna's at its floor ($0.01, $0.03, $0.01), the scores unrelated "
               "(53.04 of 70 against 4 % correct returns)"),
]


def base_group(g):
    return re.sub(r"(~c\d+)?(~\d+)?$", "", g)


def declared_coincidence(g1, g2, same):
    for c in COINCIDENCES:
        if {base_group(g1), base_group(g2)} == set(c["groups"]) and set(same) == set(c["couples"]):
            return c
    return None


def identical_costs(groups, notes=None):
    """Pairs of cost groups of the fit table (after lqm.load: republications already kept once) sharing COPY_MIN or
    more couples whose costs are identical (relative gap < COPY_REL): one set of runs whose cost would count twice. With
    a reading precision near zero (a cost copied to 15 digits), the pair's common effect absorbs the residuals and the
    group's scale σ goes to 0: the whole cost axis freezes (fit of 10 Nov 2026, ReactBench v1.0 / v1.1, R̂ 6.8)."""
    by = {g: {} for g in groups}
    for g, G in groups.items():
        for x in G["rows"]:
            by[g].setdefault(x["couple"], x)
    out = []
    for g1, g2 in itertools.combinations(sorted(by), 2):
        a, b = by[g1], by[g2]
        same = [c for c in set(a) & set(b)
                if abs(a[c]["raw"] - b[c]["raw"]) < COPY_REL * max(abs(a[c]["raw"]), abs(b[c]["raw"]))]
        if len(same) >= COPY_MIN:
            c = declared_coincidence(g1, g2, same)
            if c is not None:
                if notes is not None:
                    notes.append(f"{g1} / {g2}: {len(same)} identical costs ({', '.join(sorted(same))}), declared a "
                                 f"coincidence: {c['proof']}")
                continue
            d = max(max(a[c]["d"], b[c]["d"]) for c in same)
            out.append(f"{g1} / {g2}: {len(same)} identical costs of {len(set(a) & set(b))} shared couples"
                       f" (largest reading precision d among them {d:.2g}"
                       + (", near zero: σ can collapse)" if d < 1e-6 else ")"))
    return out


DUP_COST_RATIO = 1.5
DUP_SCORE_SHARE = 0.10


def discordant_twins(data, order):
    """Pairs of rows of one couple in one group and setup whose values are too far apart to be replicates."""
    by = collections.defaultdict(list)
    for r in data:
        if r["model"] in order and r["effort"] in lqm.EFFORTS:
            by[(r["group"], r["model"], r["effort"], lqm.harness_base(r["harness"]), r["score_metric"], r["unit"])].append(r)
    out = []
    for (g, m, e, *_), rs in sorted(by.items()):
        if len(rs) < 2:
            continue
        costs = [float(r["cost_usd"]) for r in rs if r["cost_usd"] not in ("", None) and float(r["cost_usd"]) > 0]
        scores = [float(r["score"]) for r in rs if r["score"] not in ("", None)]
        why = []
        if len(costs) > 1 and max(costs) / min(costs) > DUP_COST_RATIO:
            why.append(f"costs {min(costs):g}..{max(costs):g}")
        if len(scores) > 1:
            b = lqm.bound(rs[0]["score_metric"]) or max(abs(x) for x in scores) or 1
            if (max(scores) - min(scores)) / b > DUP_SCORE_SHARE:
                why.append(f"scores {min(scores):g}..{max(scores):g}")
        if why:
            out.append(f"{g} {m}@{e} ×{len(rs)}: " + ", ".join(why))
    return out


def smoke(axis, seed=11):
    """Short fit of one axis (SMOKE_CHAINS chains of SMOKE_WARMUP warm-up + SMOKE_DRAWS draws); returns (R̂ max, worst
    parameters)."""
    groups, _, _ = load(axis)
    data, _ = lqm.stan_data(groups, axis)
    st = dict(lqm.SAMPLER[axis], chains=SMOKE_CHAINS, warmup=SMOKE_WARMUP, samples=SMOKE_DRAWS)
    post = lqm.sample_once(data, axis, st, seed)
    diag, _ = lqm.diagnostics(post)
    return diag["rhat_max"], diag["worst_rhat"]


def smoke_verdict(results):
    """results: [(axis, R̂ max)] in the order run → the first axis whose R̂ is undefined (too few draws) or above
    SMOKE_RHAT, or None when every axis passes."""
    for axis, rhat in results:
        if rhat is None or rhat > SMOKE_RHAT:
            return axis
    return None


def smoke_all(run=smoke, say=print):
    """The smoke fit of each axis in turn (SMOKE_AXES); → the axis that stops the full fit, or None. An axis over the
    threshold stops the next one from being sampled."""
    results = []
    for axis in SMOKE_AXES:
        rhat, worst = run(axis)
        say(f"smoke fit ({axis}, {SMOKE_CHAINS} × ({SMOKE_WARMUP} + {SMOKE_DRAWS})): R̂ max {rhat} · worst {list(worst)[:4]}")
        results.append((axis, rhat))
        bad = smoke_verdict(results)
        if bad is not None:
            say(f"!! smoke fit, {bad} axis: a chain is in another region (R̂ > {SMOKE_RHAT}, or undefined): the full fit "
                "is not started")
            return bad
    return None


def memory_limit():
    try:
        v = open("/sys/fs/cgroup/memory.max").read().strip()
        return None if v == "max" else int(v)
    except OSError:
        return None


def memory_check():
    """(estimated peak in bytes, limit in bytes, detail) of the next fit; None when no peak was measured yet."""
    import json
    try:
        peaks = json.load(open(MEMORY_PEAKS))
    except (OSError, ValueError):
        return None
    est = {}
    for axis in ("cost", "quality"):
        if axis not in peaks:
            continue
        groups = load(axis)[0]
        n = sum(len(g["rows"]) for g in groups.values())
        st = lqm.SAMPLER[axis]
        draws = st["chains"] * (st["warmup"] + st["samples"])
        m = peaks[axis]
        est[axis] = m["peak_bytes"] * (n / m["rows"]) * (draws / m["draws"])
    parallel = lqm.PARALLEL_AXES and (os.cpu_count() or 1) >= sum(lqm.SAMPLER[a]["chains"] for a in ("cost", "quality"))
    need = sum(est.values()) if parallel else max(est.values(), default=0)
    return need, memory_limit(), dict(est, parallel=parallel)


def main(run_smoke=False):
    data = rows()
    errors, twins = label_errors(data), twin_metrics(data)
    for e in errors:
        print("!! label contradicted by value:", e)
    for t in twins:
        print("?? same runs under two metrics?", t)
    for f in fraction_above_one(data):
        print("?? fraction above 1:", f)
    from catalog import MODEL_ORDER
    for t in discordant_twins(data, set(MODEL_ORDER)):
        print("?? one couple twice in a group, discordant (two builds or configurations under one key?):", t)
    notes = []
    copies = identical_costs(load("cost")[0], notes)
    for c in notes:
        print("?? identical costs in two cost groups, a declared coincidence:", c)
    for c in copies:
        print("!! identical costs in two cost groups, not recognised as copies:", c)
    if errors or copies:
        return 1
    mc = memory_check()
    if mc is None:
        print("?? memory: no measured peak yet (model/memory-peaks.json): the fit starts unchecked")
    else:
        need, limit, detail = mc
        axes = ", ".join(f"{a} {v / 2**30:.1f} GB" for a, v in detail.items() if a != "parallel")
        print(f"memory: estimated peak {need / 2**30:.1f} GB ({axes}; axes {'together' if detail['parallel'] else 'in turn'})"
              + (f", limit {limit / 2**30:.1f} GB" if limit else ""))
        if limit and need > MEMORY_SHARE * limit:
            print(f"!! the fit would exceed {MEMORY_SHARE:.0%} of the container's memory: not started "
                  "(raise the limit, or run the axes in turn)")
            return 1
    if run_smoke and smoke_all() is not None:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(run_smoke="--smoke" in sys.argv[1:]))
