"""The model's results as the page shows them: reads model/fit-cache.json (the model's only product), checks that it
matches its inputs and converged, and turns its reference-free values into grids relative to the display couple."""
import hashlib, json, math, os, sys

from config import ROOT, GRID_ANCHOR, EFFORT_ORDER
sys.path.insert(0, os.path.join(ROOT, "data"))
from catalog import MODEL_ORDER

FIT_CACHE = os.path.join(ROOT, "model", "fit-cache.json")


def inputs_fingerprint(inputs):
    """SHA-256 of the fit's input files, as model/fit.py computes it (the contract between the model and the site)."""
    h = hashlib.sha256()
    for path in inputs:
        h.update(path.encode())
        with open(os.path.join(ROOT, path), "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def fused_grids():
    """Relative cost and quality grids {model: {effort: [value, low, high]}}, published couples only, relative to
    GRID_ANCHOR: value = exp(centre − centre_anchor), low/high = value·exp(∓ quasi-standard error of the couple).
    Refuses to build from a fit that no longer matches its inputs, or that did not converge. Also returns the fit's
    diagnostics and, per axis, the Monte Carlo error of each published value on the displayed scale."""
    try:
        cache = json.load(open(FIT_CACHE))
    except (OSError, ValueError):
        cache = {}
    if not cache.get("inputs") or cache.get("fingerprint") != inputs_fingerprint(cache["inputs"]):
        sys.exit("!! model/fit-cache.json does not match the data, the catalogue or the model: "
                 "run .stan/venv/bin/python model/fit.py")
    for axis in ("cost", "quality"):
        if not cache["diagnostics"][axis]["converged"]:
            sys.exit(f"!! the {axis} fit did not converge: {cache['diagnostics'][axis]}")
    grids, mcse = {}, {}
    for axis in ("cost", "quality"):
        S = cache[axis]
        ref = S[GRID_ANCHOR][0]
        grid, err = {}, {}
        for m in MODEL_ORDER:
            row = {}
            for e in EFFORT_ORDER:
                v = S.get(f"{m}@{e}")
                if v and v[2] >= 2:                                 # published: measured by two publishers or more
                    c, h = v[0] - ref, v[1]
                    row[e] = [round(math.exp(c), 3), round(math.exp(c - h), 3), round(math.exp(c + h), 3)]
                    err[f"{m}@{e}"] = 0.0 if f"{m}@{e}" == GRID_ANCHOR else \
                        math.exp(c) * math.hypot(v[4], S[GRID_ANCHOR][4])   # Monte Carlo error of the displayed ratio
            if row: grid[m] = row
        grids[axis], mcse[axis] = grid, err
    return grids["cost"], grids["quality"], cache["diagnostics"], mcse


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

