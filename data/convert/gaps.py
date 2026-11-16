#!/usr/bin/env python3
"""Registry-gap report per source, from a build's status report: what the registry lacks for the source's measures
to be established, so the registry is fixed before the next build (nothing is invented here). Standard library only.

    python3 data/convert/gaps.py build/status-report.json [--source SOURCE_ID] [--registry data/registry \\
        --findings data/findings] [--json]

Per source:
- heads: prefix heads naming no route (with --registry/--findings, from data/convert/precheck.py);
- ids: model values resolving to no key, or to several (aliases without a run date that places them);
- configurations: (model, configuration) pairs refused because the model's list lacks them, or the list is empty;
- defaults: models whose no-effort-sent rows found no documented default covering the run;
- prices: models whose cost found no registered price over its price date, or no base price.
"""
import argparse, collections, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def gaps(rep, source=None):
    out = collections.defaultdict(lambda: dict(ids=collections.Counter(), configurations=collections.Counter(),
                                               defaults=collections.Counter(), prices=collections.Counter()))
    for ref, e in rep["measures"].items():
        if e.get("kind") == "legacy" or (source and e.get("source") != source):
            continue
        g = out[e["source"]]
        f = e.get("fields") or {}
        mf = f.get("model") or {}
        if not mf.get("value"):
            for x in mf.get("resolution") or []:
                if x["outcome"].startswith("unresolved"):
                    g["ids"][f"{x['value']}  ({x['outcome'][12:]})"] += 1
            if not mf.get("resolution"):
                g["ids"][mf.get("detail") or "no model fact"] += 1
            continue
        key = mf["value"]
        cf = f.get("configuration") or {}
        offered = f.get("configurations_offered") or []
        st = e["status"].get("quality") or e["status"].get("cost") or ""
        if st == "out:effort-not-established":
            det = cf.get("detail") or ""
            if not offered:
                g["configurations"][(key, "(empty configuration list)")] += 1
            elif "not one of the model's configurations" in det or "not in the model's list" in det:
                g["configurations"][(key, cf.get("value"))] += 1
            elif cf.get("step") == 7 or "documented default" in det:
                g["defaults"][key] += 1
        c = f.get("cost") or {}
        why = (c.get("reprice_detail") or "") + " " + (e.get("reason_detail") or {}).get("cost", "")
        if e["status"].get("cost") == "out:cost-not-comparable" and re.search(r"no base price|not registered|no registered price", why):
            g["prices"][key] += 1
    return {s: {k: (dict(v.most_common()) if k != "configurations" else
                    {f"{a} @ {b}": n for (a, b), n in v.most_common()}) for k, v in g.items()}
            for s, g in out.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report")
    ap.add_argument("--source")
    ap.add_argument("--registry")
    ap.add_argument("--findings")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        rep = json.load(open(a.report, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: {a.report}: {e}", file=sys.stderr)
        return 2
    res = gaps(rep, a.source)
    if a.registry and a.findings:
        import precheck
        for s in res:
            res[s]["heads"] = precheck.precheck(a.registry, a.findings, s)["unknown_heads"]
    if a.json:
        print(json.dumps(res, indent=1, ensure_ascii=False))
        return 0
    for s, g in res.items():
        print(f"== {s}")
        for k in ("heads", "ids", "configurations", "defaults", "prices"):
            items = g.get(k) or {}
            print(f"  {k}: {sum(items.values())} row(s), {len(items)} distinct")
            for v, n in list(items.items())[:25]:
                print(f"    ×{n:<4} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
