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

def groups_data():
    """§3 linking graph, DATA-DRIVEN. Nodes = the (model, effort) couples each source group actually measured,
    derived from raw-data.csv (no more hand-maintained mirror that could drift, cf. the old skillsbench case).
    Only the editorial metadata per group — display label, edge type (sweep/xmodel/xgen), verified config note —
    lives in GMETA. Some sources publish several sub-benchmarks (AIReiter) → MERGE folds them into one node-set
    so corroboration counts the source once."""
    GMETA = {
      "osworld":("OSWorld","sweep","Anthropic/AA · balayage low→max ✓"),
      "aa-index":("AA Index","xmodel","AA-Index · max ✓"),
      "aa-index-pertask":("AA /task","xmodel","AA-Index · max ✓"),
      "swerebench":("swe-rebench","xgen","ReAct minimal · Opus4.8 xhigh/4.7 high, Sonnet défaut ✓"),
      "workbench":("WorkBench","xmodel","ReAct natif · temp 0, like-for-like, thinking NS ✓"),
      "braintrust":("Braintrust","sweep","retrieval · budget T25/T50 ✓"),
      "stageclaw":("STAGE-Claw","xmodel","OpenClaw · reasoning DISABLED, temp 0 ✓"),
      "tobench":("TOBench","xgen","ReAct · thinking NS ✓"),
      "ceobench":("CEO-Bench","xmodel","terminal-agent · Opus/Sonnet=MAX, Haiku=thinking ✓"),
      "automationbench":("AutomationB.","xmodel","harness+effort NON précisés ✓"),
      "officeqa":("OfficeQA","xgen","Claude Agent SDK · reasoning HIGH ✓"),
      "slopcode":("SlopCode","xgen","Claude Code · Reasoning HIGH ✓"),
      "posttrain":("PostTrainB.","sweep","papier · medium/high ✓"),
      "skillsbench":("SkillsBench","xmodel","Claude Code 2.1.19 · temp 0, thinking NS ✓"),
      "aireiter":("AIReiter","xmodel","Claude Code · high ✓"),
      "ctala":("ctala","xmodel","Claude Code CLI · reasoning non config, temp 0.7 ✓"),
      "drona23":("drona23","xgen","Claude Code CLI · thinking NS, identique ✓"),
      "ponytail":("ponytail","xgen","Claude Code headless · thinking NS ✓"),
      "ianlpaterson":("ianlpaterson","xgen","OpenRouter · reasoning OFF ✓"),
      "hal-swemini":("HAL swe-mini","xgen","HAL · high vs défaut ✓"),
      "hal-science":("HAL sci","xgen","HAL · high ✓"),
      "george-liu":("george-liu","sweep","Claude Code · low/max ✓"),
      "zenn-qcd":("zenn QCD","sweep","API brut · low/xhigh ✓"),
      "whitekumalabo":("whitekumalabo","sweep","Claude Code · low/max ✓"),
      "qiita-nogataka":("qiita","sweep","API brut · low/max ✓"),
      "codesota":("CodeSOTA","xmodel","prix list blended (pas un run) ✓"),
      "coderev":("code-review","xmodel","VibeOps · temp 0.1, thinking NS ✓"),
      "wildclaw":("WildClaw","xgen","OpenRouter (4 harness) · thinking NS ✓"),
      "truefoundry":("TrueFoundry","xmodel","AI Gateway · single-turn sans outils, effort NS ✓"),
      "emb":("EMB","xmodel","bash+execute · Opus4.8=MAX, Sonnet5 NS ✓"),
      "willison":("Willison SVG","sweep","llm CLI · balayage low→max, tâche triviale (SVG) ✓"),
      "futuresearch":("DeepResearch","sweep","Deep Research Bench · low/high ✓"),
      "cursorbench":("CursorBench","sweep","Cursor 3.1 · balayage low→max, effort apparié ✓ (éditeur=vendeur)"),
      "scsweproeff":("SWE-Pro sweep","sweep","Opus 4.8 card p196 · balayage low→max, tokens de sortie ✓"),
      "schleeff":("HLE sweep","sweep","Opus 4.8 card p203 · HLE outils, balayage low→max ✓"),
      "scosweff":("OSWorld sweep","sweep","Opus 4.8 card p222 · balayage low→max, tokens de sortie ✓"),
    }
    MERGE = {"aireiter2":"aireiter", "aireiter3":"aireiter"}   # sub-benchmarks of one source → one node-set
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT,"raw-data.csv")))
            if r["group"] and not r["group"].startswith("#")]
    order, buckets = [], {}
    for r in rows:
        gk = MERGE.get(r["group"], r["group"])
        if gk not in buckets: buckets[gk] = []; order.append(gk)
        buckets[gk].append(r)
    out = []
    for gk in order:
        rs = buckets[gk]; nodes, seen = [], set()
        for r in rs:
            nid = f'{r["model"]}@{eff(r["effort"])}'
            if nid not in seen: seen.add(nid); nodes.append(nid)
        lbl, t, h = GMETA.get(gk, (gk, "xmodel", "config ✓"))
        out.append({"s": rs[0]["source"], "g": lbl, "t": t, "h": h, "n": nodes})
    return out

