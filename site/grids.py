"""The model's results as the page uses them: reads model/fit-cache.json (the model's only product), checks that it
matches its inputs and converged, and hands the page its reference-free values (no reference couple: the page counts
cost from the cheapest couple and reads quality as an expected panel score)."""
import hashlib, json, math, os, sys

from config import ROOT, EFFORT_ORDER, LEVELS
sys.path.insert(0, os.path.join(ROOT, "data"))
from catalog import DISPLAY_ORDER   # the site shows the Claude models; the fit may hold others (the global fit)

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
        for m in DISPLAY_ORDER:
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


def thinking_switch(root=ROOT):
    """The model keys whose thinking is a switch apart from the effort level: their maker has x-terms.thinking
    'switch' in data/schema/vocab.json (Anthropic: thinking: {type: disabled | adaptive} beside output_config.effort),
    the maker read from data/registry/models.json."""
    with open(os.path.join(root, "data", "schema", "vocab.json"), encoding="utf-8") as f:
        makers = json.load(f)["$defs"]["maker"]["x-terms"]
    with open(os.path.join(root, "data", "registry", "models.json"), encoding="utf-8") as f:
        models = json.load(f)["models"]
    return {k for k, m in models.items() if makers.get(m.get("maker"), {}).get("thinking") == "switch"}


def monotonicity_report(cg, qg, switch=None):
    """Effort is a ladder: within a model, a higher rung should neither cost nor score less than the one below.
    The rungs are `minimal`, `low` … `max`, with `nothink` (thinking off) as the rung below them where thinking off is
    the bottom of one ladder (OpenAI's reasoning_effort none); where thinking is a switch apart from the effort
    (`switch`, by default thinking_switch(): the Anthropic models, whose thinking off combines with any effort), `nothink`
    is not a rung and is compared with `think` only, so thinking off above `low` is not an inversion. `think` (the
    one "on" position of an on/off model, which has no level) is compared with `nothink` only on every model. `solo` has no rung. An inversion is reported at build
    time, never corrected: inside the interval it is left as the data give it (a documented exception: Sonnet 4.6 falls
    after `high`, which the Sonnet 5 card itself prints)."""
    switch = thinking_switch() if switch is None else switch
    out = []
    for grid, name in ((cg, "cost"), (qg, "quality")):
        for m, es in grid.items():
            ladder = LEVELS if m in switch else ["nothink"] + LEVELS
            for ORD in (ladder, ["nothink", "think"]):
                seq = [(e, es[e][0]) for e in ORD if e in es]
                for (a, va), (b, vb) in zip(seq, seq[1:]):
                    if vb < va: out.append(f"{name}: {m} {a}({va}) > {b}({vb})")
    return out
