#!/usr/bin/env python3
"""Artifact generator. Reads data + modular css/body/js, computes derived ratio data,
assembles index.html. Run: python3 gen/build.py  (from the scratchpad dir)."""
import csv, html as htmlmod, json, os, re, subprocess, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)            # scratchpad
OUT  = os.path.join(ROOT, "index.html")

# Publication: every absolute URL derives from SITE_URL (canonical root, trailing slash).
SITE_URL    = "https://claude-models.agensse.com/"
REPO_URL    = "https://github.com/alexandregensse-blip/claude-models-value-analysis"
TITLE       = "Claude cost vs quality: Fable, Opus, Sonnet, Haiku compared"
DESCRIPTION = ("What each Claude model (Fable, Opus, Sonnet, Haiku) costs at every effort level, and which gives "
               "the best quality for the price. Open data, CC BY 4.0.")
INDEXNOW_KEY = "b3573dbc1da690e66e9ef05b081b7abe"   # public by design: served as /<key>.txt, proves ownership to IndexNow (Bing…)

MX = {"fable-5.1":0,"fable-5":1,"opus-5.5":2,"opus-5":3,"opus-4.8":4,"opus-4.7":5,"sonnet-5":6,"sonnet-4.6":7,"haiku-4.5":8}
EXP = {"low","medium","high","xhigh","max"}
EMAP = {"T25":"medium","T50":"high"}    # braintrust thinking-budget tiers → nearest effort
GRID_ANCHOR = "opus-5@high"                 # (model@effort) pinned to 1.0 on both grids
PRICE_OUT = {"fable-5.1":50,"fable-5":50,"opus-5.5":20,"opus-5":25,"opus-4.8":25,"opus-4.7":25,"sonnet-5":15,"sonnet-4.6":15,"haiku-4.5":5}  # output $/Mtok

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
      "aa-index":("AA Index","sweep","AA-Index · cross-model at max + Opus 5 sweep low→max ✓"),
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
      "cursorbench":("CursorBench","sweep","Sonnet 5 card p118 · 5 models × sweep low→max, $ cost, scores printed ✓"),
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
      "sc5deepswe":("DeepSWE v1.1","sweep","Opus 5 card p150 · 4 models × sweep low→max, $ cost ✓"),
      "sc5hle":("HLE (Opus 5)","sweep","Opus 5 card p157 · HLE tools, 4 models × sweep low→max, $ cost ✓"),
      "sc5browse":("BrowseComp 10M","sweep","Opus 5 card p160 · 10M budget, sweep low→max; Fable=Mythos 5, $ cost ✓"),
      "sc5dsqa":("DeepSearchQA (O5)","sweep","Opus 5 card p161 · 980k budget, 4 models × sweep low→max, $ cost ✓"),
      "sc5draco":("DRACO (Opus 5)","sweep","Opus 5 card p162 · 980k budget, sweep low→max; Fable=Mythos 5, $ cost ✓"),
      "swerebench2":("swe-rebench 07/26","xmodel","ReAct minimal · Opus5/Fable5/Sonnet5 all at high ✓"),
      "cursorbench32":("CursorBench 3.2","sweep","Cursor 3.2 · matched effort, $ cost ✓ (vendor benchmark)"),
      "aabriefcase":("AA-Briefcase","sweep","AA agentic knowledge work · Opus 5 sweep low→max, Elo ✓"),
      "sc5osworld":("OSWorld 2.0","sweep","Opus 5 card p174 · price vs perf, 4 models; effort inferred from cost order ✓"),
      "sc5autobench":("AutomationB. 5","sweep","Opus 5 card p180 · Zapier, linear-$ chart; Fable=Mythos 5, effort inferred ✓"),
      "aa-index-pertask2":("AA /task v3","xmodel","AA-Index v3 · max ✓"),
      "valsvibecode":("Vals VibeCode","sweep","Vals AI · Opus 5 sweep low→max (scores), $ cost at leaderboard setting ✓"),
      "valsindex":("Vals Index","xmodel","Vals AI · 24-bench composite, 6 models all at max; overlaps EMB+VibeCode ✓"),
      "osworld2b":("OSWorld 2.0 batch","xmodel","arXiv 2606.29537 · 108 workflows, 500 steps, batched tool calls, max ✓"),
      "osworld2s":("OSWorld 2.0 single","xmodel","arXiv 2606.29537 · 108 workflows, 500 steps, single tool call, max ✓"),
      "scf51fcode":("FrontierCode-Ext","sweep","Cognition leaderboard JSON · v1.1 Extended (150 tasks), 3 models × low→max, measured USD/rollout ✓"),
      "scf51hlet":("HLE tools (F5.1)","sweep","Fable 5.1 card p177 · HLE with tools, 3 models × sweep low→max, $ cost, scores printed ✓"),
      "scf51hlen":("HLE no-tools (F5.1)","sweep","Fable 5.1 card p178 · HLE without tools, 3 models × sweep low→max, $ cost, scores printed ✓"),
      "scf51draco":("DRACO (F5.1)","sweep","Fable 5.1 card p179 · 980k budget, 3 models × sweep low→max, $ cost, scores printed ✓"),
      "scf51osw":("OSWorld 2.0 (F5.1)","sweep","Fable 5.1 card p190 · partial-credit price/perf, 3 models; effort inferred from cost order ✓"),
      "aa-index4":("AA Index v4","sweep","AA model pages · Fable 5.1 sweep low→max + Fable 5/Opus 5 at max, per-suite $ ✓"),
      "aa-index-pertask3":("AA /task v4","xmodel","AA launch article · per-task $, Fable 5.1 xhigh/max vs Fable 5/Opus 5 max ✓"),
      "valsindex2":("Vals Index 09/26","xmodel","Vals AI · current composite, 5 models all at max ✓"),
      "scfrontiercode":("FrontierCode v1","sweep","Sonnet 5 card p117 · 4 models × sweep low→max, $ cost, scores printed ✓"),
      "retort49":("retort exp-49","sweep","Claude Code · one task, 2 models × low→max, n=3; repo states its own quality saturation → cost only ✓"),
      "runebench":("RuneBench","xmodel","Harbor+Modal · 16 skills, 30-min budget, XP metric; mispriced Opus 5 cells omitted ✓"),
      "melvynx":("Melvynx bench","sweep","Claude Code · 7 valid tasks, Opus 5 high vs max, manual rubric ✓"),
      "aa-index43":("AA Index v4.3","sweep","AA · index v4.3 of 7 Sep (TB 4.0 + AutomationBench-AA), Fable 5.1 and Opus 5 × full ladder ✓"),
      "firecrawl":("Firecrawl 57-run","xmodel","claude -p in sandbox-exec · 3 models at matched high, measured usage; 7/7 all → cost only ✓"),
      "alebench":("ALE-Bench","xmodel","Epoch archive · 3 models at matched high, measured token splits ✓"),
      "weirdml":("WeirdML","sweep","Epoch archive · 3 models × high/max, cost per run ✓"),
      "livebench":("LiveBench","xmodel","3 models at max, measured tokens × rates; published weighting not reproducible → cost only ✓"),
      "willison51":("Willison SVG 5.1","sweep","llm CLI · one fixed SVG prompt, Fable 5.1 low→max, measured tokens; trivial task ✓"),
      "worldbuild":("WorldBuild Bench","xmodel","own harness · 3 game briefs, Fable 5 vs Opus 5 both at high, real API ledger ✓"),
      "stet25":("Stet 25-PR","xmodel","Claude Code · 25 replayed PRs, Opus 5 vs Opus 4.8 both at medium, relative cost ✓"),
      "fcodemain":("FrontierCode main","sweep","Cognition leaderboard JSON · v1.1 main (100 tasks), 3 models × low→max, measured USD/rollout ✓"),
      "zapierab":("Zapier AutomationB.","sweep","AutomationBench 1.0.6 · 657 held-out tasks, strict pass/fail, measured tokens × list ✓"),
      "aagdpval":("AA GDPval v2","sweep","AA evaluation page · 220 tasks, Elo; cost derived from AA's published token counts ✓"),
      "aaautob":("AA AutomationB.","xmodel","AA evaluation page · 657 tasks partial-credit, 3 models at max ✓"),
      "swerefactor":("SWE Refactor","sweep","arXiv 2608.23564 · 20 whole-repo migrations, Claude Code, measured API spend, 2 models × ladder ✓"),
      "quotebench":("QuoteBench","sweep","arXiv 2608.13547 · 56 frozen tasks, provider-reported output tokens, 3 models × ladder ✓"),
      "ai4ai":("AI4AI-Bench","sweep","arXiv 2608.20318 · 10 ML-research repos, measured exploration spend, 2 models × ladder ✓"),
      "obvbench":("ObviousBench 0.2","sweep","inspect-ai · 144 items ×3 epochs, 3 models × full ladder, measured tokens ✓"),
      "bughunt":("bug-hunt-bench","sweep","Claude Code 2.1.251 · 105 planted bugs, blind judge, 3 models × ladder ✓"),
      "vlmexam":("vlm-exam","sweep","roboflow · identical 133-image set, 3 models × low/high, measured tokens ✓"),
      "harnesseval":("harnesseval","sweep","Claude Code · 6 PRs common to every cell, CLI-metered cost ✓"),
      "vibeoscad":("vibe-openscad","sweep","output_config.effort explicit · 3 models × ladder; quality saturates → cost only ✓"),
      "nurbbench":("nurb-benchmarks","sweep","Claude Code · 6 CAD tasks, 2 models × full ladder; quality saturates → cost only ✓"),
      "kingy30":("Kingy 30-case","xmodel","Vercel AI Gateway pinned to Anthropic · 30 identical cases, measured ledger; quality saturated → cost only ✓"),
      "tb40":("Terminal-Bench 4.0","xmodel","tbench.ai primary payload · 66 tasks × 330 trials, Claude Code, all at max; cost basis undocumented ✓"),
      "chartogt":("Chartography +tools","sweep","Fable 5.1 card p186 · 5 models × sweep low→max, $ cost; Opus 4.8 series joined from Opus 5 card p171 ✓"),
      "chartogn":("Chartography −tools","sweep","Fable 5.1 card p186 · tools disabled — separate regime, kept out of the effort grid ✓"),
      "valsfab2":("Vals Finance Agent v2","xmodel","Vals AI · Finance Agent v2, Claude models at their stated compute_effort, measured cost/test ✓"),
      "valslegal":("Vals Legal Research","xmodel","Vals AI · Legal Research, Claude models at their stated compute_effort, measured cost/test ✓"),
      "valsmedscribe":("Vals MedScribe","xmodel","Vals AI · MedScribe, Claude models at their stated compute_effort, measured cost/test ✓"),
      "valstax":("Vals Tax Agent","xmodel","Vals AI · Tax Agent, Claude models at their stated compute_effort, measured cost/test ✓"),
      "valsbenefits":("Vals Public Benefits v1.1","xmodel","Vals AI · Public Benefits v1.1, Claude models at their stated compute_effort, measured cost/test ✓"),
      "valsvcb100":("Vals Vibe Code Bench 1-100","xmodel","Vals AI · Vibe Code Bench 1-100, Claude models at their stated compute_effort, measured cost/test ✓"),
      "valsioi":("Vals IOI","xmodel","Vals AI · IOI, Claude models at their stated compute_effort, measured cost/test ✓"),
      "valsmystery":("Vals MysteryMechanism","xmodel","Vals AI · MysteryMechanism, Claude models at their stated compute_effort, measured cost/test ✓"),
      "valsrsi":("Vals RSI Index","xmodel","Vals AI · RSI Index (autonomous LLM R&D, 5 campaigns), Claude models at max, measured cost per suite — board updated 21 Sep (early access for Opus 5.5) ✓"),
      "senkoflysim":("Senko Flysim","xmodel","Senko Rašić · one-shot flight-sim game in Claude Code, xhigh, CLI-reported cost (rounded $, quality not scored) ✓"),
      "senkovoxel":("Senko Voxel","xmodel","Senko Rašić · one-shot Minecraft-like game in Claude Code, xhigh, CLI-reported cost (rounded $, quality not scored) ✓"),
      "senkorts":("Senko RTS","xmodel","Senko Rašić · one-shot RTS game in Claude Code, xhigh, CLI-reported cost (rounded $, quality not scored) ✓"),
      "playcodesvg":("Playcode MacBook SVG","sweep","Playcode · one-shot MacBook SVG, high/xhigh/max per model, provider-billed cost (quality ordinal, not scored) ✓"),
      "valstb4":("Vals TB 4.0","xmodel","Vals AI · Terminal-Bench 4.0, all Claude at max, measured cost/test ✓"),
      "valsmedcode":("Vals MedCode","xmodel","Vals AI · ICD-10-CM coding, 2,755 records, all at max ✓"),
      "valssage":("Vals SAGE","xmodel","Vals AI · grading student math work against a rubric, all at max ✓"),
      "valsbiomyst":("Vals BioMystery","xmodel","Vals AI · BioMysteryBench (Terminus), Opus 5.5 vs Opus 5 at max ✓"),
      "valstbsci":("Vals TB-Science","xmodel","Vals AI · Terminal-Bench-Science, all at max ✓"),
      "valssre":("Vals SRE-Bench","xmodel","Vals AI · binary reverse engineering (despite the name), all at max ✓"),
      "qiita-takuya-reason":("Qiita reasoning","sweep","Qiita (Takuya) · 19 reasoning questions × 3 runs, Claude Code without tools, measured tokens × list price ✓"),
      "sonarjava":("Sonar Java","sweep","Sonar leaderboard JSON · 4,444 Java tasks, single-shot, measured tokens × list price; Opus 5.5 medium/high ✓"),
      "sc55hlet":("HLE tools (O5.5)","sweep","Opus 5.5 card p185 · HLE with tools, 3 models × sweep low→max, $ cost, scores printed ✓"),
      "sc55amnt":("ArXivMath no-tools","sweep","Opus 5.5 card p182 · ArXivMath Aug 2026, 57 problems, 3 models × low→max, $ cost, scores printed ✓"),
      "sc55amt":("ArXivMath tools","sweep","Opus 5.5 card p183 · ArXivMath Aug 2026 with code sandbox, 3 models × low→max, scores printed ✓"),
      "sc55draco":("DRACO (O5.5)","sweep","Opus 5.5 card p187 · 980k budget, 3 models × low→max, $ cost, scores printed; a new run, not the F5.1-card one ✓"),
      "sc55wandr":("WANDR","sweep","Opus 5.5 card p188 · Perplexity wide-search, offline index, 980k budget, 3 models × low→max, scores printed ✓"),
      "sc55osw":("OSWorld 2.0 (O5.5)","sweep","Opus 5.5 card p207 · partial credit, 3 models × 5 efforts; effort inferred from cost order ✓"),
      "sc55bcad":("BenchCAD V2C","sweep","Opus 5.5 card p205 · Vision2Code with tools, voxel IoU, 4 models × 5 efforts; effort inferred from cost order ✓"),
      "sc55chartq":("Chartography regraded","sweep","Opus 5.5 card p202 · same transcripts as chartogt, re-graded scores — quality only, costs stay in chartogt ✓"),
      "scoosw47":("OSWorld eff. (4.7)","sweep","Opus 4.7 card p209 · pass@1 vs output tokens, 3 models × low→max ✓"),
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
        cands = ["arxiv.org/abs/" + c[len("arxiv-"):] if c.startswith("arxiv-") else c for c in cands]   # source id, not a domain
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
    CUR = set(MX)                                            # 9 current models
    EFFOK = {"low","medium","high","xhigh","max","solo"}     # 'solo' = haiku 4.5 (no discrete effort)
    ANCHOR = GRID_ANCHOR
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT,"raw-data.csv")))
            if r["group"] and not r["group"].startswith("#")]
    bench = collections.defaultdict(dict)                    # benchmark → couple → log(value)
    srcs  = collections.defaultdict(lambda: collections.defaultdict(set))
    eap   = collections.defaultdict(lambda: collections.defaultdict(set))   # sources whose run was early access
    PUBLISHER = {"anthropic-chart": "anthropic-syscard"}    # one publisher = one source (Anthropic's own evals)
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

