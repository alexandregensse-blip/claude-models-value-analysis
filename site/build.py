#!/usr/bin/env python3
"""Site generator. Reads the model's results (model/fit-cache.json), the data file and the catalogue, bundles the
CSS, HTML body and client script, and writes index.html and the root files at the repository root.
Run: python3 site/build.py (Python standard library and Node.js only; the fit itself is model/fit.py)."""
import json, math, os, re, sys

from config import HERE, OUT, REPO_URL, ROOT
from grids import fused_grids, monotonicity_report
from render import inject, prerender
from seo import content_date, content_fingerprint, head_tags, write_root_files
from sources import groups_data
import duels
sys.path.insert(0, os.path.join(ROOT, "data"))
from catalog import DISPLAY_ORDER, MODELS

def main():
    CG, QG, PANEL, DIAG, MCSE = fused_grids()
    GD = groups_data()

    css  = open(os.path.join(HERE,"style.css")).read()
    body = open(os.path.join(HERE,"body.html")).read()
    app  = open(os.path.join(HERE,"app.js")).read()
    app  = app.replace("__MODELS__", json.dumps({m: dict(label=MODELS[m]["label"], c=MODELS[m]["colour"],
                       **({"tag": True} if MODELS[m].get("flag_task_size") else {})) for m in DISPLAY_ORDER},
                       separators=(",",":"), ensure_ascii=False))
    app  = app.replace("__COSTGRID__", json.dumps(CG, separators=(",",":")))
    app  = app.replace("__QUALGRID__", json.dumps(QG, separators=(",",":")))
    app  = app.replace("__PANEL__", json.dumps(PANEL, separators=(",",":")))
    app  = app.replace("__GROUPS_DATA__", json.dumps(GD, separators=(",",":")))
    body = body.replace("__REPO__", REPO_URL)
    body = body.replace("__NCOSTROWS__", str(DIAG["cost"]["rows"])).replace("__NSCOREROWS__", str(DIAG["quality"]["rows"]))
    span = math.exp(max(c[0] for v in CG.values() for c in v.values()) - min(c[0] for v in CG.values() for c in v.values()))
    ntrend = sum(len(CG[m]) for m in duels.CURRENT if m in CG)   # couples of the latest model of each family: the price trend
    body = body.replace("__NTREND__", str(ntrend))
    body = body.replace("__COSTSPAN__", str(round(span)))
    pre  = prerender(app, css)
    body = inject(body, pre)
    duel_body, duel_summary = duels.build(CG, QG, PANEL)
    date = content_date(content_fingerprint(body, pre, [CG, QG, PANEL, GD, duel_body, duels.TITLE, duels.DESCRIPTION]))
    body = body.replace("__GENDATE__", date.strftime("%d %b %Y"))   # last change to the content (text, figures, data)
    html = (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        + head_tags(date, pre.get(".nsrc", "")) +
        f"<style>\n{css}\n</style>\n"
        f"</head>\n<body>\n{body}\n<script>\n{app}\n</script>\n</body>\n</html>\n"
    )
    open(OUT,"w",encoding="utf-8").write(html)
    write_root_files(date, pre, duel_summary)
    print(f"built {duels.FILE}  ({duels.write(duel_body, css, date)} bytes)")
    print(f"built {OUT}  ({len(html)} bytes)")
    for axis in ("cost", "quality"):
        d = DIAG[axis]
        print(f"  {axis}: {d['rows']} rows in {d['groups']} groups · set aside {d['set_aside']} · R-hat max {d['rhat_max']}"
              f" · unpublished {d['unpublished']}")
        value = {f"{m}@{e}": math.exp(v[0] - min(x[0] for es in CG.values() for x in es.values()))
                 for m, es in CG.items() for e, v in es.items()} if axis == "cost" else {}
        half = (lambda c: 0.05 if axis == "quality" else 0.005 if value[c] < 1 else 0.05 if value[c] < 10 else 0.5)
        loose = sorted(c for c, e in MCSE[axis].items() if e > half(c))   # half of the last displayed digit: 4.1×, 18×, 65.8 %
        print(f"  {axis}: Monte Carlo error above half the last displayed digit: {loose or 'none'}")
    viol = monotonicity_report(CG, QG)
    known = {("quality", "sonnet-4.6", "high", "max")}         # printed by the Sonnet 5 card itself — keyed on the rungs, not
                                                                # the values, which move with the data
    def key(v):
        m = re.match(r"(\w+): (\S+) (\w+)\([-\d.]+\) > (\w+)\(", v); return m.groups() if m else None
    for v in viol:
        print(("  effort-ladder OK (documented): " if key(v) in known else "  !! EFFORT LADDER INVERTED: ") + v)

if __name__ == "__main__":
    main()

