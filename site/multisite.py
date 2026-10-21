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
import datetime, hashlib, html as htmlmod, json, math, os, re, shutil, sys

from config import HERE, ROOT, REPO_URL, EFFORT_ORDER
from grids import fused_grids, monotonicity_report
from render import inject, prerender
from sources import groups_data
sys.path.insert(0, os.path.join(ROOT, "data"))
from catalog import MODELS as CAT, MODEL_LINE, MODEL_ORDER

SET  = json.load(open(os.path.join(HERE, "makers.json"), encoding="utf-8"))
OUT  = os.path.join(ROOT, SET["out_dir"])
BASE = SET["base_url"]
DRAFT = SET.get("draft", "")            # one setting: "" removes the banner and the noindex tag on every page
DASH = ["", "6 4", "1.5 3.5"]           # a model's builds and modes: solid, dashed, dotted (hollow points)
esc = lambda s: htmlmod.escape(s, quote=True)
warn = lambda s: print("  !! " + s)


# ---------------------------------------------------------------- per-site models, labels, colours
def maker_keys(mk):
    """A maker's catalogue keys in legend order: each base model of its settings, then that model's lines (the
    catalogue's dated builds, previews and modes), in catalogue order. Warns about a key of the maker's prefixes
    that the settings do not place."""
    M = SET["makers"][mk]
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
            name = SET["makers"][mk]["models"].get(k) if mk else None
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
    gcur = [k for mk, M in SET["makers"].items() for k in M["current"]]
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
                 noun=M["name"], hide_landscape=[], hide_note="", generation=SET["global"]["generation"])
        s.update({k: v for k, v in M.items() if k in s})
        s.update(id=mk, name=M["name"], path=M["path"], keys=maker_keys(mk), current=M["current"], legacy=M["legacy"],
                 maker_of=maker_of, label=labeller({}), tag=tag)
        out.append(s)
    return out


# ---------------------------------------------------------------- page text: exact replacements
def patch(text, reps, what):
    for old, new in reps:
        n = text.count(old) if isinstance(old, str) else len(old.findall(text))
        if n != 1:
            sys.exit(f"!! {what}: expected one occurrence of {old if isinstance(old, str) else old.pattern!r:.90}, found {n}")
        text = text.replace(old, new) if isinstance(old, str) else old.sub(lambda m: new, text)
    return text


LEGEND_FN = r'''
// Legend: one entry per model; a model's builds and modes (a dated build, a preview, a Pro mode) are listed inside its
// entry, each with the stroke it has on the charts (solid, dashed, dotted; hollow points for all but the first).
const lsty=m=>MODELS[m].ls||0;
function legendModels(ms){ const groups=[], at={};
  ms.forEach(m=>{ const b=MODELS[m].base||m; if(!(b in at)){ at[b]=groups.length; groups.push({b,ms:[]}); } groups[at[b]].ms.push(m); });
  const smp=(m,col)=>`<svg class="lgs" width="24" height="10" aria-hidden="true"><line x1="1" y1="5" x2="23" y2="5" stroke="${col}" stroke-width="2.2"${lsty(m)?` stroke-dasharray="${DASH[lsty(m)]}"`:""}/><circle cx="12" cy="5" r="3.2" fill="${lsty(m)?cvar('--panel'):col}" stroke="${col}" stroke-width="1.6"/></svg>`;
  return groups.map(g=>{ const m0=g.ms[0], col=cvar(MODELS[m0].c);
    if(g.ms.length===1&&!MODELS[m0].lt) return `<span class="lg"><span class="sw" style="background:${col}"></span>${MODELS[m0].label}</span>`;
    return `<span class="lg"><span class="sw" style="background:${col}"></span>${MODELS[m0].bl}<span class="lgl">${g.ms.map(m=>`<span class="lgi">${smp(m,col)}${MODELS[m].lt}</span>`).join("")}</span></span>`; }).join(""); }
'''