def monotonicity_report(cg, qg):
    """Effort is a ladder: within a model, a higher rung should not cost less than a lower one.
    A violation is almost never a real measurement — it means the couples above and below are
    consolidated over DIFFERENT benchmark sets, so their medians are not comparable. Printed at
    build time so it cannot pass unnoticed (a real, documented exception exists on the quality
    side: Sonnet 4.6 falls after `high`, which the Sonnet 5 card itself prints)."""
    ORD = ["low", "medium", "high", "xhigh", "max"]
    out = []
    for grid, name in ((cg, "cost"), (qg, "quality")):
        for m, es in grid.items():
            seq = [(e, es[e][0]) for e in ORD if e in es]
            for (a, va), (b, vb) in zip(seq, seq[1:]):
                if vb < va: out.append(f"{name}: {m} {a}({va}) > {b}({vb})")
    return out

def content_date():
    """Date of the last committed change to the data or the generator; today while they have uncommitted changes.
    Feeds the visible "Updated" date, JSON-LD dateModified and the sitemap lastmod, so none moves on a no-op rebuild."""
    paths = ["raw-data.csv", "gen"]
    git = lambda *a: subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True, check=True).stdout.strip()
    try:
        if not git("status", "--porcelain", "--", *paths):
            return datetime.date.fromisoformat(git("log", "-1", "--format=%cs", "--", *paths))
    except (OSError, subprocess.CalledProcessError, ValueError):
        pass
    return datetime.date.today()

