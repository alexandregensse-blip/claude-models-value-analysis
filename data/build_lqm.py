#!/usr/bin/env python3
"""Phase 1 of docs/DATA-PIPELINE.md §6: lqm.load keeps its composites rule, homogeneity split and republication rule;
this step recovers its per-row outcome by comparing its input (build/fit-quality.csv, build/fit-cost.csv) with the rows
it keeps (group, couple, value), and writes it into build/status-report.json and build/data.csv:

    a row dropped by its composites rule      → out:composite
    by its republication rule                 → out:republished
    in a split part with one couple           → out:single-couple (cost: out:cost-single-couple)
    in a group saturated at a bound           → out:saturated
    filtered before its rules (effort not in lqm.EFFORTS, model not in the list): recorded as lqm_outcome only (the
    tree's status stands: the configurations-per-model method change is pending in lqm.py).

lqm.py is imported unchanged; its group-keyed catalog maps (COMPOSITES, FAMILY_OF) are resolved through
build/group-map.json in this process (each fit group inherits its base group's entries; composites defined in
benchmarks.json are added on their setups). Standard library only (lqm.load needs no numpy).

    python3 data/build_lqm.py build/            # after data/build.py --no-lqm
"""
import collections, csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
AXES = (("quality", "score", "fit-quality.csv"), ("cost", "cost_usd", "fit-cost.csv"))


def base_of(lqm_group):
    """lqm's split suffix '~2' removed (the build's cost suffix '~c1' kept)."""
    return re.sub(r"~\d+$", "", lqm_group)


def expanded_maps(lqm, rep, gm):
    """COMPOSITES and FAMILY_OF keyed by fit groups."""
    setup_of = {}
    for e in rep["measures"].values():
        for g in (e.get("group"), e.get("cost_group")):
            if g:
                setup_of[g] = e["setup"]
    bench = {}
    p = rep["build"].get("benchmarks")
    if p and os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            bench = json.load(f).get("setups", {})
    fam = dict(lqm.FAMILY_OF)
    comps = dict(lqm.COMPOSITES)
    for g, b in gm.items():
        s = setup_of.get(g)
        fam[g] = lqm.FAMILY_OF.get(b) or (bench.get(s, {}).get("family") if s else None)
        members = set(lqm.COMPOSITES.get(b, []))
        sc = (bench.get(s, {}) if s else {}).get("composite") or {}
        members_setups = set(sc.get("components", []))
        if members or members_setups:
            comps[g] = sorted(h for h, hb in gm.items() if hb in members or setup_of.get(h) in members_setups)
    return comps, fam


def run(out_dir, models=None):
    sys.path.insert(0, os.path.join(REPO, "model"))
    sys.path.insert(0, HERE)
    import lqm
    rp = os.path.join(out_dir, "status-report.json")
    with open(rp, encoding="utf-8") as f:
        rep = json.load(f)
    with open(os.path.join(out_dir, "group-map.json"), encoding="utf-8") as f:
        gm = json.load(f)
    models = models or rep["build"]["fit_models"]
    comps, fam = expanded_maps(lqm, rep, gm)
    saved = lqm.COMPOSITES, lqm.FAMILY_OF
    lqm.COMPOSITES, lqm.FAMILY_OF = comps, fam
    rep["lqm"] = {}
    try:
        for axis, field, name in AXES:
            path = os.path.join(out_dir, name)
            groups, lrep, republished = lqm.load(path, models, field=field)
            outcome(lqm, rep, axis, field, path, groups, republished, comps, models)
            rep["lqm"][axis] = dict(report=dict(lrep), republished=[list(r) for r in republished])
    finally:
        lqm.COMPOSITES, lqm.FAMILY_OF = saved
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
            why = "effort not in lqm.EFFORTS (method change pending)" if fr["effort"] not in lqm.EFFORTS else \
                "model not in the fit's list" if fr["model"] not in models else "value not usable"
            lo[axis] = f"filtered before lqm's rules: {why}"
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
    """build/data.csv rows are written in the report's measure order: their status columns follow the report."""
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
    rep = run(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "build"))
    print(f"lqm outcome written: quality {rep['counts']['quality']}; cost {rep['counts']['cost']}")