def app_patches(S):
    j = lambda v: json.dumps(v, separators=(",", ":"), ensure_ascii=False)
    return [
        ('const LEGACY=["opus-4.7","sonnet-4.6","opus-4.8"];', f"const LEGACY={j(S['legacy_keys'])};"),
        ('const CURRENT=["fable-5.1","opus-5.5","sonnet-5.5","haiku-5.5"];',
         f"const CURRENT={j(S['current_keys'])};\nconst HIDE_B={j(S['hide_landscape'])}, LEGACY_HINT={j(S['legacy_hint'])}, "
         f"DASH={j(DASH)};   // per-site settings (site/makers.json)"),
        ('const visibleModels=()=>Object.keys(MODELS).filter(m=>showLegacy||!LEGACY.includes(m));\n',
         'const visibleModels=()=>Object.keys(MODELS).filter(m=>showLegacy||!LEGACY.includes(m));\n' + LEGEND_FN),
        ('const legacy=id=>tgl(id,showLegacy,"Older models","Opus 4.7 · Sonnet 4.6","toggleLegacy");',
         'const legacy=id=>LEGACY.length?tgl(id,showLegacy,"Older models",LEGACY_HINT,"toggleLegacy"):"";'),
        ('const pts=couples().filter(p=>p.m!=="haiku-4.5");', 'const pts=couples().filter(p=>!HIDE_B.includes(p.m));'),
        ('"stroke-width":2.2,"stroke-linejoin":"round"}));\n    mp.forEach(p=>s.appendChild(el("circle",{cx:X(p.c),cy:Y(p.t),r:3.6,fill:col,stroke:cvar(\'--panel\'),"stroke-width":1.4})));',
         '"stroke-width":2.2,"stroke-linejoin":"round",...(lsty(m)?{"stroke-dasharray":DASH[lsty(m)]}:{})}));\n'
         '    mp.forEach(p=>s.appendChild(el("circle",lsty(m)?{cx:X(p.c),cy:Y(p.t),r:3.6,fill:cvar(\'--panel\'),stroke:col,"stroke-width":1.8}'
         ':{cx:X(p.c),cy:Y(p.t),r:3.6,fill:col,stroke:cvar(\'--panel\'),"stroke-width":1.4})));'),
        ('visibleModels().filter(m=>m!=="haiku-4.5").map(m=>`<span class="lg"><span class="sw" style="background:${cvar(MODELS[m].c)}"></span>${MODELS[m].label}</span>`).join("")',
         'legendModels(visibleModels().filter(m=>!HIDE_B.includes(m)))'),
        ('visibleModels().map(m=>`<span class="lg"><span class="sw" style="background:${cvar(MODELS[m].c)}"></span>${MODELS[m].label}</span>`).join("")',
         'legendModels(visibleModels())'),
        ('s.appendChild(el("circle",p.front?{cx:X(p.c),cy:Y(p.t),r:5.6,fill:col,stroke:cvar(\'--panel\'),"stroke-width":1.3}\n      :{cx:X(p.c),cy:Y(p.t),r:3.4,fill:col,"fill-opacity":.25})); });',
         's.appendChild(el("circle",p.front?(lsty(p.m)?{cx:X(p.c),cy:Y(p.t),r:5.6,fill:cvar(\'--panel\'),stroke:col,"stroke-width":2.4}:{cx:X(p.c),cy:Y(p.t),r:5.6,fill:col,stroke:cvar(\'--panel\'),"stroke-width":1.3})\n'
         '      :(lsty(p.m)?{cx:X(p.c),cy:Y(p.t),r:3.4,fill:"none",stroke:col,"stroke-opacity":.35,"stroke-width":1.4}:{cx:X(p.c),cy:Y(p.t),r:3.4,fill:col,"fill-opacity":.25}))); });'),
        (re.compile(r"const GMODEL = \{\n.*?\n\};\n", re.S),
         "const GMODEL = Object.fromEntries(Object.keys(MODELS).map(m=>[m,{l:MODELS[m].label,c:MODELS[m].c,cur:1}]));   // the page's models\n"),
        ('  const pub=s=>s==="anthropic-chart"?"anthropic-syscard":s;        // one publisher = one source (mirrors PUBLISHER in build.py)\n'
         '  const nSrc=new Set(curGroups.map(g=>pub(g.s))).size;',
         '  const nSrc=new Set(curGroups.map(g=>g.p)).size;                  // one publisher = one source (data/catalog/publishers.json)'),
    ]


