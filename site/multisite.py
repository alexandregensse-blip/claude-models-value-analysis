#!/usr/bin/env python3
"""Multi-site generator (draft, built locally only) for models.agensse.com: the global page — every maker's current
models on one chart, frontier, price trend, tiers and crown computed across makers — and one page per model maker
(/claude/, /openai/, …), each like the Claude page: its models, its effort ladders, its tiers and crown among its own
couples, its sources table.
Run: python3 site/multisite.py  →  out/models/ (index.html, <maker>/index.html, llms.txt, robots.txt, favicons).
--local-links: links between the pages to each page's index.html, for a copy opened from the disk (default: /openai/).
The Claude page (python3 site/build.py, served at the repository root) is untouched: this reuses its page — app.js,
body.html, style.css, the pre-render — and applies the per-site settings of site/makers.json as exact text
replacements, each checked to apply exactly where expected, so a change to the page that breaks one stops this build
instead of slipping through. Rules: docs/DISPLAY-METHODOLOGY.md § 16."""
import argparse, datetime, hashlib, html as htmlmod, json, math, os, re, shutil, sys, urllib.parse

from config import HERE, ROOT, REPO_URL, DATA_URL, EFFORT_ORDER, CAP
from build import effort_columns
import duels
from grids import fused_grids, monotonicity_report
from render import inject, prerender
from sources import groups_data
sys.path.insert(0, os.path.join(ROOT, "data"))
from catalog import MODELS as CAT, MODEL_LINE, MODEL_ORDER, DISPLAY_ORDER

SET  = json.load(open(os.path.join(HERE, "makers.json"), encoding="utf-8"))
OUT  = os.path.join(ROOT, SET["out_dir"])
BASE = SET["base_url"]
DRAFT = SET.get("draft", "")            # one setting: "" removes the banner and the noindex tag on every page
LOCAL_LINKS = False                     # --local-links: links between the pages to each page's index.html, for a copy
                                        # opened from the disk; by default the published addresses (/openai/, no index.html)
DASH = ["", "6 4", "1.5 3.5"]           # a model's builds and modes: solid, dashed, dotted (hollow points)


def load_variants():
    """Price variants of a couple ({"model@effort": [{kind, label, cost_ratio, until, evidence}]}) from the registry's
    dated price records (makers.json `price_variants`: data/registry/prices.json), kinds `promotion` and `off-peak`, of
    the fit catalogue's models. A record is a variant of every couple of its model (of its configurations, when it
    lists them) when:
    - it is in force: an end the maker states (`to_basis` stated) not past today, or a record seen at the model's last
      capture on its route and currency (`to_basis` last-capture, no record of that route and currency seen later), or
      no end;
    - its route is the route of the model's base price (data/build.py's base_price, the price the published cost is at);
    - every tariff (input, output, cache, long-context tiers) is in one ratio to the base price, on the same classes
      (a record with no classes and a stated `factor` applies that factor to all of them).
    Otherwise it is not shown; each record read is listed with its outcome in out/models/price-variants.json."""
    import importlib.util, types
    spec = importlib.util.spec_from_file_location("databuild", os.path.join(ROOT, "data", "build.py"))
    DB = importlib.util.module_from_spec(spec); spec.loader.exec_module(DB)    # its price helpers (no build is run)
    path = SET["price_variants"]
    reg = json.load(open(os.path.join(ROOT, path), encoding="utf-8"))
    ctx, today = types.SimpleNamespace(prices=reg), datetime.date.today().isoformat()
    recs = reg["prices"]
    last_seen = {}                                            # (model, route, currency) → latest end of any record
    for p in recs:
        if p.get("to"): k = (p["model"], p["route"], p["currency"]); last_seen[k] = max(last_seen.get(k, ""), p["to"])
    out, log = {}, []
    for p in recs:
        if p["kind"] not in ("promotion", "off-peak") or p["model"] not in CAT: continue
        m, ev = p["model"], (p.get("evidence") or [{}])[0]
        row = dict(model=m, route=p["route"], kind=p["kind"], currency=p["currency"], classes=p.get("classes"),
                   factor=p.get("factor"), configurations=p.get("configurations"), **{"from": p["from"], "to": p.get("to")},
                   to_basis=p.get("to_basis"), url=ev.get("url"), quote=ev.get("quote"), note=p.get("note"))
        log.append(row)
        end = (p.get("to") or "")[:10]
        if p.get("to") and p.get("to_basis") == "stated" and end < today:
            row["outcome"] = f"ended {end} (stated end)"; continue
        if p.get("to") and p.get("to_basis") != "stated" and p["to"] < last_seen[(m, p["route"], p["currency"])]:
            row["outcome"] = f"last seen {end}, the model's prices seen later on that route without it"; continue
        if p["from"][:10] > today:
            row["outcome"] = "not yet in force"; continue
        cfgs = p.get("configurations") or [None]
        bases = [DB.base_price(ctx, m, currency=p["currency"], config=c) for c in cfgs]
        if any(b is None for b in bases):
            row["outcome"] = f"no base price in {p['currency']}"; continue
        if any(b["route"] != p["route"] for b in bases):
            row["outcome"] = f"route {p['route']} is not the base price's ({bases[0]['route']})"; continue
        ratios = []
        for b in bases:
            bv, vv = DB.price_vector(b), DB.price_vector(p)
            if not vv and p.get("factor"):
                ratios.append(float(p["factor"])); continue
            ratios.append(DB.uniform_ratio(vv, bv) if set(vv) == set(bv) else None)
            if ratios[-1] is None:
                row["outcome"] = ("tariffs not in one ratio to the base price " if set(vv) == set(bv) else
                                  "not the base price's classes ") + json.dumps({k: [vv.get(k), bv.get(k)] for k in sorted(set(vv) | set(bv))})
        if None in ratios or max(ratios) - min(ratios) > 1e-9:
            row.setdefault("outcome", "ratio differs between configurations"); continue
        r = ratios[0]
        if not 0 < r < 1:
            row["outcome"] = f"ratio {r:g} to the base price: not a reduction"; continue
        row["outcome"], row["cost_ratio"] = "shown", r
        stated = p.get("to_basis") == "stated" and p.get("to")
        label = (("promotional price" if p["kind"] == "promotion" else "off-peak rate") + f" ({r:.3g}× the list price"
                 + (f", until {end}" if stated else f", last seen {end}" if p.get("to") else "") + ")")
        v = {"kind": "promo" if p["kind"] == "promotion" else "offpeak", "label": label, "cost_ratio": r,
             "until": end if stated else None, "seen": None if stated else (end or p["from"][:10]), "evidence": ev.get("url")}
        effs = set(CAT_EFFORTS.get(m, []))
        for e in sorted(effs):
            if p.get("configurations") and e not in p["configurations"]: continue
            lst = out.setdefault(f"{m}@{e}", [])
            if not any(x["kind"] == v["kind"] and abs(x["cost_ratio"] - r) < 1e-9 for x in lst):   # one per kind and ratio
                lst.append(v)
    return path, out, log


esc = lambda s: htmlmod.escape(s, quote=True)
warn = lambda s: print("  !! " + s)
CAT_EFFORTS = {}                                              # model → efforts of its couples in the fit
for _ax in ("cost", "quality"):
    for _c in json.load(open(os.path.join(ROOT, "model", "fit-cache.json")))[_ax]:
        _m, _e = _c.split("@"); CAT_EFFORTS.setdefault(_m, set()).add(_e)
VARIANTS_FILE, VARIANTS, VARIANTS_LOG = load_variants()


# ---------------------------------------------------------------- per-site models, labels, colours
def maker_keys(mk):
    """A maker's catalogue keys in legend order: each base model of its settings, then that model's lines (the
    catalogue's dated builds, previews and modes), in catalogue order. Warns about a key of the maker's prefixes
    that the settings do not place."""
    M = SET["makers"][mk]
    if M.get("from_claude_page"):                             # the Claude page's own models, in its legend order
        return list(DISPLAY_ORDER)
    lines_of = {}
    for k in MODEL_ORDER:
        if k in MODEL_LINE: lines_of.setdefault(MODEL_LINE[k], []).append(k)
    keys = []
    for b in M["models"]:
        keys += [b] + lines_of.get(b, [])
    for k in MODEL_ORDER:
        if any(k.startswith(p) for p in M["prefixes"]) and k not in keys:
            warn(f"{mk}: catalogue key {k} is not placed in site/makers.json (left out)")
    return keys