def head_tags(date, anchor_label, counts):
    """Title, description, canonical, icon, Open Graph, Twitter card and the JSON-LD Dataset. Every value is on the page."""
    a = lambda v: htmlmod.escape(v, quote=True)
    dataset = {
        "@context": "https://schema.org", "@type": "Dataset",
        "name": TITLE,
        "description": ("What each recent Claude model actually costs, at every effort level — reconstructed from public "
                        "measurements and reduced to a relative cost by chaining same-task comparisons. Aggregated from "
                        f"{counts}; costs and qualities are relative to {anchor_label} = 1.00."),
        "url": SITE_URL, "sameAs": REPO_URL,
        "creator": {"@type": "Person", "name": "Alexandre Gensse", "url": "https://github.com/alexandregensse-blip"},
        "dateModified": date.isoformat(),
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "isAccessibleForFree": True,
        "keywords": ["Claude", "Claude models", "LLM cost", "effort level", "Fable", "Opus", "Sonnet", "Haiku",
                     "benchmark", "Pareto frontier"],
        "variableMeasured": [f"Relative cost per task ({anchor_label} = 1.00)", f"Relative quality ({anchor_label} = 1.00)"],
        "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": SITE_URL + "raw-data.csv"}],
    }
    ld = json.dumps(dataset, ensure_ascii=False, indent=1).replace("</", "<\\/")
    return (
        f"<title>{a(TITLE)}</title>\n"
        f'<meta name="description" content="{a(DESCRIPTION)}">\n'
        f'<link rel="canonical" href="{SITE_URL}">\n'
        '<link rel="icon" href="favicon.svg" type="image/svg+xml">\n'
        '<meta property="og:type" content="website">\n'
        f'<meta property="og:url" content="{SITE_URL}">\n'
        f'<meta property="og:title" content="{a(TITLE)}">\n'
        f'<meta property="og:description" content="{a(DESCRIPTION)}">\n'
        f'<meta property="og:image" content="{SITE_URL}og-image.png">\n'
        '<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n'
        '<meta property="og:image:alt" content="Claude cost vs quality: Fable, Opus, Sonnet, Haiku compared — claude-models.agensse.com">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        f'<script type="application/ld+json">\n{ld}\n</script>\n'
    )

