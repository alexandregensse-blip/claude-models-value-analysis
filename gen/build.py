#!/usr/bin/env python3
"""Site generator. Reads raw-data.csv, fuses it into relative cost and quality grids (gen/lqm.py), bundles the
CSS, HTML body and client script, and writes index.html and the root files. Run: python3 gen/build.py"""
import csv, hashlib, html as htmlmod, json, math, os, re, subprocess, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT  = os.path.join(ROOT, "index.html")

# Publication: every absolute URL derives from SITE_URL (canonical root, trailing slash).
SITE_URL    = "https://claude-models.agensse.com/"
REPO_URL    = "https://github.com/alexandregensse-blip/claude-models-value-analysis"
TITLE       = "Claude cost vs quality: Fable, Opus, Sonnet, Haiku compared"
SITE_NAME   = "Claude cost vs quality"   # site name suggested to Google (JSON-LD WebSite) instead of the bare domain
DESCRIPTION = ("What each Claude model (Fable, Opus, Sonnet, Haiku) costs at every effort level, and which gives "
               "the best quality for the price. Open data, CC BY 4.0.")
SITE_HOST   = SITE_URL.split("://", 1)[1].rstrip("/")   # shown in the share image and its alt text
# Both belong to this site: a fork sets them to "" (no tag, no key file) or to its own values.
BING_SITE_VERIFICATION = "F362761CB53AA11BE0A561143021D184"   # Bing Webmaster Tools ownership (msvalidate.01); keep it
INDEXNOW_KEY = "b3573dbc1da690e66e9ef05b081b7abe"   # public by design: served as /<key>.txt, proves ownership to IndexNow (Bing…)

MX = {"fable-5.1":0,"fable-5":1,"opus-5.5":2,"opus-5":3,"opus-4.8":4,"opus-4.7":5,"sonnet-5.5":6,"sonnet-5":7,"sonnet-4.6":8,"haiku-4.5":9}
GRID_ANCHOR = "opus-5@high"                 # reference couple: shown as 1.0 on both axes (a display choice)


# ---------------------------------------------------------------- fusion (gen/lqm.py; method in METHODOLOGY.md)
# The fit runs apart from the build, in the Stan environment: .stan/venv/bin/python gen/fit.py writes fit-cache.json
# (per couple, reference-free: log centre, quasi-standard error, publishers). The build divides by GRID_ANCHOR.
FIT = dict(chains=4, warmup=1000, samples=1000, seed=11, adapt_delta=0.95)
FIT_CACHE = os.path.join(HERE, "fit-cache.json")
EFFORT_ORDER = ["low", "medium", "high", "xhigh", "max", "solo"]

def fit_fingerprint():
    h = hashlib.sha256()
    for path in (os.path.join(ROOT, "raw-data.csv"), os.path.join(HERE, "lqm.py"), os.path.join(HERE, "lqm.stan"),
                 os.path.join(HERE, "catalog.py")):
        h.update(open(path, "rb").read())
    h.update(json.dumps([list(MX), FIT], sort_keys=True).encode())
    return h.hexdigest()

def fused_grids():
    """Relative cost and quality grids {model: {effort: [value, low, high]}}, published couples only, relative to
    GRID_ANCHOR: value = exp(centre − centre_anchor), low/high = value·exp(∓ quasi-standard error of the couple).
    Refuses to build from a fit that no longer matches the data or the model, or that did not converge."""
    try:
        cache = json.load(open(FIT_CACHE))
    except (OSError, ValueError):
        cache = {}
    if cache.get("fingerprint") != fit_fingerprint():
        sys.exit("!! gen/fit-cache.json does not match the data, the model or its settings: "
                 "run .stan/venv/bin/python gen/fit.py")
    for axis in ("cost", "quality"):
        if not cache["diagnostics"][axis]["converged"]:
            sys.exit(f"!! the {axis} fit did not converge: {cache['diagnostics'][axis]}")
    grids = {}
    for axis in ("cost", "quality"):
        S = cache[axis]
        ref = S[GRID_ANCHOR][0]
        grid = {}
        for m in MX:
            row = {}
            for e in EFFORT_ORDER:
                v = S.get(f"{m}@{e}")
                if v and v[2] >= 2:                                 # published: measured by two publishers or more
                    c, h = v[0] - ref, v[1]
                    row[e] = [round(math.exp(c), 3), round(math.exp(c - h), 3), round(math.exp(c + h), 3)]
            if row: grid[m] = row
        grids[axis] = grid
    return grids["cost"], grids["quality"], cache["diagnostics"]

