#!/usr/bin/env python3
"""Checks run before a fit, so that a data error does not cost a full fit (model/fit.py runs them first).

  1. Label against values (blocking): a score above the bound its metric label states ('playable-of-2' holding 100,
     'score/10' holding 100) is a transcription error; the fit would read the group on the wrong scale.
  2. Same runs under two metrics (warning): two groups of one publisher sharing 3 or more couples, not already
     recognised as republications nor declared one run's measurements (the build's column `run`, rule same-run-weight), whose costs agree within 1 % on every shared couple (the same runs cost the same
     whatever the metric), or, without costs, whose scores do, are probably one set of runs counted twice; they are
     merged or told apart by hand. Setups sharing a run_set (benchmarks.json) are one run declared; a pair the
     sources establish as distinct runs is declared in DISTINCT_RUNS with its proof and reported as « -- declared ».
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
     one configuration agree; these do not. Replicates the source declares (seeds, separate runs of one case) are
     named in REPLICATES with their exact values and proof, and reported as « -- declared ».
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


# Pairs of groups the sources establish as distinct runs although their values agree within DUP_REL (the maintainer's
# consigne of 11 Nov 2026, « résous les ?? du precheck »): the two data.csv groups and the proof. A declared pair is
# reported, not flagged.
DISTINCT_RUNS = [
    dict(groups=("arxiv-2609.29933-t12-mmlongbench-doc-extractor-mmlb-column-k-10",
                 "arxiv-2609.29933-t12-mmlongbench-doc-extractor-mmlb-column-k-20"),
         proof="Table 12 « Retrieval-depth sweep with ColQwen2.5 » (« accuracy / mean input tokens »): k = 10 and k = 20 "
               "retrieved pages are two runs with other inputs — Qwen3.5-27B « 0.594 / 18k | 0.595 / 34k », 4B "
               "0.528 / 0.530, 9B 0.560 / 0.564 — the accuracy flattening above k = 10, the inputs doubling"),
] + [dict(groups=(f"arxiv-2610.27043-t2-mintaka-{a}", f"arxiv-2610.27043-t2-mintaka-{b}"),
          proof="Table 2, one column per Mintaka language (« low 78.8 76.5 77.8 77.2 77.9 77.5 77.0 76.2 78.2 … » for "
                "Gemini 3.5 Flash): each language is its own translated question set, run apart; Gemini 3.5 Flash's "
                "accuracy lies within 76-79 % in every language, hence values within 1 %")
     for a, b in (("de", "es"), ("de", "hi"), ("de", "pt"), ("es", "hi"), ("es", "it"), ("hi", "it"), ("hi", "pt"))]


def declared_distinct(g1, g2):
    return next((d for d in DISTINCT_RUNS if set(d["groups"]) == {g1, g2}), None)


def setup_run_sets():
    """data.csv group → its setup's run_set (data/registry/benchmarks.json): setups sharing a run_set are declared one
    run's measurements (rule same-run-weight), whether or not their rows are in on quality today."""
    import json
    setups = json.load(open(os.path.join(ROOT, "data", "registry", "benchmarks.json"), encoding="utf-8"))["setups"]
    try:
        gs = json.load(open(os.path.join(build_lqm.BUILD, "group-setups.json"), encoding="utf-8"))["groups"]
    except (OSError, ValueError, KeyError):
        gs = {}

    def of(group):
        sid = gs.get(group) or re.split(r"[@#]", group)[0]
        return (setups.get(sid) or {}).get("run_set")
    return of


