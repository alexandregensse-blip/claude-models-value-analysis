#!/usr/bin/env python3
"""Artifact generator. Reads data + modular css/body/js, computes derived ratio data,
assembles cost-matrix.html. Run: python3 gen/build.py  (from the scratchpad dir)."""
import csv, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)            # scratchpad
OUT  = os.path.join(ROOT, "cost-matrix.html")

MX = {"fable-5":0,"opus-4.8":1,"opus-4.7":2,"sonnet-5":3,"sonnet-4.6":4,"haiku-4.5":5}
EXP = {"low","medium","high","xhigh","max"}
EMAP = {"T25":"medium","T50":"high"}    # braintrust thinking-budget tiers → nearest effort
PRICE_OUT = {"fable-5":50,"opus-4.8":25,"opus-4.7":25,"sonnet-5":15,"sonnet-4.6":15,"haiku-4.5":5}  # output $/Mtok

def eff(e): return EMAP.get(e, e)
def num(x):
    try: return float(x)
    except: return None

def comparisons():
    """One entry per matched-effort model-pair comparison in a source: cost and/or token ratio + price ratio."""
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT,"raw-data.csv")))
            if r["group"] and not r["group"].startswith("#")]
    groups = {}
    for r in rows: groups.setdefault(r["group"], []).append(r)
    comps = []
    for g, rs in groups.items():
        cur = [r for r in rs if r["model"] in MX]
        for i in range(len(cur)):
            for j in range(i+1, len(cur)):
                a, b = cur[i], cur[j]
                if a["model"] == b["model"]: continue          # different models only
                if MX[a["model"]] > MX[b["model"]]: a, b = b, a
                ea, eb = eff(a["effort"]), eff(b["effort"])
                if ea in ("nothink","priceblend") or eb in ("nothink","priceblend"): continue   # no-thinking runs + list-price blends set aside
                if ea != eb: continue                          # matched effort only
                e = ea if ea in EXP else "grey"
                pair = f'{a["model"].replace("-"," ")}/{b["model"].replace("-"," ")}'
                pr = PRICE_OUT[a["model"]] / PRICE_OUT[b["model"]]
                ca, cb = num(a["cost_usd"]), num(b["cost_usd"])
                ta, tb = num(a["tokens_out"]), num(b["tokens_out"])
                comps.append({
                    "pair": pair, "e": e, "src": a["source"], "pr": pr,
                    "cost": round(ca/cb,3) if (ca and cb and cb>0) else None,
                    "tok":  round(ta/tb,3) if (ta and tb and tb>0) else None,
                })
    return comps

def build_RD(comps):
    """Measured points get C#/T# ids; a single-metric comparison is REPRODUCED on the other axis
    via the price ratio (derived=1, keeps the origin id). cost=tok*pr ; tok=cost/pr."""
    cm = [c for c in comps if c["cost"] is not None]
    tm = [c for c in comps if c["tok"]  is not None]
    def idmap(ms, key, prefix):
        byp = {}
        for c in ms: byp.setdefault(c["pair"], []).append(c)
        pairs = sorted(byp, key=lambda k: (-len(byp[k]), k))
        out, n = {}, 0
        for pair in pairs:
            for c in sorted(byp[pair], key=lambda z: z[key]):
                n += 1; out[id(c)] = f"{prefix}{n}"
        return out
    cid, tid = idmap(cm,"cost","C"), idmap(tm,"tok","T")
    cost, tok = [], []
    for c in comps:
        if c["cost"] is not None:
            i = cid[id(c)]; cost.append([c["pair"], c["cost"], c["e"], c["src"], i, 0])
            if c["tok"] is None:
                tok.append([c["pair"], round(c["cost"]/c["pr"],3), c["e"], c["src"], i, 1])
        if c["tok"] is not None:
            i = tid[id(c)]; tok.append([c["pair"], c["tok"], c["e"], c["src"], i, 0])
            if c["cost"] is None:
                cost.append([c["pair"], round(c["tok"]*c["pr"],3), c["e"], c["src"], i, 1])
    return {"cost": cost, "tok": tok}

def consolidated(comps):
    """Data-driven consolidated square per (pair, effort) = MEDIAN of measured (non-grey) points at that effort.
    Rows: [effort, costMedian|None, tokMedian|None]. Reflects the real clusters (varies by effort), unlike the
    old separable matrix ratio which was constant across efforts."""
    from statistics import median
    costs, toks = {}, {}
    for c in comps:
        if c["e"] == "grey": continue
        if c["cost"] is not None: costs.setdefault((c["pair"], c["e"]), []).append(c["cost"])
        if c["tok"]  is not None: toks.setdefault((c["pair"], c["e"]), []).append(c["tok"])
    pairs = {k[0] for k in costs} | {k[0] for k in toks}
    out = {}
    for pair in pairs:
        rows = []
        for e in ["low","medium","high","xhigh","max"]:
            cv, tv = costs.get((pair,e)), toks.get((pair,e))
            if cv or tv:
                rows.append([e, round(median(cv),3) if cv else None, round(median(tv),3) if tv else None])
        if rows: out[pair] = rows
    return out

