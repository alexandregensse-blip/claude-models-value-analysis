"""The head-to-head page: every pair of current Claude models (plus each model against its predecessor), effort by
effort, from the same fitted values as the main page. Static HTML: no script is needed to read it. Every sentence is
computed from the grids, with the main page's rule for uncertainty: one couple is ahead of another on an axis when
the normal law on the difference of the two centres, with the two quasi-standard errors, puts it ahead with
probability REACH (0.84, the level of the intervals shown everywhere); otherwise the two are level within the
uncertainty (docs/DISPLAY-METHODOLOGY.md § 7)."""
import html as htmlmod, json, math, os, sys

from config import ROOT, SITE_URL, SITE_NAME, TITLE as HOME_TITLE, EFFORT_ORDER
from grids import panel_score
sys.path.insert(0, os.path.join(ROOT, "data"))
from catalog import MODELS

FILE  = "claude-models-head-to-head.html"
URL   = SITE_URL + FILE
TITLE = "Fable vs Opus vs Sonnet vs Haiku: Claude models head-to-head"
DESCRIPTION = ("Every pair of Claude models compared effort by effort: how much more one costs than the other, how much "
               "quality it buys, and the cheapest effort of each that matches the other. Open data, CC BY 4.0.")
CURRENT = ["fable-5.1", "opus-5.5", "sonnet-5.5", "haiku-4.5"]           # the latest model of each family
SUCCESSION = [("fable-5.1", "fable-5"), ("opus-5.5", "opus-5"), ("sonnet-5.5", "sonnet-5")]
REACH = 0.84
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
    x0 = min(v[0] for es in CG.values() for v in es.values())            # the cheapest couple: cost 1.0×
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

    sections, toc, summary = [], [], []
    for a, b in pairs():
        if not rungs(a) or not rungs(b):
            continue
        A, B = L(a), L(b)
        sid = slug(a, b)
        toc.append(f'<li><a href="#{sid}">{esc(A)} vs {esc(B)}</a></li>')
        common = [e for e in rungs(a) if e in rungs(b)]
        rows, lines = [], []
        for e in common:
            p, q = couple(a, e), couple(b, e)
            pa, pc = ahead(p, q), cheaper(p, q)
            qual = (f"{esc(A)} higher" if pa >= REACH else f"{esc(B)} higher" if pa <= 1 - REACH else "level within the uncertainty")
            cost = (f"{esc(A)} cheaper" if pc >= REACH else f"{esc(B)} cheaper" if pc <= 1 - REACH else "level within the uncertainty")
            rows.append(f"<tr><td>{esc(EFF[e])}</td><td class=\"num\">{fmt_cost(p['c'])}</td><td class=\"num\">{fmt_cost(q['c'])}</td>"
                        f"<td class=\"num\">{p['s']:.1f}&nbsp;%</td><td class=\"num\">{q['s']:.1f}&nbsp;%</td>"
                        f"<td>{cost}</td><td>{qual}</td></tr>")
        if common:
            ratios = [couple(a, e)["c"] / couple(b, e)["c"] for e in common]
            gaps = [couple(a, e)["s"] - couple(b, e)["s"] for e in common]
            lo, hi = min(ratios), max(ratios)
            span = fmt_ratio(lo) if abs(hi / lo - 1) < 0.05 else f"{fmt_ratio(lo)} to {fmt_ratio(hi)}"
            pts = lambda g: f"{abs(g):.1f} point{'' if f'{abs(g):.1f}' == '1.0' else 's'} {'higher' if g >= 0 else 'lower'}"
            glo, ghi = min(gaps), max(gaps)
            gspan = pts(glo) if abs(ghi - glo) < 0.05 else f"between {pts(glo)} and {pts(ghi)}"
            lines.append(f"At the same effort ({', '.join(EFF[e] for e in common)}), {A} costs {span} what {B} costs "
                         f"and scores {gspan} on the benchmark panel.")
        else:
            single = b if rungs(b) == ["solo"] else a
            lines.append(f"{L(single)} is measured at a single setting, with no effort levels, so the two are "
                         f"compared through their cheapest matches.")
        for x, y in ((a, b), (b, a)):                                    # the cheapest match, both ways
            best = max((couple(x, e) for e in rungs(x)), key=lambda p: p["t"])
            m = match(best, y)
            if m:
                ratio = m["c"] / best["c"]
                rel = (f"{fmt_ratio(1 / ratio)} less" if ratio < 1 else f"{fmt_ratio(ratio)} more")
                lines.append(f"To match {name(best)} ({best['s']:.1f} %, cost {fmt_cost(best['c'])}), the cheapest "
                             f"{L(y)} setting is {EFF[m['e']] if m['e'] != 'solo' else 'its only setting'} "
                             f"({m['s']:.1f} %, cost {fmt_cost(m['c'])}): {rel} per task.")
            else:
                strongest = max((couple(y, e) for e in rungs(y)), key=lambda q: q["t"])
                lines.append(f"No {L(y)} setting reaches {name(best)} ({best['s']:.1f} %): {L(y)}'s best is "
                             f"{EFF[strongest['e']]} at {strongest['s']:.1f} %.")
        summary.append(f"{A} vs {B}: " + " ".join(lines))
        table = ("" if not common else
                 f'<div class="chartbox"><table><thead><tr><th>Effort</th><th>{esc(A)} cost</th><th>{esc(B)} cost</th>'
                 f'<th>{esc(A)} score</th><th>{esc(B)} score</th><th>Cost</th><th>Quality</th></tr></thead><tbody>'
                 + "".join(rows) + "</tbody></table></div>")
        sections.append(
            f'<section id="{sid}"><div class="card pad"><h2>{esc(A)} vs {esc(B)}</h2>'
            + "".join(f"<p>{esc(t)}</p>" for t in lines) + table + "</div></section>")

    body = f"""<div class="wrap">
  <header class="hero">
    <div class="eyebrow">Data analysis · <a href="{SITE_URL}">{esc(SITE_NAME)}</a></div>
    <h1>Claude models head-to-head <span class="h1-line">Fable vs Opus vs Sonnet vs Haiku, effort by effort</span></h1>
    <p class="lede">Each pair of Claude models compared on the same scales as the <a href="{SITE_URL}">main comparison</a>: cost as a multiple of the cheapest (model, effort) couple, quality as the expected score on the benchmark panel. For every pair: the gap at each shared effort level, and the cheapest effort of each model that matches the other's best.</p>
  </header>
  <main>
  <nav class="card pad" aria-label="Pairs"><ul class="tight">{''.join(toc)}</ul></nav>
  {''.join(sections)}
  <section id="how"><div class="card pad"><h2>How to read these comparisons</h2>
    <p>The values are the ones the <a href="{SITE_URL}">main page</a> shows, fitted from public measurements taken on the same tasks. One model is <b>cheaper</b> or <b>higher</b> than the other at an effort level when the fitted difference puts it ahead with 84&nbsp;% probability, the level of the intervals shown everywhere on the site; otherwise the two are <b>level within the uncertainty</b>. A <b>match</b> is the cheapest setting of the other model that the first does not out-score at that level. Costs count the whole task (tokens at list price, as each source measured them), not the price per token.</p>
  </div></section>
  </main>
  <div class="foot">
    <p><b>Alexandre Gensse</b> · <a href="https://github.com/alexandregensse-blip/claude-models-value-analysis" target="_blank" rel="noopener">github.com/alexandregensse-blip</a> · <a href="{SITE_URL}">{esc(HOME_TITLE)}</a></p>
    <p class="faint" style="margin-top:8px">All figures are <b>indicative and for informational purposes only</b> — derived from public third-party measurements, not an official benchmark, and not affiliated with or endorsed by Anthropic. Verify before relying on any value.</p>
    <p class="faint" style="margin-top:8px">Data and text under <a href="https://creativecommons.org/licenses/by/4.0/" rel="license">CC BY 4.0</a> · <a href="raw-data.csv">download the data (CSV)</a></p>
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


def write(body, css, date):
    html = ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            + head(date) + f"<style>\n{css}\n</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n")
    with open(os.path.join(ROOT, FILE), "w", encoding="utf-8") as f:
        f.write(html)
    return len(html)