def body_patches(S, engines):
    cur = ' aria-current="page"'
    nav = "".join(f'<a href="{S["up"]}{t["path"]}"{cur if t["id"] == S["id"] else ""}>{esc(t["name"])}</a>' for t in S["all"])
    banner = f'  <p class="draft-banner" role="note">{esc(DRAFT)}</p>\n' if DRAFT else ""
    noun = (S["noun"] + " ") if S["noun"] else ""
    eng = ("run with " + (f'<a href="https://github.com/pymc-devs/nutpie">nutpie</a> on both axes' if engines == {"nutpie"}
           else ", ".join(sorted(engines))))
    return [
        ('<div class="wrap">\n  <header class="hero">',
         f'<div class="wrap">\n  <nav class="sitenav" aria-label="Model makers">{nav}</nav>\n{banner}  <header class="hero">'),
        ('<h1>Claude models compared <span class="h1-line">cost vs quality at every effort level</span></h1>', f"<h1>{S['h1']}</h1>"),
        ('What each recent Claude model actually costs, at every effort level, and the quality it delivers — fused from public benchmark measurements for every (model, effort) pair.',
         S["lede"]),
        ('        <p class="lede">To compare two models directly — Fable, Opus, Sonnet or Haiku, effort by effort — see the <a href="claude-models-head-to-head.html">head-to-head page</a>.</p>\n', ""),
        ("Quality vs. cost of every Claude model, at each effort level", f"Quality vs. cost of every {noun}model, at each effort level"),
        (" <b>Haiku&nbsp;4.5</b> lives only in the matrix and Pareto.",
         S["hide_note"] + ("" if not S["has_lines"] else " A model's <b>builds and modes</b> — a dated build, a preview, a Pro mode — share its colour and "
         "its legend entry: the first is drawn <b>solid</b>, the others <b>dashed</b> or <b>dotted</b> with <b>hollow</b> "
         "points, and each is labelled with what it is. They are separate couples, each with its own effort ladder.")),
        ("Best Claude model for the price — the Pareto frontier", f"Best {noun}model for the price — the Pareto frontier"),
        ("Normalized cost matrix — Claude effort levels compared", f"Normalized cost matrix — {noun}effort levels compared"),
        (" <b>Haiku&nbsp;4.5</b> = a single merged cell (<b>single operating point</b>&nbsp;: no discrete effort parameter, see the measurement sources).",
         " A model with a <b>single operating point</b> (no discrete effort parameter, <i>solo</i> in the data) fills a single merged cell."),
        (re.compile(r"<p>Each release buys the same quality for less — .*?</p>"), f"<p>{S['generation']}</p>"),
        ('<p class="sub"><b>Checks.</b> ',
         '<p class="sub"><b>Checks</b>, on the fit of 29 September 2026, before the other makers\' couples joined the data<b>.</b> '),
        ('run with CmdStan (cost) and <a href="https://github.com/pymc-devs/nutpie">nutpie</a> (quality)', eng),
        ("not affiliated with or endorsed by Anthropic", "not affiliated with or endorsed by any model maker"),
        ('<a href="raw-data.csv">download the data (CSV)</a>', f'<a href="{REPO_URL}/blob/main/raw-data.csv">download the data (CSV)</a>'),
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


# ---------------------------------------------------------------- one page
def build_page(S, css0, body0, app0):
    CG, QG, PANEL, DIAG, MCSE = fused_grids(models=S["keys"], both_axes=True)
    models, mcss = page_models(S, S["keys"], CG)
    shown = list(models)
    S["has_lines"] = any("ls" in v for v in models.values())
    lines_of = lambda ks: [k for k in shown if k in ks or MODEL_LINE.get(k) in ks]
    S["current_keys"] = [k for k in S["current"] if k in CG]
    for k in S["current"]:
        if k not in S["keys"]: warn(f"{S['id']}: current key {k} is not one of the page's keys")
    S["legacy_keys"] = ([k for k in shown if k not in S["current_keys"]] if S["legacy"] is None else lines_of(S["legacy"]))
    leg = [k for k in S["legacy_keys"] if not models[k].get("ls")]
    names = [models[k].get("bl", models[k]["label"]) for k in leg]
    S["legacy_hint"] = (" · ".join(names) if len(names) <= 3 else " · ".join(names[:2]) + f" and {len(names) - 2} more")
    couples = {f"{m}@{e}" for m, es in CG.items() for e in es}
    GD = groups_data(couples=couples, unverified="—")
    css = with_colours(css0, *mcss) + EXTRA_CSS
    app = patch(app0, app_patches(S), f"app.js ({S['id']})")
    app = app.replace("__MODELS__", json.dumps(models, separators=(",", ":"), ensure_ascii=False))
    app = app.replace("__COSTGRID__", json.dumps(CG, separators=(",", ":")))
    app = app.replace("__QUALGRID__", json.dumps(QG, separators=(",", ":")))
    app = app.replace("__PANEL__", json.dumps(PANEL, separators=(",", ":")))
    app = app.replace("__GROUPS_DATA__", json.dumps(GD, separators=(",", ":"), ensure_ascii=False))
    engines = {DIAG[a].get("engine", "?") for a in ("cost", "quality")}
    body = patch(body0, body_patches(S, engines), f"body.html ({S['id']})")
    body = body.replace("__REPO__", REPO_URL)
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
    d = os.path.join(OUT, S["path"]); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(html)
    vis = [k for k in shown if k not in S["legacy_keys"]]
    info = dict(id=S["id"], path=S["path"], title=S["title"], bytes=len(html.encode()), date=date.isoformat(),
                couples_default=sum(len(CG[k]) for k in vis), models_default=len(vis),
                couples_all=sum(len(CG[k]) for k in shown), models_all=len(shown),
                counts=plain(pre.get(".nsrc", "")), answer=pre.get("answer-full", ""),
                ladder=monotonicity_report({k: CG[k] for k in vis}, {k: QG[k] for k in vis}),
                ladder_all=monotonicity_report(CG, QG))
    return info


def main():
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
    for i in infos:
        print(f"built {os.path.relpath(os.path.join(OUT, i['path'], 'index.html'), ROOT)}  ({i['bytes']} bytes) · "
              f"{i['couples_default']} couples of {i['models_default']} models shown by default "
              f"({i['couples_all']} of {i['models_all']} with older models) · {i['counts']}")
        for v in i["ladder"]:
            print("  effort ladder inverted (shown by default): " + v)
    print(f"wrote {os.path.relpath(OUT, ROOT)}/llms.txt, robots.txt, summary.json, favicons"
          + (" — DRAFT: banner and noindex on every page" if DRAFT else ""))


if __name__ == "__main__":
    main()
