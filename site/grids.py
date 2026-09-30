"""The model's results as the page uses them: reads model/fit-cache.json (the model's only product), checks that it
matches its inputs and converged, and hands the page its reference-free values (no reference couple: the page counts
cost from the cheapest couple and reads quality as an expected panel score)."""
import hashlib, json, math, os, sys

from config import ROOT, EFFORT_ORDER
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


def panel_score(curve, t):
    """Expected panel score of latent quality θ = t, read on the fit's panel curve [[θ, score], …]: linear in logit
    between its nodes, extended linearly in logit beyond them (as site/app.js reads it)."""
    lg = lambda s: math.log(s / (1 - s))
    i = next((k for k in range(1, len(curve) - 1) if curve[k][0] >= t), len(curve) - 1)
    (t0, s0), (t1, s1) = curve[i - 1], curve[i]
    return 1 / (1 + math.exp(-(lg(s0) + (lg(s1) - lg(s0)) * (t - t0) / (t1 - t0))))


def fused_grids():
    """The fitted values the page decides on, reference-free, published couples only: cost {model: {effort: [ln cost,
    quasi-standard error]}} and quality {model: {effort: [θ, quasi-standard error]}} (θ the latent quality, logit
    scale), with the panel curve θ → expected panel score that labels θ. Refuses to build from a fit that no longer
    matches its inputs, or that did not converge. Also returns the fit's diagnostics and, per axis, the Monte Carlo
    error of each published value as the page prints it: the cost as a multiple of the cheapest couple (two
    decimals), the quality as an expected panel score in % (one decimal)."""
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
    curve = cache["diagnostics"]["quality"]["panel_curve"]
    grids, mcse = {}, {}
    for axis in ("cost", "quality"):
        S = cache[axis]
        grid, err = {}, {}
        for m in MODEL_ORDER:
            row = {}
            for e in EFFORT_ORDER:
                v = S.get(f"{m}@{e}")
                if v and v[2] >= 2:                                 # published: measured by two publishers or more
                    row[e] = [round(v[0], 4), round(v[1], 4)] if axis == "cost" else [round(v[5][0], 4), round(v[5][1], 4)]
            if row: grid[m] = row
        grids[axis] = grid
    cheapest = min((v[0], f"{m}@{e}") for m, es in grids["cost"].items() for e, v in es.items())[1]
    for m, es in grids["cost"].items():                             # Monte Carlo error of the displayed multiple
        for e, v in es.items():
            c = f"{m}@{e}"
            mcse.setdefault("cost", {})[c] = 0.0 if c == cheapest else \
                math.exp(v[0] - cache["cost"][cheapest][0]) * math.hypot(cache["cost"][c][4], cache["cost"][cheapest][4])
    for m, es in grids["quality"].items():                          # … and of the displayed score, in points of %
        for e, v in es.items():
            t, dt = v[0], cache["quality"][f"{m}@{e}"][5][2]
            mcse.setdefault("quality", {})[f"{m}@{e}"] = 100 * abs(panel_score(curve, t + 1e-3) - panel_score(curve, t - 1e-3)) / 2e-3 * dt
    return grids["cost"], grids["quality"], curve, cache["diagnostics"], mcse


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

