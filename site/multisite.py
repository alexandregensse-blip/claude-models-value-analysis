#!/usr/bin/env python3
"""Multi-site generator (draft, built locally only) for models.agensse.com: the global page — every maker's current
models on one chart, frontier, price trend, tiers and crown computed across makers — and one page per model maker
(/claude/, /openai/, …), each like the Claude page: its models, its effort ladders, its tiers and crown among its own
couples, its sources table.
Run: python3 site/multisite.py  →  out/models/ (index.html, <maker>/index.html, llms.txt, robots.txt, favicons).
The Claude page (python3 site/build.py, served at the repository root) is untouched: this reuses its page — app.js,
body.html, style.css, the pre-render — and applies the per-site settings of site/makers.json as exact text
replacements, each checked to apply exactly where expected, so a change to the page that breaks one stops this build
instead of slipping through. Rules: docs/DISPLAY-METHODOLOGY.md § 16."""
import argparse, datetime, hashlib, html as htmlmod, json, math, os, re, shutil, sys

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
             "until": end if stated else None, "evidence": ev.get("url")}
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
  const ink=cvar('--ink'), hollow=ms.some(m=>lsty(m)), vk=Object.keys(VARIANTS).some(k=>ms.includes(k.split("@")[0]));
  return (hollow?`<span class="lg"><svg class="lgs" width="12" height="10" aria-hidden="true"><circle cx="6" cy="5" r="3.4" fill="${cvar('--panel')}" stroke="${ink}" stroke-width="1.6"/></svg>hollow point: another build or mode of a model (a dated build, a preview, a Pro mode), named in its label</span>`:"")
    +(vk?`<span class="lg"><svg class="lgs" width="30" height="10" aria-hidden="true"><line x1="2" y1="5" x2="23" y2="5" stroke="${ink}" stroke-width="1.2" stroke-dasharray="1.5 3"/><path d="M 24 1 L 28 5 L 24 9 L 20 5 Z" fill="${cvar('--panel')}" stroke="${ink}" stroke-width="1.4"/></svg>the same couple at a promotional or off-peak price — shown, never used in a pick</span>`:""); }
// Global page: the couples of older models that another model of the same maker strictly beats, hidden by default.
function hideCouples(){ Object.keys(HIDE_C).forEach(m=>[[COSTGRID,GRID_ALL.cost],[QUALGRID,GRID_ALL.qual]].forEach(([G,A])=>{ if(!A[m]) return;
  G[m]=showLegacy?A[m]:Object.fromEntries(Object.entries(A[m]).filter(([e])=>!HIDE_C[m].includes(e))); })); }
// Price variants (a promotion, an off-peak rate) of a couple: the same couple at another price. Drawn as a hollow
// diamond joined to its couple by a dotted line, labelled in tooltips and tables; never a candidate of the frontier,
// the trend, the tiers or the crown.
const VTAG={promo:"promo",offpeak:"off-peak"};
function variantPts(pts){ const o=[]; pts.forEach(p=>(VARIANTS[p.m+"@"+p.e]||[]).forEach(v=>o.push({m:p.m,e:p.e,c:p.c*v.cost_ratio,t:p.t,s:p.s,
  base:p,front:p.front,vl:v.label,tag:VTAG[v.kind]||v.kind}))); return o; }
function drawVariants(s,pts,X,Y,fade){ variantPts(pts).forEach(v=>{ const col=cvar(MODELS[v.m].c), op=fade&&!v.front?0.3:0.9, x=X(v.c), y=Y(v.t), r=4.6;
  s.appendChild(el("line",{x1:X(v.base.c),y1:y,x2:x,y2:y,stroke:col,"stroke-width":1.3,"stroke-dasharray":"1.5 3","stroke-opacity":op}));
  s.appendChild(el("path",{d:`M ${x} ${y-r} L ${x+r} ${y} L ${x} ${y+r} L ${x-r} ${y} Z`,fill:cvar('--panel'),stroke:col,"stroke-width":1.6,"stroke-opacity":op})); }); }
