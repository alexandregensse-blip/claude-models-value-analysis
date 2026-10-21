"""The sources table: every group of the data file with the couples it measured, its display label and its verified
configuration (data/catalog/groups.json)."""
import csv, os, sys

from config import ROOT
sys.path.insert(0, os.path.join(ROOT, "data"))
from catalog import DISPLAY_ORDER, GROUP_DISPLAY, GROUP_MERGE, PUBLISHER_OF


def model_label(m):
    """'opus-5.5' → 'Opus 5.5'."""
    name, _, version = m.partition("-")
    return f"{name.capitalize()} {version}".strip()

SHOWN = set(DISPLAY_ORDER)            # the site's models: the data file may hold other makers' rows (the global fit)


def groups_data(couples=None, unverified=None):
    """§3 linking graph, DATA-DRIVEN. Nodes = the (model, effort) couples each source group actually measured,
    derived from raw-data.csv.
    Only the editorial metadata per group — display label, edge type (sweep/xmodel/xgen), verified config note —
    lives in the catalogue (data/catalog/groups.json). Some sources publish several sub-benchmarks (AIReiter) → MERGE folds them into one node-set
    so corroboration counts the source once.
    The Claude page (no argument) lists the Claude couples each group measured. The multi-site pages (site/multisite.py)
    pass `couples`, the couples the page displays: a group is listed with those it measured, each row also carries its
    publisher (data/catalog/publishers.json), and a group without editorial metadata gets `unverified` as its
    configuration note instead of a check mark."""
    GMETA, MERGE = GROUP_DISPLAY, GROUP_MERGE          # editorial metadata: data/catalog/groups.json
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT, "raw-data.csv")))
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
            if (nid in couples if couples is not None else r["model"] in SHOWN) and nid not in seen:
                seen.add(nid); nodes.append(nid)
        if not nodes:                                                   # a source with no Claude couple: not this site's
            continue
        lbl, t, h = GMETA.get(gk, (gk, "xmodel", "config ✓" if unverified is None else unverified))
        out.append({"s": rs[0]["source"], "g": lbl, "t": t, "h": h, "n": nodes, "u": pick_url(rs, rs[0]["source"])})
        if couples is not None:
            out[-1]["p"] = PUBLISHER_OF.get(rs[0]["source"], rs[0]["source"])   # one publisher = one source
    return out


