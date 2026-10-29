#!/usr/bin/env python3
"""Phase 1 of docs/DATA-PIPELINE.md §6: lqm.load keeps its composites rule, homogeneity split and republication rule;
this step recovers its per-row outcome by comparing its input (fit-quality.csv, fit-cost.csv) with the rows
it keeps (group, couple, value), and writes it into status-report.json and data.csv:

    a row dropped by its composites rule      → out:composite
    by its republication rule                 → out:republished
    in a split part with one couple           → out:single-couple (cost: out:cost-single-couple)
    in a group saturated at a bound           → out:saturated
    filtered before its rules for its configuration (not in lqm.EFFORTS) → out:effort-not-established, so that the
    status never says `in` for a row the fit drops (the tree already keeps such a configuration out: vocab x-terms
    in_fit false; this is the guard should the two lists part);
    filtered for another reason (model not in the list, value not usable): recorded as lqm_outcome only.
    lqm.EFFORTS holds the configurations the build writes (nothink, minimal, think, solo and the levels, 29 Oct);
    between-tools and an odd label stay out of it.

lqm.py is imported unchanged; its group-keyed catalog maps (COMPOSITES, FAMILY_OF) are resolved through the build's
group-map.json and group-setups.json in this process (fit_maps: each fit group inherits its base group's entries; the
families and composites defined in benchmarks.json are added on their setups). model/fit.py, model/precheck.py and
model/validation read the fit tables through the same fit_maps. Standard library only (lqm.load needs no numpy).

    python3 data/build_lqm.py data/build/       # after data/build.py --no-lqm
"""
import collections, contextlib, csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
AXES = (("quality", "score", "fit-quality.csv"), ("cost", "cost_usd", "fit-cost.csv"))


def base_of(lqm_group):
    """lqm's split suffix '~2' removed (the build's cost suffix '~c1' kept)."""
    return re.sub(r"~\d+$", "", lqm_group)


def group_setups(measures, gm, benchmarks_path):
    """What the group-keyed catalog maps need from the registry, for the fit groups of group-map.json: each group's
    setup (as the report's measures give it: a measure's `group` and `cost_group`; legacy rows have none), and each such
    setup's benchmark family and composite components (benchmarks.json). The build writes it as group-setups.json, so
    that the fit resolves the maps from the build's products alone, without the status report."""
    setup_of = {}
    for e in measures.values():
        for g in (e.get("group"), e.get("cost_group")):
            if g:
                setup_of[g] = e["setup"]
    bench = {}
    if benchmarks_path and os.path.isfile(benchmarks_path):
        with open(benchmarks_path, encoding="utf-8") as f:
            bench = json.load(f).get("setups", {})
    groups = {g: setup_of[g] for g in sorted(gm) if g in setup_of}
    setups = {}
    for s in sorted(set(groups.values())):
        b = bench.get(s, {})
        sc = b.get("composite") or {}
        setups[s] = dict(family=b.get("family"), components=sorted(
            {c if isinstance(c, str) else c.get("setup") for c in sc.get("components", [])} - {None}))
    return dict(groups=groups, setups=setups)


def expanded_maps(lqm, gm, gs):
    """COMPOSITES and FAMILY_OF keyed by fit groups: each fit group inherits its base group's entries (group-map.json),
    and the family and composite components of its setup (group-setups.json)."""
    setup_of, setups = gs["groups"], gs["setups"]
    fam = dict(lqm.FAMILY_OF)
    comps = dict(lqm.COMPOSITES)
    for g, b in gm.items():
        s = setup_of.get(g)
        fam[g] = lqm.FAMILY_OF.get(b) or (setups.get(s, {}).get("family") if s else None)
        members = set(lqm.COMPOSITES.get(b, []))
        members_setups = set(setups.get(s, {}).get("components", []) if s else [])
        if members or members_setups:
            comps[g] = sorted(h for h, hb in gm.items() if hb in members or setup_of.get(h) in members_setups)
    return comps, fam