const vNote=(m,e,c)=>(VARIANTS[m+"@"+e]||[]).map(v=>`<small class="vnote" title="${v.label}">${VTAG[v.kind]||v.kind} ${fmtC(c*v.cost_ratio)}×</small>`).join("");
// Selection (the bar at the top of the page): FILT.items are the page's makers (global page) or its models (a maker
// page); OFF the items turned off. The page's grids are rebuilt from the full copy with only the couples shown — the
// older-model switch, the beaten couples and the selection — so every chart, table and decision (frontier, numbers,
// trend, tiers, crown) is taken on what is shown, exactly as the older-model switch does on the Claude page. The
// selection is kept in the address (#makers=… or #models=…, the items shown turned on; none when all are on).
const selOK=m=>!OFF.has(FILT.of[m]);
const visItems=()=>{ const v=new Set(Object.keys(MODELS).filter(m=>showLegacy||!LEGACY.includes(m)).map(m=>FILT.of[m])); return FILT.items.filter(i=>v.has(i.id)); };
const LG_NUM=`<svg class="lgs" width="16" height="16" aria-hidden="true"><rect x="1" y="1" width="14" height="14" rx="7" fill="${cvar('--panel')}" stroke="${cvar('--ink')}" stroke-width="1.3"/><text x="8" y="11.5" font-size="9.5" font-weight="700" text-anchor="middle" fill="${cvar('--ink')}">1</text></svg>numbers: the Pareto frontier's couples, from the cheapest, named in the list under the chart`;
function shownGrid(o){ const C={},Q={}, keys=[...new Set([...Object.keys(GRID_ALL.cost),...Object.keys(GRID_ALL.qual)])];
  keys.forEach(m=>{ if(o.has(FILT.of[m])||(LEGACY.includes(m)&&!showLegacy)) return;
    const f=A=>HIDE_C[m]&&!showLegacy?Object.fromEntries(Object.entries(A).filter(([e])=>!HIDE_C[m].includes(e))):A;
    if(GRID_ALL.cost[m]) C[m]=f(GRID_ALL.cost[m]); if(GRID_ALL.qual[m]) Q[m]=f(GRID_ALL.qual[m]); });
  return {C,Q}; }
// A selection the page can draw: the price trend needs two couples of a current model, the tiers two frontier couples.
function selValid(o){ const {C,Q}=shownGrid(o), rows=[];
  for(const m in C) for(const e in C[m]) if(Q[m]&&Q[m][e]) rows.push({m,e,x:C[m][e][0],t:Q[m][e][0]});
  return rows.filter(p=>CURRENT.includes(p.m)).length>=2&&frontier(rows).front.length>=2; }
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
function renderFilterBar(leg){ const host=document.getElementById("filterbar"); if(!host) return;
  const vis=visItems();
  const chip=i=>{ const on=!OFF.has(i.id), o=new Set(OFF); o.add(i.id); const lock=on&&!selValid(o);
    return `<button type="button" class="fchip" id="fchip-${i.id}" aria-pressed="${on}"${lock?` aria-disabled="true" title="${FILT.lock}"`:""} style="--fc:${cvar(i.c)}" onclick="selToggle('${i.id}')"><span class="fchip-dot" aria-hidden="true"></span>${i.label}</button>`; };
  host.innerHTML=`<span class="fbar-k">${FILT.key==="makers"?"Makers":"Models"}</span>`
    +`<button type="button" class="fchip fchip-all" id="fchip-all" aria-pressed="${vis.every(i=>!OFF.has(i.id))}" onclick="selAll()">All</button>`
    +vis.map(chip).join("")+(leg?`<span class="fbar-sep" aria-hidden="true"></span>${leg}`:""); }
if(typeof addEventListener==="function") addEventListener("hashchange",()=>{ OFF=readSel(); applyLegacy(); tierDefaults(); renderAll(); });
// The Pareto frontier's couples carry a number on the charts (a small badge, from the cheapest), named in a list under
// each chart; hovering or tapping a badge, its point or its row highlights both. Badges keep a fixed size on screen.
const pxu=s=>{ const w=typeof s.getBoundingClientRect==="function"?s.getBoundingClientRect().width:0; return w>0?1100/w:1; };   // SVG units per screen pixel
const HL={};                                                // owner (chart or list id) → {couple key: [set(on)]}
function hlFront(k){ for(const o in HL) for(const kk in HL[o]) HL[o][kk].forEach(f=>f(kk===k)); }
let FRONT_NO={};
function frontRows(pts){ const fr=frontier(couples()).front, by={}; pts.forEach(p=>{ by[p.m+"@"+p.e]=p; });
  FRONT_NO={}; fr.forEach((p,i)=>{ FRONT_NO[p.m+"@"+p.e]=i+1; });
  return fr.map((p,i)=>({p:by[p.m+"@"+p.e],n:i+1})).filter(f=>f.p); }
