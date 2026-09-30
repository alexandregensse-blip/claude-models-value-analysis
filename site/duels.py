"""The head-to-head page: every pair of current Claude models (plus each model against its predecessor), effort by
effort, from the same fitted values as the main page. Static HTML: no script is needed to read it. Every sentence is
computed from the grids, at the 0.84 level of the main page (docs/DISPLAY-METHODOLOGY.md § 7), axis by axis: one
couple is ahead of another on an axis when the normal law on the difference of the two centres, with the two
quasi-standard errors, puts it ahead with probability REACH or more; otherwise the two are level within the
uncertainty. The rules of this page: docs/DISPLAY-METHODOLOGY.md § 15."""
import html as htmlmod, json, math, os, re, sys

from config import ROOT, SITE_URL, SITE_NAME, TITLE as HOME_TITLE, EFFORT_ORDER
from grids import panel_score
sys.path.insert(0, os.path.join(ROOT, "data"))
from catalog import MODELS

FILE  = "claude-models-head-to-head.html"
URL   = SITE_URL + FILE
TITLE = "Fable vs Opus vs Sonnet vs Haiku: Claude models head-to-head"
DESCRIPTION = ("Every pair of Claude models compared effort by effort: the cost gap, the quality gap, and the cheapest "
               "effort of each that matches the other. Open data.")
CURRENT = ["fable-5.1", "opus-5.5", "sonnet-5.5", "haiku-4.5"]           # the latest model of each family
SUCCESSION = [("fable-5.1", "fable-5"), ("opus-5.5", "opus-5"), ("sonnet-5.5", "sonnet-5")]
REACH = 0.84
LEGACY = ["opus-4.7", "sonnet-4.6"]                                    # hidden on the main page (site/app.js)
EFF = {"low": "low", "medium": "medium", "high": "high", "xhigh": "xHigh", "max": "max", "solo": "its only setting"}

Phi = lambda z: 0.5 * (1 + math.erf(z / math.sqrt(2)))
esc = lambda s: htmlmod.escape(s, quote=True)
slug = lambda a, b: f"{a}-vs-{b}".replace(".", "-")


def pairs():
    out = [(a, b) for i, a in enumerate(CURRENT) for b in CURRENT[i + 1:]]
    return out + SUCCESSION


def fmt_cost(c):
    """As the main page prints a multiple of the cheapest couple: 1.8×, 18×."""
    return f"{c:.1f}×" if c < 10 else f"{c:.0f}×"


def fmt_ratio(r):
    return f"{r:.1f}×" if r < 10 else f"{r:.0f}×"