def twin_metrics(data, notes=None):
    """Pairs of groups of one publisher, 3 or more shared couples, not already recognised as republications nor
    declared one run (the build's column `run`, or setups sharing a run_set), whose costs agree within DUP_REL on every
    shared couple (the same runs cost the same, whatever the metric), or, without costs, whose scores do. A pair
    declared distinct runs (DISTINCT_RUNS) goes to `notes`."""
    from catalog import MODEL_ORDER
    run_set = setup_run_sets()
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
        if run_set(g1) and run_set(g1) == run_set(g2):
            continue                                                 # setups declared one run (benchmarks.json run_set)
        cost = set(a["cost_usd"]) & set(b["cost_usd"])
        score = set(a["score"]) & set(b["score"])
        msg = None
        if len(cost) >= 3 and all(gap(a["cost_usd"][c], b["cost_usd"][c]) < DUP_REL for c in cost):
            msg = f"{g1} / {g2} ({s1}): same cost on {len(cost)} shared couples"
        elif len(cost) < 3 and len(score) >= 3 and all(gap(a["score"][c], b["score"][c]) < DUP_REL for c in score):
            msg = f"{g1} / {g2} ({s1}): same score on {len(score)} shared couples, no cost to tell them apart"
        if msg:
            d = declared_distinct(g1, g2)
            if d is None:
                out.append(msg)
            elif notes is not None:
                notes.append(f"{msg}; declared distinct runs: {d['proof']}")
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
# Replicates declared by their sources (the maintainer's consigne of 11 Nov 2026, « résous les ?? du precheck »):
# several runs of one configuration, each a measurement of it, whose spread the check would otherwise read as two
# configurations under one key. A declaration names the setup (the data.csv group without '@publisher' / '#campaign'),
# the couple, and the exact (score, cost) pairs of its rows as data.csv writes them: another row, or another value,
# is flagged again.
REPLICATES = [
    dict(setup="s7t-wsp-exp5-seaquest", couple="fable-5.2@high",
         rows=(("53.546", ""), ("35.597", ""), ("57.534", "")),
         proof="three seeds of one configuration: results/exp5_high/seaquest/r0, r1 and r2 (score.json, score.mean)"),
    dict(setup="tc-claude-2_1_205-fathom-v1_0_0-base", couple="haiku-4.5@nothink",
         rows=(("0", "1.6958095"), ("0", "1.0490046999999998"), ("0", "1.2319570999999996")),
         proof="three runs of one TestCabinet case (« case: fathom v1.0.0 base none », harness « claude 2.1.205 »), rows "
               "616d9520…, 7dff2919…, f3b4b11c…, each with its own start time (2026-07-09T02:55, 02:04 …): every run "
               "records its own tokens and cost (« Every run records cost two ways »)"),
    dict(setup="tc-claude-2_1_235-pong-v2_1_0-base", couple="haiku-4.5@nothink",
         rows=(("0", "1.0508769000000002"), ("0", "0.8449548000000004"), ("0", "0.7061620000000002"),
               ("52", "0.8828445"), ("0", "0.6544832999999999")),
         proof="five runs of one TestCabinet case (pong v2.1.0 base, harness claude 2.1.235), rows e8f76489…, b871521b…, "
               "6733b72e…, 5b6f78a5…, 213b1c55…, each its own run"),
    dict(setup="llm-chess-vs-random", couple="gpt-5.4@low",
         rows=(("70", ""), ("40", "")),
         proof="two runs of ten games of one configuration (« gpt-5.4-low__2026-03-08-18-12-13___aggregate_results.json » "
               "7 of 10, « gpt-5.4-low__2026-04-19-11-06-21 » 4 of 10, reasoning_effort low in both), two log folders"),
    dict(setup="playcodesvg", couple="gemini-3.8-flash@medium",
         rows=(("", "0.043"), ("", "0.049"), ("", "0.056"), ("", "0.075")),
         proof="Playcode's Gemini 3.8 Flash rows « default », « low », « medium », « max » ran the model's default four "
               "times (« our harness had never wired Gemini's thinking_level, so every launch-sweep Gemini run had been at "
               "the default »; « measured each model's default repeatedly »), one API call each (« One API call per "
               "cell »)"),
    dict(setup="nurb-bit-block", couple="gpt-5.6-terra@medium",
         rows=(("0.947", "0.675"), ("0.892", "1.6470000000000002")),
         proof="two rows of one benchmark revision (0.22.2/0.1.0@e8f4e93e23fd) and one configuration, Codex 0.149.0 and "
               "0.149.1 (a patch release: one configuration, lqm.harness_base)"),
    dict(setup="nurb-bundle-holder", couple="gpt-5.6-terra@medium",
         rows=(("0.867", "1.269"), ("0.760", "1.035")),
         proof="two rows of one benchmark revision (0.22.2/0.1.0@c16e77e91b9a), Codex 0.149.1 and 0.149.0 (patch release)"),
    dict(setup="nurb-pole-rest", couple="gpt-5.6-terra@medium",
         rows=(("1.000", "0.675"), ("0.828", "0.747")),
         proof="two rows of one benchmark revision (0.22.2/0.1.0@de974b4cb0c3), Codex 0.149.1 and 0.149.0 (patch release)"),
    dict(setup="nurb-leg-cup", couple="gpt-5.6-luna@max",
         rows=(("1.000", "0.030000000000000002"), ("1.000", "0.066")),
         proof="two rows of one benchmark revision (0.23.0/0.1.0@6817426c8779), Codex 0.150.0 and 0.149.1 (harness "
               "versions: one configuration, lqm.harness_base)"),
]


def declared_replicates(group, couple, rs):
    vals = sorted((r["score"], r["cost_usd"]) for r in rs)
    for d in REPLICATES:
        if re.split(r"[@#]", group)[0] == d["setup"] and couple == d["couple"] and vals == sorted(d["rows"]):
            return d
    return None


def discordant_twins(data, order, notes=None):
    """Pairs of rows of one couple in one group and setup whose values are too far apart to be replicates; declared
    replicates (REPLICATES) go to `notes`."""
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
            msg = f"{g} {m}@{e} ×{len(rs)}: " + ", ".join(why)
            d = declared_replicates(g, f"{m}@{e}", rs)
            if d is None:
                out.append(msg)
            elif notes is not None:
                notes.append(f"{msg}; declared replicates: {d['proof']}")
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
    declared = []
    errors, twins = label_errors(data), twin_metrics(data, declared)
    for e in errors:
        print("!! label contradicted by value:", e)
    for t in twins:
        print("?? same runs under two metrics?", t)
    for f in fraction_above_one(data):
        print("?? fraction above 1:", f)
    from catalog import MODEL_ORDER
    for t in discordant_twins(data, set(MODEL_ORDER), declared):
        print("?? one couple twice in a group, discordant (two builds or configurations under one key?):", t)
    for t in declared:
        print("-- declared:", t)
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