// Placement: each badge goes to the first spot, nearest first, around its point — starting up-left, the side of the
// frontier no couple can occupy — whose box overlaps no badge already placed and covers no point; its leader line joins it to its point.
function frontBadges(s,id,F,obst,X,Y,mL,mT,iw,ih){ const u=pxu(s), r=8*u, gap=3*u, reg=HL[id]={}, placed=[];
  const pp=obst.map(p=>[X(p.c),Y(p.t)]), inPlot=(x,y,m)=>x>=mL+m&&x<=mL+iw-m&&y>=mT+m&&y<=mT+ih-m;
  const ang=[]; for(let i=0;i<16;i++){ const k=(i+1)>>1; ang.push((135+(i%2?1:-1)*k*22.5)*Math.PI/180); }
  F.forEach(({p,n})=>{ const ax=X(p.c), ay=Y(p.t); if(!inPlot(ax,ay,0)) return;
    let best=null, bad0=1e9;
    for(let ring=0; ring<12&&bad0>0; ring++){ const d=r+4*u+ring*(r+gap);
      for(const a of ang){ const x=ax+d*Math.cos(a), y=ay-d*Math.sin(a); if(!inPlot(x,y,r)) continue;
        let bad=0; placed.forEach(q=>{ if(Math.max(Math.abs(q.x-x),Math.abs(q.y-y))<2*r+gap) bad+=1000; });
        pp.forEach(([px,py])=>{ if(Math.max(Math.abs(px-x),Math.abs(py-y))<r+2*u) bad+=1; });
        if(bad<bad0){ bad0=bad; best={x,y}; if(!bad) break; } } }
    if(!best) best={x:ax,y:ay};
    const col=cvar(MODELS[p.m].c), g=el("g",{class:"fbadge","data-k":p.m+"@"+p.e}), dx=best.x-ax, dy=best.y-ay, dd=Math.hypot(dx,dy);
    if(dd>r+6*u){ const k1=3*u/dd, k2=1-r/dd;            // from the point's edge to the badge's
      g.appendChild(el("line",{x1:ax+dx*k1,y1:ay+dy*k1,x2:ax+dx*k2,y2:ay+dy*k2,stroke:col,"stroke-width":u,"stroke-opacity":0.6})); }
    const c=el("rect",{x:best.x-r,y:best.y-r,width:2*r,height:2*r,rx:r,fill:cvar('--panel'),stroke:col,"stroke-width":1.5*u});
    const t=el("text",{x:best.x,y:best.y+3.6*u,"font-size":(n<10?10:9)*u,"font-weight":700,"text-anchor":"middle",fill:cvar('--ink')}); t.textContent=n;
    g.appendChild(c); g.appendChild(t); s.appendChild(g);
    (reg[p.m+"@"+p.e]=reg[p.m+"@"+p.e]||[]).push(on=>{ c.setAttribute("fill",on?col:cvar('--panel')); t.setAttribute("fill",on?cvar('--panel'):cvar('--ink'));
      c.setAttribute("stroke-width",(on?2.5:1.5)*u); });
    placed.push({x:best.x,y:best.y,r,p,n,k:p.m+"@"+p.e}); });
  return placed; }
function frontList(id,F){ const host=document.getElementById(id); if(!host) return; host.innerHTML=""; const reg=HL[id]={};
  F.forEach(({p,n})=>{ const k=p.m+"@"+p.e, li=document.createElement("li");
    li.setAttribute("data-k",k); li.setAttribute("tabindex","0"); li.setAttribute("style",`--fc:${cvar(MODELS[p.m].c)}`);
    li.innerHTML=`<span class="fl-n">${n}</span><span class="fl-m">${MODELS[p.m].label}${p.e==="solo"?"":" · "+capE(p.e)}</span><span class="fl-v">${fmtC(p.c)}× · ${pct(p.s)}</span>`;
    (reg[k]=reg[k]||[]).push(on=>{ if(on) li.setAttribute("class","hl"); else li.removeAttribute("class"); });
    li.onpointerenter=e=>{ if(e.pointerType==="mouse") hlFront(k); }; li.onpointerleave=e=>{ if(e.pointerType==="mouse") hlFront(null); };
    li.onpointerup=e=>{ if(e.pointerType!=="mouse") hlFront(li.getAttribute("class")==="hl"?null:k); };   // a tap (touch, pen) toggles
    li.onfocus=()=>hlFront(k); li.onblur=()=>hlFront(null);
    host.appendChild(li); }); }