def build(CG, QG, PANEL):
    """Returns (html of the page body, plain summary lines for llms.txt)."""
    x0 = min(v[0] for m, es in CG.items() if m not in LEGACY for v in es.values())   # the cheapest couple shown: 1.0×
    def couple(m, e):
        x, hx = CG[m][e]; t, ht = QG[m][e]
        return dict(m=m, e=e, x=x, hx=hx, t=t, ht=ht, c=math.exp(x - x0), s=100 * panel_score(PANEL, t))
    def rungs(m):
        return [e for e in EFFORT_ORDER if e in CG.get(m, {}) and e in QG.get(m, {})]
    def ahead(p, q):                                                     # P(p scores higher than q)
        return Phi((p["t"] - q["t"]) / math.hypot(p["ht"], q["ht"]))
    def cheaper(p, q):                                                   # P(p costs less than q)
        return Phi((q["x"] - p["x"]) / math.hypot(p["hx"], q["hx"]))
    L = lambda m: MODELS[m]["label"]
    name = lambda p: f"{L(p['m'])} at {EFF[p['e']]}" if p["e"] != "solo" else L(p["m"])

    def match(p, other):
        """The cheapest couple of model `other` that p does not out-score at REACH: it matches p's quality within the
        uncertainty or beats it."""
        cand = [couple(other, e) for e in rungs(other)]
        ok = [q for q in cand if ahead(p, q) < REACH]
        return min(ok, key=lambda q: q["x"]) if ok else None

    duels_data, summary = [], []
    for a, b in pairs():
        if not rungs(a) or not rungs(b):
            continue
        A, B = L(a), L(b)
        common = [e for e in rungs(a) if e in rungs(b)]
        rows, lines = [], []
        for e in common:
            p, q = couple(a, e), couple(b, e)
            pa, pc = ahead(p, q), cheaper(p, q)
            rows.append(dict(e=e, p=p, q=q,
                             qual=(A if pa >= REACH else B if pa <= 1 - REACH else None),
                             cost=(A if pc >= REACH else B if pc <= 1 - REACH else None)))
        if common:
            ratios = [couple(a, e)["c"] / couple(b, e)["c"] for e in common]
            gaps = [couple(a, e)["s"] - couple(b, e)["s"] for e in common]
            lo, hi = min(ratios), max(ratios)
            span = fmt_ratio(lo) if abs(hi / lo - 1) < 0.05 else f"{fmt_ratio(lo)} to {fmt_ratio(hi)}"
            pts = lambda g: f"{abs(g):.1f} point{'' if f'{abs(g):.1f}' == '1.0' else 's'} {'higher' if g >= 0 else 'lower'}"
            glo, ghi = min(gaps), max(gaps)
            if abs(ghi - glo) < 0.05:
                gspan = pts(glo)
            elif (glo >= 0) == (ghi >= 0):                               # same sign: "0.7 to 12.3 points higher"
                g1, g2 = sorted((abs(glo), abs(ghi)))
                gspan = f"{g1:.1f} to {g2:.1f} points {'higher' if glo >= 0 else 'lower'}"
            else:
                gspan = f"between {pts(glo)} and {pts(ghi)}"
            lines.append(f"At the same effort ({', '.join(EFF[e] for e in common)}), {A} costs {span} what {B} costs "
                         f"and scores {gspan} on the benchmark panel.")
        elif "solo" in (rungs(a) + rungs(b)):
            single = b if rungs(b) == ["solo"] else a
            lines.append(f"{L(single)} is measured at a single setting, with no effort levels, so the two are "
                         f"compared through their cheapest matches.")
        else:
            lines.append(f"{A} and {B} share no measured effort level, so they are compared through their cheapest matches.")
        heads = []                                                       # candidates for the pair's headline
        for x, y in ((a, b), (b, a)):                                    # the cheapest match, both ways
            best = max((couple(x, e) for e in rungs(x)), key=lambda p: p["t"])
            m = match(best, y)
            if m:
                ratio = m["c"] / best["c"]
                rel = (f"{fmt_ratio(1 / ratio)} cheaper" if ratio < 1 else f"{fmt_ratio(ratio)} dearer")
                lines.append(f"To match {name(best)} ({best['s']:.1f} %, cost {fmt_cost(best['c'])}), the cheapest "
                             f"{L(y)} setting is {EFF[m['e']] if m['e'] != 'solo' else 'its only setting'} "
                             f"({m['s']:.1f} %, cost {fmt_cost(m['c'])}): {rel} per task.")
                heads.append(dict(ratio=ratio, best=best, m=m))
            else:
                strongest = max((couple(y, e) for e in rungs(y)), key=lambda q: q["t"])
                lines.append(f"No {L(y)} setting reaches {name(best)} ({best['s']:.1f} %): {L(y)}'s best is "
                             f"{EFF[strongest['e']]} at {strongest['s']:.1f} %.")
        note = [f"{L(m)}'s cost is size-sensitive: a verbose model, its cost swings widely between short and long "
                f"agentic tasks, hence its wide interval." for m in (a, b) if MODELS[m].get("flag_task_size")]
        summary.append(f"{A} vs {B}: " + " ".join(lines + note))
        head = min(heads, key=lambda h: h["ratio"]) if heads else None
        duels_data.append(dict(a=a, b=b, A=A, B=B, sid=slug(a, b), rows=rows, lines=lines, note=note, head=head,
                               ca=[couple(a, e) for e in rungs(a)], cb=[couple(b, e) for e in rungs(b)]))

    dot = lambda m: f'<span class="dot" style="background:var({MODELS[m]["colour"]})"></span>'
    effname = lambda p: "" if p["e"] == "solo" else f" · {EFF[p['e']].capitalize()}"

    def card(d):
        h = d["head"]
        if h:
            big, word = (fmt_ratio(1 / h["ratio"]), "cheaper") if h["ratio"] < 1 else (fmt_ratio(h["ratio"]), "dearer")
            verb = "matches" if abs(h["m"]["s"] - h["best"]["s"]) < 3 or h["m"]["s"] < h["best"]["s"] else "outscores"
            pick = (f'{dot(h["m"]["m"])}{esc(L(h["m"]["m"]))}{esc(effname(h["m"]))}',
                    f'{verb} {esc(L(h["best"]["m"]))}{esc(effname(h["best"]))}',
                    f'<b>{h["m"]["s"]:.1f}&nbsp;%</b> vs {h["best"]["s"]:.1f}&nbsp;% · cost <b>{fmt_cost(h["m"]["c"])}</b> vs {fmt_cost(h["best"]["c"])}')
            yld = f'<div class="tier-yield{" dearer" if word == "dearer" else ""}">{big}<small>{word}</small></div>'
        else:
            pick = ("", "", "")
            yld = ""
        return (f'<a class="card pad tier duelcard" href="#{d["sid"]}"><div class="tier-head"><span class="tier-q">Head-to-head</span>'
                f'<span class="tier-name">{dot(d["a"])}{esc(d["A"])} <span class="vs">vs</span> {dot(d["b"])}{esc(d["B"])}</span></div>'
                f'<div class="tier-top"><div class="tier-left"><span class="tier-pick">{pick[0]}</span>'
                f'<span class="tier-nums">{pick[1]}</span><span class="tier-nums">{pick[2]}</span></div>{yld}</div></a>')

    def chart(d):
        W, H, mL, mR, mT, mB = 1100, 400, 66, 150, 22, 64
        iw, ih = W - mL - mR, H - mT - mB
        allp = d["ca"] + d["cb"]
        xl, xh = math.log(min(p["c"] for p in allp) / 1.25), math.log(max(p["c"] for p in allp) * 1.25)
        sl, sh = min(p["s"] for p in allp), max(p["s"] for p in allp)
        pad = max(2.0, (sh - sl) * 0.12); sl, sh = sl - pad, sh + pad
        X = lambda c: mL + (math.log(c) - xl) / (xh - xl) * iw
        Y = lambda v: mT + (sh - v) / (sh - sl) * ih
        o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Quality vs cost of {esc(d["A"])} and {esc(d["B"])}, one point per effort">']
        for t in [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200]:                          # cost ticks, log scale
            if xl <= math.log(t) <= xh:
                x = X(t)
                o.append(f'<line x1="{x:.1f}" y1="{mT}" x2="{x:.1f}" y2="{mT+ih}" style="stroke:var(--line)" stroke-width="1"/>'
                         f'<text x="{x:.1f}" y="{mT+ih+20}" text-anchor="middle" font-size="12" style="fill:var(--muted)">{t:g}×</text>')
        step = 2 if sh - sl <= 14 else 5 if sh - sl <= 40 else 10
        v = math.ceil(sl / step) * step
        while v <= sh:
            y = Y(v)
            o.append(f'<line x1="{mL}" y1="{y:.1f}" x2="{mL+iw}" y2="{y:.1f}" style="stroke:var(--line)" stroke-width="1"/>'
                     f'<text x="{mL-10}" y="{y+4:.1f}" text-anchor="end" font-size="12" style="fill:var(--muted)">{v:g}&#8202;%</text>')
            v += step
        o.append(f'<text x="{mL+iw/2}" y="{H-14}" text-anchor="middle" font-size="12.5" style="fill:var(--muted)">cost per task, × the cheapest couple (log scale)</text>'
                 f'<text x="16" y="{mT+ih/2}" text-anchor="middle" font-size="12.5" transform="rotate(-90 16 {mT+ih/2})" style="fill:var(--muted)">expected score on the panel</text>')
        for pts_, m, up in ((d["ca"], d["a"], True), (d["cb"], d["b"], False)):
            col = f'var({MODELS[m]["colour"]})'
            if len(pts_) > 1:
                o.append('<path d="' + " ".join(("M" if i == 0 else "L") + f"{X(p['c']):.1f} {Y(p['s']):.1f}" for i, p in enumerate(pts_))
                         + f'" fill="none" style="stroke:{col}" stroke-width="2.4" stroke-linejoin="round"/>')
            for p in pts_:
                x, y = X(p["c"]), Y(p["s"])
                o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.4" style="fill:{col};stroke:var(--panel)" stroke-width="1.6"/>')
                if p["e"] != "solo":
                    o.append(f'<text x="{x:.1f}" y="{y-10 if up else y+19:.1f}" text-anchor="middle" font-size="10.5" style="fill:{col}">{EFF[p["e"]]}</text>')
            last = pts_[-1]
            o.append(f'<text x="{X(last["c"])+12:.1f}" y="{Y(last["s"])+(-6 if up else 14):.1f}" font-size="13.5" font-weight="600" style="fill:{col}">{esc(L(m))}</text>')
        o.append("</svg>")
        return "".join(o)

    def table(d):
        if not d["rows"]:
            return ""
        th = "".join(f"<th>{esc(EFF[r['e']])}</th>" for r in d["rows"])
        def row(m, key):
            col = MODELS[m]["colour"]
            cells = "".join(f'<td><div class="cell" style="background:color-mix(in srgb,var({col}) 13%,transparent)">'
                            f'{fmt_cost(r[key]["c"])}<small>{r[key]["s"]:.1f}&nbsp;%</small></div></td>' for r in d["rows"])
            return f'<tr><td class="mdl">{dot(m)}{esc(L(m))}</td>{cells}</tr>'
        pill = lambda who, what: (f'<span class="conf c-high">{esc(who)} {what}</span>' if who else '<span class="conf c-med">level</span>')
        verdict = lambda key, what: "".join(f"<td>{pill(r[key], what)}</td>" for r in d["rows"])
        return (f'<details class="fold"><summary>Effort by effort — {esc(d["A"])} vs {esc(d["B"])}</summary><div class="fold-body pad">'
                f'<div class="chartbox"><table class="duel-tbl"><thead><tr><th style="text-align:left">Model</th>{th}</tr></thead><tbody>'
                f'{row(d["a"], "p")}{row(d["b"], "q")}'
                f'<tr><td class="mdl muted">Cost</td>{verdict("cost", "cheaper")}</tr>'
                f'<tr><td class="mdl muted">Quality</td>{verdict("qual", "higher")}</tr></tbody></table></div>'
                f'<p class="cap">Each cell: cost as a multiple of the cheapest couple, and the expected score on the benchmark panel. '
                f'<b>Cheaper</b> or <b>higher</b> when the fitted difference puts it ahead with at least 84&nbsp;% probability; <b>level</b> otherwise.</p>'
                f'</div></details>')

    cards = "".join(card(d) for d in duels_data)
    blocks = "".join(
        f'<section id="{d["sid"]}" class="block"><div class="card pad"><h2 class="blocktitle">{esc(d["A"])} vs {esc(d["B"])}</h2>'
        f'<div class="legend"><span class="lg"><span class="sw" style="background:var({MODELS[d["a"]]["colour"]})"></span>{esc(d["A"])}</span>'
        f'<span class="lg"><span class="sw" style="background:var({MODELS[d["b"]]["colour"]})"></span>{esc(d["B"])}</span></div>'
        f'<div class="chartbox">{chart(d)}</div>'
        f'<ul class="tight duel-lines">' + "".join(f"<li>{esc(t)}</li>" for t in d["lines"]) + "</ul>"
        + "".join(f'<p class="cap">{esc(t)}</p>' for t in d["note"]) +
        f'</div>{table(d)}</section>' for d in duels_data)

    home = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "body.html"), encoding="utf-8").read()
    corner = re.search(r'<div class="hero-corner">.*?<div class="gh-name">.*?</div>\s*</div>', home, re.S).group(0)
    body = f"""<div class="wrap">
  <header class="hero">
    {corner}
    <div class="eyebrow">Data analysis · <a href="{SITE_URL}">{esc(SITE_NAME)}</a></div>
    <h1>Claude models head-to-head <span class="h1-line">Fable vs Opus vs Sonnet vs Haiku</span></h1>
    <div class="hero-row">
      <div class="lede-col">
        <p class="lede">Each pair of Claude models compared effort by effort, on the same scales as the <a href="{SITE_URL}">main comparison</a>: how much more one costs than the other, how much quality it buys, and the cheapest setting of each that matches the other's best.</p>
      </div>
      <div class="meta meta-side">
        <div><span class="k">Scales</span><br><b>cost × the cheapest couple · expected score on the panel</b></div>
        <div><span class="k">Pairs</span><br><b>{len(duels_data)}</b></div>
        <div><span class="k">Updated</span><br><b>__GENDATE__</b></div>
      </div>
    </div>
  </header>
  <main>
  <section id="atglance" class="major"><div class="grid duelgrid">{cards}</div></section>
  {blocks}
  <section id="how" class="block"><details class="fold"><summary>How to read these comparisons</summary><div class="fold-body pad">
    <p class="sub">The values are the ones the <a href="{SITE_URL}">main page</a> shows, fitted from public measurements taken on the same tasks. One model is <b>cheaper</b> or <b>higher</b> than the other at an effort level when the fitted difference puts it ahead with at least 84&nbsp;% probability, the level of the intervals shown everywhere on the site; otherwise the two are <b>level within the uncertainty</b>. A <b>match</b> is the cheapest setting of the other model that the first does not out-score at that level. Costs are what a whole task cost, as each source measured it (the run's actual spend, cache included), not the price per token.</p>
  </div></details></section>
  </main>
  <div class="foot">
    <p><b>Alexandre Gensse</b> · <a href="https://github.com/alexandregensse-blip/claude-models-value-analysis" target="_blank" rel="noopener">github.com/alexandregensse-blip</a> · <a href="{SITE_URL}">{esc(HOME_TITLE)}</a></p>
    <p class="faint" style="margin-top:8px">All figures are <b>indicative and for informational purposes only</b> — derived from public third-party measurements, not an official benchmark, and not affiliated with or endorsed by Anthropic. Verify before relying on any value.</p>
    <p class="faint" style="margin-top:8px">Data and text under <a href="https://creativecommons.org/licenses/by/4.0/" rel="license">CC BY 4.0</a> · code under <a href="https://github.com/alexandregensse-blip/claude-models-value-analysis/blob/main/LICENSE">MIT</a> · <a href="raw-data.csv">download the data (CSV)</a></p>
  </div>
</div>"""
    return body, summary