def model_label(m):
    """'opus-5.5' → 'Opus 5.5'."""
    name, _, version = m.partition("-")
    return f"{name.capitalize()} {version}".strip()

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
      "zenn-qcd":("zenn QCD #27","sweep","Claude Code 2.1.197 · 3 DB tasks × 10 runs, Opus 4.8 & Sonnet 5 × low→xhigh, CLI-reconciled cost ✓"),
      "whitekumalabo":("whitekumalabo","sweep","Claude Code · low/max ✓"),
      "qiita-nogataka":("qiita","sweep","raw API · low/max ✓"),
      "codesota":("CodeSOTA","xmodel","list-price blended (not a run) ✓"),
      "coderev":("code-review","xmodel","VibeOps · temp 0.1, thinking NS ✓"),
      "wildclaw":("WildClaw","xgen","OpenRouter (4 harness) · thinking NS ✓"),
      "truefoundry":("TrueFoundry","xmodel","AI Gateway · single-turn no tools, effort NS ✓"),
      "emb":("EMB","xmodel","Vals AI · bash+execute, 10 Claude models at max (payload compute_effort) — snapshot 27 Sep, re-priced ✓"),
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
      "sc5hle":("HLE (Opus 5)","sweep","Opus 5 card p157 · HLE tools, 4 models × sweep low→max, $ cost ✓"),
      "sc5browse":("BrowseComp 10M","sweep","Opus 5 card p160 · 10M budget, sweep low→max; Fable=Mythos 5, $ cost ✓"),
      "sc5dsqa":("DeepSearchQA (O5)","sweep","Opus 5 card p161 · 980k budget, 4 models × sweep low→max, $ cost ✓"),
      "sc5draco":("DRACO (Opus 5)","sweep","Opus 5 card p162 · 980k budget, sweep low→max; Fable=Mythos 5, $ cost ✓"),
      "swerebench2":("swe-rebench 07/26","xmodel","ReAct minimal · Opus5/Fable5/Sonnet5 all at high ✓"),
      "cursorbench32":("CursorBench 3.2","sweep","Cursor 3.2 · matched effort, $ cost ✓ (vendor benchmark)"),
      "aabriefcase":("AA-Briefcase","sweep","AA model payload 27 Sep · agentic knowledge work, Elo; 4 models × full ladder + 3 at max; costPerTask per eval ✓"),
      "sc5osworld":("OSWorld 2.0","sweep","Opus 5 card p174 · price vs perf, 4 models; effort inferred from cost order ✓"),
      "sc5autobench":("AutomationB. 5","sweep","Opus 5 card p180 · Zapier, linear-$ chart; Fable=Mythos 5, effort inferred ✓"),
      "aa-index-pertask2":("AA /task v3","xmodel","AA-Index v3 · max ✓"),
      "valsvibecode":("Vals VibeCode","sweep","Vals AI · Opus 5 sweep low→max (scores), $ cost at leaderboard setting; board entries — snapshot 27 Sep, re-priced ✓"),
      "valsindex":("Vals Index","xmodel","Vals AI · 24-bench composite v1.2 (archived), 7 entries, Opus 4.7 high; overlaps EMB+VibeCode — snapshot 27 Sep, re-priced (archive re-read 29 Sep) ✓"),
      "osworld2b":("OSWorld 2.0 batch","xmodel","arXiv 2606.29537 · 108 workflows, 500 steps, batched tool calls, max ✓"),
      "osworld2s":("OSWorld 2.0 single","xmodel","arXiv 2606.29537 · 108 workflows, 500 steps, single tool call, max ✓"),
      "scf51fcode":("FrontierCode-Ext","sweep","Cognition leaderboard JSON · v1.1 Extended (150 tasks), Claude models × low→max incl. Sonnet 5.5, measured USD/rollout ✓"),
      "scf51hlet":("HLE tools (F5.1)","sweep","Fable 5.1 card p177 · HLE with tools, 3 models × sweep low→max, $ cost, scores printed ✓"),
      "scf51hlen":("HLE no-tools (F5.1)","sweep","Fable 5.1 card p178 · HLE without tools, 3 models × sweep low→max, $ cost, scores printed ✓"),
      "scf51draco":("DRACO (F5.1)","sweep","Fable 5.1 card p179 · 980k budget, 3 models × sweep low→max, $ cost, scores printed ✓"),
      "scf51osw":("OSWorld 2.0 (F5.1)","sweep","Fable 5.1 card p190 · partial-credit price/perf, 3 models; effort inferred from cost order ✓"),
      "aa-index4":("AA Index v4","sweep","AA model pages · Fable 5.1 sweep low→max + Fable 5/Opus 5 at max, per-suite $ ✓"),
      "aa-index-pertask3":("AA /task v4","xmodel","AA launch article · per-task $, Fable 5.1 xhigh/max vs Fable 5/Opus 5 max ✓"),
      "valsindex2":("Vals Index 09/26","xmodel","Vals AI · current composite v2, 10 Claude entries (Sonnet 5.5 incl.), max (Opus 4.7 high) — snapshot 27 Sep, re-priced ✓"),
      "scfrontiercode":("FrontierCode v1","sweep","Sonnet 5 card p117 · 4 models × sweep low→max, $ cost, scores printed ✓"),
      "retort74":("retort exp-74 py","sweep","Claude Code · rest-api-crud in Python, Opus 5.5 × low→max, n=3; requirement coverage 1.0 everywhere → cost only ✓"),
      "retort74go":("retort exp-74 go","sweep","Claude Code · rest-api-crud in Go, Opus 5.5 × low→max, n=3; requirement coverage 1.0 everywhere → cost only ✓"),
      "vulcanbench-ciiv4":("VulcanBench CII v4","sweep","Claude Code 2.1.280 · 23 legacy binary-parity tasks, Opus 5.5 × low→max, CLI-reported cost; refusal fallback on (0→48 % of replies by Opus 4.8) ✓"),
      "ccc12task":("Claude Code Camp 12-task","xmodel","beehiiv newsletter · Claude Code, default effort, 12 tasks×3 reps, cost+tokens only ✓"),
      "simbcdb":("Simbian Cyber Defense Benchmark","xmodel","median-cost-per-investigation ✓"),
      "finsheet":("FinSheet-Bench","xmodel","thinking-toggle-not-dial ✓"),
      "semlayerraw":("Semantic Layers for Data Analytics (schema-only)","xmodel","paired-protocol ✓"),
      "semlayerdoc":("Semantic Layers for Data Analytics (+semantic doc)","xmodel","paired-protocol ✓"),
      "tb2hf-0error":("TB2.1 HF · 0error","xgen","harborframework HF dataset · 0error-Ledger scaffold, opus-4.7 default, n≈230-241/446 ✓"),
      "tb2hf-wozcode":("TB2.1 HF · WOZCODE","xgen","harborframework HF dataset · WOZCODE scaffold, opus-4.7 default, n≈443-445/446 ✓"),
      "tb2hf-vix":("TB2.1 HF · vix","xgen","harborframework HF dataset · vix scaffold, opus-4.7 default, n≈388-440/446, tokens_out only ✓"),
      "tb2hf-simplai":("TB2.1 HF · Simplai","xgen","harborframework HF dataset · Simplai-Agent scaffold, sonnet-4.6 default, n≈360-428/446 ✓"),
      "tb2hf-polaris":("TB2.1 HF · Polaris","xgen","harborframework HF dataset · Polaris scaffold, opus-4.7 default (multi-model agent, sampled trials 100% opus-4.7), real $ cost, n≈268-444/446 ✓"),
      "wkl-l1":("WhiteKUMALabo effort×L1","sweep","Claude Code 2.1.76 · bug-fix tasks, Opus 4.6 low/medium/high/max ✓"),
      "wkl-l2":("WhiteKUMALabo effort×L2","sweep","Claude Code 2.1.76 · refactor tasks, Opus 4.6 low/medium/high/max ✓"),
      "wkl-l4":("WhiteKUMALabo effort×L4","sweep","Claude Code 2.1.76 · system-design tasks, Opus 4.6 low/medium/high/max ✓"),
      "wkl-f5o48-t1":("WhiteKUMALabo F5/O4.8 T1","xmodel","Claude Code 2.1.170 · bugfix, effort high, n=3 median, saturated pass ✓"),
      "wkl-f5o48-t2":("WhiteKUMALabo F5/O4.8 T2","xmodel","Claude Code 2.1.170 · intro-text, blind 15pt judge ✓"),
      "wkl-f5o48-t3":("WhiteKUMALabo F5/O4.8 T3","xmodel","Claude Code 2.1.170 · task decomposition, blind 15pt judge ✓"),
      "wkl-f5o48-t4":("WhiteKUMALabo F5/O4.8 T4","xmodel","Claude Code 2.1.170 · 1-sentence summary, cost/speed only ✓"),
      "qiita-suwanobu-a1":("Qiita suwa_nobu cache-write","xmodel","Opus 5 vs Opus 5.5 · same task, cold-cache round, CLI-metered cost ✓"),
      "qiita-suwanobu-a2":("Qiita suwa_nobu cache-read","xmodel","Opus 5 vs Opus 5.5 · same task, warm-cache rounds 2-3, CLI-metered cost ✓"),
      "nttdata-compaction":("Zenn nttdata_tech compaction","sweep","bedrock-runtime · Opus 5.5 auto-compaction summary tokens by effort, n=1, low/default/max(8192) ✓; max@2048 dropped, censored ✓"),
      "featherbench":("FeatherBench","xgen","OpenRouter(Anthropic) · 28-task multi-domain suite (coding/data/realworld/security/tool-use), effort=high (Haiku=solo), mean cost/tokens per task-run, consolidated results/summary.json; only Opus 5.5 rung saturated ✓"),
      "jeveffort":("jev-effort","sweep","Claude Code 2.1.280 · Opus 5.5 baseline arm, high vs max fixed effort, 6 coding tasks x2 runs ✓"),
      "lmarenaagent":("LMArena Agent","xmodel","Agent Mode real sessions (Code/Chat/Work) · cost=median $/task (14d window), score=Net Improvement composite signal, effort read from model-variant label; live board, read 27 Sep 2026 ✓"),
      "mcpmark":("MCPMark","sweep","eval-sys/mcpmark legacy board · 5 MCP servers (FS/GitHub/Notion/Playwright/Postgres), Sonnet 4 low/default/high + Opus 4.1/Sonnet 4.5/Opus 4.5, Cost-per-run; low>high cost inversion kept as measured ✓"),
      "swebenchverified":("SWE-bench Verified","xgen","swebench.com official board · mini-SWE-agent (v0.0.0->v2.0.0) submissions, instance_cost=mean $/instance, resolved%; 3 rows unverified-pending on site ✓"),
      "vexbench":("VEX-Bench","xmodel","Claude Code 2.1.150 · high, Opus 4.6 vs Sonnet 4.6, cost+tokens per case ✓"),
      "effihallu":("EffiBench IIV","xmodel","direct API · n=5/model, IIV-penalty abstention on optimal code ✓"),
      "ifgap-bbq":("BBQ effort (interface-gap)","sweep","direct API · budget_tokens low/med/high, Sonnet4.6 & Haiku4.5 ✓"),
      "ifgap-hella":("HellaSwag effort (interface-gap)","sweep","direct API · budget_tokens low/med/high, Sonnet4.6 & Haiku4.5 ✓"),
      "cliffcompact-tb2":("CliffCompaction TB2.0","xgen","Terminus-2 · k=1 proprietary baselines, Opus 4.6 & 4.7 ✓"),
      "cliffcompact-swebv":("CliffCompaction SWE-bV","xgen","mini-swe-agent · k=1 baselines, Opus 4.5(high)/4.6, Sonnet 3.7 ✓"),
      "aipricingguru":("AI Pricing Guru Labs","xmodel","OpenRouter cost-per-task-v2 · 49-task suite, 6 Claude models, effort unstated ✓"),
      "marginlabswe":("Marginlab SWE-Bench-Pro","xgen","Claude Code CLI · daily rolling tracker, 6 Opus generations by release window, score-only ✓"),
      "boxconsumer":("Box · consumer products","xgen","Box AI blog · Opus 5 vs 5.5, one representative task, score-only ✓"),
      "boxfinserv":("Box · financial services","xgen","Box AI blog · Opus 5 vs 5.5, one representative task, score-only ✓"),
      "boxtech":("Box · technology","xgen","Box AI blog · Opus 5 vs 5.5, one representative task, score-only ✓"),
      "valswsfinance":("Vals Web Search (finance)","sweep","vals.ai payload · Fable 5, Native vs Exa search backend, compute_effort=max ✓"),
      "valswslegal":("Vals Web Search (legal)","sweep","vals.ai payload · Fable 5, Native vs Exa search backend, compute_effort=max ✓"),
      "mobilecybench":("MobileCybench token/cost accounting","xgen","Claude Code 100-run aggregate · Opus4.8/Opus5 default, tokens+cost ✓"),
      "mrsgen":("MRS-to-text (Hajdik split)","xmodel","3-exemplar prompt · Sonnet4.5/Opus5 default, BLEU, score-only ✓"),
      "mrsparse":("text-to-MRS (Hajdik split)","xmodel","3-exemplar prompt · Sonnet4.5/Opus5 default, EDM-F1, score-only ✓"),
      "strokeeval":("Japanese Stroke LLM Eval","xmodel","multi-turn Japanese conversation · Fable5/Opus4.7 default, score-only ✓"),
      "rsigeneval2":("Designer-RSI · GenEval2","xmodel","no-skill baseline · Sonnet4/Opus4.6 low, success% ✓"),
      "rsidpgbench":("Designer-RSI · DPG-Bench","xmodel","no-skill baseline · Sonnet4/Opus4.6 low, success% ✓"),
      "rsioneigen":("Designer-RSI · OneIG-EN","xmodel","no-skill baseline · Sonnet4/Opus4.6 low, success% ✓"),
      "rsioneigzh":("Designer-RSI · OneIG-ZH","xmodel","no-skill baseline · Sonnet4/Opus4.6 low, success% ✓"),
      "rsiopencole":("Designer-RSI · OpenCOLE","xmodel","no-skill baseline · Sonnet4/Opus4.6 low, completion% ✓"),
      "rsigraphicbench":("Designer-RSI · GraphicBench","xmodel","no-skill baseline · Sonnet4/Opus4.6 low, completion% ✓"),
      "rsicreatidesign":("Designer-RSI · CreatiDesign","xmodel","no-skill baseline · Sonnet4/Opus4.6 low, completion% ✓"),
      "rsibanner400":("Designer-RSI · BannerRequest400","xmodel","no-skill baseline · Sonnet4/Opus4.6 low, completion% ✓"),
      "broodwar":("Brood War Bench","xmodel","Claude Code CLI · round-robin StarCraft:Brood War tournament, 171 games, default effort only ✓"),
      "retort4675brc":("retort exp-46/75 brazil C","xgen","Claude Code · brazil-soccer-mcp in C, Opus 5 default vs Opus 5.5 low, n=1 ✓"),
      "retort4675brclj":("retort exp-46/75 brazil Clojure","xgen","Claude Code · brazil-soccer-mcp in Clojure, Opus 5 default vs Opus 5.5 low, n=1 ✓"),
      "retort4675brcpp":("retort exp-46/75 brazil C++","xgen","Claude Code · brazil-soccer-mcp in C++, Opus 5 default vs Opus 5.5 low, n=1 ✓"),
      "retort4675brcs":("retort exp-46/75 brazil C#","xgen","Claude Code · brazil-soccer-mcp in C#, Opus 5 default vs Opus 5.5 low, n=1 ✓"),
      "retort4675brerl":("retort exp-46/75 brazil Erlang","xgen","Claude Code · brazil-soccer-mcp in Erlang, Opus 5 default vs Opus 5.5 low, n=1 ✓"),
      "retort4675brjava":("retort exp-46/75 brazil Java","xgen","Claude Code · brazil-soccer-mcp in Java, Opus 5 default vs Opus 5.5 low, n=1 ✓"),
      "retort4675brobjc":("retort exp-46/75 brazil Obj-C","xgen","Claude Code · brazil-soccer-mcp in Objective-C, Opus 5 default vs Opus 5.5 low, n=1 ✓"),
      "retort4675brrust":("retort exp-46/75 brazil Rust","xgen","Claude Code · brazil-soccer-mcp in Rust, Opus 5 default vs Opus 5.5 low, n=1 ✓"),
      "retort4675brswift":("retort exp-46/75 brazil Swift","xgen","Claude Code · brazil-soccer-mcp in Swift, Opus 5 default vs Opus 5.5 low, n=1 ✓"),
      "retort4675brelixir":("retort exp-46/75 brazil Elixir","xgen","Claude Code · brazil-soccer-mcp in Elixir, Opus 5 default vs Opus 5.5 low, n=1 ✓"),
      "retort4675brts":("retort exp-46/75 brazil TypeScript","xgen","Claude Code · brazil-soccer-mcp in TypeScript, Opus 5 default (cost untraced) vs Opus 5.5 low, both saturated ✓"),
      "retort4675rtclj":("retort exp-46/75 bookshop Clojure","xgen","Claude Code · bookshop/rest-api-crud in Clojure, Opus 5 default (n=1) vs Opus 5.5 low (n=3) ✓"),
      "retort4675rtrust":("retort exp-46/75 bookshop Rust","xgen","Claude Code · bookshop/rest-api-crud in Rust, Opus 5 default (n=1) vs Opus 5.5 low (n=3) ✓"),
      "retort4675rtelixir":("retort exp-46/75 bookshop Elixir","xgen","Claude Code · bookshop/rest-api-crud in Elixir, Opus 5 default (cost untraced) vs Opus 5.5 low, both saturated ✓"),
      "valscodemig":("Vals Code Migration","xmodel","Vals AI · Code Migration, 10 Claude entries, compute_effort max (Haiku thinking null) — snapshot 27 Sep, re-priced ✓"),
      "valshlab":("Vals HLAB","xmodel","Vals AI · Harvey's Legal Agent Benchmark, all at max, several at floor — snapshot 27 Sep, re-priced ✓"),
      "valsprogram":("Vals ProgramBench","xmodel","Vals AI · ProgramBench, max, mostly floor scores, 3 entries without cost — snapshot 27 Sep, re-priced ✓"),
      "valsproof":("Vals ProofBench","xmodel","Vals AI · ProofBench v1.1, all at max (Opus 5 now max in payload), 4 saturated — snapshot 28 Sep, re-priced ✓"),
      "valsthi":("Vals Time Horizon KSP","xmodel","Vals AI · Time Horizon Index: KSP, 3 Claude at max, board 2026-09-14 ✓"),
      "valscua":("Vals CUA-bench","xmodel","Vals AI · CUA-bench via Claude Code, Opus 5.5, Opus 5 and Fable 5.1 at max — snapshot 27 Sep, re-priced (board 22 Sep) ✓"),
      "valstb20":("Vals Terminal-Bench 2.0","xmodel","Vals AI · Terminal-Bench 2.0 (older board, 2026-06-04), stated compute_effort ✓"),
      "valsbenefits1":("Vals Public Benefits v1","xmodel","Vals AI · Public Benefits Bench v1 (board 2026-06-09), max + Haiku default ✓"),
      "valsaime":("Vals AIME","xmodel","Vals AI · AIME, compute_effort null (effort unverified), board 2026-04-16 ✓"),
      "valscaselaw":("Vals CaseLaw v2","xmodel","Vals AI · CaseLaw v2, compute_effort null (effort unverified), board 2026-05-04 ✓"),
      "valsmedqa":("Vals MedQA","xmodel","Vals AI · MedQA, Sonnet 4.6 vs Haiku 4.5 thinking, effort null, board 2026-04-16 ✓"),
      "valsswecc":("Vals SWE-bench Claude Code","xmodel","Vals AI · SWE-bench, Opus 4.8 in Claude Code harness (single row, pairs with valsswebench) ✓"),
      "valsvibecc":("Vals VibeCode Claude Code","xmodel","Vals AI · Vibe Code Bench, Opus 4.8 and Sonnet 4.6 in Claude Code harness ✓"),
      "yebench":("claude-effort-bench","sweep","Claude Code 2.1.206 · 3 multi-file tasks × 5 reps, Opus 5 & Sonnet 5 × medium→xhigh, CLI cost (Sonnet ×2/3), deterministic verifiers; ~30 % silent no-op runs scored 0 ✓"),
      "lob9":("Low or Bust","sweep","Claude Code -p · 9 one-shot coding/reasoning/writing tasks, Fable 5 & Opus 4.8 × low→xhigh, 1 trial, CLI cost incl. harness cache writes ✓"),
      "lobhard":("Low or Bust hard","sweep","Claude Code -p · 8 trap tasks, Fable 5 × low→xhigh, 1 trial ✓"),
      "lobdeleg":("Low or Bust 2 monolith","sweep","Claude Code agentic · 2 ten-step packages × 3 trials, Fable 5 low/medium/high, hidden tests saturated → tokens only ✓"),
      "lobdelegw":("Low or Bust 2 workers","sweep","Claude Code · fresh low/high worker per step, Fable 5, saturated → tokens only ✓"),
      "dwdefect":("Dealwatch defect review","xmodel","Claude Code orchestrator · 5 re-seeded bugs, Fable 5.1 vs Opus 5.5 @high, 1 run, list-price cost ✓"),
      "dwfeature":("Dealwatch small feature","xmodel","same repo · 6-req feature, hidden tests saturated → cost only ✓"),
      "ecoreview":("claude-eco review baseline","xmodel","Claude Code 2.1.233 · one code-review task n=5, 5 models at CC default effort, grader re-run on raw answers (3 issues), CLI cost (Sonnet ×2/3) ✓"),
      "effmine":("effortmining pilot","sweep","Claude Code 2.1.201 · 12 short tasks × 3 reps, Opus 4.8 × low→max, median output tokens, pass rate (saturated ≥high) ✓"),
      "wookccb":("wook3024 CC bench","sweep","Claude Code · 3 tasks × 2 runs, Sonnet 4.6 & Opus 4.6 × medium/high (+ fixed-thinking Opus), CLI cost ✓"),
      "forgep1":("forge Phase 1","sweep","Claude Code · 3 tasks, Sonnet 4.6 medium/high/max, correct/partial only ✓"),
      "forgep2":("forge Phase 2","xmodel","Claude Code + Repomix · 3 tasks, Haiku/Sonnet 4.6/Opus 4.6 × medium/max, saturated → tokens only ✓"),
      "bartyaoe":("Opus 5.5 AoE2 build","sweep","Claude Code 2.1.281 · one long game-build prompt, Opus 5.5 × low→max, 1 run, CLI cost, no score → cost only ✓"),
      "effpick":("effort-pick sweep","sweep","API · 4 short writing tasks, Claude Opus (5, unverified) × low→xhigh, output tokens only ✓"),
      "wcbcc":("Weather-card CC","sweep","Claude Code · one-shot HTML weather card, 2×2 slots, Fable 5.1/5, Opus 5.5/5/4.8, Sonnet 5, Haiku × low→max, output tokens only ✓"),
      "wcbcur":("Weather-card Cursor","sweep","Cursor CLI · same task, Claude models × effort (non-thinking ids), tokens only ✓"),
      "wcbcurxl":("Weather-card Cursor-xl","sweep","Cursor CLI xl · same task, tokens only ✓"),
      "wcbcurth":("Weather-card Cursor thinking","sweep","Cursor CLI · -thinking model ids × effort, tokens only ✓"),
      "wcbcurxlth":("Weather-card Cursor-xl thinking","sweep","Cursor CLI xl · -thinking ids × effort, tokens only ✓"),
      "latitude-easy":("latitude easy tier","xmodel","ai-sdk · 12 single-file bug tasks ×3, 3 Claude models at default effort, list price ✓"),
      "vlmexam-ocr":("vlm-exam OCR","xmodel","roboflow/vlm-exam · 37 samples, similarity; Fable 5.1 & Opus 5.5 low/high ×3 runs, others low ×1 ✓"),
      "vlmexam-extraction":("vlm-exam extraction","xmodel","roboflow/vlm-exam · 97 samples, LLM-judge accuracy; same models as OCR ✓"),
      "vlmexam-counting":("vlm-exam counting","xmodel","roboflow/vlm-exam · 74 samples, LLM-judge accuracy ✓"),
      "vlmexam-identification":("vlm-exam identification","xmodel","roboflow/vlm-exam · 32 samples, near ceiling ✓"),
      "vlmexam-detection":("vlm-exam detection","xmodel","roboflow/vlm-exam · 250 images, mAP@50 ✓"),
      "retroboard-pw":("Retro board +Playwright","sweep","Claude Code 2.1.132 · retro-board build with Playwright MCP; Opus 4.7 high/xhigh, Opus 4.6, Sonnet 4.6; /cost medians ✓"),
      "retroboard-design":("Retro board design prompt","sweep","Claude Code 2.1.132 · full Antigravity design prompt; Opus 4.7 high/xhigh, Opus 4.6, Sonnet 4.6 high/max ✓"),
      "retroboard-abridged":("Retro board abridged prompt","sweep","Claude Code 2.1.132 · abridged design prompt; Opus 4.7 high/xhigh, Opus 4.6 ✓"),
      "retort55py":("retort exp-55 py","sweep","Claude Code · rest-api-crud Python, Opus 5 low→max, n=2 (max n=2); coverage 1.0 → cost only ✓"),
      "retort55go":("retort exp-55 go","sweep","Claude Code · rest-api-crud Go, Opus 5 low→max, n=2 (max n=1); coverage 1.0 → cost only ✓"),
      "retort55brpy":("retort exp-55 brazil py","sweep","Claude Code · brazil-soccer-mcp Python, Opus 5 low→max, n=1 ✓"),
      "retort55brgo":("retort exp-55 brazil go","sweep","Claude Code · brazil-soccer-mcp Go, Opus 5 low/high/xhigh/max (medium has no cost), n=1 ✓"),
      "retort15tdd":("retort exp-15 rest TDD","xmodel","Claude Code · rest-api-crud TDD prompt, Sonnet 5 vs Sonnet 4.6, 5 languages n=1 ✓"),
      "retort15bdd":("retort exp-15 rest BDD","xmodel","Claude Code · rest-api-crud BDD prompt, Sonnet 5 vs Opus 4.8, 4 languages n=1 ✓"),
      "retort15brtdd":("retort exp-15 brazil TDD","xmodel","Claude Code · brazil-soccer-mcp TDD, Sonnet 5 vs Sonnet 4.6, 3 languages ✓"),
      "retort15brbdd":("retort exp-15 brazil BDD","xmodel","Claude Code · brazil-soccer-mcp BDD, Sonnet 5 vs Opus 4.8, 2 languages ✓"),
      "retort6":("retort exp-6","xmodel","Claude Code · rest-api-crud, Opus 4.7 vs 4.8 default, 6 languages ×3 ✓"),
      "retort6beads":("retort exp-6 beads","xmodel","Claude Code + beads · rest-api-crud, Opus 4.7 vs 4.8, 6 languages ×3 ✓"),
      "retort8":("retort exp-8","xmodel","Claude Code · rest-api-crud Elixir/Erlang, Opus 4.7 vs 4.8 ×3 ✓"),
      "retort5br":("retort exp-5 brazil","xmodel","Claude Code · brazil-soccer-mcp, Opus 4.7 vs 4.8, 6 languages ✓"),
      "retort65":("retort exp-65","sweep","Claude Code · rest-api-crud, Fable 5.1 low vs default, 4 languages ×3, prompt balanced ✓"),
      "retort4648":("retort exp-46/48 bookshop","xmodel","Claude Code · bookshop task, Opus 5 vs Fable 5 default, 8 matched languages n=1 ✓"),
      "vulcanbench3-o5":("VulcanBench v3 Opus 5","sweep","VulcanBench harness · 23 tasks ×1, Opus 5 low/medium/high, report No.10 (26 Jul) ✓"),
      "tilth-mcp":("tilth MCP arm","xmodel","tilth README @cff4dda · MCP arm, 3 models; author retracted 19 Sep (harness defects) ✓"),
      "ponytail-pony":("ponytail skill arm","xmodel","promptfoo · 5 tasks ×30, ponytail skill, 3 Claude models ✓"),
      "ponytail-caveman":("ponytail caveman arm","xmodel","promptfoo · 5 tasks ×30, caveman skill, cost only ✓"),
      "ctala-cc":("ctala Claude Code route","xmodel","ctala models.json · Claude Code subscription route, 7 models, unranked (exam incomplete), list-price per assumed call ✓"),
      "melvynx-xh3":("Melvynx xhigh trio","xmodel","Claude Code · 3 apps, Fable 5 vs Sonnet 5 xhigh, same batch, verified runs, cost only ✓"),
      "melvynx-med2":("Melvynx medium duo","xmodel","Claude Code · 2 apps, Fable 5 vs Sonnet 5 medium, cost only ✓"),
      "lcb-compression":("LLM cost bench compression","xmodel","raw API · 80 prompts, prompt-compression lever, Haiku 4.5 vs Sonnet 4.6 ✓"),
      "lcb-outputcap":("LLM cost bench output cap","xmodel","raw API · 80 prompts, output-cap lever ✓"),
      "aiarena-london":("ai-arena london","sweep","Claude Code · london-island, Fable 5 high vs max, tokens only ✓"),
      "aiarena-savannah":("ai-arena savannah","xmodel","Claude Code · savannah-ecosystem, Fable 5 vs Sonnet 5 max, tokens only ✓"),
      "aiarena-tokyo":("ai-arena tokyo","xmodel","Claude Code · tokyo-island, Fable 5 vs Sonnet 5 max, tokens only; Sonnet metrics identical to savannah ✓"),
      "bullshitbench-v1":("BullshitBench v1","xmodel","CC issue 83510 · v1 n=55 detect-strict + median output tokens, 7 couples ✓"),
      "vibeoscad-png1":("vibe-openscad iter-png-1","xmodel","vibe-openscad · 7 tasks, 1 PNG-feedback round, 5 Claude models ✓"),
      "vibeoscad-png2":("vibe-openscad iter-png-2","xmodel","vibe-openscad · 7 tasks, 2 PNG rounds ✓"),
      "vibeoscad-png3":("vibe-openscad iter-png-3","xmodel","vibe-openscad · 7 tasks, 3 PNG rounds ✓"),
      "vibeoscad-pdf":("vibe-openscad PDF page","xmodel","vibe-openscad · 2 tier-4 datasheet tasks, 8 Claude models default ✓"),
      "sp-pr2258":("superpowers PR2258","xmodel","superpowers-evals campaign 5 · Opus 5 vs Opus 4.8 xhigh, interrupted, base+head pooled ✓"),
      "fablemode-inj":("fable-mode injected","xmodel","fable-mode RESULTS · 6 tasks with fable-mode prompt, Opus 4.8 vs Haiku 4.5, tokens only ✓"),
      "gliu-o5o55":("George Liu · Opus 5 vs 5.5","sweep","Claude Code 10-prompt suite · low→max · IFEval /9 ✓"),
      "gliu-s5s46":("George Liu · Sonnet 5 vs 4.6","xgen","Claude Code 10-prompt suite · medium/high baselines ✓"),
      "gliu-o48f5":("George Liu · Opus 4.8 vs Fable 5","xgen","Claude Code 10-prompt suite · medium/high baselines ✓"),
      "skillsbench-noskill":("SkillsBench (no skills)","xmodel","arXiv 2602.12670v4 T2+T15 · same runs' no-Skills condition ✓"),
      "coderev-syn25":("code-review (synthetic, n=25)","xmodel","arXiv 2606.15689 T4 · VibeOps prompt, score only ✓"),
      "coderev-syn100":("code-review (synthetic, n=100)","xmodel","arXiv 2606.15689 T4 · VibeOps prompt, score only ✓"),
      "codrouter-id":("CodeRouterBench (in-dist.)","xmodel","arXiv 2606.22902 T9 · single-turn, 9 dimensions, score only ✓"),
      "sakana-rhi46":("RHI (Sonnet 4.6)","sweep","arXiv 2607.15524 Fig. 5b · 30 ML tasks, cost normalized to sonnet-4.6-high ✓"),
      "vlnr2r-msa":("R2R-CE (mini-swe-agent)","xmodel","arXiv 2607.26148 Fig. 3 · minimal interface, vendor-default effort, score only ✓"),
      "lsp-t2s-lsp":("LSP vs grep (LSP arm)","xmodel","arXiv 2608.13568 §6.2 · 6 SWE-bench-Lite localization tasks, tokens-to-success ✓"),
      "databricks-pi":("Databricks · Pi harness","sweep","Opus 4.8 high/xhigh/max ✓"),
      "databricks":("Databricks · Claude Code","sweep","Opus 4.8 high/xhigh/max + Sonnet 5/4.6, Haiku 4.5 ✓"),
      "synthorai-single":("Synthorai single-shot arithmetic (13 tasks ×3)","sweep","Opus 5.5 and Opus 5 full ladders + default, API list-price cost; accuracy ≥97 % everywhere ✓"),
      "synthorai-loop":("Synthorai multi-hop tool loop (4 Qs ×12)","sweep","Opus 5.5 default/low/max vs Opus 5 default ✓"),
      "cyberq-debug":("CyberQ code-debug prompt","sweep","Opus 5.5 ladder + Opus 5 default/medium, single runs, list-price est. ✓"),
      "cyberq-secshort":("CyberQ security short answer","sweep","Opus 5.5 ladder + Opus 5, no score ✓"),
      "cyberq-extract":("CyberQ structured extraction","sweep","Opus 5.5 ladder + Opus 5, no score ✓"),
      "qiita-takuya-code":("Qiita Takuya coding set (5 tasks ×3)","xmodel","Opus 5.5 high/medium, Opus 5, Fable 5.1; hidden tests 100 % (saturated) ✓"),
      "rails-s1":("Agents on Rails · atomic","xmodel","rubyonrails.org/ai + rails/ai-evals runs · 21 Writebook tasks ×3, miniswen, list-price cost/run ✓"),
      "rails-s2":("Agents on Rails · features","sweep","rubyonrails.org/ai + rails/ai-evals runs · 20 tickets ×3, miniswen; Opus 5 & Fable 5.1 high→max, Opus 5.5 default ✓"),
      "endor-asl":("Agent Security League","xmodel","Endor Labs post 24 Sep · 200 tasks, Claude Code, total run cost/200, effort unstated ✓"),
      "snorkel-tbplus":("Snorkel Terminal-Bench+","xmodel","Snorkel blog 23 Sep · 24 tasks pass@1, score only, effort unstated ✓"),
      "crabbit-o55oss":("CodeRabbit OSS-Aug","sweep","CodeRabbit blog 22 Sep · 80 patterns, Opus 5.5 Standard vs Max, recall, score only ✓"),
      "crabbit-o55sig":("CodeRabbit Signal","xmodel","CodeRabbit blogs 22 & 28 Sep · 13 hard patterns, frozen cassette · Opus 5.5 Standard/Max score only; Sonnet 5.5 thinking on/off and Sonnet 5 with measured cost ✓"),
      "atomic-expense":("Atomic Agent expense-lib","xmodel","Atomic Agent 0.6.5 via OpenRouter · 5 bugs + 2 features, 32 hidden tests, n=3, provider default effort, billed cost; saturated ✓"),
      "dende-sla":("dende SLA-deadline fn","sweep","Claude Code 2.1.284 -p, no tools · Sonnet 5.5 low→max + Opus 5.5 medium/high, 15 tests, n=1–2, CLI list-price cost; saturated ✓"),
      "riku-bugfix":("riku bug-fix (5 planted)","xgen","Claude Code 2.1.284, no tools · Sonnet 5 vs 5.5, n=3 medians, relative cost only ✓"),
      "riku-table":("riku table task","xgen","Claude Code 2.1.284, no tools · Sonnet 5 vs 5.5, n=3 medians, relative cost only; saturated ✓"),
      "riku-slides":("riku slides task","xgen","Claude Code 2.1.284, no tools · Sonnet 5 vs 5.5, n=3 medians, relative cost only; saturated ✓"),
      "killswitch":("KillSwitch-Bench","xmodel","Claude Code, esoteric adversarial language · 5 tasks × 2 attempts, $5 cap, default effort, cost = tokens × list ✓"),
      "occam-base":("Occam bench, no plugin","sweep","Claude Code headless · 18 procedural tasks, hidden verifier · Sonnet 5.5 & Opus 5.5 at max/medium + Haiku 4.5 ✓"),
      "occam-rules":("Occam bench, Occam plugin","sweep","same 18 tasks, Occam rules loaded · Sonnet 5.5 & Opus 5.5 at max/medium + Haiku 4.5 ✓"),
      "occam-ponytail":("Occam bench, Ponytail 4.10","sweep","same 18 tasks, Ponytail plugin · Sonnet 5.5 & Opus 5.5 at max/medium + Haiku 4.5 ✓"),
      "occam-base-s1":("Occam bench seed 1","xgen","9 tasks (seed 1), no plugin; Sonnet 5 max from the calibration run ✓"),
      "kjl-waterslide":("KJL waterslide game","xmodel","Claude Code xhigh · one-shot game build, Sonnet 5.5 vs Opus 5.5, cost only ✓"),
      "parafr-flightsim":("Para-FR flight sim","xmodel","Claude Code medium · one prompt, ≈$5 each, Sonnet 5.5 vs Opus 5.5, cost only (approx) ✓"),
      "merkus3":("MrMerkus 3-task tests","xgen","3 tasks, 70 hidden checks · harness differs (Claude Code vs Antigravity), saturated, score only ✓"),
      "crabbit-s55oss":("CodeRabbit OSS-Aug (Sonnet 5.5)","xmodel","CodeRabbit blog 28 Sep · 44 PRs, Sonnet 5.5 vs Sonnet 5, cost only (judge pending) ✓"),
      "boxs55-all":("Box AI eval (Sonnet 5.5)","xmodel","Box blog 28 Sep · internal enterprise eval, Sonnet 5.5 vs 5, score only ✓"),
      "boxs55-finserv":("Box AI eval · finance","xmodel","Box blog 28 Sep · financial services subset, Sonnet 5.5 vs 5, score only ✓"),
      "boxs55-legal":("Box AI eval · legal","xmodel","Box blog 28 Sep · legal subset, Sonnet 5.5 vs 5, score only ✓"),
      "boxs55-lifesci":("Box AI eval · life sciences","xmodel","Box blog 28 Sep · life sciences subset, Sonnet 5.5 vs 5, score only ✓"),
      "boxs55-public":("Box AI eval · public sector","xmodel","Box blog 28 Sep · public sector subset, Sonnet 5.5 vs 5, score only ✓"),
      "suwanobu-12m":("Qiita suwa_nobu 12 models","xgen","Claude Code 2.1.283 · trivial read/count/write task, cold cache, median of 3, CLI cost, CLI default effort ✓"),
      "crabbit-f51":("CodeRabbit review (Fable 5.1)","xmodel","CodeRabbit blog 1 Sep · 45 tasks/105 issues, Fable 5.1 low/high + Fable 5, Opus 5, score only ✓"),
      "deloitte-cr":("Deloitte code review","xmodel","Opus 5.5 launch page partner quote · bugs caught, score only, n unstated ✓"),
      "hebbia-cite":("Hebbia citation recall","xmodel","Opus 5.5 launch page partner quote · rubric coverage, score only ✓"),
      "classmethod-o55":("Classmethod Bedrock prime fn","sweep","DevelopersIO 23 Sep · Opus 5.5 low/medium/high, 1 run, output tokens only ✓"),
      "docswebpro":("SWE-bench Pro subset (Anthropic docs)","sweep","Anthropic-internal 478-problem subset, customer-billed cost ✓"),
      "docsdrb2":("DeepResearch Bench II (Anthropic docs)","sweep","50-task subset, 33-task basis, customer-billed ✓"),
      "docscode370":("Internal coding, 370 repo tasks (Anthropic docs)","sweep","plain API agent, customer-billed per attempt ✓"),
      "docswidesearch":("WideSearch (Anthropic docs)","sweep","Fable 5 low/medium/default, 3 runs ✓"),
      "docsdeepwide":("DeepWideSearch (Anthropic docs)","sweep","Fable 5, 220 questions, 3 runs ✓"),
      "docsbrowsecomp":("BrowseComp 500-cut (Anthropic docs)","sweep","Fable 5, 1-3 runs per setting ✓"),
      "docsgdpval":("GDPval (Anthropic docs)","sweep","Fable 5, 1 run, cost incl. grading ✓"),
      "docscorpus":("Corpus defect sweep (Anthropic docs)","sweep","21.6M-token corpus, F1, per episode ✓"),
      "tb30json":("TB 3.0 (claude.dev payload)","sweep","claude.dev 'Spending your effort' embedded data · 74 tasks×5, Opus 5 / Fable 5 / Fable 5.1 labelled rungs, median tokens, no USD ✓"),
      "tb30chart":("TB 3.0 (claude.dev chart)","sweep","claude.dev 'Spending your effort' SVG · 70 tasks, Opus 5.5 / Fable 5.1 / Opus 5 / Fable 5 × low→max, median tokens, no USD; Opus 5.5 run 3 wk later, 128k cap ✓"),
      "osworld2o5":("OSWorld 2.0 board (Opus 5)","sweep","osworld-v2.xlang.ai official JSON · v2.1 full 108 tasks, batched, 500 steps, Opus 5 low→max, output tokens/task, no cost ✓"),
      "osworld2o5a":("OSWorld 2.0 board v08.08 (Opus 5)","sweep","osworld-v2.xlang.ai official JSON · release v2026.08.08, 7-run avg, Opus 5 low→max, score only ✓"),
      "osworld2s150":("OSWorld 2.0 single 150 steps","xmodel","osworld-v2.xlang.ai official JSON · 108 tasks, 150-step budget, Opus 4.7 max, Sonnet 4.6 medium/max ✓"),
      "osworld2s300":("OSWorld 2.0 single 300 steps","xmodel","osworld-v2.xlang.ai official JSON · 108 tasks, 300-step budget, Opus 4.7 max, Sonnet 4.6 medium/max ✓"),
      "sealpro2":("SWE-Bench Pro V2 (Scale)","xmodel","Scale Labs board via Wayback 23 Sep 2026 · full set, Claude Code, one effort per model, score only, saturated ✓"),
      "sealpro2h":("SWE-Bench Pro V2 HARD (Scale)","xmodel","Scale Labs board via Wayback 23 Sep 2026 · HARD subset, Claude Code, score only ✓"),
      "surfevolver":("Surface Evolver bench","xmodel","yhenon/surface-evolver-llm-eval aggregates.json · 16 runs/model, OpenRouter recorded cost, Opus 4.8 none/high, Sonnet 5 medium, Fable 5 high ✓"),
      "cbcostopt":("Cookbook cost optimization","sweep","Anthropic cookbook cost_optimization.ipynb · 10-claim agent ×2 trials, Opus 5 & Sonnet 5 low→high, Haiku 4.5; list-price cost from usage ✓"),
      "llmconfbench":("LLMConfBench","xmodel","arXiv 2609.20666 · conformer energy ranking, 27 molecules × 3 prompts via OpenRouter, Opus 5 and Sonnet 5 at high; cost summed from the repo's per-call logs ✓"),
      "vectorise-effort":("Vectorise doc-search effort test (Vidali gist)","sweep","33 multilingual MCP questions, output tokens only, 24 Sep 2026 ✓"),
      "vectorise-graded":("Vectorise doc-search, judge-graded (Vidali gist)","xmodel","citation recall by cross-model judge, 22 Sep 2026 evening run ✓"),
      "lighthouse-svg":("Lighthouse SVG one-shot (Reddit)","xmodel","one prompt, Copilot AIU, Opus capped at stop, subjective rank ✓"),
      "arcagi2":("ARC-AGI-2","sweep","ARC Prize evaluations.json · semi-private, costPerTask per model × effort; Opus 5.5 & Fable 5.1 full ladders ✓"),
      "arcagi1":("ARC-AGI-1","sweep","ARC Prize evaluations.json · semi-private, costPerTask per model × effort; scores ≥97.5 % flagged gen5-saturated ✓"),
      "aatb40":("AA TB 4.0","sweep","AA model payload · Terminal-Bench 4.0 (AA harness), 4 models × ladder + 3 at max; floor scores blank ✓"),
      "aascicode":("AA SciCode","sweep","AA model payload · SciCode, 4 models × ladder + 3 at max ✓"),
      "aahle":("AA HLE","sweep","AA model payload · HLE no tools, 4 models × ladder + 3 at max ✓"),
      "aagdppdf":("AA GDP-PDF","sweep","AA model payload · GDP-PDF all-pass, 4 models × ladder + 3 at max; noisy ✓"),
      "aacritpt":("AA CritPt","sweep","AA model payload · CritPt physics, 4 models × ladder + 3 at max; floor scores blank ✓"),
      "aalcr":("AA-LCR","sweep","AA model payload · long-context reasoning, input-dominated cost ✓"),
      "aaomni":("AA Omniscience","sweep","AA model payload · Omniscience accuracy (not the penalised index) ✓"),
      "aacai":("AA Coding Agent Index","xmodel","AA · Claude Code harness, DeepSWE+TB4.0+SWE-Atlas, 3 Claude models at max, measured $ incl. cache; fallback 3–9 % ✓"),
      "deepswe":("DeepSWE v1.1","sweep","Datacurve live JSON · 113 tasks × 4 runs, mini-swe-agent, 4 models × full ladder + Sonnet 4.6 high, mean $/attempt ✓"),
      "valscyber":("Vals CyberBench","xmodel","Vals AI · OSS-Fuzz PoC+patch, mini-swe-agent, 5 Claude models at max — snapshot 27 Sep, re-priced ✓"),
      "valsskills":("Vals SkillsBench","xmodel","Vals AI · SkillsBench with skills, OpenHands, 5 Claude models at max — snapshot 27 Sep, re-priced ✓"),
      "petribench":("PetriBench","sweep","arXiv 2609.19883 · 4,800 Petri-net questions, raw API adaptive thinking + output_config.effort, Opus 5 M/H/XH + Sonnet 5 M/H, measured tokens × list ✓"),
      "sweeffort":("SWE-Effort 25","sweep","arXiv 2608.01347 App. N · 25 hard SWE-bench Verified, Claude Code 2.1.220, Opus 5 & Sonnet 5 × low/high/xhigh, billed cost ✓"),
      "ffinance":("FrontierFinance","sweep","arXiv 2608.11683 Fig. 9 · Finance Agent v2 harness, Opus 4.8 low→xhigh, API cost/query (vector-read) ✓"),
      "osworldpro":("OSWorld-Pro","xmodel","arXiv 2609.24890 · OSWorld harness, 250 turns, 4 Claude models all at max, tokens × OpenRouter list incl. cache ✓"),
      "tautau":("τ^τ-Bench","xmodel","arXiv 2609.04611 · 53 agent-construction tasks in Claude Code, Opus 5 vs Sonnet 5 both at max, build spend at list ✓"),
      "progdistill":("ProgramDistill-300","xmodel","arXiv 2609.18805 · 300 web-app repair tasks, R2E-Gym harness, Opus 5 vs Sonnet 5 at high, tokens × LiteLLM list ✓"),
      "gamelogic":("GameLogicBench","xmodel","arXiv 2609.21562 · 72 Godot game-logic tasks in Claude Code, effort=high, Opus 5 vs Sonnet 5, tokens × vendor list ✓"),
      "rubench":("RuBench 1.0","xmodel","arXiv 2607.06411 · 25 Russian repo tasks × 3 runs, Claude Code 2.1.201, all at xhigh, CLI-reported cost ✓"),
      "kimicode2":("Kimi Code Bench 2.0","xmodel","arXiv 2607.24653 Fig. 13a · Moonshot in-house suite via Claude Code, Opus 4.8 vs Fable 5 at max, measured cost (vector-read) ✓"),
      "fuzzbrain":("FuzzingBrain-Bench","xgen","arXiv 2608.25158 · 77 fuzzing challenges, raw API no thinking param, 3 models, tokens × list (cache-aware) ✓"),
      "bvb":("BVB","xmodel","arXiv 2609.15478 · Mini-BVB via LiteLLM, $3/scene cap, 5 Claude models at high (+ omitted-effort runs), LiteLLM list cost ✓"),
      "nnakapa-o5f51":("nnakapa QCD #37","sweep","Claude Code 2.1.258 · 3 DB tasks × 10 runs, Opus 5 & Fable 5.1 × low→xhigh, CLI-reconciled cost, hidden-test gate ✓"),
      "nnakapa-o5s5":("nnakapa QCD #34","sweep","Claude Code 2.1.226 · 3 DB tasks × 10 runs, Sonnet 5 & Opus 5 × low→xhigh, CLI-reconciled cost ($2/$10 Sonnet), hidden-test gate ✓"),
      "nnakapa-o5o48f5":("nnakapa QCD #29","sweep","Claude Code 2.1.220 · 3 DB tasks × 10 runs, Opus 5, Opus 4.8 & Fable 5 × low→xhigh, CLI-reconciled cost, hidden-test gate ✓"),
      "nnakapa-s5cc":("nnakapa QCD #35 CC","sweep","Claude Code 2.1.229 (1M ctx) · 3 DB tasks × 10 runs, Sonnet 5 × low→xhigh, CLI-reconciled cost ($2/$10) ✓"),
      "willison55":("Willison SVG 5.5","sweep","llm CLI · one fixed SVG prompt, Opus 5.5 and Sonnet 5.5 low→xhigh, measured tokens; max hit the 128k cap on both (omitted); trivial task ✓"),
      "nnakapa-s5cop":("nnakapa #35 Copilot","sweep","GitHub Copilot CLI 1.0.79 · same 3 DB tasks × 10 runs, Sonnet 5 × low→xhigh, billed cost ✓"),
      "nnakapa-s5cop2":("nnakapa #36 Copilot","sweep","GitHub Copilot CLI 1.0.80 · same 3 DB tasks × 10 runs, Sonnet 5 × low→xhigh, billed cost ✓"),
      "nnakapa-o47o48":("nnakapa QCD #20","sweep","Claude Code 2.1.157 · 3 DB tasks × 10 runs, Opus 4.7 & Opus 4.8 × low→xhigh ✓"),
      "nnakapa-f5o48":("nnakapa QCD #24","sweep","Claude Code 2.1.170 · 3 DB tasks × 10 runs, Fable 5 & Opus 4.8 × low→xhigh ✓"),
      "merc-core10":("MERC core-10","sweep","Claude Code -p, no tools · 10 graded tasks, 6 models × low→max, n=2; usage × list (5m cache-write); scores 94–98/98 → cost only ✓"),
      "renchris-o55":("renchris review o55","sweep","claude -p no tools, CC 2.1.280 · 9 code briefs / 36 anchored defects, Opus 5.5 low→max + Opus 5 @high, 3 blind judges; CLI list cost ✓"),
      "renchris-f51":("renchris review f51","sweep","claude -p no tools, CC 2.1.260 (64K cap) · same 9-brief corpus, Fable 5.1 low→xhigh (max incomplete), 3 blind judges ✓"),
      "kayben-review":("kayben plan review","sweep","claude -p no tools, CC 2.1.282 · 13 seeded defects, Opus 5.5 & Sonnet 5 × medium/high/xhigh, n=10, effort verified in transcripts ✓"),
      "kayben-review-f51":("kayben plan review f51","sweep","same doc, cap10 prompt · Fable 5.1 low→max, n=5 ✓"),
      "vulcanbench-ciiv4-f51":("VulcanBench F-v4 f51","sweep","Claude Code 2.1.259–261 · same 23 tasks, Fable 5.1 × low→max, v3.4 judge, per-model list ledger; fallback 7–40 % ✓"),
      "vulcanbench-ciiv4-o5":("VulcanBench F-v4 o5","sweep","Claude Code 2.1.257 · same 23 tasks, Opus 5 × low/med/high/max, CLI list cost, functional pass only ✓"),
      "rampnet-fable":("RampNet Fable","xmodel","same rig/prompt, effort=low, Anthropic 1P path · Fable 5 vs 5.1 ✓"),
      "caloriebench":("CalorieBench","xmodel","Anthropic API · 200 food photos, effort=high sent without thinking → nothink regime, within-20 % score ✓"),
      "an55tb40":("TB 4.0 (Anthropic launch charts)","sweep","Anthropic launch page chart CSVs (Opus 5.5 and Sonnet 5.5 pages) · 5 models × low→max; production safeguards on (fallbacks); Sonnet 5 anomalously low, flagged ✓"),
      "ffinance-x":("FrontierFinance T4","xmodel","arXiv 2608.11683 Table 4 · effort omitted, Fable 5 vs Opus 4.8 ✓"),
      "valslcb":("Vals LiveCodeBench","xmodel","Vals AI · LiveCodeBench, Claude models at their stated compute_effort, measured cost/test ✓"),
      "valsmmmu":("Vals MMMU","xmodel","Vals AI · MMMU, Claude models at their stated compute_effort, measured cost/test ✓"),
      "valscorpfin":("Vals CorpFin v2","xmodel","Vals AI · CorpFin v2, Claude models at their stated compute_effort, measured cost/test ✓"),
      "valslegalbench":("Vals LegalBench","xmodel","Vals AI · LegalBench, Claude models at their stated compute_effort, measured cost/test — snapshot 27 Sep, re-priced ✓"),
      "valsmortgage":("Vals MortgageTax","xmodel","Vals AI · MortgageTax, Claude models at their stated compute_effort, measured cost/test ✓"),
      "valstaxeval":("Vals TaxEval v2","xmodel","Vals AI · TaxEval v2, Claude models at their stated compute_effort, measured cost/test ✓"),
      "valsmmindex":("Vals Multimodal Index","xmodel","Vals AI · Multimodal Index, Claude models at their stated compute_effort, measured cost/test ✓"),
      "valsswebench":("Vals SWE-bench","xmodel","Vals AI · SWE-bench, Claude models at their stated compute_effort, measured cost/test ✓"),
      "valsgpqa":("Vals GPQA","xmodel","Vals AI · GPQA, Claude models at their stated compute_effort, measured cost/test, near-ceiling → cost only ✓"),
      "valsmmlupro":("Vals MMLU-Pro","xmodel","Vals AI · MMLU-Pro, Claude models at their stated compute_effort, measured cost/test, near-ceiling → cost only ✓"),
      "retort49":("retort exp-49","sweep","Claude Code · one task, 2 models × low→max, n=3; repo states its own quality saturation → cost only ✓"),
      "runebench":("RuneBench","xmodel","Harbor+Modal · 16 skills, 30-min budget, XP metric; mispriced Opus 5 cells omitted ✓"),
      "melvynx":("Melvynx bench","sweep","Claude Code · 7 valid tasks, Opus 5 high vs max, manual rubric ✓"),
      "aa-index43":("AA Index v4.3","sweep","AA · index v4.3 of 7 Sep (TB 4.0 + AutomationBench-AA), Fable 5.1 and Opus 5 × full ladder ✓"),
      "firecrawl":("Firecrawl 57-run","xmodel","claude -p in sandbox-exec · 3 models at matched high, measured usage; 7/7 all → cost only ✓"),
      "alebench":("ALE-Bench","xmodel","Epoch archive · 3 models at matched high, measured token splits ✓"),
      "weirdml":("WeirdML","sweep","Epoch archive · 3 models × high/max, cost per run ✓"),
      "livebench":("LiveBench","xmodel","new-livebench CSVs · 2026-06-25 release, 13 Claude configs (max/xhigh/high/medium), measured tokens × rates, global = mean of 7 category means ✓"),
      "cursorbench40":("CursorBench 4.0","sweep","cursor.com payload · v4.0 long-horizon suite, Opus 5/5.5, Fable 5.1, Sonnet 5/5.5 × low→max, measured tokens × list incl. cache ✓"),
      "willison51":("Willison SVG 5.1","sweep","llm CLI · one fixed SVG prompt, Fable 5.1 low→max, measured tokens; trivial task ✓"),
      "worldbuild":("WorldBuild Bench","xmodel","own harness · 3 game briefs, Fable 5 vs Opus 5 both at high, real API ledger ✓"),
      "stet25":("Stet 25-PR","xmodel","Claude Code · 25 replayed PRs, Opus 5 vs Opus 4.8 both at medium, relative cost ✓"),
      "fcodemain":("FrontierCode main","sweep","Cognition leaderboard JSON · v1.1 main (100 tasks), Claude models × low→max incl. Sonnet 5.5, measured USD/rollout ✓"),
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
      "valsfab2":("Vals Finance Agent v2","xmodel","Vals AI · Finance Agent v2, Claude models at their stated compute_effort, measured cost/test — snapshot 27 Sep, re-priced ✓"),
      "valslegal":("Vals Legal Research","xmodel","Vals AI · Legal Research, Claude models at their stated compute_effort, measured cost/test — snapshot 27 Sep, re-priced ✓"),
      "valsmedscribe":("Vals MedScribe","xmodel","Vals AI · MedScribe, Claude models at their stated compute_effort, measured cost/test ✓"),
      "valstax":("Vals Tax Agent","xmodel","Vals AI · Tax Agent, 10 Claude entries at their stated compute_effort — snapshot 27 Sep, re-priced ✓"),
      "valsbenefits":("Vals Public Benefits v1.1","xmodel","Vals AI · Public Benefits v1.1, Claude models at their stated compute_effort, measured cost/test — snapshot 27 Sep, re-priced ✓"),
      "valsvcb100":("Vals Vibe Code Bench 1-100","xmodel","Vals AI · Vibe Code Bench 1-100, Claude models at their stated compute_effort, measured cost/test ✓"),
      "valsioi":("Vals IOI","xmodel","Vals AI · IOI, Claude models at their stated compute_effort, measured cost/test — snapshot 27 Sep, re-priced ✓"),
      "valsmystery":("Vals MysteryMechanism","xmodel","Vals AI · MysteryMechanism, Claude models at their stated compute_effort, measured cost/test — snapshot 27 Sep, re-priced ✓"),
      "valsrsi":("Vals RSI Index","xmodel","Vals AI · RSI Index v1.1 (autonomous LLM R&D, 4 campaigns), Claude models at max, cost per suite = sum of 4 — snapshot 27 Sep, re-priced (board 25 Sep) ✓"),
      "senkoflysim":("Senko Flysim","xmodel","Senko Rašić · one-shot flight-sim game in Claude Code, xhigh, CLI-reported cost (rounded $, quality not scored) ✓"),
      "senkovoxel":("Senko Voxel","xmodel","Senko Rašić · one-shot Minecraft-like game in Claude Code, xhigh, CLI-reported cost (rounded $, quality not scored) ✓"),
      "senkorts":("Senko RTS","xmodel","Senko Rašić · one-shot RTS game in Claude Code, xhigh, CLI-reported cost (rounded $, quality not scored) ✓"),
      "playcodesvg":("Playcode MacBook SVG","sweep","Playcode · one-shot MacBook SVG, high/xhigh/max per model, provider-billed cost (quality ordinal, not scored) ✓"),
      "valstb21":("Vals TB 2.1","xmodel","Vals AI · Terminal-Bench 2.1, Claude models at their stated compute_effort (Sonnet 5.5, Opus 5.5 high) — snapshot 27 Sep, re-priced ✓"),
      "valstb4":("Vals TB 4.0","xmodel","Vals AI · Terminal-Bench 4.0, all Claude at max, measured cost/test — snapshot 27 Sep, re-priced ✓"),
      "valsmedcode":("Vals MedCode","xmodel","Vals AI · ICD-10-CM coding, 2,755 records, all at max ✓"),
      "valssage":("Vals SAGE","xmodel","Vals AI · grading student math work against a rubric, all at max ✓"),
      "valsbiomyst":("Vals BioMystery","xmodel","Vals AI · BioMysteryBench (Terminus), Sonnet 5.5, Opus 5.5 and Opus 5 at max — snapshot 27 Sep, re-priced ✓"),
      "valstbsci":("Vals TB-Science","xmodel","Vals AI · Terminal-Bench-Science, all at max — snapshot 27 Sep, re-priced ✓"),
      "valssre":("Vals SRE-Bench","xmodel","Vals AI · binary reverse engineering (despite the name), all at max — snapshot 27 Sep, re-priced ✓"),
      "qiita-takuya-reason":("Qiita reasoning","sweep","Qiita (Takuya) · 19 reasoning questions × 3 runs, Claude Code without tools, measured tokens × list price ✓"),
      "sonarjava":("Sonar Java","sweep","Sonar leaderboard JSON · 4,444 Java tasks, single-shot, measured tokens × list price; Opus 5.5 medium/high ✓"),
      "sc55hlet":("HLE tools (O5.5)","sweep","Opus 5.5 card p185 · HLE with tools, 3 models × sweep low→max, $ cost, scores printed ✓"),
      "sc55amnt":("ArXivMath no-tools","sweep","Opus 5.5 card p182 · ArXivMath Aug 2026, 57 problems, 3 models × low→max, $ cost, scores printed ✓"),
      "sc55amt":("ArXivMath tools","sweep","Opus 5.5 card p183 · ArXivMath Aug 2026 with code sandbox, 3 models × low→max, scores printed ✓"),
      "sc55draco":("DRACO (O5.5)","sweep","Opus 5.5 card p187 · 980k budget, 3 models × low→max, $ cost, scores printed; a new run, not the F5.1-card one ✓"),
      "sc55wandr":("WANDR","sweep","Opus 5.5 card p188 · Perplexity wide-search, offline index, 980k budget, 3 models × low→max, scores printed ✓"),
      "scs55hlen":("HLE no-tools (S55)","sweep","Sonnet 5.5 card p120 · 980k budget, 3 models × low→max, $ cost (perfect caching), scores printed ✓"),
      "scs55osws":("OSWorld 2.1 strict","sweep","Sonnet 5.5 card p132 · strict pass, Opus 5.5 × 5 (effort from cost order) + Sonnets at max; other Sonnet points held ✓"),
      "scs55bcadn":("BenchCAD V2C −tools","sweep","Sonnet 5.5 card p129 · tools disabled, 4 models × 5, separate regime kept out of the effort grid ✓"),
      "scs55chartqn":("Chartography −tools regraded","sweep","Sonnet 5.5 card p127 · re-graded no-tools scores, quality only, costs in chartogn ✓"),
      "scs55swemulti":("SWE-bench Multilingual (S55)","xmodel","Sonnet 5.5 card table 8.1.A · 3 models at max, score-only ✓"),
      "scs55swemm":("SWE-bench Multimodal (S55)","xmodel","Sonnet 5.5 card table 8.1.A · 3 models at max, score-only ✓"),
      "scs55tbsci":("TB-Science 0.1 (S55)","xmodel","Sonnet 5.5 card p114 · Claude Code --bare, 5 models at max, score-only ✓"),
      "scs55progb":("ProgramBench 166 (S55)","xmodel","Sonnet 5.5 card p118 · mini-swe-agent, 3 models, score-only ✓"),
      "scs55offqa":("OfficeQA (S55)","xmodel","Sonnet 5.5 card p132 · 3 models at max, score-only ✓"),
      "scs55offqapro":("OfficeQA Pro (S55)","xmodel","Sonnet 5.5 card p132 · 133 q, 3 models at max, score-only ✓"),
      "scs55toolath":("Toolathlon-Verified","xmodel","Sonnet 5.5 card table 8.14.5.A · 7 Claude models at max, Pass@1, score-only ✓"),
      "scs55gmmlu":("GMMLU (S55)","xmodel","Sonnet 5.5 card p140 · 4 models at max, 1 trial, score-only ✓"),
      "scs55milu":("MILU (S55)","xmodel","Sonnet 5.5 card p140 · 4 models at max, score-only ✓"),
      "scs55physb":("PhysicianBench","sweep","Sonnet 5.5 card p138 · Sonnet 5.5 low→max labelled + 4 models at max, score-only (time axis) ✓"),
      "scs55hbpro":("HealthBench Pro (adj.)","sweep","Sonnet 5.5 card p138 · length-adjusted, Sonnet 5.5 low→max + 3 at max, score-only ✓"),
      "scs55hb":("HealthBench (adj.)","sweep","Sonnet 5.5 card p138 · length-adjusted, Sonnet 5.5 low→max + 2 at max (digitized), score-only ✓"),
      "cdhillclimb":("claude.dev hillclimb","xmodel","claude.dev hillclimb post · 30 support tickets, audited prompt, Opus 5.5 vs Sonnet 5 at low, cost per ticket ✓"),
      "scs55biomyhs":("BioMystery hard-sub (S55)","xmodel","Sonnet 5.5 card p142 · 4 models at max, bio safeguards off, score-only ✓"),
      "scs55biomyhd":("BioMystery hard-dist (S55)","xmodel","Sonnet 5.5 card p142 · 4 models at max, bio safeguards off, score-only ✓"),
      "scs55spatial":("Spatial transcriptomics (S55)","xmodel","Sonnet 5.5 card p142 · 4 models at max, bio safeguards off, score-only ✓"),
      "scs55scell":("Single-cell (S55)","xmodel","Sonnet 5.5 card p142 · 4 models at max, bio safeguards off, score-only ✓"),
      "scs55morph":("Morphology (S55)","xmodel","Sonnet 5.5 card p142 · 4 models at max, bio safeguards off, score-only ✓"),
      "scs55medchem":("MedChem (S55)","xmodel","Sonnet 5.5 card p142 · 4 models at max, bio safeguards off, score-only ✓"),
      "scs55protseq":("Protein sequence (S55)","xmodel","Sonnet 5.5 card p142 · 4 models at max, bio safeguards off, score-only ✓"),
      "scs55protlib":("Protein library (S55)","xmodel","Sonnet 5.5 card p142 · 4 models at max, bio safeguards off, score-only ✓"),
      "scs55binder":("Binder design (S55)","xmodel","Sonnet 5.5 card p142 · 4 models at max, bio safeguards off, score-only ✓"),
      "scs55bioimg":("Bio-imaging (S55)","xmodel","Sonnet 5.5 card p142 · 4 models at max, bio safeguards off, score-only ✓"),
      "scs55prottrb":("Protein trouble-shoot (S55)","xmodel","Sonnet 5.5 card p142 · 4 models at max, bio safeguards off, score-only ✓"),
      "scs55protund":("Protein understanding (S55)","xmodel","Sonnet 5.5 card p142 · 4 models at max, bio safeguards off, score-only ✓"),
      "scswebenchpro":("SWE-bench Pro (cards)","xmodel","Sonnet 5 card and Sonnet 5.5 card table 8.1.A · 5 Claude models at max, score only ✓"),
      "aaharvey":("AA Harvey LAB","sweep","AA model payload · Harvey's Legal Agent Bench (AA's own run, separate from Vals's HLAB), score-only, 8 models × ladder + 4 at max ✓"),
      "aatbsci":("AA Terminal-Bench-Science","sweep","AA model payload · Terminal-Bench-Science 0.1 (AA harness, separate from Vals's board), score-only, 4 models × ladder + 2 at max ✓"),
      "aamlcr":("AA MLCR","sweep","AA model payload · MLCR-AA, score-only; Sonnet 5.5 max-only, Opus 5 full ladder, 5 others at max ✓"),
      "nnrlog-webtool":("nantokanaru_log web-tool task","xmodel","note.com 29 Sep · Claude Code high, n=2, fresh context each run, cost = API-price conversion ✓"),
      "nnrlog-game":("nantokanaru_log browser game","xmodel","note.com 29 Sep · same setup, n=2, no browser-test tool ✓"),
      "nnrlog-total":("nantokanaru_log 7-task total","xmodel","note.com 29 Sep · same setup, 7 tasks × 2 runs aggregated, cost only ✓"),
      "tankai-wareki":("tank_ai wareki converter","sweep","note.com 29 Sep · Claude Code subagents at fixed model × effort, n=1, 38 auto-graded tests, score only ✓"),
      "ramen-bench":("Ramen Bench","sweep","not-stbenjam/ramen-bench · one-shot creative-coding HTML, Sonnet 5.5, Opus 5.5, Opus 5, Fable 5.1 × low→max, Claude Code run.json, cost only ✓"),
      "minebench-voxel":("MineBench voxel arena","xmodel","minebench.ai live API · voxel builds, 15 prompts, Elo arena read 29 Sep, measured cost for 8 of 12 Claude models ✓"),
      "frontierswe":("FrontierSWE v2","xmodel","Proximal frontierswe.com + Sonnet 5.5 card · 34 ultra-long tasks, max effort, proximus harness, mean reward@5; cost basis undocumented ✓"),
      "cfgk3s55":("CFG k3s DevOps","sweep","computingforgeeks Sonnet 5.5 review · 3 tasks × 3 runs, raw API single file; score = k3s deploy + HTTP 200 pass rate of the K8s task, cost summed over the 3 tasks ✓"),
      "sc55osw":("OSWorld 2.1 (O5.5)","sweep","Opus 5.5 card p207 + Sonnet 5.5 card p131 · v2.1 files of 10 Sep, partial credit, 3 models × 5 efforts (effort from cost order) + Sonnets at max ✓"),
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
            nid = f'{r["model"]}@{r["effort"]}'
            if nid not in seen: seen.add(nid); nodes.append(nid)
        lbl, t, h = GMETA.get(gk, (gk, "xmodel", "config ✓"))
        out.append({"s": rs[0]["source"], "g": lbl, "t": t, "h": h, "n": nodes, "u": pick_url(rs, rs[0]["source"])})
    return out