if(typeof addEventListener==="function"){ let rw=0; addEventListener("resize",()=>{ const s=document.getElementById("chartB"), w=s?s.getBoundingClientRect().width:0;
  if(w&&Math.abs(w-rw)>1){ rw=w; drawB(); drawPareto(); } }); }   // the badges and the tooltip keep their size on screen
'''

HOVER_FN = r'''function hoverTip(s,ells,pts,X,Y,mL,iw,bdg){ const DEF=0.15,HOV=0.78;   // multi-site: the frontier's badges, a tooltip of fixed size on screen
  const tip=el("g",{"pointer-events":"none",opacity:0}), trect=el("rect",{rx:3,fill:cvar('--panel'),stroke:cvar('--line'),"stroke-width":1,"fill-opacity":0.97});
  const ttxt=el("text",{"font-size":9.5,"font-weight":600,"text-anchor":"middle"}); tip.appendChild(trect); tip.appendChild(ttxt); s.appendChild(tip);
  s.onmousemove=ev=>{ const P=new DOMPoint(ev.clientX,ev.clientY).matrixTransform(s.getScreenCTM().inverse()), u=pxu(s), touch=!!ev.pointerType&&ev.pointerType!=="mouse";
    ells.forEach(o=>{ const dx=P.x-o.cx, dy=P.y-o.cy, rx=dx>0?o.rxR:o.rxL, ry=dy>0?o.ryD:o.ryU; o.el.setAttribute("opacity",((dx/rx)**2+(dy/ry)**2<=1)?HOV:DEF); });
    let hit=null, best=null, bd=(touch?22:7)*u, hd=touch?6*u:0;   // the nearest: a badge (from its edge, 0 inside) or a point (from its centre)
    (bdg||[]).forEach(b=>{ const d=Math.max(0,Math.max(Math.abs(P.x-b.x),Math.abs(P.y-b.y))-b.r); if(d<=hd){ hd=d; hit=b; } });
    pts.forEach(p=>{ const d=Math.hypot(P.x-X(p.c),P.y-Y(p.t)); if(d<bd){ bd=d; best=p; } });
    if(hit&&(!best||hd===0||hd<bd)) best=hit.p; else hit=null;
    const k=best&&!best.vl?best.m+"@"+best.e:null; hlFront(k);
    if(best){ const fs=11.5*u, n=k&&FRONT_NO[k], y0=hit?hit.y-hit.r-6*u:Y(best.t)-10*u;
      const name=`${n?n+". ":""}${MODELS[best.m].label} · ${capE(best.e)}${best.vl?" · "+best.vl:""}`, val=`cost ${fmtC(best.c)}× · score ${pct(best.s)}`;
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
  s.onpointerup=ev=>{ if(ev.pointerType!=="mouse") s.onmousemove(ev); }; }   // a tap (touch, pen) names the point or badge under it, as a hover does
'''


def app_patches(S):
    j = lambda v: json.dumps(v, separators=(",", ":"), ensure_ascii=False)
    return [
        (re.compile(r"function hoverTip\(s,ells,pts,X,Y,mL,iw\)\{.*?\n(?=// Force-directed label layout)", re.S), HOVER_FN),
        (re.compile(r"const LEGACY=\[[^\]\n]*\];"), f"const LEGACY={j(S['legacy_keys'])};"),
        (re.compile(r"const CURRENT=\[[^\]\n]*\];"),
         f"const CURRENT={j(S['current_keys'])};\nconst HIDE_B={j(S['hide_landscape'])}, LEGACY_HINT={j(S['legacy_hint'])}, "
         f"DASH={j(DASH)}, HIDE_C={j(S['hide_couples'])}, VARIANTS={j(S['variants'])}, FILT={j(S['filt'])};   // per-site settings (site/makers.json)"),
        ('  else { delete COSTGRID[m]; delete QUALGRID[m]; } }); }', '  else { delete COSTGRID[m]; delete QUALGRID[m]; } }); hideCouples(); applyFilter(); }'),
        ('const xmn=Math.min(...pts.map(p=>p.clo)), xmx=Math.max(...pts.map(p=>p.chi)),',
         'const xmn=Math.min(...pts.map(p=>p.clo),...variantPts(pts).map(v=>v.c)), xmx=Math.max(...pts.map(p=>p.chi),...variantPts(pts).map(v=>v.c)),', 2),
        ('  const segs=[];                                                          // curves + points on top',
         '  drawVariants(s,pts,X,Y,false);\n  const segs=[];                                                          // curves + points on top'),
        ('  placeLabels(s,labs,ppix,segs,W,mL,mT,ih);\n  hoverTip(s,ells,pts,X,Y,mL,iw);\n  const lg=document.getElementById("legendB");',
         '  const bdg=frontBadges(s,"chartB",F,pts.concat(variantPts(pts)),X,Y,mL,mT,iw,ih);   // the frontier\'s numbers, listed under the chart\n'
         '  hoverTip(s,ells,pts.concat(variantPts(pts)),X,Y,mL,iw,bdg);\n  frontList("flistB",F);\n  const lg=document.getElementById("legendB");'),
        ('  // frontier labels (model · effort), force-directed to dodge overlaps and the frontier line\n'
         '  const ppix=front.map(p=>({x:X(p.c),y:Y(p.t)})), segs=[];\n'
         '  for(let i=0;i<front.length-1;i++) segs.push([X(front[i].c),Y(front[i].t),X(front[i+1].c),Y(front[i+1].t)]);\n'
         '  const labs=front.map(p=>{ const t=`${MODELS[p.m].label}${p.e==="solo"?"":" · "+capE(p.e)}`, w=t.length*7.2+8;\n'
         '    return {ax:X(p.c),ay:Y(p.t),lx:X(p.c)+18+w/2,ly:Y(p.t),t,col:cvar(MODELS[p.m].c),lead:cvar(MODELS[p.m].c),w,h:17,fs:13,mdl:true}; });\n'
         '  placeLabels(s,labs,ppix,segs,W,mL,mT,ih);\n  hoverTip(s,ells,pts,X,Y,mL,iw);\n  const lg=document.getElementById("legendP");',
         '  const F=frontRows(pts), bdg=frontBadges(s,"chartP",F,pts.concat(variantPts(pts)),X,Y,mL,mT,iw,ih);   // the frontier\'s numbers, from the cheapest\n'
         '  hoverTip(s,ells,pts.concat(variantPts(pts)),X,Y,mL,iw,bdg);\n  const lg=document.getElementById("legendP");'),
        ('  const pb=document.getElementById("pareto-blocks");   // chained mini-blocks (cost order), same style as the tier cards but small\n'
         '  if(pb) pb.innerHTML=front.map((p,i)=>`${i?\'<span class="pconn">→</span>\':\'\'}<span class="pblock" style="border-color:${cvar(MODELS[p.m].c)}"><b>${MODELS[p.m].label}</b><span class="pblock-e">${capE(p.e)}</span><span class="pblock-n">${pct(p.s)} · ${fmtC(p.c)}×</span></span>`).join("");',
         '  frontList("pareto-blocks",F);                        // the frontier\'s couples by number (cost order): model · effort, cost, score'),
        ('+`<span class="lg"><span class="sw" style="opacity:.25;background:var(--ink);border-radius:50%"></span>dominated</span>`',
         '+`<span class="lg">${LG_NUM}</span><span class="lg"><span class="sw" style="opacity:.25;background:var(--ink);border-radius:50%"></span>dominated</span>`'),
        ('front.forEach(p=>{ if(p.t<Tmn||p.t>Tmx) return; svg+=`<circle cx="${X(p.t)}" cy="${mT+ih}" r="3.2" fill="${cvar(MODELS[p.m].c)}" stroke="${cvar(\'--panel\')}" stroke-width="1"/>`; });\n  host.innerHTML=svg+`</svg>`;',
         'front.forEach((p,i)=>{ if(p.t<Tmn||p.t>Tmx) return; svg+=`<circle cx="${X(p.t)}" cy="${mT+ih}" r="3.2" fill="${cvar(MODELS[p.m].c)}" stroke="${cvar(\'--panel\')}" stroke-width="1" data-k="${p.m}@${p.e}">`\n'
         '    +`<title>${i+1}. ${MODELS[p.m].label}${p.e==="solo"?"":" · "+capE(p.e)} — cost ${fmtC(p.c)}× · score ${pct(p.s)}</title></circle>`; });\n'
         '  host.innerHTML=svg+`</svg><p class="tuner-tip" aria-live="polite"></p>`;   // the frontier\'s couples: their number and identity on hover or tap\n'
         '  host.onmousemove=host.onpointerup=ev=>{ const c=ev.target&&ev.target.closest?ev.target.closest("circle[data-k]"):null, tt=host.querySelector(".tuner-tip");\n'
         '    hlFront(c?c.getAttribute("data-k"):null); if(tt) tt.textContent=c?c.querySelector("title").textContent:""; };'),
        ('  pts.forEach(p=>{ const col=cvar(MODELS[p.m].c);\n    s.appendChild(el("circle",p.front?',
         '  drawVariants(s,pts,X,Y,true);\n  pts.forEach(p=>{ const col=cvar(MODELS[p.m].c);\n    s.appendChild(el("circle",p.front?'),
        ('${fmtC(c[0])}<small>merged · ${c[1]}</small></div>', '${fmtC(c[0])}<small>merged · ${c[1]}</small>${vNote(m,"solo",c[0])}</div>'),
        ('${fmtC(c[0])}<small>${c[1]}</small></div></td>`', '${fmtC(c[0])}<small>${c[1]}</small>${vNote(m,e,c[0])}</div></td>`'),
        ('<td class="num">${fmtC(p.c)}×</td><td class="num">${pct(p.s)}</td>', '<td class="num">${fmtC(p.c)}×${vNote(p.m,p.e,p.c)}</td><td class="num">${pct(p.s)}</td>'),
        ('${vIndex(r)}<small>${vIndex(r-sd)}–${vIndex(r+sd)}</small></div>`; };',
         '${vIndex(r)}<small>${vIndex(r-sd)}–${vIndex(r+sd)}</small>${(VARIANTS[p.m+"@"+p.e]||[]).map(v=>`<small class="vnote" title="${v.label}">${VTAG[v.kind]||v.kind} ${vIndex(r-Math.log(v.cost_ratio))}</small>`).join("")}</div>`; };'),
        ('const visibleModels=()=>Object.keys(MODELS).filter(m=>showLegacy||!LEGACY.includes(m));\n',
         'const visibleModels=()=>Object.keys(MODELS).filter(m=>showLegacy||!LEGACY.includes(m));\n' + LEGEND_FN),
        ('+legacy("tgl-legacy-b")', ''), ('+legacy("tgl-legacy-p")+ovals("tgl-ovals-p")+bands("tgl-bands-p");\n}',
         '+ovals("tgl-ovals-p")+bands("tgl-bands-p");\n  renderFilterBar(legacy("tgl-legacy-f"));   // the selection bar, with the older-model switch\n}'),
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
         '  const F=frontRows(pts);                                   // the page\'s frontier: numbered badges, from the cheapest (no other label)\n'),
        ('<b>hover a point</b> for its identity</span>', '<b>hover or tap a point</b> for any other (model · effort, cost, score)</span><span class="lg">${LG_NUM}</span>', 2),
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


def body_patches(S, mc_sentence):
    cur = ' aria-current="page"'
    nav = "".join(f'<a href="{S["up"]}{t["path"]}index.html"{cur if t["id"] == S["id"] else ""}>{esc(t["name"])}</a>' for t in S["all"])   # the page's file:
    # a folder link (openai/) opens the page only through a web server; opened from the disk it shows the folder
    banner = f'  <p class="draft-banner" role="note">{esc(DRAFT)}</p>\n' if DRAFT else ""
    noun = (S["noun"] + " ") if S["noun"] else ""
    shows = ("this page shows the current models of every maker, and the older couples no other model of their maker "
             "beats, but no model that another model of the same maker entirely outclasses"
             if S["id"] == "global" else f"this page shows the {S['name']} couples")
    return [
        ('<div class="wrap">\n  <header class="hero">',
         f'<div class="wrap">\n  <nav class="sitenav" aria-label="Model makers">{nav}</nav>\n{banner}'
         f'  <div class="filterbar" id="filterbar" role="toolbar" aria-label="Show or hide {"makers" if S["id"] == "global" else "models"}"></div>\n  <header class="hero">'),
        ('<h1>Claude models compared <span class="h1-line">cost vs quality at every effort level</span></h1>', f"<h1>{S['h1']}</h1>"),
        ('What each recent Claude model actually costs, at every effort level, and the quality it delivers — fused from public benchmark measurements for every (model, effort) pair.',
         S["lede"]),
        ('        <p class="lede">To compare two models directly — Fable, Opus, Sonnet or Haiku, effort by effort — see the <a href="claude-models-head-to-head.html">head-to-head page</a>.</p>\n', ""),
        ("Quality vs. cost of every Claude model, at each effort level", f"Quality vs. cost of every {noun}model, at each effort level"),
        (" <b>Haiku&nbsp;4.5</b> lives only in the matrix and Pareto.",
         S["hide_note"] + ("" if not S["has_lines"] else " A model's <b>builds and modes</b> — a dated build, a preview, a Pro mode — share its colour: "
         "the first is drawn with <b>filled</b> points, the others with <b>hollow</b> points, and its label and tooltip say "
         "what it is. They are separate couples, each with its own effort ladder.")),
        ('aria-label="Quality vs cost, one curve per model, one point per effort"></svg></div>',
         'aria-label="Quality vs cost, one point per model and effort"></svg></div>\n'
         '      <ol id="flistB" class="flist" aria-label="The Pareto frontier\'s couples, numbered from the cheapest"></ol>'),
        ('<div id="pareto-blocks" class="pareto-blocks"></div>',
         '<ol id="pareto-blocks" class="flist" aria-label="The Pareto frontier\'s couples, numbered from the cheapest"></ol>'),
        ('<b>Solid</b> = frontier, <b>faded</b> = dominated.',
         '<b>Solid</b> = frontier, <b>faded</b> = dominated; each frontier couple carries a <b>number</b>, from the cheapest, '
         'named in the list under the chart — <b>hover</b> or <b>tap</b> a number, a point or a row to bring both forward. '
         'No line joins a model\'s couples.'),
        ('<p class="cap">One curve per model, one point per configuration (thinking off, minimal, low → max, thinking on).',
         '<p class="cap">One point per couple: a model at one configuration (thinking off, minimal, low → max, thinking on); '
         'no line joins a model\'s couples. Only the couples of the <b>Pareto frontier</b> are marked, by a <b>number</b> '
         'from the cheapest, named in the list under the chart; <b>hover</b> or <b>tap</b> a number or a row to bring '
         'both forward, and any other point for its model, effort, cost and score.'),
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
    ]


EXTRA_CSS = """
.sitenav{display:flex;flex-wrap:wrap;gap:6px 8px;margin:0 0 22px;font-size:13.5px}
.sitenav a{color:var(--muted);text-decoration:none;border:1px solid var(--line2);border-radius:999px;padding:3px 12px;background:var(--panel)}
.sitenav a:hover{color:var(--ink);border-color:var(--muted)}
.sitenav a[aria-current="page"]{color:var(--paper);background:var(--ink);border-color:var(--ink);font-weight:600}
.draft-banner{margin:0 0 26px;padding:11px 16px;border:1px solid var(--warn);border-left:5px solid var(--warn);border-radius:10px;
  background:color-mix(in srgb,var(--warn) 12%,var(--panel));color:var(--ink);font-size:14.5px}
.lgl{display:inline-flex;flex-wrap:wrap;gap:2px 9px;margin-left:4px;font-size:11.5px;color:var(--muted)}
.lgi{display:inline-flex;align-items:center;gap:3px}
.lgs{flex:none}
.vnote{display:block;font-style:italic;color:var(--muted)}
.filterbar{position:sticky;top:0;z-index:30;display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;margin:-8px 0 22px;padding:9px 0;
  background:var(--paper);border-bottom:1px solid var(--line);font-size:13px}
.fbar-k{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--faint);font-weight:700;margin-right:2px;flex:none}
.fchip{font:inherit;font-size:13px;display:inline-flex;align-items:center;gap:6px;padding:4px 11px 4px 8px;border-radius:999px;flex:none;
  border:1.5px solid var(--fc,var(--line2));background:color-mix(in srgb,var(--fc,var(--ink)) 13%,var(--panel));color:var(--ink);cursor:pointer;white-space:nowrap}
.fchip:hover{border-color:var(--ink)}
.fchip:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.fchip-dot{width:10px;height:10px;border-radius:50%;background:var(--fc);flex:none}
.fchip[aria-pressed="false"]{background:var(--panel);border-color:var(--line2);color:var(--faint);text-decoration:line-through}
.fchip[aria-pressed="false"] .fchip-dot{background:transparent;box-shadow:inset 0 0 0 1.5px var(--fc)}
.fchip[aria-disabled="true"]{cursor:not-allowed}
.fchip-all{--fc:var(--ink);padding-left:11px}
.fbar-sep{width:1px;align-self:stretch;background:var(--line2);margin:0 4px;flex:none}
.filterbar .tgl{padding:4px 10px 4px 6px;flex:none;white-space:nowrap}
@media (max-width:640px){.filterbar{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:thin;-webkit-overflow-scrolling:touch}.filterbar .tgl-hint{display:none}}
.flist{list-style:none;margin:14px 0 0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:2px 12px;font-size:12.5px}
.flist li{display:flex;align-items:center;gap:7px;padding:3px 6px;border-radius:7px;min-width:0;cursor:default}
.flist li.hl{background:color-mix(in srgb,var(--fc) 16%,transparent)}
.flist li:focus-visible{outline:2px solid var(--fc);outline-offset:1px}
.fl-n{flex:none;display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border-radius:50%;border:1.5px solid var(--fc);
  background:var(--panel);font-size:10px;font-weight:700;color:var(--ink);font-variant-numeric:tabular-nums}
.flist li.hl .fl-n{background:var(--fc);color:var(--panel)}
.fl-m{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600}
.fl-v{flex:none;color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap}
.fbadge{cursor:default}
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
    S["outclassed"] = outclassed(shown, CG, QG, S["maker_of"])   # {A: [B, …]}: into the older models, current or not
    S["current_keys"] = [k for k in S["current"] if k in CG and k not in S["outclassed"]]
    for k in S["current"]:
        if k not in S["keys"]: warn(f"{S['id']}: current key {k} is not one of the page's keys")
        elif k not in CG: warn(f"{S['id']}: current model {k} has no couple published on both axes")
    if not S["current_keys"]: sys.exit(f"!! {S['id']}: no current model left for the price trend")
    S["hide_couples"] = {}
    if S["legacy"] is None:                    # global page: current models, and the couples of older models that no
        maker, base = S["maker_of"], (lambda k: MODEL_LINE.get(k, k))   # other model of the same maker strictly beats
        beaten = lambda k, e: any(maker[k2] == maker[k] and base(k2) != base(k) and CG[k2][e2][0] < CG[k][e][0]
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
    S["variants"] = {c: v for c, v in VARIANTS.items() if c.split("@")[0] in CG and c.split("@")[1] in CG[c.split("@")[0]]}
    lock = "the price trend needs two couples of a current model, and the tiers two frontier couples"
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
    body = patch(body0, body_patches(S, mc_text(CG, MCSE, models)), f"body.html ({S['id']})")
    body = body.replace("__REPO__", REPO_URL).replace("__DATA_URL__", DATA_URL)
    body = body.replace("__EFFORT_HEAD__", "".join(f"<th>{CAP[e].lower() if e in ('nothink', 'think') else e}</th>" for e in cols))
    span = math.exp(max(c[0] for v in CG.values() for c in v.values()) - min(c[0] for v in CG.values() for c in v.values()))
    body = body.replace("__COSTSPAN__", str(round(span)))
    body = body.replace("__NCOSTROWS__", str(DIAG["cost"]["rows"])).replace("__NSCOREROWS__", str(DIAG["quality"]["rows"]))
    body = body.replace("__NTREND__", str(sum(len(CG[m]) for m in S["current_keys"])))
    pre = prerender(app, css)
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
                couples_all=sum(len(CG[k]) for k in shown), models_all=len(shown), outclassed=S["outclassed"],
                counts=plain(pre.get(".nsrc", "")), answer=pre.get("answer-full", ""),
                ladder=monotonicity_report({k: CG[k] for k in vis}, {k: QG[k] for k in vis}),
                ladder_all=monotonicity_report(CG, QG))
    return info


def main():
    global DRAFT
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stale-fit", action="store_true",
                    help="build from a model/fit-cache.json whose inputs have changed since the fit (local preview only: "
                         "the couples and values are the last fit's, the sources table reads today's data; the banner says so)")
    args = ap.parse_args()
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