def read_maps(build_dir):
    """(group-map.json, group-setups.json) of a build folder."""
    with open(os.path.join(build_dir, "group-map.json"), encoding="utf-8") as f:
        gm = json.load(f)
    with open(os.path.join(build_dir, "group-setups.json"), encoding="utf-8") as f:
        gs = json.load(f)
    return gm, gs


@contextlib.contextmanager
def fit_maps(lqm, build_dir):
    """lqm.COMPOSITES and lqm.FAMILY_OF keyed by the build's fit groups while the block runs (lqm.load reads them),
    restored after: how data/build_lqm.py, model/fit.py, model/precheck.py and model/validation read the fit tables."""
    comps, fam = expanded_maps(lqm, *read_maps(build_dir))
    saved = lqm.COMPOSITES, lqm.FAMILY_OF
    lqm.COMPOSITES, lqm.FAMILY_OF = comps, fam
    try:
        yield comps, fam
    finally:
        lqm.COMPOSITES, lqm.FAMILY_OF = saved


BUILD = os.path.join(REPO, "data", "build")                 # the committed build (data/build.py's default --out)


def table(axis, build_dir=BUILD):
    """The fit table of an axis ('quality' or 'cost') in a build folder."""
    return os.path.join(build_dir, {a: n for a, _, n in AXES}[axis])


def load_table(lqm, axis, models, build_dir=BUILD, path=None):
    """lqm.load on an axis' fit table — or on a table derived from it (path: rows removed, synthetic values) — with
    the group-keyed maps resolved through the build's group map (fit_maps). → lqm.load's (groups, report, republished)."""
    field = {a: f for a, f, _ in AXES}[axis]
    with fit_maps(lqm, build_dir):
        return lqm.load(path or table(axis, build_dir), models, field=field)


def base_groups(gm):
    """data.csv group → base group: a data.csv row carries its quality group name; a cost-only row's fit group adds
    '~c<n>' to it. A group in no fit table maps to itself."""
    out = {}
    for g, b in gm.items():
        out.setdefault(re.sub(r"~c\d+$", "", g), b)
    out.update(gm)
    return out


def run(out_dir, models=None):
    sys.path.insert(0, os.path.join(REPO, "model"))
    sys.path.insert(0, HERE)
    import lqm
    rp = os.path.join(out_dir, "status-report.json")
    with open(rp, encoding="utf-8") as f:
        rep = json.load(f)
    models = models or rep["build"]["fit_models"]
    rep["lqm"] = {}
    with fit_maps(lqm, out_dir) as (comps, fam):
        for axis, field, name in AXES:
            path = os.path.join(out_dir, name)
            groups, lrep, republished = lqm.load(path, models, field=field)
            outcome(lqm, rep, axis, field, path, groups, republished, comps, models)
            rep["lqm"][axis] = dict(report=dict(lrep), republished=[list(r) for r in republished])
    rep["build"]["lqm"] = "done"
    # cost measures sharing a carrier follow it
    for e in rep["measures"].values():
        if e.get("cost_measure") and e["cost_measure"] in rep["measures"]:
            e["status"]["cost"] = rep["measures"][e["cost_measure"]]["status"]["cost"]
    import build
    rep["counts"] = build.counts(rep["measures"])
    with open(rp, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1, ensure_ascii=False)
    rewrite_data(out_dir, rep)
    return rep