def regime(kept):
    """No-think (and 'default') cost regime, COUPLE-ATOMIC. Cross-model cost ratios inside groups where BOTH
    models ran at an effort label in `kept` (e.g. {'nothink'}). Returns per-pair median ratio + source list,
    plus a per-model cost index anchored to the cheapest anchor via BFS over measured pair medians (log-space,
    shortest path — NOT a global model factor). Fable/Sonnet-5 have no such rows → absent, shown as N/A."""
    from statistics import median
    import math
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT,"raw-data.csv")))
            if r["group"] and not r["group"].startswith("#")]
    groups = {}
    for r in rows: groups.setdefault(r["group"], []).append(r)
    pair_costs, pair_srcs = {}, {}
    for g, rs in groups.items():
        cur = [r for r in rs if r["model"] in MX]
        for i in range(len(cur)):
            for j in range(i+1, len(cur)):
                a, b = cur[i], cur[j]
                if a["model"] == b["model"]: continue
                if MX[a["model"]] > MX[b["model"]]: a, b = b, a
                ea, eb = eff(a["effort"]), eff(b["effort"])
                if ea not in kept or eb not in kept or ea != eb: continue
                ca, cb = num(a["cost_usd"]), num(b["cost_usd"])
                if not (ca and cb and cb > 0): continue
                pair = f'{a["model"].replace("-"," ")}/{b["model"].replace("-"," ")}'
                pair_costs.setdefault(pair, []).append(round(ca/cb, 3))
                pair_srcs.setdefault(pair, set()).add(a["source"])
    pairs = {}
    for p, v in pair_costs.items():
        pairs[p] = {"med": round(median(v), 3), "n": len(pair_srcs[p]),
                    "lo": round(min(v), 3), "hi": round(max(v), 3), "src": sorted(pair_srcs[p])}
    # per-model index anchored to haiku-4.5=1.0 via BFS over log(median) edges (shortest path)
    ANCHOR = "haiku 4.5"
    adj = {}
    for p, d in pairs.items():
        # ratio d = cost_x / cost_y  →  logcost_y = logcost_x - log(d) ; logcost_x = logcost_y + log(d)
        x, y = p.split("/"); lr = math.log(d["med"])
        adj.setdefault(x, []).append((y, -lr)); adj.setdefault(y, []).append((x, lr))
    idx, frontier = {ANCHOR: 0.0}, [ANCHOR]
    while frontier:
        nxt = []
        for u in frontier:
            for v, lr in adj.get(u, []):
                if v not in idx: idx[v] = idx[u] + lr; nxt.append(v)
        frontier = nxt
    index = {m: round(math.exp(idx[m]), 2) for m in idx}
    return {"pairs": pairs, "index": index, "anchor": ANCHOR}

def regime_rows_html(nt, df):
    """Build the §6 table body: per-pair no-think medians, then the 'default' bucket kept visually separate."""
    def cell(d): return f'<td>{d["med"]}×</td><td>{d["n"]}</td><td>{d["lo"]}–{d["hi"]}×</td>'
    def block(title, reg, cls, empty_note):
        order = sorted(reg["pairs"], key=lambda p: -reg["pairs"][p]["med"])
        if not order:
            return f'<tr class="{cls}"><td colspan="4"><b>{title}</b> — {empty_note}</td></tr>'
        idx = reg["index"]
        idxline = " · ".join(f'{m}&nbsp;{idx[m]}×' for m in sorted(idx, key=lambda m: idx[m]))
        h = f'<tr class="{cls}"><td colspan="4"><b>{title}</b> — indice coût (Haiku 4.5 = 1×, chaîné, indicatif)&nbsp;: {idxline}</td></tr>'
        for p in order:
            d = reg["pairs"][p]
            h += f'<tr><td>{p}</td>{cell(d)}</tr><tr class="srcrow"><td colspan="4">{", ".join(d["src"])}</td></tr>'
        return h
    return (block("Sans thinking (nothink)", nt, "nt-head", "aucune paire mesurée") +
            block("Harnais par défaut — thinking non déclaré", df, "df-head",
                  "aucune paire inter-modèles à config appariée parmi les modèles courants (ces sources mélangent les efforts) → aucun ratio couple-atomique calculable ; les points « défaut » restent hors régime."))

def main():
    comps = comparisons()
    RD = build_RD(comps)
    NT = regime({"nothink"})
    DF = regime({"default"})
    CONS = consolidated(comps)
    # id map for reference
    with open(os.path.join(ROOT,"ratio-ids.md"),"w") as f:
        f.write("# Ratio-point ID map (generated by build.py)\n")
        for label,key in [("COST","cost"),("TOKENS","tok")]:
            f.write(f"\n## {label}\n")
            for p in RD[key]:
                f.write(f"{p[4]}: {p[0]}  {p[1]}x  effort={p[2]}  src={p[3]}\n")

    css  = open(os.path.join(HERE,"style.css")).read()
    body = open(os.path.join(HERE,"body.html")).read()
    app  = open(os.path.join(HERE,"app.js")).read()
    app  = app.replace("__RATIO_DATA__", json.dumps(RD, separators=(",",":")))
    app  = app.replace("__CONS_DATA__", json.dumps(CONS, separators=(",",":")))
    body = body.replace("__NOTHINK_ROWS__", regime_rows_html(NT, DF))
    html = f"<style>\n{css}\n</style>\n{body}\n<script>\n{app}\n</script>\n"
    open(OUT,"w").write(html)
    print(f"built {OUT}  ({len(html)} bytes)  cost-pts={len(RD['cost'])} tok-pts={len(RD['tok'])}")
    print(f"  no-think pairs={list(NT['pairs'])}  index={NT['index']}")
    print(f"  default  pairs={list(DF['pairs'])}  index={DF['index']}")

if __name__ == "__main__":
    main()