def write_root_files(date, pre, anchor_label):
    """robots.txt, sitemap.xml, llms.txt and the IndexNow key file, next to index.html. llms.txt reuses the
    pre-rendered answer, so it states the same conclusions as the page."""
    plain = lambda h: re.sub(r"\s+(?=:)", "", re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", "", h)))).strip()
    files = {
        "robots.txt": f"# All robots allowed, AI robots included.\nUser-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n",
        "sitemap.xml": ('<?xml version="1.0" encoding="UTF-8"?>\n'
                        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                        f"  <url><loc>{SITE_URL}</loc><lastmod>{date.isoformat()}</lastmod></url>\n</urlset>\n"),
        "llms.txt": f"""# {TITLE}

> {DESCRIPTION}

{plain(pre.get("answer", ""))}

Costs and qualities are relative to {anchor_label} = 1.00. They are computed only from ratios measured on the same task, normalised per benchmark and combined by weighted median, from {plain(pre.get(".nsrc", ""))}. Updated {date.isoformat()}. Figures are indicative, derived from public third-party measurements; not affiliated with Anthropic.

## Report

- [{TITLE}]({SITE_URL}): quality vs cost per model and effort level, Pareto frontier, best pick per task tier, normalized cost matrix, method and sources.

## Data

- [raw-data.csv]({SITE_URL}raw-data.csv): every measured row (source, model, effort, task, harness, cost, tokens, score, reference), CC BY 4.0.

## Optional

- [Source repository]({REPO_URL}): generator, method notes, version history.
""",
        f"{INDEXNOW_KEY}.txt": INDEXNOW_KEY,
    }
    for name, text in files.items():
        with open(os.path.join(ROOT, name), "w", encoding="utf-8") as f:
            f.write(text)

def prerender(app, css):
    """Runs app.js at build time (gen/prerender.js, Node, fake DOM) and returns the HTML it writes into the text
    blocks, so crawlers that do not run JavaScript read the conclusions. The browser redraws them on load."""
    try:
        r = subprocess.run(["node", os.path.join(HERE, "prerender.js")], input=json.dumps({"app": app, "css": css}),
                           capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        sys.exit(f"!! PRE-RENDER FAILED (Node is required to build): {getattr(e, 'stderr', '') or e}")
    return json.loads(r.stdout)

def inject(body, pre):
    """Writes the pre-rendered blocks into their empty placeholders in body.html."""
    for key, html in pre.items():
        put = lambda m: m.group(1) + html + m.group(m.lastindex)
        if key == ".nsrc":
            pat = r'(<span class="nsrc">)…(</span>)'
        elif key.endswith(" tbody"):
            pat = rf'(<table id="{key[1:-6]}">.*?<tbody>)(</tbody>)'
        else:
            pat = rf'(<(\w+)[^>]*\bid="{key}"[^>]*>)…?(</\2>)'
        body, n = re.subn(pat, put, body, flags=re.S)
        if not n:
            sys.exit(f"!! PRE-RENDER: no empty placeholder for {key!r} in body.html")
    return body

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
    am, ae = GRID_ANCHOR.split("@")
    alabel = {"opus-5.5":"Opus 5.5","opus-5":"Opus 5","opus-4.8":"Opus 4.8","fable-5.1":"Fable 5.1","fable-5":"Fable 5","sonnet-5":"Sonnet 5"}[am]
    app  = app.replace("__ANCHOR_JS__", json.dumps({"m": am, "e": ae, "label": f"{alabel} @{ae}"}))
    body = body.replace("__ANCHOR_HDR__", f"{alabel.replace(' ','&nbsp;')} · {ae}")
    body = body.replace("__ANCHOR__", f"{alabel.replace(' ','&nbsp;')}&nbsp;@{ae}")
    app  = app.replace("__GROUPS_DATA__", json.dumps(GD, separators=(",",":")))
    body = body.replace("__NOTHINK_ROWS__", regime_rows_html(NT, DF))
    body = body.replace("__NSAMETASK__", str(len(RD["cost"])))   # same-task cost-ratio measurement points (dynamic)
    ncpl = sum(len(v) for v in CG.values())                      # (model, effort) couples carried by the grids
    span = max(c[0] for v in CG.values() for c in v.values()) / min(c[0] for v in CG.values() for c in v.values())
    body = body.replace("__NCOUPLES__", str(ncpl))
    body = body.replace("__COSTSPAN__", str(round(span)))
    date = content_date()
    body = body.replace("__GENDATE__", date.strftime("%d %b %Y"))   # last change to the data or the generator
    pre  = prerender(app, css)
    body = inject(body, pre)
    html = (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        + head_tags(date, f"{alabel} @{ae}", pre.get(".nsrc", "")) +
        f"<style>\n{css}\n</style>\n"
        f"</head>\n<body>\n{body}\n<script>\n{app}\n</script>\n</body>\n</html>\n"
    )
    open(OUT,"w",encoding="utf-8").write(html)
    write_root_files(date, pre, f"{alabel} @{ae}")
    print(f"built {OUT}  ({len(html)} bytes)  cost-pts={len(RD['cost'])} tok-pts={len(RD['tok'])}")
    viol = monotonicity_report(CG, QG)
    known = {("quality", "sonnet-4.6", "high", "max")}         # printed by the Sonnet 5 card itself — keyed on the rungs, not
    import re                                                   # the values, which move with the anchor and the data
    def key(v):
        m = re.match(r"(\w+): (\S+) (\w+)\([\d.]+\) > (\w+)\(", v); return m.groups() if m else None
    for v in viol:
        print(("  effort-ladder OK (documented): " if key(v) in known else "  !! EFFORT LADDER INVERTED: ") + v)
    print(f"  no-think pairs={list(NT['pairs'])}  index={NT['index']}")
    print(f"  default  pairs={list(DF['pairs'])}  index={DF['index']}")

if __name__ == "__main__":
    main()
