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
                haiku = "haiku-4.5" in (a["model"], b["model"])   # haiku has no effort dial (solo) → compare vs its benchmark partner
                if ea != eb and not haiku: continue            # matched effort only (except haiku, no dial)
                e = (ea if ea in EXP else eb) if haiku else (ea if ea in EXP else "grey")
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
    derived from raw-data.csv.
    Only the editorial metadata per group — display label, edge type (sweep/xmodel/xgen), verified config note —
    lives in GMETA. Some sources publish several sub-benchmarks (AIReiter) → MERGE folds them into one node-set
    so corroboration counts the source once."""
    GMETA = {
      "osworld":("OSWorld","sweep","Anthropic/AA · sweep low→max ✓"),
      "aa-index":("AA Index","xmodel","AA-Index · max ✓"),
      "aa-index-pertask":("AA /task","xmodel","AA-Index · max ✓"),
      "swerebench":("swe-rebench","xgen","ReAct minimal · Opus4.8 xhigh/4.7 high, Sonnet default ✓"),
      "workbench":("WorkBench","xmodel","ReAct natif · temp 0, like-for-like, thinking NS ✓"),
      "braintrust":("Braintrust","sweep","retrieval · budget T25/T50 ✓"),
      "stageclaw":("STAGE-Claw","xmodel","OpenClaw · reasoning DISABLED, temp 0 ✓"),
      "tobench":("TOBench","xgen","ReAct · thinking NS ✓"),
      "ceobench":("CEO-Bench","xmodel","terminal-agent · Opus/Sonnet=MAX, Haiku=thinking ✓"),
      "automationbench":("AutomationB.","xmodel","harness+effort NOT stated ✓"),
      "officeqa":("OfficeQA","xgen","Claude Agent SDK · reasoning HIGH ✓"),
      "slopcode":("SlopCode","xgen","Claude Code · Reasoning HIGH ✓"),
      "posttrain":("PostTrainB.","sweep","papier · medium/high ✓"),
      "skillsbench":("SkillsBench","xmodel","Claude Code 2.1.19 · temp 0, thinking NS ✓"),
      "aireiter":("AIReiter","xmodel","Claude Code · high ✓"),
      "ctala":("ctala","xmodel","Claude Code CLI · reasoning not configured, temp 0.7 ✓"),
      "drona23":("drona23","xgen","Claude Code CLI · thinking NS, identical ✓"),
      "ponytail":("ponytail","xgen","Claude Code headless · thinking NS ✓"),
      "ianlpaterson":("ianlpaterson","xgen","OpenRouter · reasoning OFF ✓"),
      "hal-swemini":("HAL swe-mini","xgen","HAL · high vs default ✓"),
      "hal-science":("HAL sci","xgen","HAL · high ✓"),
      "george-liu":("george-liu","sweep","Claude Code · low/max ✓"),
      "zenn-qcd":("zenn QCD","sweep","raw API · low/xhigh ✓"),
      "whitekumalabo":("whitekumalabo","sweep","Claude Code · low/max ✓"),
      "qiita-nogataka":("qiita","sweep","raw API · low/max ✓"),
      "codesota":("CodeSOTA","xmodel","list-price blended (not a run) ✓"),
      "coderev":("code-review","xmodel","VibeOps · temp 0.1, thinking NS ✓"),
      "wildclaw":("WildClaw","xgen","OpenRouter (4 harness) · thinking NS ✓"),
      "truefoundry":("TrueFoundry","xmodel","AI Gateway · single-turn no tools, effort NS ✓"),
      "emb":("EMB","xmodel","bash+execute · Opus4.8=MAX, Sonnet5 NS ✓"),
      "willison":("Willison SVG","sweep","llm CLI · sweep low→max, trivial task (SVG) ✓"),
      "futuresearch":("DeepResearch","sweep","Deep Research Bench · low/high ✓"),
      "cursorbench":("CursorBench","sweep","Cursor 3.1 · sweep low→max, matched effort ✓ (vendor benchmark)"),
      "scsweproeff":("SWE-Pro sweep","sweep","Opus 4.8 card p196 · sweep low→max, output tokens ✓"),
      "schleeff":("HLE sweep","sweep","Opus 4.8 card p203 · HLE tools, sweep low→max ✓"),
      "scosweff":("OSWorld sweep","sweep","Opus 4.8 card p222 · sweep low→max, output tokens ✓"),
      "scfsweppro":("SWE-Pro (Fable)","sweep","Fable 5 card p255 · Fable=Mythos 5, sweep low→xhigh, $ cost ✓"),
      "scfcdiamond":("FrontierCode-D","sweep","Fable 5 card p257 · Fable=Mythos 5, sweep low→max, $ cost ✓"),
      "scfdeepqa":("DeepSearchQA","sweep","Fable 5 card p270 · Fable=Mythos 5, sweep low→max, $ cost ✓"),
      "scfhletools":("HLE (Fable)","sweep","Fable 5 card p267 · Fable=Mythos 5, sweep low→max, $ cost ✓"),
      "scfdraco":("DRACO","sweep","Fable 5 card p271 · Fable=Mythos 5, sweep low→max, $ cost ✓"),
      "scoarc":("ARC-AGI-2","sweep","Opus 4.7 card p213 · sweep low→max, $ cost ✓"),
      "scodeepqa":("DeepSearchQA","sweep","Opus 4.7 card p200 · Opus4.7 vs Sonnet4.6, sweep low→max ✓"),
    }
    MERGE = {"aireiter2":"aireiter", "aireiter3":"aireiter"}   # sub-benchmarks of one source → one node-set
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT,"raw-data.csv")))
            if r["group"] and not r["group"].startswith("#")]
    order, buckets = [], {}
    for r in rows:
        gk = MERGE.get(r["group"], r["group"])
        if gk not in buckets: buckets[gk] = []; order.append(gk)
        buckets[gk].append(r)
    def pick_url(rs, src):
        cands = [(r.get("ref") or "").strip() for r in rs]
        cands = [c for c in cands if "." in c and " " not in c]        # keep domain-like refs
        if cands:
            cands.sort(key=lambda c: ("/" in c, len(c)), reverse=True)  # prefer one with a path
            u = cands[0]
            return u if u.startswith("http") else "https://" + u
        if src.startswith("arxiv-"):                                    # fallback for arXiv sources
            return "https://arxiv.org/abs/" + src[len("arxiv-"):]
        if "syscard" in src or any("syscard" in (r.get("ref") or "") for r in rs):
            return "https://www.anthropic.com/transparency"             # Anthropic system cards live on the transparency hub
        return ""
    out = []
    for gk in order:
        rs = buckets[gk]; nodes, seen = [], set()
        for r in rs:
            nid = f'{r["model"]}@{eff(r["effort"])}'
            if nid not in seen: seen.add(nid); nodes.append(nid)
        lbl, t, h = GMETA.get(gk, (gk, "xmodel", "config ✓"))
        out.append({"s": rs[0]["source"], "g": lbl, "t": t, "h": h, "n": nodes, "u": pick_url(rs, rs[0]["source"])})
    return out

def ratio_grid(field):
    """Couple-atomic ROBUST grid for a measured field (cost_usd or score). Each (model,effort) node gets a value
    RELATIVE to opus-4.8@medium=1.0, built ONLY from within-benchmark ratios (never a cross-benchmark value
    comparison). Central value AND uncertainty band come from the SAME per-benchmark estimates:

      1. Per benchmark, take log(value) of every current (model,effort) couple — explicit efforts + haiku@solo
         (haiku has no effort dial); nothink/priceblend/default excluded. Benchmarks with <2 couples are dropped
         (a lone couple is circular — it can only echo the anchor).
      2. Normalise each benchmark to the anchor via a per-benchmark offset:
           - anchor present  → offset = log(opus-4.8@medium)               (divide by the anchor directly)
           - anchor absent   → BRIDGE offset = MEAN residual (log value − global g) over its shared couples;
                               such bridged benchmarks are down-weighted ×0.5 (indirect anchoring).
         The offset is a nuisance alignment term → MEAN (non-degenerate), not median.
      3. Each benchmark then yields one normalised estimate per couple = exp(log value − offset), with
         weight = (#independent sources) × (0.5 if bridged). The global g[couple] is the source-weighted MEDIAN
         of those estimates (robust to task-complexity outliers); the anchor is pinned to 0 each pass. Iterate.
      4. central = exp(g[couple]) = weighted median; band = **per-side Huber spread**, centred on the median:
         deviations (log estimate − log median) are clipped to ±1.5·MAD, then the lower/upper band = median·exp(∓RMS
         of the clipped negative/positive deviations). This is robust (a wild outlier is capped at 1.5·MAD) yet
         still COUNTS outliers (they widen their side up to the cap — unlike IQR which discards them), and it is
         ASYMMETRIC (captures skew). Centred on the median → the plotted dot is always inside the band. A
         single-benchmark node gets a degenerate [c,c,c] box. Haiku 4.5 → one 'solo' node (no effort ladder)."""
    import math, collections
    CUR = set(MX)                                            # 6 current models
    EFFOK = {"low","medium","high","xhigh","max","solo"}     # 'solo' = haiku 4.5 (no discrete effort)
    ANCHOR = "opus-4.8@medium"
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT,"raw-data.csv")))
            if r["group"] and not r["group"].startswith("#")]
    bench = collections.defaultdict(dict)                    # benchmark → couple → log(value)
    srcs  = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in rows:
        if r["model"] not in CUR: continue
        e, c = eff(r["effort"]), num(r[field])
        if e in EFFOK and c and c > 0:
            n = f'{r["model"]}@{e}'; bench[r["group"]][n] = math.log(c); srcs[r["group"]][n].add(r["source"])
    for b in [b for b in bench if len(bench[b]) < 2]: del bench[b]   # drop single-couple (circular) benchmarks
    couples = set(c for cv in bench.values() for c in cv)
    def bridged(b): return ANCHOR not in bench[b]
    def wt(b, c):   return len(srcs[b][c]) * (0.5 if bridged(b) else 1.0)
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
        ng = {c: wmedian([(cv[c]-o[b], wt(b,c)) for b, cv in bench.items() if c in cv]) for c in couples}
        a = ng[ANCHOR]; g = {c: ng[c]-a for c in couples}    # pin anchor to 1.0 (log 0)
    o = {b: (cv[ANCHOR] if not bridged(b) else sum(cv[c]-g[c] for c in cv)/len(cv)) for b, cv in bench.items()}
    def cell(n):
        if n not in couples: return None
        E = [(cv[n]-o[b], wt(b,n)) for b, cv in bench.items() if n in cv]
        med = wmedian(E); c = math.exp(med)                                # central = weighted median (unchanged)
        if len(E) < 2: return [round(c,2), round(c,2), round(c,2)]         # single benchmark → degenerate box
        s   = 1.4826 * wmedian([(abs(l-med), w) for l, w in E]) or 1e-9    # robust scale (MAD)
        cap = 1.5 * s                                                      # Huber: clip each deviation to ±1.5·MAD
        neg = [(max(l-med,-cap), w) for l, w in E if l < med]             # per-side RMS of the CLIPPED deviations →
        pos = [(min(l-med, cap), w) for l, w in E if l > med]             # asymmetric band that COUNTS outliers but caps them
        lo  = c*math.exp(-(sum(w*d*d for d,w in neg)/sum(w for _,w in neg))**0.5) if neg else c
        hi  = c*math.exp( (sum(w*d*d for d,w in pos)/sum(w for _,w in pos))**0.5) if pos else c
        return [round(c,2), round(lo,2), round(hi,2)]                      # band centred on the median → dot always inside
    ORD = {"fable-5":["low","medium","high","xhigh","max"],"opus-4.8":["low","medium","high","xhigh","max"],
           "sonnet-5":["low","medium","high","xhigh","max"],"opus-4.7":["low","medium","high","xhigh","max"],
           "sonnet-4.6":["low","medium","high","max"]}
    out = {}
    for m, es in ORD.items():
        out[m] = {e: cell(f"{m}@{e}") for e in es if cell(f"{m}@{e}")}
    hk = cell("haiku-4.5@solo")          # Haiku 4.5 = single node, no effort dial
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
        h = f'<tr class="{cls}"><td colspan="4"><b>{title}</b> — cost index (Haiku 4.5 = 1×, chained, indicative)&nbsp;: {idxline}</td></tr>'
        for p in order:
            d = reg["pairs"][p]
            h += f'<tr><td>{p}</td>{cell(d)}</tr><tr class="srcrow"><td colspan="4">{", ".join(d["src"])}</td></tr>'
        return h
    return (block("No thinking (nothink)", nt, "nt-head", "no measured pair") +
            block("Default harness — thinking unstated", df, "df-head",
                  "no cross-model matched-config pair among the current models (these sources mix efforts) → no couple-atomic ratio computable; the \u2018default\u2019 points stay out of regime."))

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
    body = body.replace("__NSAMETASK__", str(len(RD["cost"])))   # same-task cost-ratio measurement points (dynamic)
    html = f"<style>\n{css}\n</style>\n{body}\n<script>\n{app}\n</script>\n"
    open(OUT,"w").write(html)
    print(f"built {OUT}  ({len(html)} bytes)  cost-pts={len(RD['cost'])} tok-pts={len(RD['tok'])}")
    print(f"  no-think pairs={list(NT['pairs'])}  index={NT['index']}")
    print(f"  default  pairs={list(DF['pairs'])}  index={DF['index']}")

if __name__ == "__main__":
    main()