def ratio_grid(field):
    """Couple-atomic relative grid for a measured field (cost_usd or score). For each current (model,effort)
    node, solve a value RELATIVE to opus-4.8@medium=1.0 from same-task ratios only (explicit efforts;
    nothink/priceblend/default excluded). Edges = cross-model@same-effort OR same-model@diff-effort cost ratios,
    median per edge; node values by log-space Jacobi relaxation (harmonic/least-squares over all paths — no
    model×effort separability). CI = min/max of per-source single-hop estimates around each node. Haiku 4.5 has
    only one explicit-effort thinking point (OfficeQA@high) → emitted as a single 'solo' node."""
    from statistics import median
    import math, collections
    CUR = set(MX)                       # 6 current models
    EFFOK = {"low","medium","high","xhigh","max"}
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT,"raw-data.csv")))
            if r["group"] and not r["group"].startswith("#")]
    groups = {}
    for r in rows: groups.setdefault(r["group"], []).append(r)
    def items_of(rs):
        out = []
        for r in rs:
            if r["model"] not in CUR: continue
            e, c = eff(r["effort"]), num(r[field])
            if e in EFFOK and c and c > 0: out.append((r["model"], e, c, r["source"]))
        return out
    edgevals = collections.defaultdict(list)
    for g, rs in groups.items():
        it = items_of(rs)
        for i in range(len(it)):
            for j in range(i+1, len(it)):
                (m1,e1,c1,_),(m2,e2,c2,_) = it[i], it[j]
                if not ((m1!=m2 and e1==e2) or (m1==m2 and e1!=e2)): continue   # couple-atomic only
                n1,n2 = f"{m1}@{e1}", f"{m2}@{e2}"
                key = tuple(sorted([n1,n2])); cost = {n1:c1,n2:c2}
                edgevals[key].append(math.log(cost[key[0]]/cost[key[1]]))
    edges = {k: median(v) for k,v in edgevals.items()}
    nodes = set(n for k in edges for n in k)
    ANCHOR = "opus-4.8@medium"
    adj = collections.defaultdict(list)
    for (a,b),lr in edges.items(): adj[a].append((b,lr)); adj[b].append((a,-lr))
    logval = {n:0.0 for n in nodes}
    for _ in range(4000):
        nv = {}
        for n in nodes:
            nv[n] = 0.0 if n==ANCHOR else (sum(logval[k]+lr for k,lr in adj[n])/len(adj[n]) if adj[n] else logval[n])
        logval = nv
    rel = {n: math.exp(logval[n]) for n in nodes}
    # CI: per-source single-hop estimates around solved neighbours
    est = collections.defaultdict(list)
    for n in nodes: est[n].append(rel[n])
    for g, rs in groups.items():
        it = items_of(rs)
        for i in range(len(it)):
            for j in range(i+1, len(it)):
                (m1,e1,c1,_),(m2,e2,c2,_) = it[i], it[j]
                if not ((m1!=m2 and e1==e2) or (m1==m2 and e1!=e2)): continue
                n1,n2 = f"{m1}@{e1}", f"{m2}@{e2}"
                if n1 in rel and n2 in rel:
                    est[n1].append(rel[n2]*(c1/c2)); est[n2].append(rel[n1]*(c2/c1))
    def cell(n):
        if n not in rel: return None
        xs = [x for x in est[n] if x > 0]; r = rel[n]
        if len(xs) < 2: return [round(r,2), round(r,2), round(r,2)]   # single source → degenerate box
        lm = sum(math.log(x) for x in xs)/len(xs)
        sd = (sum((math.log(x)-lm)**2 for x in xs)/len(xs))**0.5     # std dev of the measured estimates (log-space)
        return [round(r,2), round(r*math.exp(-sd),2), round(r*math.exp(sd),2)]   # central ±1σ box (geometric)
    ORD = {"fable-5":["low","medium","high","xhigh","max"],"opus-4.8":["low","medium","high","xhigh","max"],
           "sonnet-5":["low","medium","high","xhigh","max"],"opus-4.7":["low","medium","high","xhigh","max"],
           "sonnet-4.6":["low","medium","high","max"]}
    out = {}
    for m, es in ORD.items():
        out[m] = {e: cell(f"{m}@{e}") for e in es if cell(f"{m}@{e}")}
    hk = cell("haiku-4.5@high")          # Haiku's sole explicit-effort thinking point
    if hk: out["haiku-4.5"] = {"solo": hk}
    return out

def cost_grid():    return ratio_grid("cost_usd")
def quality_grid(): return ratio_grid("score")   # quality via same-task score RATIOS, consolidated like cost (no cross-benchmark value comparison)

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
    CG = cost_grid()
    QG = quality_grid()
    GD = groups_data()
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
    app  = app.replace("__COSTGRID__", json.dumps(CG, separators=(",",":")))
    app  = app.replace("__QUALGRID__", json.dumps(QG, separators=(",",":")))
    app  = app.replace("__GROUPS_DATA__", json.dumps(GD, separators=(",",":")))
    body = body.replace("__NOTHINK_ROWS__", regime_rows_html(NT, DF))
    html = f"<style>\n{css}\n</style>\n{body}\n<script>\n{app}\n</script>\n"
    open(OUT,"w").write(html)
    print(f"built {OUT}  ({len(html)} bytes)  cost-pts={len(RD['cost'])} tok-pts={len(RD['tok'])}")
    print(f"  no-think pairs={list(NT['pairs'])}  index={NT['index']}")
    print(f"  default  pairs={list(DF['pairs'])}  index={DF['index']}")

if __name__ == "__main__":
    main()
