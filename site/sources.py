"""The sources table: every group of the data file with the couples it measured, its display label and its verified
configuration (data/catalog/groups.json)."""
import csv, os, sys

from config import ROOT
sys.path.insert(0, os.path.join(ROOT, "data"))
from catalog import DISPLAY_ORDER, GROUP_DISPLAY, GROUP_MERGE
import build_lqm

DATA = os.path.join(build_lqm.BUILD, "data.csv")      # the build's public data file (data/build.py)


def model_label(m):
    """'opus-5.5' → 'Opus 5.5'."""
    name, _, version = m.partition("-")
    return f"{name.capitalize()} {version}".strip()

SHOWN = set(DISPLAY_ORDER)            # the site's models: the data file may hold other makers' rows (the global fit)


def groups_data():
    """§3 linking graph, DATA-DRIVEN. Nodes = the (model, effort) couples each source group actually measured,
    derived from the build's data.csv: the rows the fit reads (in on either axis).
    Only the editorial metadata per group — display label, edge type (sweep/xmodel/xgen), verified config note —
    lives in the catalogue (data/catalog/groups.json), keyed by today's group names: a fit group reaches it through the
    build's group map (fit group → base group, data/build/group-map.json). Some sources publish several sub-benchmarks
    (AIReiter) → MERGE folds them into one node-set so corroboration counts the source once."""
    GMETA, MERGE = GROUP_DISPLAY, GROUP_MERGE          # editorial metadata: data/catalog/groups.json
    base = build_lqm.base_groups(build_lqm.read_maps(build_lqm.BUILD)[0])
    statuses = ("status_quality", "status_cost")
    rows = [r for r in csv.DictReader(open(DATA, encoding="utf-8"))
            if r["group"] and not r["group"].startswith("#")
            and any((r[k] or "").startswith(("in", "legacy:in")) for k in statuses)]
    order, buckets = [], {}
    for r in rows:
        b = base.get(r["group"], r["group"])
        gk = MERGE.get(b, b)
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
            if r["model"] in SHOWN and nid not in seen: seen.add(nid); nodes.append(nid)
        if not nodes:                                                   # a source with no Claude couple: not this site's
            continue
        lbl, t, h = GMETA.get(gk, (gk, "xmodel", "config ✓"))
        out.append({"s": rs[0]["source"], "g": lbl, "t": t, "h": h, "n": nodes, "u": pick_url(rs, rs[0]["source"])})
    return out