def monotonicity_report(cg, qg):
    """Effort is a ladder: within a model, a higher rung should neither cost nor score less than the one below.
    An inversion is reported at build time, never corrected: inside the interval it is left as the data give it
    (a documented exception: Sonnet 4.6 falls after `high`, which the Sonnet 5 card itself prints)."""
    ORD = ["low", "medium", "high", "xhigh", "max"]
    out = []
    for grid, name in ((cg, "cost"), (qg, "quality")):
        for m, es in grid.items():
            seq = [(e, es[e][0]) for e in ORD if e in es]
            for (a, va), (b, vb) in zip(seq, seq[1:]):
                if vb < va: out.append(f"{name}: {m} {a}({va}) > {b}({vb})")
    return out

DATE_FILE = os.path.join(HERE, "content-date.json")   # {fingerprint, date} of the last content change (committed)

def content_date(fingerprint):
    """Date of the last change to what the reader gets: the page text, the figures and the data the charts draw.
    The build fingerprints that content; while it matches the one recorded in gen/content-date.json the recorded
    date stands, otherwise today's date is recorded with the new fingerprint (commit the file with the change).
    So code, styles, icons or head tags alone never move the visible "Updated" date, JSON-LD dateModified or the
    sitemap lastmod, and a rebuild of an unchanged page changes nothing. Limits: text that app.js draws only at run
    time (tooltips, interactive labels) and attribute text (alt, aria-label) are not fingerprinted; a content change
    reverted after a build keeps the build day unless gen/content-date.json is restored with it."""
    try:
        with open(DATE_FILE, encoding="utf-8") as f:
            rec = json.load(f)
        if rec.get("fingerprint") == fingerprint:
            return datetime.date.fromisoformat(rec["date"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    date = datetime.date.today()
    with open(DATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"fingerprint": fingerprint, "date": date.isoformat()}, f, indent=1)
        f.write("\n")
    return date

def content_fingerprint(body, pre, data):
    """sha256 of the content only: title, description, the visible text of the body (pre-rendered blocks
    included, date placeholder not yet filled), the full answer used by llms.txt, and the data behind the charts."""
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", body, flags=re.S | re.I)
    text = re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", text))).strip()
    blob = json.dumps([TITLE, SITE_NAME, DESCRIPTION, text, pre.get("answer-full", ""), data],
                      ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()

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
    website = {"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": SITE_URL}
    ld = json.dumps([website, dataset], ensure_ascii=False, indent=1).replace("</", "<\\/")
    return (
        f"<title>{a(TITLE)}</title>\n"
        f'<meta name="description" content="{a(DESCRIPTION)}">\n'
        f'<link rel="canonical" href="{SITE_URL}">\n'
        '<link rel="icon" href="favicon.svg" type="image/svg+xml">\n'
        '<link rel="icon" href="favicon.png" type="image/png" sizes="96x96">\n'   # Google Search ignores SVG icons
        '<meta property="og:type" content="website">\n'
        f'<meta property="og:url" content="{SITE_URL}">\n'
        f'<meta property="og:title" content="{a(TITLE)}">\n'
        f'<meta property="og:description" content="{a(DESCRIPTION)}">\n'
        f'<meta property="og:image" content="{SITE_URL}og-image.png">\n'
        '<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n'
        f'<meta property="og:image:alt" content="{a(TITLE)} — {a(SITE_HOST)}">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        + (f'<meta name="msvalidate.01" content="{a(BING_SITE_VERIFICATION)}">\n' if BING_SITE_VERIFICATION else "") +
        f'<script type="application/ld+json">\n{ld}\n</script>\n'
    )

def write_root_files(date, pre, anchor_label):
    """robots.txt, sitemap.xml, llms.txt and the IndexNow key file, next to index.html. llms.txt reuses the
    full answer computed by app.js (answerFull), so it states the same conclusions as the page."""
    plain = lambda h: re.sub(r"\s+(?=:)", "", re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", "", h)))).strip()
    files = {
        "robots.txt": f"# All robots allowed, AI robots included.\nUser-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n",
        "sitemap.xml": ('<?xml version="1.0" encoding="UTF-8"?>\n'
                        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                        f"  <url><loc>{SITE_URL}</loc><lastmod>{date.isoformat()}</lastmod></url>\n</urlset>\n"),
        "llms.txt": f"""# {TITLE}

> {DESCRIPTION}

{pre.get("answer-full", "")}

Costs and qualities are relative to {anchor_label} = 1.00. They are fused from measurements taken on the same task by a latent-quality model that estimates each benchmark's own scale (method: METHODOLOGY.md in the source repository), from {plain(pre.get(".nsrc", ""))}. Updated {date.isoformat()}. Figures are indicative, derived from public third-party measurements; not affiliated with Anthropic.

## Report

- [{TITLE}]({SITE_URL}): quality vs cost per model and effort level, Pareto frontier, best pick per task tier, normalized cost matrix, method and sources.

## Data

- [raw-data.csv]({SITE_URL}raw-data.csv): every measured row (source, model, effort, task, harness, cost, tokens, score, reference), CC BY 4.0.

## Optional

- [Source repository]({REPO_URL}): generator, method notes, version history.
""",
    }
    if INDEXNOW_KEY:
        files[f"{INDEXNOW_KEY}.txt"] = INDEXNOW_KEY
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
        if key == "answer-full":                     # text for llms.txt, not a block of the page
            continue
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
    CG, QG, DIAG = fused_grids()
    GD = groups_data()

    css  = open(os.path.join(HERE,"style.css")).read()
    body = open(os.path.join(HERE,"body.html")).read()
    app  = open(os.path.join(HERE,"app.js")).read()
    app  = app.replace("__COSTGRID__", json.dumps(CG, separators=(",",":")))
    app  = app.replace("__QUALGRID__", json.dumps(QG, separators=(",",":")))
    am, ae = GRID_ANCHOR.split("@")
    alabel = model_label(am)
    app  = app.replace("__ANCHOR_JS__", json.dumps({"m": am, "e": ae, "label": f"{alabel} @{ae}"}))
    body = body.replace("__ANCHOR_HDR__", f"{alabel.replace(' ','&nbsp;')} · {ae}")
    body = body.replace("__ANCHOR__", f"{alabel.replace(' ','&nbsp;')}&nbsp;@{ae}")
    app  = app.replace("__GROUPS_DATA__", json.dumps(GD, separators=(",",":")))
    body = body.replace("__REPO__", REPO_URL)
    body = body.replace("__NCOSTROWS__", str(DIAG["cost"]["rows"])).replace("__NSCOREROWS__", str(DIAG["quality"]["rows"]))
    ncpl = sum(len(v) for v in CG.values())                      # (model, effort) couples carried by the grids
    span = max(c[0] for v in CG.values() for c in v.values()) / min(c[0] for v in CG.values() for c in v.values())
    body = body.replace("__NCOUPLES__", str(ncpl))
    body = body.replace("__COSTSPAN__", str(round(span)))
    pre  = prerender(app, css)
    body = inject(body, pre)
    date = content_date(content_fingerprint(body, pre, [CG, QG, GD, GRID_ANCHOR]))
    body = body.replace("__GENDATE__", date.strftime("%d %b %Y"))   # last change to the content (text, figures, data)
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
    print(f"built {OUT}  ({len(html)} bytes)")
    for axis in ("cost", "quality"):
        d = DIAG[axis]
        print(f"  {axis}: {d['rows']} rows in {d['groups']} groups · set aside {d['set_aside']} · R-hat max {d['rhat_max']}"
              f" · unpublished {d['unpublished']}")
    viol = monotonicity_report(CG, QG)
    known = {("quality", "sonnet-4.6", "high", "max")}         # printed by the Sonnet 5 card itself — keyed on the rungs, not
    import re                                                   # the values, which move with the anchor and the data
    def key(v):
        m = re.match(r"(\w+): (\S+) (\w+)\([\d.]+\) > (\w+)\(", v); return m.groups() if m else None
    for v in viol:
        print(("  effort-ladder OK (documented): " if key(v) in known else "  !! EFFORT LADDER INVERTED: ") + v)

if __name__ == "__main__":
    main()