def oklch_hex(L, C, h):
    """OKLCH → sRGB hex, chroma reduced until the colour fits in sRGB."""
    for k in range(21):
        c = C * (1 - k / 20); a, b = c * math.cos(math.radians(h)), c * math.sin(math.radians(h))
        l_, m_, s_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3, (L - 0.1055613458 * a - 0.0638541728 * b) ** 3, \
                     (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
        rgb = [4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
               -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
               -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_]
        if all(-1e-4 <= v <= 1 + 1e-4 for v in rgb):
            enc = lambda v: round(255 * (12.92 * v if v <= 0.0031308 else 1.055 * max(v, 0) ** (1 / 2.4) - 0.055))
            return "#" + "".join(f"{min(255, max(0, enc(v))):02x}" for v in rgb)
    return "#808080"


def page_models(site, keys, CG):
    """MODELS for app.js ({key: {label, c, base?, bl?, lt?, ls?, tag?}}, legend order) and the CSS of its colours.
    One colour per model; its lines share it and are told apart by their stroke (DASH) and their label."""
    groups = []                                               # [(base, [keys with couples])]
    for k in keys:
        if k not in CG: continue
        b = MODEL_LINE.get(k, k)
        if groups and groups[-1][0] == b: groups[-1][1].append(k)
        else: groups.append((b, [k]))
    out, light, dark = {}, [], []
    by_maker = {}
    for b, ks in groups: by_maker.setdefault(site["maker_of"][ks[0]], []).append(b)
    colour = {}
    for mk, bases in by_maker.items():
        M = SET["makers"][mk]
        if site["id"] != "global" and M.get("colours") == "catalog":   # the Claude page's own colours
            for b in bases: colour[b] = None
            continue
        n = len(bases)
        for i, b in enumerate(bases):
            if site["id"] == "global":                        # one hue per maker, its models in steps of lightness
                f = i / max(n - 1, 1); h = M["hue"] + (f - 0.5) * 24
                C = M.get("chroma", 0.15)                     # a maker without a hue of its own: near grey
                colour[b] = (oklch_hex(0.42 + 0.24 * f, C, h), oklch_hex(0.64 + 0.20 * f, C * 0.87, h))
            else:                                             # one maker: hues a golden angle apart
                h = M["hue"] + i * 137.508
                colour[b] = (oklch_hex(0.55, 0.15, h), oklch_hex(0.76, 0.13, h))
    for i, (b, ks) in enumerate(groups):
        mk = site["maker_of"][ks[0]]
        if colour[b] is None:
            var = CAT[ks[0]]["colour"]
        else:
            var = f"--mc{i}"; light.append(f"{var}:{colour[b][0]}"); dark.append(f"{var}:{colour[b][1]}")
        bl = site["label"](b)
        tags = [site["tag"](k) for k in ks if k != b]
        for j, k in enumerate(ks):
            e = {"label": bl if k == b else f"{bl} {site['tag'](k)}", "c": var}
            if len(ks) > 1 or k != b:
                e.update(base=b, bl=bl, ls=min(j, len(DASH) - 1),
                         lt=site["tag"](k) if k != b else ("standard" if tags and all(t == "Pro" for t in tags) else "original release"))
            if CAT[k].get("flag_task_size"): e["tag"] = True
            out[k] = e
    return out, (";".join(light), ";".join(dark))


def with_colours(css, light, dark):
    """The page's model colours, written into each of style.css's four theme blocks (the pre-render reads the first
    :root block for the light theme)."""
    if not light: return css
    return patch(css, [("@media (prefers-color-scheme:dark){:root{\n", f"@media (prefers-color-scheme:dark){{:root{{{dark};\n"),
                       (":root{\n", f":root{{{light};\n"),
                       (':root[data-theme="dark"]{\n', f':root[data-theme="dark"]{{{dark};\n'),
                       (':root[data-theme="light"]{\n', f':root[data-theme="light"]{{{light};\n')], "style.css")


# ---------------------------------------------------------------- the sites
def sites():
    """The global page and one page per maker, as settings the page builder reads."""
    out, maker_of = [], {}
    for mk, M in SET["makers"].items():
        for k in maker_keys(mk): maker_of[k] = mk
    def labeller(prefix):
        def label(k):
            mk = maker_of.get(k)
            M = SET["makers"][mk] if mk else {}
            name = CAT[k]["label"] if M.get("from_claude_page") else M.get("models", {}).get(k)
            if name is None:
                warn(f"no label for {k} in site/makers.json: the catalogue key is shown"); name = k
            return prefix.get(mk, "") + name
        return label
    def tag(k):
        t = SET["makers"][maker_of[k]]["lines"].get(k)
        if t is None:
            warn(f"no tag for the line {k} in site/makers.json: the catalogue key is shown"); t = k
        return t
    G = SET["global"]
    gkeys = [k for mk in SET["makers"] for k in maker_keys(mk)]
    FAM = dict(SET["families"])
    for mk, M in SET["makers"].items():                       # Claude: the Claude page's CURRENT and LEGACY (site/duels.py)
        if M.get("from_claude_page"):
            for k in maker_keys(mk):
                if k in FAM: sys.exit(f"!! {k}: a Claude key in the families of site/makers.json (it follows site/duels.py)")
                FAM[k] = {"current": k in duels.CURRENT, "hidden": k in duels.LEGACY, "source": "site/duels.py"}
    for k in maker_of:
        if k not in FAM: warn(f"no family entry for {k} in site/makers.json: shown, not current")
    is_cur = lambda k: FAM.get(k, {}).get("current", False)
    gcur = [k for k in gkeys if is_cur(k)]
    out.append(dict(G, id="global", name="All makers", keys=gkeys, current=gcur, legacy=None, maker_of=maker_of,
                    label=labeller(G.get("label_prefix", {})), tag=tag))
    for mk, M in SET["makers"].items():
        s = dict(title=f"{M['name']} models compared: cost vs quality at every effort level",
                 site_name=f"{M['name']} models cost vs quality",
                 description=(f"What each {M['name']} model costs at every effort level, and which gives the best "
                              f"quality for the price. Open data, CC BY 4.0."),
                 h1=f"{M['name']} models compared <span class=\"h1-line\">cost vs quality at every effort level</span>",
                 lede=(f"What each recent {M['name']} model actually costs, at every effort level, and the quality it "
                       f"delivers — fused from public benchmark measurements for every (model, effort) pair, on the "
                       f"same scales as every other maker's on this site."),
                 noun=M["name"], hide_landscape=[], hide_note="",
                 generation=None if M.get("from_claude_page") else SET["global"]["generation"])
        s.update({k: v for k, v in M.items() if k in s})
        mkeys = maker_keys(mk)
        s.update(id=mk, name=M["name"], path=M["path"], keys=mkeys, current=[k for k in mkeys if is_cur(k)],
                 legacy=[k for k in mkeys if FAM.get(k, {}).get("hidden", False)],
                 maker_of=maker_of, label=labeller({}), tag=tag)
        out.append(s)
    return out


# ---------------------------------------------------------------- page text: exact replacements
def patch(text, reps, what):
    for rep in reps:
        old, new, want = rep if len(rep) == 3 else (*rep, 1)
        n = text.count(old) if isinstance(old, str) else len(old.findall(text))
        if n != want:
            sys.exit(f"!! {what}: expected {want} occurrence(s) of {old if isinstance(old, str) else old.pattern!r:.90}, found {n}")
        text = text.replace(old, new) if isinstance(old, str) else old.sub(lambda m: new, text)
    return text


LEGEND_FN = r'''
// Legend: no model list (the frontier's labels and the tooltips name the couples); the symbols only: a model's
// builds and modes (a dated build, a preview, a Pro mode) as hollow points, and the price variants.
const lsty=m=>MODELS[m].ls||0;
function legendSymbols(ms){
  const ink=cvar('--ink'), hollow=ms.some(m=>lsty(m)), on=k=>ms.includes(k.split("@")[0]);
  const pk=Object.keys(PROMO).some(on), ok=Object.keys(VARIANTS).some(k=>on(k)&&VARIANTS[k].some(v=>v.kind!=="promo"));
  const dia=`<svg class="lgs" width="30" height="10" aria-hidden="true"><line x1="2" y1="5" x2="23" y2="5" stroke="${ink}" stroke-width="1.2" stroke-dasharray="1.5 3"/><path d="M 24 1 L 28 5 L 24 9 L 20 5 Z" fill="${cvar('--panel')}" stroke="${ink}" stroke-width="1.4"/></svg>`;
  return (hollow?`<span class="lg"><svg class="lgs" width="12" height="10" aria-hidden="true"><circle cx="6" cy="5" r="3.4" fill="${cvar('--panel')}" stroke="${ink}" stroke-width="1.6"/></svg>hollow point: another build or mode of a model (a dated build, a preview, a Pro mode), named in its label</span>`:"")
    +(pk?`<span class="lg">${dia}a couple on promotion: the filled point is its promotional price, the price in force (every pick reads it); the hollow diamond its list price</span>`:"")
    +(ok?`<span class="lg">${dia}the same couple at an off-peak rate (some hours only) — shown, never used in a pick</span>`:""); }
// Global page: the couples of older models that another model of the same maker strictly beats, hidden by default.
function hideCouples(){ Object.keys(HIDE_C).forEach(m=>[[COSTGRID,GRID_ALL.cost],[QUALGRID,GRID_ALL.qual]].forEach(([G,A])=>{ if(!A[m]) return;
  G[m]=showLegacy?A[m]:Object.fromEntries(Object.entries(A[m]).filter(([e])=>!HIDE_C[m].includes(e))); })); }
// The other prices of a couple, each a hollow diamond joined to its couple by a dotted line, named in tooltips and
// tables, never a candidate of the frontier, the trend, the tiers or the crown: the LIST price of a couple on
// promotion (its point is at the promotional price, the price in force: PROMO), and an off-peak rate (some hours only).
const VTAG={promo:"promo",offpeak:"off-peak"};
const listOf=k=>PROMO[k]?1/PROMO[k].cost_ratio:1;            // list price ÷ the price shown
function variantPts(pts){ const o=[]; pts.forEach(p=>{ const k=p.m+"@"+p.e, li=listOf(k), b={m:p.m,e:p.e,t:p.t,s:p.s,base:p,front:p.front};
  if(PROMO[k]) o.push({...b,c:p.c*li,vl:`list price (${promoTag(k)})`,tag:"list"});
  (VARIANTS[k]||[]).forEach(v=>{ if(v.kind!=="promo") o.push({...b,c:p.c*li*v.cost_ratio,vl:v.label,tag:VTAG[v.kind]||v.kind}); }); }); return o; }
function drawVariants(s,pts,X,Y,fade){ variantPts(pts).forEach(v=>{ const col=cvar(MODELS[v.m].c), op=fade&&!v.front?0.3:0.9, x=X(v.c), y=Y(v.t), r=4.6;
  s.appendChild(el("line",{x1:X(v.base.c),y1:y,x2:x,y2:y,stroke:col,"stroke-width":1.3,"stroke-dasharray":"1.5 3","stroke-opacity":op}));
  s.appendChild(el("path",{d:`M ${x} ${y-r} L ${x+r} ${y} L ${x} ${y+r} L ${x-r} ${y} Z`,fill:cvar('--panel'),stroke:col,"stroke-width":1.6,"stroke-opacity":op})); }); }
const vSegs=(pts,X,Y)=>variantPts(pts).map(v=>[X(v.base.c),Y(v.t),X(v.c),Y(v.t)]);   // a variant's dotted line
// Under a cost or a value: the promotion in force and the list price; an off-peak rate. f(rel) writes the figure at
// rel × the price shown.
const vNotes=(m,e,f)=>{ const k=m+"@"+e, li=listOf(k);
  return (PROMO[k]?`<small class="vnote" title="${PROMO[k].label}">${promoTag(k)} · list ${f(li)}</small>`:"")
    +(VARIANTS[k]||[]).filter(v=>v.kind!=="promo").map(v=>`<small class="vnote" title="${v.label}">${VTAG[v.kind]||v.kind} ${f(li*v.cost_ratio)}</small>`).join(""); };
const vNote=(m,e,c)=>vNotes(m,e,rel=>fmtC(c*rel)+"×");
const pTag=p=>PROMO[p.m+"@"+p.e]?" · "+promoTag(p.m+"@"+p.e):"";   // after a couple's name: "· promo until 30 Nov"
// Selection (the bar above the first chart): FILT.items are the page's makers (global page) or its models (a maker
// page); OFF the items turned off. The page's grids are rebuilt from the full copy with only the couples shown — the
// older-model switch, the beaten couples and the selection — so the charts, the tables, the frontier and its labels are
// taken on what is shown. The price trend is not: it stays the default view's (trendRows), so the crown, the
// "× cheaper" and the tiers read against the same trend whatever the selection (the maintainer, 19 Nov 2026). The
// selection is kept in the address (#makers=… or #models=…, the items shown turned on; none when all are on).
const selOK=m=>!OFF.has(FILT.of[m]);
const visItems=()=>{ const v=new Set(Object.keys(MODELS).filter(m=>showLegacy||!LEGACY.includes(m)).map(m=>FILT.of[m])); return FILT.items.filter(i=>v.has(i.id)); };
const LG_LAB=`<span class="lgt">model · effort</span>the Pareto frontier's couples, labelled where there is room`;
// The price trend's couples: those of the default view — every current model of the page, every maker and model on,
// older models off — whatever the selection (the maintainer, 19 Nov 2026: « desactiver un fabricant ne doit pas
// recalculer la tendance des prix »). Same rows, in the same order, as couples() gives fitTrend by default.
var TREND_FIXED=null;
function trendRows(){ if(TREND_FIXED) return TREND_FIXED; const rows=[];
  Object.keys(GRID_ALL.cost).forEach(m=>{ if(!CURRENT.includes(m)||LEGACY.includes(m)) return; const cg=GRID_ALL.cost[m], qg=GRID_ALL.qual[m]||{};
    for(const e in cg){ if(HIDE_C[m]&&HIDE_C[m].includes(e)) continue; const q=qg[e]; if(q) rows.push({m,e,x:cg[e][0],hx:cg[e][1],t:q[0],ht:q[1]}); } });
  return TREND_FIXED=rows; }
function shownGrid(o){ const C={},Q={}, keys=[...new Set([...Object.keys(GRID_ALL.cost),...Object.keys(GRID_ALL.qual)])];
  keys.forEach(m=>{ if(o.has(FILT.of[m])||(LEGACY.includes(m)&&!showLegacy)) return;
    const f=A=>HIDE_C[m]&&!showLegacy?Object.fromEntries(Object.entries(A).filter(([e])=>!HIDE_C[m].includes(e))):A;
    if(GRID_ALL.cost[m]) C[m]=f(GRID_ALL.cost[m]); if(GRID_ALL.qual[m]) Q[m]=f(GRID_ALL.qual[m]); });
  return {C,Q}; }
// A selection the page can draw: the tiers need two frontier couples (the price trend, the default view's, needs none).
function selValid(o){ const {C,Q}=shownGrid(o), rows=[];
  for(const m in C) for(const e in C[m]) if(Q[m]&&Q[m][e]) rows.push({m,e,x:C[m][e][0],t:Q[m][e][0]});
  return frontier(rows).front.length>=2; }
function applyFilter(){ const {C,Q}=shownGrid(OFF); Object.keys(COSTGRID).forEach(m=>delete COSTGRID[m]); Object.keys(QUALGRID).forEach(m=>delete QUALGRID[m]);
  Object.assign(COSTGRID,C); Object.assign(QUALGRID,Q); }
function readSel(){ let h=""; try{ h=typeof location!=="undefined"?decodeURIComponent(location.hash||""):""; }catch(e){}
  const mt=h.match(new RegExp("[#&]"+FILT.key+"=([^&]*)")); if(!mt) return new Set();
  const on=new Set(mt[1].split(",").filter(Boolean)), o=new Set(visItems().map(i=>i.id).filter(id=>!on.has(id)));
  return selValid(o)?o:new Set(); }
function writeSel(){ try{ if(typeof history==="undefined"||typeof location==="undefined") return;
  const v=visItems().map(i=>i.id), on=v.filter(id=>!OFF.has(id));
  history.replaceState(null,"",on.length<v.length?"#"+FILT.key+"="+on.join(","):location.pathname+location.search); }catch(e){} }
let OFF=readSel();
function setSel(o){ const fid=document.activeElement?.id; OFF=o; writeSel(); applyLegacy(); tierDefaults(); renderAll(); if(fid) document.getElementById(fid)?.focus(); }
function selToggle(id){ const o=new Set(OFF); if(o.has(id)) o.delete(id); else o.add(id); if(selValid(o)) setSel(o); }
function selAll(){ setSel(new Set()); }
function renderFilterBar(){ const host=document.getElementById("filterbar"); if(!host) return;
  const vis=visItems();
  const chip=i=>{ const on=!OFF.has(i.id), o=new Set(OFF); o.add(i.id); const lock=on&&!selValid(o);
    return `<button type="button" class="fchip" id="fchip-${i.id}" aria-pressed="${on}"${lock?` aria-disabled="true" title="${FILT.lock}"`:""} style="--fc:${cvar(i.c)}" onclick="selToggle('${i.id}')"><span class="fchip-dot" aria-hidden="true"></span>${i.label}</button>`; };
  host.innerHTML=`<span class="fbar-lbl">Filter by ${FILT.key==="makers"?"maker":"model"}</span><button type="button" class="fchip fchip-all" id="fchip-all" aria-pressed="${vis.every(i=>!OFF.has(i.id))}" onclick="selAll()">All</button>`
    +vis.map(chip).join("")
    +(LEGACY.length?`<button type="button" class="fchip fchip-old" id="tgl-legacy-f" role="switch" aria-checked="${showLegacy}" title="${LEGACY_HINT}" onclick="toggleLegacy()"><span class="fchip-dot" aria-hidden="true"></span>Older models</button>`:""); }
function fillNtrend(){ document.querySelectorAll(".ntrend").forEach(e=>e.textContent=String(trendRows().length)); }
if(typeof addEventListener==="function") addEventListener("hashchange",()=>{ OFF=readSel(); applyLegacy(); tierDefaults(); renderAll(); });
// The Pareto frontier's couples carry a label on the charts, "model · effort", small (11 px on screen, whatever the
// width), muted, without background or frame; any other point is named by the tooltip. Labels keep their size on screen.
const pxu=s=>{ const w=typeof s.getBoundingClientRect==="function"?s.getBoundingClientRect().width:0; return w>0?1100/w:1; };   // SVG units per screen pixel
const HL={};                                                // owner (chart id) → {couple key: [set(on)]}
function hlFront(k){ for(const o in HL) for(const kk in HL[o]) HL[o][kk].forEach(f=>f(kk===k)); }
function frontRows(pts){ const fr=frontier(couples()).front, by={}; pts.forEach(p=>{ by[p.m+"@"+p.e]=p; });
  return fr.map(p=>by[p.m+"@"+p.e]).filter(Boolean); }
const flText=p=>`${MODELS[p.m].label}${p.e==="solo"?"":" · "+capE(p.e)}${pTag(p)}`;
let MCTX=null;                                              // text width: the browser's own measure, else 0.6 em a character
function textPx(s,t,fs){ try{ if(MCTX===null){ const c=document.createElement("canvas"); MCTX=c&&c.getContext?c.getContext("2d"):false; }
    if(MCTX){ MCTX.font=`${fs}px ${getComputedStyle(s).fontFamily||"sans-serif"}`; const w=MCTX.measureText(t).width; if(w>0) return w; } }catch(e){ MCTX=false; }
  return 0.6*fs*t.length; }
// Segment × box (Liang–Barsky): does the segment cross the box?
function segHits(x1,y1,x2,y2,b){ let t0=0,t1=1; const dx=x2-x1, dy=y2-y1;
  for(const [p,q] of [[-dx,x1-b.x0],[dx,b.x1-x1],[-dy,y1-b.y0],[dy,b.y1-y1]]){
    if(p===0){ if(q<0) return false; } else { const r=q/p; if(p<0){ if(r>t1) return false; if(r>t0) t0=r; } else { if(r<t0) return false; if(r<t1) t1=r; } } }
  return true; }
// Segment × segment: do they cross (or touch)?
function segX(a,b){ const o=(p,q,r)=>Math.sign((q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0]));
  const A=[a[0],a[1]],B=[a[2],a[3]],C=[b[0],b[1]],D=[b[2],b[3]];
  return o(A,B,C)!==o(A,B,D)&&o(C,D,A)!==o(C,D,B); }
// Placement: each label (cost order) goes to the first free spot around its point, nearest first — beside it, starting
// up-left, the side of the frontier no couple can occupy — whose box, with a margin, overlaps no label already placed,
// no point and no line of the chart (the frontier, a variant's dotted line). A label set off its point (beyond the
// first ring) gets a short leader line, thin and muted, from the point's edge to the label's box; a spot is free only
// if that line crosses no other leader line and no other label, and no leader line already drawn crosses the label.
// A label with no free spot is left out; its point reads on hover or tap. s.__labels counts them.
function frontLabels(s,id,F,obst,segs,X,Y,mL,mT,iw,ih){ const u=pxu(s), fs=11*u, h=13*u, m=1.5*u, reg=HL[id]={}, placed=[], leads=[];
  const pp=obst.map(p=>[X(p.c),Y(p.t)]), pr=6.5+m;           // a point: its largest mark (r 5.6, a diamond 4.6) and the margin
  const grow=(b,g)=>({x0:b.x0-g,y0:b.y0-g,x1:b.x1+g,y1:b.y1+g});
  const free=b=>b.x0>=mL&&b.x1<=mL+iw&&b.y0>=mT&&b.y1<=mT+ih
    &&!placed.some(q=>b.x0<q.x1+m&&q.x0<b.x1+m&&b.y0<q.y1+m&&q.y0<b.y1+m)
    &&!pp.some(([px,py])=>{ const cx=Math.max(b.x0,Math.min(px,b.x1)), cy=Math.max(b.y0,Math.min(py,b.y1)); return Math.hypot(px-cx,py-cy)<pr; })
    &&!segs.some(g=>segHits(g[0],g[1],g[2],g[3],grow(b,m)))
    &&!leads.some(g=>segHits(g[0],g[1],g[2],g[3],grow(b,m)));
  // the leader line of a box set off its point: from the point's edge (5.6 + 1 units) to 1 px short of the box
  const lead=(ax,ay,b)=>{ const cx=Math.max(b.x0,Math.min(ax,b.x1)), cy=Math.max(b.y0,Math.min(ay,b.y1)), d=Math.hypot(cx-ax,cy-ay);
    if(!(d>6.6+2*u)) return null; const ux=(cx-ax)/d, uy=(cy-ay)/d; return [ax+ux*6.6,ay+uy*6.6,cx-ux*u,cy-uy*u]; };
  const leadOK=g=>!leads.some(o=>segX(g,o))&&!placed.some(q=>segHits(g[0],g[1],g[2],g[3],grow(q,m)));
  let hidden=0;
  F.forEach(p=>{ const ax=X(p.c), ay=Y(p.t), t=flText(p), w=textPx(s,t,fs); let best=null, bl=null;
    if(ax<mL||ax>mL+iw||ay<mT||ay>mT+ih){ return; }
    for(let ring=0; ring<4&&!best; ring++){ const d=pr+ring*4*u, dd=d*0.7;
      const cand=[[ax-dd-w,ay-dd-h],[ax-d-w,ay-h/2]];          // up-left, left, then above and below sliding along, right, the corners
      for(const f of [1,0.75,0.5,0.25,0]) cand.push([ax-f*w,ay-d-h]);
      cand.push([ax+dd,ay+dd],[ax+d,ay-h/2]);
      for(const f of [0,0.25,0.5,0.75,1]) cand.push([ax-f*w,ay+d]);
      cand.push([ax+dd,ay-dd-h],[ax-dd-w,ay+dd]);
      for(const [x0,y0] of cand){ const b={x0,y0,x1:x0+w,y1:y0+h}; if(!free(b)) continue;
        const g=ring?lead(ax,ay,b):null; if(g&&!leadOK(g)) continue;
        best=b; bl=g; break; } }
    if(!best){ hidden++; return; }
    const col=cvar(MODELS[p.m].c), k=p.m+"@"+p.e;
    let ln=null; if(bl){ ln=el("line",{class:"flead","data-k":k,x1:bl[0],y1:bl[1],x2:bl[2],y2:bl[3],stroke:cvar('--muted'),"stroke-width":0.8*u,"stroke-opacity":0.6}); s.appendChild(ln); leads.push(bl); }
    const tx=el("text",{class:"flabel","data-k":k,x:best.x0,y:best.y1-3*u,"font-size":fs,fill:cvar('--muted'),"text-anchor":"start"}); tx.textContent=t;
    s.appendChild(tx);
    (reg[k]=reg[k]||[]).push(on=>{ tx.setAttribute("fill",on?col:cvar('--muted')); if(ln) ln.setAttribute("stroke",on?col:cvar('--muted')); });
    placed.push({...best,x:(best.x0+best.x1)/2,y:(best.y0+best.y1)/2,w,h,p,k}); });
  s.__labels={shown:placed.length,hidden,frontier:F.length,leaders:leads.length};
  return placed; }
if(typeof addEventListener==="function"){ let rw=0; addEventListener("resize",()=>{ const s=document.getElementById("chartB"), w=s?s.getBoundingClientRect().width:0;
  if(w&&Math.abs(w-rw)>1){ rw=w; drawB(); drawPareto(); } }); }   // the labels and the tooltip keep their size on screen
'''

PRICES_FN = r'''// PRICES IN FORCE (the maintainer, 19 Nov 2026: « les promotion ne sont pas prises en compte dans les annotations et
// les scores / pareto »). A promotion kept (VARIANTS, kind promo: every tariff in one ratio, no stated end past) is the
// price the couple sells at today, for everyone: it replaces the list price in every decision — the frontier and its
// labels, the price trend, the value, the tiers and the crown, the outclassed models, the tables. The page is static:
// it compares the reader's date with the promotion's stated end, so an ended promotion goes back to the list price and
// everything below is taken again on load (the pre-render runs at the build date). An off-peak rate holds at some hours
// only, not for everyone: it stays a variant, out of every decision.
const TODAY=(d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`)(new Date());
const PROMO={};                                             // "model@effort" → the promotion in force (the lowest price)
for(const k in VARIANTS) VARIANTS[k].forEach(v=>{ if(v.kind!=="promo"||(v.until&&v.until<TODAY)) return;
  if(!PROMO[k]||v.cost_ratio<PROMO[k].cost_ratio) PROMO[k]=v; });
for(const k in PROMO){ const [m,e]=k.split("@"); if(!COSTGRID[m]||!COSTGRID[m][e]){ delete PROMO[k]; continue; }
  COSTGRID[m]={...COSTGRID[m],[e]:[COSTGRID[m][e][0]+Math.log(PROMO[k].cost_ratio),COSTGRID[m][e][1]]}; }
const MON=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const fmtD=d=>{ const [y,mo,da]=d.split("-").map(Number); return `${da} ${MON[mo-1]}${y!==+TODAY.slice(0,4)?" "+y:""}`; };
const promoTag=k=>{ const v=PROMO[k]; return v?(v.until?`promo until ${fmtD(v.until)}`:`promo, seen ${fmtD(v.seen)}`):""; };
// At these prices: the models another model of their maker entirely outclasses (site/multisite.py outclassed()), the
// current models (the trend's couples), the older models and, on the global page, the beaten couples hidden by default.
(function(){ const E=1e-9, dom=(o,p)=>o[0]<=p[0]+E&&o[1]>=p[1]-E&&(o[0]<p[0]-E||o[1]>p[1]+E);
  const shown=Object.keys(MODELS).filter(k=>COSTGRID[k]), CG=COSTGRID, QG=QUALGRID, pts={};
  shown.forEach(k=>{ pts[k]=Object.keys(CG[k]).map(e=>[CG[k][e][0],QG[k][e][0]]); });
  shown.forEach(a=>{ const bs=shown.filter(b=>b!==a&&MAKER_OF[b]===MAKER_OF[a]&&pts[a].every(p=>pts[b].some(o=>dom(o,p)))); if(bs.length) OUTCLASSED[a]=bs; });
  CUR_BASE.forEach(k=>{ if(CG[k]&&!OUTCLASSED[k]) CURRENT.push(k); });
  if(LEG_BASE===null){ const base=k=>MODELS[k].base||k, hc={};      // global page: the couples another model of its maker strictly beats
    const beaten=(k,e)=>shown.some(k2=>MAKER_OF[k2]===MAKER_OF[k]&&base(k2)!==base(k)&&Object.keys(CG[k2]).some(e2=>CG[k2][e2][0]<CG[k][e][0]&&QG[k2][e2][0]>QG[k][e][0]));
    shown.forEach(k=>{ if(CURRENT.includes(k)) return; const out=Object.keys(CG[k]).filter(e=>beaten(k,e)); if(out.length) hc[k]=out; });
    shown.forEach(k=>{ if(OUTCLASSED[k]||(hc[k]||[]).length===Object.keys(CG[k]).length) LEGACY.push(k); });
    for(const k in hc) if(!LEGACY.includes(k)) HIDE_C[k]=hc[k];
    const n=LEGACY.reduce((a,k)=>a+Object.keys(CG[k]).length,0)+Object.values(HIDE_C).reduce((a,v)=>a+v.length,0);
    LEGACY_HINT=`${n} couples that another model of the same maker beats`; }
  else { shown.forEach(k=>{ if(LEG_BASE.includes(k)||OUTCLASSED[k]) LEGACY.push(k); });
    const names=LEGACY.filter(k=>!MODELS[k].ls).map(k=>MODELS[k].bl||MODELS[k].label);
    LEGACY_HINT=names.length<=3||HINT_ALL?names.join(" · "):names.slice(0,2).join(" · ")+` and ${names.length-2} more`; } })();
'''

TIER_Q_HEAD = r'''// DATA-DERIVED targets, multi-site (the maintainer, 19 Nov 2026: « j'ai l'impression que les tiers sont hyper bas
// maintenant, remonte le seuil de perf min pour grunt », then « B »): the four θ* are the 20th, 40th, 60th and 80th
// percentiles (TIER_Q) of θ over every couple shown on the page — couples(), the selection and the older-model switch in
// force —, linearly interpolated between the sorted values at rank f·(n − 1). They depend on θ only, not on the prices,
// and are taken again on what is shown when the selection changes. σ follows the mean spacing of the targets,
// gap = (θ*₄ − θ*₁) ⁄ 3: adjacent windows cross at half weight midway, σ = gap ⁄ (2·√ln 2).
const TIER_Q=[0.2,0.4,0.6,0.8];
'''

TIER_Q_FN = r'''function tierDefaults(){
  const th=couples().map(p=>p.t).sort((x,y)=>x-y), n=th.length; if(!n) return;
  const q=f=>{ const i=f*(n-1), j=Math.floor(i), k=Math.min(j+1,n-1); return th[j]+(th[k]-th[j])*(i-j); };   // linear between sorted values
  const ts=TIER_Q.map(q), lo=ts[0], hi=ts[ts.length-1], gap=(hi-lo)/Math.max(TIERS.length-1,1), sig=gap/(2*Math.sqrt(Math.LN2));
  TIERS.forEach((T,i)=>{ T.t=ts[i]; T.sig=sig; });
  TIERQ={lo,hi,gap,sig};
}
'''

HOVER_FN = r'''function hoverTip(s,ells,pts,X,Y,mL,iw,bdg){ const DEF=0.15,HOV=0.78;   // multi-site: the frontier's labels, a tooltip of fixed size on screen
  const tip=el("g",{"pointer-events":"none",opacity:0}), trect=el("rect",{rx:3,fill:cvar('--panel'),stroke:cvar('--line'),"stroke-width":1,"fill-opacity":0.97});
  const ttxt=el("text",{"font-size":9.5,"font-weight":600,"text-anchor":"middle"}); tip.appendChild(trect); tip.appendChild(ttxt); s.appendChild(tip);
  s.onmousemove=ev=>{ const P=new DOMPoint(ev.clientX,ev.clientY).matrixTransform(s.getScreenCTM().inverse()), u=pxu(s), touch=!!ev.pointerType&&ev.pointerType!=="mouse";
    ells.forEach(o=>{ const dx=P.x-o.cx, dy=P.y-o.cy, rx=dx>0?o.rxR:o.rxL, ry=dy>0?o.ryD:o.ryU; o.el.setAttribute("opacity",((dx/rx)**2+(dy/ry)**2<=1)?HOV:DEF); });
    let hit=null, best=null, bd=(touch?22:7)*u, hd=touch?6*u:0;   // the nearest: a label (from its box, 0 inside) or a point (from its centre)
    (bdg||[]).forEach(b=>{ const d=Math.max(0,Math.abs(P.x-b.x)-b.w/2,Math.abs(P.y-b.y)-b.h/2); if(d<=hd){ hd=d; hit=b; } });
    pts.forEach(p=>{ const d=Math.hypot(P.x-X(p.c),P.y-Y(p.t)); if(d<bd){ bd=d; best=p; } });
    if(hit&&(!best||hd===0||hd<bd)) best=hit.p; else hit=null;
    const k=best&&!best.vl?best.m+"@"+best.e:null; hlFront(k);
    if(best){ const fs=11.5*u, y0=hit?hit.y-hit.h/2-6*u:Y(best.t)-10*u;
      const name=`${MODELS[best.m].label} · ${capE(best.e)}${best.vl?" · "+best.vl:pTag(best)}`, val=`cost ${fmtC(best.c)}× · score ${pct(best.s)}`;
      ttxt.setAttribute("font-size",fs); ttxt.setAttribute("fill",cvar(MODELS[best.m].c)); ttxt.setAttribute("x",X(best.c)); ttxt.setAttribute("y",y0);
      ttxt.textContent=`${name} — ${val}`; let bb=ttxt.getBBox(), sp=[];
      if(bb.width>iw-10*u){ ttxt.textContent=""; sp=[el("tspan",{dy:-fs*1.2}),el("tspan",{dy:fs*1.2})]; sp[0].textContent=name; sp[1].textContent=val;
        sp.forEach(t=>ttxt.appendChild(t)); bb=ttxt.getBBox(); }
      const half=bb.width/2+5*u, x=Math.min(Math.max(X(best.c),mL+half),mL+iw-half);
      ttxt.setAttribute("x",x); sp.forEach(t=>t.setAttribute("x",x)); bb=ttxt.getBBox();
      trect.setAttribute("x",bb.x-4*u); trect.setAttribute("y",bb.y-2*u); trect.setAttribute("width",bb.width+8*u); trect.setAttribute("height",bb.height+4*u);
      trect.setAttribute("rx",3*u); trect.setAttribute("stroke-width",u); tip.setAttribute("opacity",1); }
    else tip.setAttribute("opacity",0); };
  s.onmouseleave=()=>{ ells.forEach(o=>o.el.setAttribute("opacity",DEF)); tip.setAttribute("opacity",0); hlFront(null); };
  s.onpointerup=ev=>{ if(ev.pointerType!=="mouse") s.onmousemove(ev); }; }   // a tap (touch, pen) names the point or label under it, as a hover does
'''


def app_patches(S):
    j = lambda v: json.dumps(v, separators=(",", ":"), ensure_ascii=False)
    return [
        (re.compile(r"function hoverTip\(s,ells,pts,X,Y,mL,iw\)\{.*?\n(?=// Force-directed label layout)", re.S), HOVER_FN),
        (re.compile(r"const LEGACY=\[[^\]\n]*\];"), "const LEGACY=[];                 // multi-site: filled on load (PRICES_FN), at the prices in force"),
        ('function fitTrend(all){ const rows=all.filter(p=>CURRENT.includes(p.m)); let a=0, l=0;',
         'function fitTrend(all){ const rows=trendRows(); let a=0, l=0;   // multi-site: the default view\'s couples, whatever the selection'),
        (re.compile(r"const CURRENT=\[[^\]\n]*\];"),
         f"const CURRENT=[];\nconst HIDE_B={j(S['hide_landscape'])}, "
         f"DASH={j(DASH)}, HIDE_C={{}}, VARIANTS={j(S['variants'])}, FILT={j(S['filt'])};   // per-site settings (site/makers.json)\n"
         f"const CUR_BASE={j(S['cur_base'])}, LEG_BASE={j(S['legacy'])}, MAKER_OF={j(S['page_maker_of'])}, HINT_ALL={j(S['hint_all'])};   "
         "// before the prices in force: CURRENT, LEGACY, HIDE_C and LEGACY_HINT are taken from them on load\n"
         "let LEGACY_HINT=\"\", OUTCLASSED={};"),
        ('const PANEL=__PANEL__;\n', 'const PANEL=__PANEL__;\n' + PRICES_FN),
        # The tier targets (the maintainer, 19 Nov 2026, rule B): the 20th, 40th, 60th and 80th percentiles of θ over the
        # couples shown, in place of the even spread between the frontier's bounds (TIER_E) of the Claude page.
        (re.compile(r"// DATA-DERIVED targets\. .*?\nconst TIER_E=0\.05;\n", re.S), TIER_Q_HEAD),
        (re.compile(r"function tierDefaults\(\)\{\n.*?\n  TIERQ=\{lo,hi,gap,sig\};\n\}\n", re.S), TIER_Q_FN),
        # The tier windows' axis runs from the weakest couple shown to the strongest (the maintainer, 19 Nov 2026: « le grunt
        # qui va jusqu'au min et le cutting qui va jusqu'au max » ; display only, the windows and the picks are unchanged).
        ('  // Axis spans the targets\' range (from tierDefaults) plus half a gap of padding, so the end windows are not clipped.\n'
         '  const padT=0.5*TIERQ.gap, Tmn=TIERQ.lo-padT, Tmx=TIERQ.hi+padT;',
         '  // multi-site: the axis runs from the weakest couple shown to the strongest, so Grunt reaches the min and Cutting-Edge the max.\n'
         '  const th=couples().map(p=>p.t), Tmn=Math.min(TIERQ.lo,...th), Tmx=Math.max(TIERQ.hi,...th);'),
        ('  else { delete COSTGRID[m]; delete QUALGRID[m]; } }); }', '  else { delete COSTGRID[m]; delete QUALGRID[m]; } }); hideCouples(); applyFilter(); }'),
        ('const xmn=Math.min(...pts.map(p=>p.clo)), xmx=Math.max(...pts.map(p=>p.chi)),',
         'const xmn=Math.min(...pts.map(p=>p.clo),...variantPts(pts).map(v=>v.c)), xmx=Math.max(...pts.map(p=>p.chi),...variantPts(pts).map(v=>v.c)),', 2),
        ('  const segs=[];                                                          // curves + points on top',
         '  drawVariants(s,pts,X,Y,false);\n  const segs=[];                                                          // curves + points on top'),
        ('  placeLabels(s,labs,ppix,segs,W,mL,mT,ih);\n  hoverTip(s,ells,pts,X,Y,mL,iw);\n  const lg=document.getElementById("legendB");',
         '  const bdg=frontLabels(s,"chartB",F,pts.concat(variantPts(pts)),vSegs(pts,X,Y),X,Y,mL,mT,iw,ih);   // the frontier\'s labels, where there is room\n'
         '  hoverTip(s,ells,pts.concat(variantPts(pts)),X,Y,mL,iw,bdg);\n  const lg=document.getElementById("legendB");'),
        ('  // frontier labels (model · effort), force-directed to dodge overlaps and the frontier line\n'
         '  const ppix=front.map(p=>({x:X(p.c),y:Y(p.t)})), segs=[];\n'
         '  for(let i=0;i<front.length-1;i++) segs.push([X(front[i].c),Y(front[i].t),X(front[i+1].c),Y(front[i+1].t)]);\n'
         '  const labs=front.map(p=>{ const t=`${MODELS[p.m].label}${p.e==="solo"?"":" · "+capE(p.e)}`, w=t.length*7.2+8;\n'
         '    return {ax:X(p.c),ay:Y(p.t),lx:X(p.c)+18+w/2,ly:Y(p.t),t,col:cvar(MODELS[p.m].c),lead:cvar(MODELS[p.m].c),w,h:17,fs:13,mdl:true}; });\n'
         '  placeLabels(s,labs,ppix,segs,W,mL,mT,ih);\n  hoverTip(s,ells,pts,X,Y,mL,iw);\n  const lg=document.getElementById("legendP");',
         '  const F=frontRows(pts), segs=vSegs(pts,X,Y);   // the frontier\'s labels avoid its line and the variants\' dotted lines\n'
         '  for(let i=0;i<front.length-1;i++) segs.push([X(front[i].c),Y(front[i].t),X(front[i+1].c),Y(front[i+1].t)]);\n'
         '  const bdg=frontLabels(s,"chartP",F,pts.concat(variantPts(pts)),segs,X,Y,mL,mT,iw,ih);\n'
         '  hoverTip(s,ells,pts.concat(variantPts(pts)),X,Y,mL,iw,bdg);\n  const lg=document.getElementById("legendP");'),
        ('  const pb=document.getElementById("pareto-blocks");   // chained mini-blocks (cost order), same style as the tier cards but small\n'
         '  if(pb) pb.innerHTML=front.map((p,i)=>`${i?\'<span class="pconn">→</span>\':\'\'}<span class="pblock" style="border-color:${cvar(MODELS[p.m].c)}"><b>${MODELS[p.m].label}</b><span class="pblock-e">${capE(p.e)}</span><span class="pblock-n">${pct(p.s)} · ${fmtC(p.c)}×</span></span>`).join("");',
         '  // no list under the chart: the frontier\'s couples are labelled on it, and listed in the frontier table'),
        ('+`<span class="lg"><span class="sw" style="opacity:.25;background:var(--ink);border-radius:50%"></span>dominated</span>`',
         '+`<span class="lg">${LG_LAB}</span><span class="lg"><span class="sw" style="opacity:.25;background:var(--ink);border-radius:50%"></span>dominated</span>`'),
        ('front.forEach(p=>{ if(p.t<Tmn||p.t>Tmx) return; svg+=`<circle cx="${X(p.t)}" cy="${mT+ih}" r="3.2" fill="${cvar(MODELS[p.m].c)}" stroke="${cvar(\'--panel\')}" stroke-width="1"/>`; });\n  host.innerHTML=svg+`</svg>`;',
         'front.forEach((p,i)=>{ if(p.t<Tmn||p.t>Tmx) return; svg+=`<circle cx="${X(p.t)}" cy="${mT+ih}" r="3.2" fill="${cvar(MODELS[p.m].c)}" stroke="${cvar(\'--panel\')}" stroke-width="1" data-k="${p.m}@${p.e}">`\n'
         '    +`<title>${MODELS[p.m].label}${p.e==="solo"?"":" · "+capE(p.e)} — cost ${fmtC(p.c)}× · score ${pct(p.s)}</title></circle>`; });\n'
         '  host.innerHTML=svg+`</svg><p class="tuner-tip" aria-live="polite"></p>`;   // the frontier\'s couples: their identity on hover or tap\n'
         '  host.onmousemove=host.onpointerup=ev=>{ const c=ev.target&&ev.target.closest?ev.target.closest("circle[data-k]"):null, tt=host.querySelector(".tuner-tip");\n'
         '    hlFront(c?c.getAttribute("data-k"):null); if(tt) tt.textContent=c?c.querySelector("title").textContent:""; };'),
        ('  pts.forEach(p=>{ const col=cvar(MODELS[p.m].c);\n    s.appendChild(el("circle",p.front?',
         '  drawVariants(s,pts,X,Y,true);\n  pts.forEach(p=>{ const col=cvar(MODELS[p.m].c);\n    s.appendChild(el("circle",p.front?'),
        ('${fmtC(c[0])}<small>merged · ${c[1]}</small></div>', '${fmtC(c[0])}<small>merged · ${c[1]}</small>${vNote(m,"solo",c[0])}</div>'),
        ('${fmtC(c[0])}<small>${c[1]}</small></div></td>`', '${fmtC(c[0])}<small>${c[1]}</small>${vNote(m,e,c[0])}</div></td>`'),
        ('<td class="num">${fmtC(p.c)}×</td><td class="num">${pct(p.s)}</td>', '<td class="num">${fmtC(p.c)}×${vNote(p.m,p.e,p.c)}</td><td class="num">${pct(p.s)}</td>'),
        ('${vIndex(r)}<small>${vIndex(r-sd)}–${vIndex(r+sd)}</small></div>`; };',
         '${vIndex(r)}<small>${vIndex(r-sd)}–${vIndex(r+sd)}</small>${vNotes(p.m,p.e,rel=>vIndex(r-Math.log(rel)))}</div>`; };'),
        # the tier cards, the crown and the answer say a promotion
        ('<span class="tier-nums">Cost <b>${fmtC(w.c)}×</b>', '<span class="tier-nums">Cost <b>${fmtC(w.c)}×</b>${pTag(w)}'),
        ('<div class="crown-line">Cost <b>${fmtC(c.c)}×</b>', '<div class="crown-line">Cost <b>${fmtC(c.c)}×</b>${pTag(c)}'),
        ('const nm=p=>`${MODELS[p.m].label}${atE(p.e)}`;', 'const nm=p=>`${MODELS[p.m].label}${atE(p.e)}${PROMO[p.m+"@"+p.e]?` (${promoTag(p.m+"@"+p.e)})`:""}`;'),
        ('function renderAll(){renderControls();', 'function renderAll(){fillNtrend();renderControls();'),
        ('const visibleModels=()=>Object.keys(MODELS).filter(m=>showLegacy||!LEGACY.includes(m));\n',
         'const visibleModels=()=>Object.keys(MODELS).filter(m=>showLegacy||!LEGACY.includes(m));\n' + LEGEND_FN),
        ('+legacy("tgl-legacy-b")', ''), ('+legacy("tgl-legacy-p")+ovals("tgl-ovals-p")+bands("tgl-bands-p");\n}',
         '+ovals("tgl-ovals-p")+bands("tgl-bands-p");\n  renderFilterBar();   // the selection bar, with the older-model switch\n}'),
        (re.compile(r'const legacy=id=>tgl\(id,showLegacy,"Older models","[^"\n]*","toggleLegacy"\);'),
         'const legacy=id=>LEGACY.length?tgl(id,showLegacy,"Older models",LEGACY_HINT,"toggleLegacy"):"";'),
        ('const pts=couples().filter(p=>p.m!=="haiku-4.5");', 'const pts=couples().filter(p=>!HIDE_B.includes(p.m));'),
        # Charts of the multi-site pages: points only (no effort ladder joining a model's couples), labels on the
        # Pareto frontier's couples only, the others named on hover or tap (hoverTip); no model list in the legends.
        ('    s.appendChild(el("path",{d:mp.map((p,i)=>(i?"L":"M")+X(p.c)+" "+Y(p.t)).join(" "),fill:"none",stroke:col,"stroke-width":2.2,"stroke-linejoin":"round"}));\n'
         '    mp.forEach(p=>s.appendChild(el("circle",{cx:X(p.c),cy:Y(p.t),r:3.6,fill:col,stroke:cvar(\'--panel\'),"stroke-width":1.4})));\n'
         '    for(let i=0;i<mp.length-1;i++) segs.push([X(mp[i].c),Y(mp[i].t),X(mp[i+1].c),Y(mp[i+1].t)]); }',
         '    mp.forEach(p=>s.appendChild(el("circle",lsty(m)?{cx:X(p.c),cy:Y(p.t),r:3.6,fill:cvar(\'--panel\'),stroke:col,"stroke-width":1.8}'
         ':{cx:X(p.c),cy:Y(p.t),r:3.6,fill:col,stroke:cvar(\'--panel\'),"stroke-width":1.4}))); }   // points only: no line joins a model\'s couples'),
        ('  const ppix=pts.map(p=>({x:X(p.c),y:Y(p.t)})), labs=[];                  // effort labels + model-name labels, force-directed together\n'
         '  pts.forEach(p=>labs.push({ax:X(p.c),ay:Y(p.t),lx:X(p.c),ly:Y(p.t)-9,t:tagE(p.e),col:cvar(MODELS[p.m].c),lead:cvar(MODELS[p.m].c),w:tagE(p.e).length*5.4+4,h:11,fs:8.5,mdl:false}));\n'
         '  for(const m in byM){ const mp=byM[m].slice().sort((a,b)=>effRank(a.e)-effRank(b.e)), last=mp[mp.length-1], w=MODELS[m].label.length*7+6;\n'
         '    labs.push({ax:X(last.c),ay:Y(last.t),lx:X(last.c)+16+w/2,ly:Y(last.t)+4,t:MODELS[m].label,col:cvar(MODELS[m].c),lead:cvar(MODELS[m].c),w,h:15,fs:12.5,mdl:true}); }\n',
         '  const F=frontRows(pts);                                   // the page\'s frontier, labelled where there is room (no other label)\n'),
        ('<b>hover a point</b> for its identity</span>', '<b>hover or tap a point</b> for any other (model · effort, cost, score)</span><span class="lg">${LG_LAB}</span>', 2),
        ('visibleModels().filter(m=>m!=="haiku-4.5").map(m=>`<span class="lg"><span class="sw" style="background:${cvar(MODELS[m].c)}"></span>${MODELS[m].label}</span>`).join("")',
         'legendSymbols(visibleModels().filter(m=>!HIDE_B.includes(m)&&selOK(m)))'),
        ('visibleModels().map(m=>`<span class="lg"><span class="sw" style="background:${cvar(MODELS[m].c)}"></span>${MODELS[m].label}</span>`).join("")',
         'legendSymbols(visibleModels().filter(selOK))'),
        ('s.appendChild(el("circle",p.front?{cx:X(p.c),cy:Y(p.t),r:5.6,fill:col,stroke:cvar(\'--panel\'),"stroke-width":1.3}\n      :{cx:X(p.c),cy:Y(p.t),r:3.4,fill:col,"fill-opacity":.25})); });',
         's.appendChild(el("circle",p.front?(lsty(p.m)?{cx:X(p.c),cy:Y(p.t),r:5.6,fill:cvar(\'--panel\'),stroke:col,"stroke-width":2.4}:{cx:X(p.c),cy:Y(p.t),r:5.6,fill:col,stroke:cvar(\'--panel\'),"stroke-width":1.3})\n'
         '      :(lsty(p.m)?{cx:X(p.c),cy:Y(p.t),r:3.4,fill:"none",stroke:col,"stroke-opacity":.35,"stroke-width":1.4}:{cx:X(p.c),cy:Y(p.t),r:3.4,fill:col,"fill-opacity":.25}))); });'),
        (re.compile(r"const GMODEL = \{\n.*?\n\};\n", re.S),
         "const GMODEL = Object.fromEntries(Object.keys(MODELS).map(m=>[m,{l:MODELS[m].label,c:MODELS[m].c,cur:1}]));   // the page's models\n"),
        ('  const pub=s=>s==="anthropic-chart"?"anthropic-syscard":s;        // one publisher = one source (mirrors PUBLISHER in build.py)\n'
         '  const nSrc=new Set(curGroups.map(g=>pub(g.s))).size;',
         '  const nSrc=new Set(curGroups.map(g=>g.p)).size;                  // one publisher = one source (data/catalog/publishers.json)'),
        ('const cur=x=>{const m=x.split("@")[0];return GMODEL[m]&&GMODEL[m].cur;};', 'const cur=x=>{const m=x.split("@")[0];return GMODEL[m]&&GMODEL[m].cur&&selOK(m);};'),
        ('const curNode=x=>{const m=x.split("@")[0];return GMODEL[m]&&GMODEL[m].cur;};', 'const curNode=x=>{const m=x.split("@")[0];return GMODEL[m]&&GMODEL[m].cur&&selOK(m);};'),
    ]


def page_href(S, t):
    """The link from page S to page t: its clean address on the site (/, /openai/), or with --local-links the file
    itself (../openai/index.html), which opens from the disk too (a folder link shows the folder there)."""
    if LOCAL_LINKS:
        return f'{S["up"]}{t["path"]}index.html'
    return urllib.parse.urlparse(BASE).path + t["path"]


def body_patches(S, mc_sentence):
    cur = ' aria-current="page"'
    nav = "".join(f'<a href="{page_href(S, t)}"{cur if t["id"] == S["id"] else ""}>{esc(t["name"])}</a>' for t in S["all"])
    banner = f'  <p class="draft-banner" role="note">{esc(DRAFT)}</p>\n' if DRAFT else ""
    noun = (S["noun"] + " ") if S["noun"] else ""
    shows = ("this page shows the current models of every maker, and the older couples no other model of their maker "
             "beats, but no model that another model of the same maker entirely outclasses"
             if S["id"] == "global" else f"this page shows the {S['name']} couples")
    what = "makers" if S["id"] == "global" else "models"
    return [
        # The head, top to bottom (the maintainer, 19 Nov 2026): a plain text navigation, the title and its subtitle,
        # the introduction; the filters sit just above the first chart, and stick to the top only once scrolled past.
        ('<div class="wrap">\n  <header class="hero">\n    <div class="hero-corner">',
         f'<div class="wrap">\n  <nav class="sitenav" aria-label="Model makers">{nav}</nav>\n  <header class="hero">\n'
         f'    <h1>{S["h1"]}</h1>\n'
         '    <div class="eyebrow">Data analysis · aggregated from <span class="nsrc">…</span></div>\n'
         '    <div class="hero-corner">'),
        ('    <div class="eyebrow">Data analysis · aggregated from <span class="nsrc">…</span></div>\n'
         '    <h1>Claude models compared <span class="h1-line">cost vs quality at every effort level</span></h1>\n', ""),
        ('  </header>\n\n  <main>\n', f'  </header>\n{banner}\n  <main>\n'),
        ('  <!-- ============ CHART : consolidated curves ============ -->\n  <section id="frontier">',
         f'  <div class="filterbar" id="filterbar" role="toolbar" aria-label="Show or hide {what}"></div>\n\n'
         '  <!-- ============ CHART : consolidated curves ============ -->\n  <section id="frontier">'),
        ('What each recent Claude model actually costs, at every effort level, and the quality it delivers — fused from public benchmark measurements for every (model, effort) pair.',
         S["lede"]),
        ('        <p class="lede">To compare two models directly — Fable, Opus, Sonnet or Haiku, effort by effort — see the <a href="claude-models-head-to-head.html">head-to-head page</a>.</p>\n', ""),
        ("Quality vs. cost of every Claude model, at each effort level", f"Quality vs. cost of every {noun}model, at each effort level"),
        ("<b>__NTREND__ couples of the latest model of each family</b>",
         '<b><span class="ntrend">__NTREND__</span> couples of the latest model of each family</b>'),   # the page fills it on load
        (" <b>Haiku&nbsp;4.5</b> lives only in the matrix and Pareto.",
         S["hide_note"] + ("" if not S["has_lines"] else " A model's <b>builds and modes</b> — a dated build, a preview, a Pro mode — share its colour: "
         "the first is drawn with <b>filled</b> points, the others with <b>hollow</b> points, and its label and tooltip say "
         "what it is. They are separate couples, each with its own effort ladder.")),
        ('aria-label="Quality vs cost, one curve per model, one point per effort"></svg></div>',
         'aria-label="Quality vs cost, one point per model and effort"></svg></div>'),
        ('      <div id="pareto-blocks" class="pareto-blocks"></div>\n', ""),
        ('<b>Solid</b> = frontier, <b>faded</b> = dominated.',
         '<b>Solid</b> = frontier, <b>faded</b> = dominated; the frontier couples are <b>labelled</b> (model · effort) where '
         'there is room — <b>hover</b> or <b>tap</b> any point for its model, effort, cost and score. '
         'No line joins a model\'s couples.'),
        ('<p class="cap">One curve per model, one point per configuration (thinking off, minimal, low → max, thinking on).',
         '<p class="cap">One point per couple: a model at one configuration (thinking off, minimal, low → max, thinking on); '
         'no line joins a model\'s couples. Only the couples of the <b>Pareto frontier</b> are <b>labelled</b> (model · '
         'effort), where there is room; <b>hover</b> or <b>tap</b> any point for its model, effort, cost and score.'),
        ("Best Claude model for the price — the Pareto frontier", f"Best {noun}model for the price — the Pareto frontier"),
        ("Normalized cost matrix — Claude effort levels compared", f"Normalized cost matrix — {noun}effort levels compared"),
    ] + ([(re.compile(r"<p>Each release buys the same quality for less — .*?</p>"), f"<p>{S['generation']}</p>")]
          if S.get("generation") else []) + [
        ('<p class="sub"><b>Checks</b> (on the fit of 29 September 2026). ',
         '<p class="sub"><b>Checks</b> (on the fit of 29 September 2026, before the other makers\' couples joined the data). '),
        ("The fit takes the other makers' couples measured in the same groups (OpenAI, Google, xAI, DeepSeek, Qwen, GLM, Kimi): "
         "they link more benchmarks; this page shows the Claude couples.",
         "The fit takes the couples of eight makers measured in the same groups (Anthropic, OpenAI, Google, xAI, DeepSeek, "
         f"Qwen, GLM, Kimi), on one scale; {shows}."),
        (re.compile(r"in this fit (?:every figure is stable to that digit|[^<]*?far inside their intervals)\."), mc_sentence),
        ("not affiliated with or endorsed by Anthropic", "not affiliated with or endorsed by any model maker"),
        # the tier targets, rule B (the maintainer, 19 Nov 2026)
        ("they spread evenly between the frontier's weakest and strongest couples, each end drawn 5&nbsp;% of the span inward, "
         "so that the bottom tier follows the weakest couple available and the top tier the best — as models improve, the "
         "targets move with them. The width follows the spacing on one rule&nbsp;: adjacent windows cross at <b>half weight</b> "
         "midway between their targets.",
         "they are the <b>20th, 40th, 60th and 80th percentiles</b> of the quality of the couples shown on the page, so that "
         "the four tiers sit across the bulk of today's couples — as models improve, the targets move with them, and turning "
         "makers or models off takes them again on what is shown. They depend on quality only, not on prices. The width "
         "follows the mean spacing of the targets on one rule&nbsp;: adjacent windows cross at <b>half weight</b> midway "
         "between their targets."),
        ("The four tiers spread their targets across the frontier and pick, around each target,",
         "The four tiers set their targets at the 20th, 40th, 60th and 80th percentiles of the quality of the couples shown "
         "and pick, among the frontier couples, around each target,"),
    ]


EXTRA_CSS = """
.sitenav{display:flex;flex-wrap:wrap;gap:4px 18px;margin:0 0 20px;font-size:13.5px;line-height:1.5}
.sitenav a{color:var(--muted);text-decoration:none}
.sitenav a:hover{color:var(--ink);text-decoration:underline}
.sitenav a[aria-current="page"]{color:var(--ink);font-weight:700}
.hero h1{margin-top:0}
.hero h1 + .eyebrow{margin-top:10px}
.draft-banner{margin:4px 0 26px;padding:11px 16px;border:1px solid var(--warn);border-left:5px solid var(--warn);border-radius:10px;
  background:color-mix(in srgb,var(--warn) 12%,var(--panel));color:var(--ink);font-size:14.5px}
.lgl{display:inline-flex;flex-wrap:wrap;gap:2px 9px;margin-left:4px;font-size:11.5px;color:var(--muted)}
.lgi{display:inline-flex;align-items:center;gap:3px}
.lgs{flex:none}
.lgt{font-size:11px;color:var(--muted);margin-right:5px}
.vnote{display:block;font-style:italic;color:var(--muted)}
.filterbar{position:sticky;top:0;z-index:30;display:flex;flex-wrap:nowrap;align-items:center;gap:6px;margin:0 0 18px;padding:8px 0;
  overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch;background:var(--paper);border-bottom:1px solid var(--line);font-size:12.5px}
.filterbar::-webkit-scrollbar{display:none}
.fchip{font:inherit;font-size:12.5px;display:inline-flex;align-items:center;gap:6px;padding:3px 10px 3px 8px;border-radius:999px;flex:none;
  border:1px solid var(--line2);background:transparent;color:var(--ink);cursor:pointer;white-space:nowrap;line-height:1.4}
.fchip:hover{border-color:var(--muted)}
.fchip:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.fchip-dot{width:7px;height:7px;border-radius:50%;background:var(--fc);flex:none}
.fchip[aria-pressed="false"]{color:var(--faint)}
.fchip[aria-pressed="false"] .fchip-dot{background:transparent;box-shadow:inset 0 0 0 1.2px var(--fc)}
.fchip[aria-disabled="true"]{cursor:not-allowed}
.fchip-all{padding-left:10px}
.fbar-lbl{font-size:12.5px;color:var(--muted);flex:none;white-space:nowrap;margin-right:2px}
.fchip-old{--fc:var(--muted);margin-left:8px}
.fchip-old[aria-checked="false"]{color:var(--muted)}
.fchip-old[aria-checked="false"] .fchip-dot{background:transparent;box-shadow:inset 0 0 0 1.2px var(--fc)}
.flabel,.flead{pointer-events:none}
.tuner-tip{min-height:1.3em;margin:4px 0 0;font-size:12px;color:var(--muted);text-align:center}
"""


# ---------------------------------------------------------------- head, date, files
def head(S, date, counts):
    a = lambda v: esc(v)
    url = BASE + S["path"]
    dataset = {"@context": "https://schema.org", "@type": "Dataset", "name": S["title"],
               "description": (S["description"] + f" Aggregated from {counts}; cost as a multiple of the cheapest couple, "
                               "quality as the expected score on the benchmark panel."),
               "url": url, "sameAs": REPO_URL,
               "creator": {"@type": "Person", "name": "Alexandre Gensse", "url": "https://github.com/alexandregensse-blip"},
               "dateModified": date.isoformat(), "license": "https://creativecommons.org/licenses/by/4.0/",
               "isAccessibleForFree": True}
    ld = json.dumps([{"@context": "https://schema.org", "@type": "WebSite", "name": S["site_name"], "url": BASE}, dataset],
                    ensure_ascii=False, indent=1).replace("</", "<\\/")
    return (f"<title>{a(S['title'])}</title>\n"
            f'<meta name="description" content="{a(S["description"])}">\n'
            + ('<meta name="robots" content="noindex, nofollow">\n' if DRAFT else "") +
            f'<link rel="canonical" href="{url}">\n'
            f'<link rel="icon" href="{S["up"]}favicon.svg" type="image/svg+xml">\n'
            f'<link rel="icon" href="{S["up"]}favicon.png" type="image/png" sizes="96x96">\n'
            '<meta property="og:type" content="website">\n'
            f'<meta property="og:url" content="{url}">\n'
            f'<meta property="og:title" content="{a(S["title"])}">\n'
            f'<meta property="og:description" content="{a(S["description"])}">\n'
            '<meta name="twitter:card" content="summary">\n'
            f'<script type="application/ld+json">\n{ld}\n</script>\n')


DATES = os.path.join(OUT, ".content-dates.json")   # {path: {fingerprint, date}}: the date moves only with the content

def content_date(path, blob):
    fp = hashlib.sha256(json.dumps(blob, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    try: rec = json.load(open(DATES))
    except (OSError, ValueError): rec = {}
    if rec.get(path, {}).get("fingerprint") != fp:
        rec[path] = {"fingerprint": fp, "date": datetime.date.today().isoformat()}
        json.dump(rec, open(DATES, "w"), indent=1, sort_keys=True)
    return datetime.date.fromisoformat(rec[path]["date"])


def plain(h):
    return re.sub(r"\s+(?=:)", "", re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", "", h)))).strip()


def mc_text(CG, MCSE, models):
    """The page's Monte Carlo sentence, as build.py checks it: a value whose Monte Carlo error exceeds half of its last
    displayed digit (a cost multiple 0.005 below 1, 0.05 below 10, 0.5 above; a score 0.05 point)."""
    x0 = min(v[0] for es in CG.values() for v in es.values())
    loose = []
    for axis in ("cost", "quality"):
        for c, e in sorted(MCSE[axis].items()):
            m, eff = c.split("@")
            val = math.exp(CG[m][eff][0] - x0) if axis == "cost" else 0
            half = 0.05 if axis == "quality" else 0.005 if val < 1 else 0.05 if val < 10 else 0.5
            if e > half:
                loose.append(f"the {axis} of {models[m]['label']}" + ("" if eff == "solo" else f" at {eff}"))
    if not loose:
        return "in this fit every figure on this page is stable to that digit."
    words = "one two three four five six seven eight nine ten".split()
    n = len(loose)
    return (f"in this fit {words[n - 1] if n <= 10 else n} figure{'s' if n > 1 else ''} on this page can move by one unit "
            f"in that digit ({', '.join(loose)}), far inside their intervals.")


# ---------------------------------------------------------------- models another model of their maker outclasses
def outclassed(keys, CG, QG, maker_of):
    """{A: [B, …]} for each model A of the page that another model B of the same maker entirely outclasses: every
    couple of A shown on the page is dominated by at least one couple of B — B costs no more and scores no less, and
    is strictly better on one of the two — on the values the page's frontier uses (ln cost and θ, the tolerance of
    frontier() in site/app.js). Such a model goes into the older models, hidden by default, current or not (the
    maintainer, 19 Nov 2026; docs/DISPLAY-METHODOLOGY.md § 16). No other threshold."""
    E = 1e-9
    dom = lambda o, p: o[0] <= p[0] + E and o[1] >= p[1] - E and (o[0] < p[0] - E or o[1] > p[1] + E)
    pts = {k: [(CG[k][e][0], QG[k][e][0]) for e in CG[k]] for k in keys if k in CG}
    out = {}
    for a, pa in pts.items():
        bs = [b for b, pb in pts.items() if b != a and maker_of[b] == maker_of[a]
              and all(any(dom(o, p) for o in pb) for p in pa)]
        if bs: out[a] = bs
    return out


# ---------------------------------------------------------------- one page
def build_page(S, css0, body0, app0):
    CG, QG, PANEL, DIAG, MCSE = fused_grids(models=S["keys"], both_axes=True)
    models, mcss = page_models(S, S["keys"], CG)
    shown = list(models)
    S["has_lines"] = any("ls" in v for v in models.values())
    S["variants"] = {c: v for c, v in VARIANTS.items() if c.split("@")[0] in CG and c.split("@")[1] in CG[c.split("@")[0]]}
    # The prices in force today (the build date; the page takes them again on the reader's date, PRICES_FN): a promotion
    # kept replaces the list price in every decision. CG stays at the list price, the page applies the promotions.
    S["promos"] = {}
    for c, vs in S["variants"].items():
        for v in vs:
            if v["kind"] == "promo" and (not v["until"] or v["until"] >= datetime.date.today().isoformat()):
                if c not in S["promos"] or v["cost_ratio"] < S["promos"][c]["cost_ratio"]: S["promos"][c] = v
    CGe = {m: dict(es) for m, es in CG.items()}
    for c, v in S["promos"].items():
        m, e = c.split("@"); CGe[m][e] = [CG[m][e][0] + math.log(v["cost_ratio"]), CG[m][e][1]]
    S["cur_base"] = [k for k in S["current"] if k in CG]
    S["page_maker_of"] = {k: S["maker_of"][k] for k in models}
    S["hint_all"] = bool(S["legacy"] is not None and SET["makers"][S["id"]].get("from_claude_page"))
    S["outclassed"] = outclassed(shown, CGe, QG, S["maker_of"])   # {A: [B, …]}: into the older models, current or not
    S["current_keys"] = [k for k in S["current"] if k in CG and k not in S["outclassed"]]
    for k in S["current"]:
        if k not in S["keys"]: warn(f"{S['id']}: current key {k} is not one of the page's keys")
        elif k not in CG: warn(f"{S['id']}: current model {k} has no couple published on both axes")
    if not S["current_keys"]: sys.exit(f"!! {S['id']}: no current model left for the price trend")
    S["hide_couples"] = {}
    if S["legacy"] is None:                    # global page: current models, and the couples of older models that no
        maker, base = S["maker_of"], (lambda k: MODEL_LINE.get(k, k))   # other model of the same maker strictly beats
        beaten = lambda k, e: any(maker[k2] == maker[k] and base(k2) != base(k) and CGe[k2][e2][0] < CGe[k][e][0]
                                  and QG[k2][e2][0] > QG[k][e][0] for k2 in shown for e2 in CG[k2])
        for k in shown:
            if k in S["current_keys"]: continue
            out = [e for e in CG[k] if beaten(k, e)]
            if out: S["hide_couples"][k] = out
        S["legacy_keys"] = [k for k in shown if k in S["outclassed"] or len(S["hide_couples"].get(k, [])) == len(CG[k])]
        S["hide_couples"] = {k: es for k, es in S["hide_couples"].items() if k not in S["legacy_keys"]}
        n = sum(len(CG[k]) for k in S["legacy_keys"]) + sum(map(len, S["hide_couples"].values()))
        S["legacy_hint"] = f"{n} couples that another model of the same maker beats"
    else:
        S["legacy_keys"] = [k for k in shown if k in S["legacy"] or k in S["outclassed"]]
        leg = [k for k in S["legacy_keys"] if not models[k].get("ls")]
        names = [models[k].get("bl", models[k]["label"]) for k in leg]
        S["legacy_hint"] = (" · ".join(names) if len(names) <= 3 or SET["makers"][S["id"]].get("from_claude_page")
                            else " · ".join(names[:2]) + f" and {len(names) - 2} more")
    lock = "the tiers need two frontier couples"
    if S["id"] == "global":                    # the selection bar: one chip per maker, in its hue (the middle of its models')
        mks = [mk for mk in SET["makers"] if any(S["maker_of"][k] == mk for k in models)]
        S["filt"] = dict(key="makers", lock=lock, of={k: S["maker_of"][k] for k in models},
                         items=[dict(id=mk, label=SET["makers"][mk]["name"], c=f"--mk-{mk}") for mk in mks])
        C = lambda mk: SET["makers"][mk].get("chroma", 0.15)
        mcss = tuple(";".join(x for x in (mcss[i], ";".join(f"--mk-{mk}:{oklch_hex(L, C(mk) * f, SET['makers'][mk]['hue'])}"
                                                               for mk in mks)) if x) for i, (L, f) in enumerate([(0.54, 1), (0.74, 0.87)]))
    else:                                      # a maker page: one chip per model (its builds and modes with it)
        bases = list(dict.fromkeys(v.get("base", k) for k, v in models.items()))
        S["filt"] = dict(key="models", lock=lock, of={k: v.get("base", k) for k, v in models.items()},
                         items=[dict(id=b, label=models[b].get("bl", models[b]["label"]) if b in models else
                                     next(v["bl"] for v in models.values() if v.get("base") == b),
                                     c=next(v["c"] for k, v in models.items() if v.get("base", k) == b)) for b in bases])
    couples = {f"{m}@{e}" for m, es in CG.items() for e in es}
    GD = groups_data(couples=couples, unverified="—")
    css = with_colours(css0, *mcss) + EXTRA_CSS
    app = patch(app0, app_patches(S), f"app.js ({S['id']})")
    app = app.replace("__MODELS__", json.dumps(models, separators=(",", ":"), ensure_ascii=False))
    cols = effort_columns(CG)                                  # as site/build.py: low … max, and the others present
    app = app.replace("__EFFORT_ORDER__", json.dumps(EFFORT_ORDER)).replace("__EFFORT_COLS__", json.dumps(cols))
    app = app.replace("__CAPE__", json.dumps(CAP, separators=(",", ":")))
    app = app.replace("__COSTGRID__", json.dumps(CG, separators=(",", ":")))
    app = app.replace("__QUALGRID__", json.dumps(QG, separators=(",", ":")))
    app = app.replace("__PANEL__", json.dumps(PANEL, separators=(",", ":")))
    app = app.replace("__GROUPS_DATA__", json.dumps(GD, separators=(",", ":"), ensure_ascii=False))
    body = patch(body0, body_patches(S, mc_text(CGe, MCSE, models)), f"body.html ({S['id']})")
    body = body.replace("__REPO__", REPO_URL).replace("__DATA_URL__", DATA_URL)
    body = body.replace("__EFFORT_HEAD__", "".join(f"<th>{CAP[e].lower() if e in ('nothink', 'think') else e}</th>" for e in cols))
    span = math.exp(max(c[0] for v in CG.values() for c in v.values()) - min(c[0] for v in CG.values() for c in v.values()))
    body = body.replace("__COSTSPAN__", str(round(span)))
    body = body.replace("__NCOSTROWS__", str(DIAG["cost"]["rows"])).replace("__NSCOREROWS__", str(DIAG["quality"]["rows"]))
    body = body.replace("__NTREND__", str(sum(len(CG[m]) for m in S["current_keys"])))
    pre = prerender(app, css, skip=["pareto-blocks"])   # no list under the Pareto chart on these pages
    body = inject(body, pre)
    text = re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)\b.*?</\1>", " ", body, flags=re.S))))
    date = content_date(S["path"] or "/", [S["title"], S["description"], text, pre.get("answer-full", ""), CG, QG, GD])
    body = body.replace("__GENDATE__", date.strftime("%d %b %Y"))
    html = ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            + head(S, date, plain(pre.get(".nsrc", ""))) +
            f"<style>\n{css}\n</style>\n</head>\n<body>\n{body}\n<script>\n{app}\n</script>\n</body>\n</html>\n")
    if (left := sorted(set(re.findall(r"__[A-Z][A-Z_]*__", html)))):
        sys.exit(f"!! {S['id']}: placeholders left in the page: {left}")
    d = os.path.join(OUT, S["path"]); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(html)
    vis = [k for k in shown if k not in S["legacy_keys"]]
    hid = lambda k: S["hide_couples"].get(k, [])
    info = dict(id=S["id"], path=S["path"], title=S["title"], bytes=len(html.encode()), date=date.isoformat(),
                couples_default=sum(len(CG[k]) - len(hid(k)) for k in vis), models_default=len(vis),
                variants={c: [x["label"] for x in v] for c, v in S["variants"].items()},
                promotions_in_force={c: dict(ratio=v["cost_ratio"], until=v["until"], seen=v["seen"]) for c, v in S["promos"].items()},
                current_keys=S["current_keys"], legacy_keys=S["legacy_keys"], hide_couples=S["hide_couples"],
                couples_all=sum(len(CG[k]) for k in shown), models_all=len(shown), outclassed=S["outclassed"],
                counts=plain(pre.get(".nsrc", "")), answer=pre.get("answer-full", ""),
                ladder=monotonicity_report({k: CGe[k] for k in vis}, {k: QG[k] for k in vis}),
                ladder_all=monotonicity_report(CGe, QG))
    return info


def main():
    global DRAFT, LOCAL_LINKS
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stale-fit", action="store_true",
                    help="build from a model/fit-cache.json whose inputs have changed since the fit (local preview only: "
                         "the couples and values are the last fit's, the sources table reads today's data; the banner says so)")
    ap.add_argument("--local-links", action="store_true",
                    help="links between the pages to each page's index.html (../openai/index.html), for a copy opened "
                         "from the disk; without it, the published addresses (/, /openai/)")
    args = ap.parse_args()
    LOCAL_LINKS = args.local_links
    if args.stale_fit:
        import grids
        cache = json.load(open(grids.FIT_CACHE))
        if cache.get("fingerprint") != grids.inputs_fingerprint(cache["inputs"]):
            warn("model/fit-cache.json does not match its inputs: built anyway (--stale-fit), banner added")
            grids.inputs_fingerprint = lambda inputs: cache["fingerprint"]
            DRAFT = (DRAFT + " " if DRAFT else "") + ("Stale fit: the figures are those of the last fit, whose inputs "
                     "have changed since; the page is a preview of the layout, not of today's numbers.")
    css0 = open(os.path.join(HERE, "style.css")).read()
    body0 = open(os.path.join(HERE, "body.html")).read()
    app0 = open(os.path.join(HERE, "app.js")).read()
    os.makedirs(OUT, exist_ok=True)
    all_sites = sites()
    infos = []
    for S in all_sites:
        S["all"] = all_sites
        S["up"] = "../" * S["path"].count("/")
        infos.append(build_page(S, css0, body0, app0))
    for f in ("favicon.svg", "favicon.png"):
        shutil.copyfile(os.path.join(ROOT, f), os.path.join(OUT, f))
    open(os.path.join(OUT, "robots.txt"), "w").write(
        "# Draft: the pages carry a noindex tag.\nUser-agent: *\nAllow: /\n" if DRAFT else
        f"User-agent: *\nAllow: /\n\nSitemap: {BASE}sitemap.xml\n")
    if not DRAFT:
        open(os.path.join(OUT, "sitemap.xml"), "w").write(
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "".join(f"  <url><loc>{BASE}{i['path']}</loc><lastmod>{i['date']}</lastmod></url>\n" for i in infos) + "</urlset>\n")
    elif os.path.exists(os.path.join(OUT, "sitemap.xml")):
        os.remove(os.path.join(OUT, "sitemap.xml"))
    llms = [f"# {SET['global']['title']}\n", f"> {SET['global']['description']}\n"] + ([f"{DRAFT}\n"] if DRAFT else [])
    for i in infos:
        llms.append(f"## [{i['title']}]({BASE}{i['path']})\n\n{i['answer']}\n\nFrom {i['counts']}. Updated {i['date']}.\n")
    llms.append("Costs are multiples of the cheapest couple shown on each page; quality is the expected score on the benchmark "
                "panel. Method: docs/METHODOLOGY.md and docs/DISPLAY-METHODOLOGY.md in the source repository "
                f"({REPO_URL}). Data: raw-data.csv, CC BY 4.0.\n")
    open(os.path.join(OUT, "llms.txt"), "w", encoding="utf-8").write("\n".join(llms))
    json.dump(infos, open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump(VARIANTS_LOG, open(os.path.join(OUT, "price-variants.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for r in VARIANTS_LOG:
        print(f"  price variant {r['model']} {r['route']} {r['kind']} {r['currency']} {r['from'][:10]}→{(r['to'] or '')[:10]}: {r['outcome']}")
    for i in infos:
        print(f"built {os.path.relpath(os.path.join(OUT, i['path'], 'index.html'), ROOT)}  ({i['bytes']} bytes) · "
              f"{i['couples_default']} couples of {i['models_default']} models shown by default "
              f"({i['couples_all']} of {i['models_all']} with older models) · {i['counts']}")
        for v in i["ladder"]:
            print("  effort ladder inverted (shown by default): " + v)
    print(f"wrote {os.path.relpath(OUT, ROOT)}/llms.txt, robots.txt, summary.json, price-variants.json, favicons"
          + (" — DRAFT: banner and noindex on every page" if DRAFT else ""))


if __name__ == "__main__":
    main()