def head(date):
    a = lambda v: htmlmod.escape(v, quote=True)
    ld = [{"@context": "https://schema.org", "@type": "WebPage", "name": TITLE, "description": DESCRIPTION, "url": URL,
           "isPartOf": {"@type": "WebSite", "name": SITE_NAME, "url": SITE_URL},
           "author": {"@type": "Person", "name": "Alexandre Gensse", "url": "https://github.com/alexandregensse-blip"},
           "dateModified": date.isoformat(), "license": "https://creativecommons.org/licenses/by/4.0/"},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": SITE_NAME, "item": SITE_URL},
              {"@type": "ListItem", "position": 2, "name": "Head-to-head", "item": URL}]}]
    return (f"<title>{a(TITLE)}</title>\n"
            f'<meta name="description" content="{a(DESCRIPTION)}">\n'
            f'<link rel="canonical" href="{URL}">\n'
            '<link rel="icon" href="favicon.svg" type="image/svg+xml">\n'
            '<link rel="icon" href="favicon.png" type="image/png" sizes="96x96">\n'
            '<meta property="og:type" content="website">\n'
            f'<meta property="og:url" content="{URL}">\n'
            f'<meta property="og:title" content="{a(TITLE)}">\n'
            f'<meta property="og:description" content="{a(DESCRIPTION)}">\n'
            f'<meta property="og:image" content="{SITE_URL}og-image.png">\n'
            '<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n'
            f'<meta property="og:image:alt" content="{a(HOME_TITLE)}">\n'
            '<meta name="twitter:card" content="summary_large_image">\n'
            f'<script type="application/ld+json">\n{json.dumps(ld, ensure_ascii=False, indent=1).replace("</", "<" + chr(92) + "/")}\n</script>\n')