def outcome(lqm, rep, axis, field, path, groups, republished, comps, models):
    kept = collections.Counter()
    for g, G in groups.items():
        for x in G["rows"]:
            kept[(base_of(g), x["couple"], x["raw"])] += 1
    rows = [r for r in csv.DictReader(open(path, encoding="utf-8")) if r["group"] and not r["group"].startswith("#")]

    def passes(r):
        try:
            v = float(r[field])
        except (TypeError, ValueError):
            return False
        return r["model"] in models and r["effort"] in lqm.EFFORTS and not (field == "cost_usd" and v <= 0)
    measured = collections.defaultdict(set)
    for r in rows:
        if passes(r):
            measured[r["group"]].add(f'{r["model"]}@{r["effort"]}')
    partners = collections.defaultdict(set)              # group → groups it shares a republished series with
    for t in republished:
        a_, b_ = base_of(t[0]), base_of(t[1])
        partners[a_].add(b_)
        partners[b_].add(a_)
    metric_of = {}
    for r in rows:
        metric_of.setdefault(r["group"], r["score_metric"])
    couples_in = collections.defaultdict(set)
    for r in rows:
        if passes(r):
            couples_in[r["group"]].add(f'{r["model"]}@{r["effort"]}')
    entries = [(ref, e, e.get("fit_rows", {}).get(axis)) for ref, e in rep["measures"].items()]
    entries = [(ref, e, fr) for ref, e, fr in entries if fr]
    by_group = collections.defaultdict(list)
    for ref, e, fr in entries:
        by_group[fr["group"]].append(fr)
    for ref, e, fr in entries:
        c = f'{fr["model"]}@{fr["effort"]}'
        r = {"model": fr["model"], "effort": fr["effort"], field: fr["value"]}
        lo = e.setdefault("lqm_outcome", {})
        if not passes(r):
            why = "effort not in lqm.EFFORTS" if fr["effort"] not in lqm.EFFORTS else \
                "model not in the fit's list" if fr["model"] not in models else "value not usable"
            lo[axis] = f"filtered before lqm's rules: {why}"
            st = e["status"][axis] or ""
            if fr["effort"] not in lqm.EFFORTS and st.startswith(("in", "legacy:in")):
                e["status"][axis] = "legacy:out:effort-not-in-efforts" if st == "legacy:in" else "out:effort-not-established"
                e["reason_detail"][axis] = f"lqm.load (phase 1): {fr['effort']} is not in lqm.EFFORTS"
            continue
        k = (fr["group"], c, float(fr["value"]))
        if kept[k] > 0:
            kept[k] -= 1
            lo[axis] = "kept"
            continue
        g = fr["group"]
        if g in comps and any(c in measured.get(h, set()) for h in comps[g]):
            code = "out:composite"
        elif any(c in couples_in[h] for h in partners.get(g, ())):
            code = "out:republished"                     # its couple is in the group it was copied from
        else:
            vals = [x for x in by_group[g] if passes({"model": x["model"], "effort": x["effort"], field: x["value"]})]
            n = None
            if axis == "quality":
                n = lqm.bound(metric_of.get(g, ""))
            at = n is not None and all(float(x["value"]) >= 0.9995 * n or float(x["value"]) <= 0.0005 * n
                                       for x in vals) and len({float(x["value"]) for x in vals}) == 1
            code = "out:saturated" if at else ("out:single-couple" if axis == "quality" else "out:cost-single-couple")
        lo[axis] = f"dropped by lqm.load: {code}"
        st = e["status"][axis] or ""
        if st == "legacy:in":
            e["status"][axis] = "legacy:" + code
            e["reason_detail"][axis] = f"lqm.load (phase 1): {code}"
        elif st.startswith("in"):
            e["status"][axis] = code
            e["reason_detail"][axis] = f"lqm.load (phase 1): {code}"


def rewrite_data(out_dir, rep):
    """data.csv rows are written in the report's measure order: their status columns follow the report."""
    p = os.path.join(out_dir, "data.csv")
    with open(p, encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f)
        cols, rows = rd.fieldnames, list(rd)
    for r, e in zip(rows, rep["measures"].values()):
        r["status_quality"] = e["status"]["quality"] or ""
        r["status_cost"] = e["status"]["cost"] or ""
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    rep = run(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "data", "build"))
    print(f"lqm outcome written: quality {rep['counts']['quality']}; cost {rep['counts']['cost']}")