EXTRA_CSS = """/* head-to-head page: the main page's tier cards, one per pair */
.duelgrid{grid-template-columns:repeat(3,minmax(0,1fr))}
@media (max-width:1080px){.duelgrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:520px){.duelgrid{grid-template-columns:1fr}}
a.duelcard{color:inherit;text-decoration:none;transition:border-color .15s}
a.duelcard:hover{border-color:var(--line2)}
a.duelcard:focus-visible{outline:2px solid var(--opus5);outline-offset:2px}
.duelcard .tier-name .dot{width:10px;height:10px}
.duelcard .vs{font-size:13px;color:var(--faint);margin:0 4px}
.duelcard .tier-top{border-bottom:none;padding-bottom:0;margin-bottom:0}
.duelcard .tier-left{flex:1 1 auto}
.duelcard .tier-yield{flex:0 0 auto}
.tier-yield.dearer{color:var(--muted)}
.duel-lines{margin-top:18px}
.duel-tbl td.mdl{min-width:120px}"""


def write(body, css, date):
    html = ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            + head(date) + f"<style>\n{css}\n{EXTRA_CSS}\n</style>\n</head>\n<body>\n{body.replace('__GENDATE__', date.strftime('%d %b %Y'))}\n</body>\n</html>\n")
    with open(os.path.join(ROOT, FILE), "w", encoding="utf-8") as f:
        f.write(html)
    return len(html)
