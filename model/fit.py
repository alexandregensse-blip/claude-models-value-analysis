#!/usr/bin/env python3
"""Fits the latent-quality model (lqm.py, lqm.stan) on both axes and writes model/fit-cache.json, the model's only
product, which the site reads. Run in the Stan environment:  .stan/venv/bin/python model/fit.py

The cache holds, per couple and axis, reference-free values on the log scale — [centre, quasi-standard error,
publishers, new-source 16–84 % interval, Monte Carlo error of the centre, and on the quality axis the latent quality
θ as [median, quasi-standard error, Monte Carlo error]] — with the fit's diagnostics, the list of
its input files and their fingerprint. A fit that misses the convergence criteria (lqm.CONVERGED) is written with
converged = false, and the site refuses it; so does it a fit whose inputs have changed since.

An axis whose model data (the rows it sees, after preparation) and model code are unchanged since the cached fit, and
whose cached fit converged, is not refitted: adding a quality-only source does not redo the cost axis. `--all` refits
both axes regardless. The checks of model/precheck.py run first (a score beyond its label's bound stops the run; the
same runs under two metrics are reported; a 3-minute smoke fit of the quality axis must reach R̂ ≤ 1.5); `--no-smoke`
skips the smoke fit."""
import hashlib, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import lqm
from catalog import FILES as CATALOG_FILES, MODEL_ORDER

FIT_CACHE = os.path.join(HERE, "fit-cache.json")
SEED = 11
INPUTS = ["raw-data.csv", *CATALOG_FILES, "model/lqm.py", "model/lqm.stan", "model/fit.py"]


def fingerprint(inputs=INPUTS, root=ROOT):
    """SHA-256 of the input files, in order: any change to the data, the catalogue, the model or its settings (all
    in these files) makes the cache stale."""
    h = hashlib.sha256()
    for path in inputs:
        h.update(path.encode())
        with open(os.path.join(root, path), "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def axis_fingerprint(data):
    """SHA-256 of what one axis' fit depends on: the model code and settings, and the axis' prepared data."""
    h = hashlib.sha256()
    for path in ("model/lqm.py", "model/lqm.stan"):
        with open(os.path.join(ROOT, path), "rb") as f:
            h.update(f.read())
    h.update(json.dumps(dict(data=data, seed=SEED), sort_keys=True, default=lambda a: a.tolist()).encode())
    return h.hexdigest()


def main(refit_all=False, smoke=True):
    import precheck
    if precheck.main(run_smoke=smoke):                               # data errors, then a 3-minute smoke fit
        sys.exit("!! pre-fit checks failed (model/precheck.py): the fit is not started")
    out = dict(inputs=INPUTS, fingerprint=fingerprint(), seed=SEED, sampler=lqm.SAMPLER, diagnostics={})
    try:
        old = json.load(open(FIT_CACHE))
    except (OSError, ValueError):
        old = {}
    for axis, field in (("cost", "cost_usd"), ("quality", "score")):
        t = time.time()
        groups, report, republished = lqm.load(os.path.join(ROOT, "raw-data.csv"), MODEL_ORDER, field=field)
        afp = axis_fingerprint(lqm.stan_data(groups, axis)[0])
        od = old.get("diagnostics", {}).get(axis, {})
        if not refit_all and od.get("data_fingerprint") == afp and od.get("converged") and axis in old:
            out[axis], out["diagnostics"][axis] = old[axis], od
            print(f"{axis}: unchanged since the cached fit, kept", flush=True)
            continue
        post, maps = lqm.fit(groups, axis, seed=SEED, log=lambda m: print(m, flush=True))
        S, diag = lqm.summarise(post, maps, groups, lqm.stan_data(groups, axis)[0], seed=SEED)
        out[axis] = {c: [round(v["centre"], 5), round(v["half"], 5), v["publishers"], [round(x, 5) for x in v["new_source"]],
                         round(v["mcse"], 6)] + ([[round(x, 5) for x in v["theta"]]] if "theta" in v else [])
                     for c, v in sorted(S.items())}
        diag.update(groups=len(groups), rows=sum(len(g["rows"]) for g in groups.values()), set_aside=dict(report),
                    republished=[list(p) for p in republished],
                    unpublished=sorted(c for c, v in S.items() if not v["published"]),
                    converged=lqm.converged(diag), seconds=round(time.time() - t), data_fingerprint=afp)
        out["diagnostics"][axis] = diag
        print(f"{axis}: {json.dumps(diag)}", flush=True)
        json.dump(dict(old, **{k: v for k, v in out.items() if k != "diagnostics"},  # each axis kept as soon as it is
                       diagnostics=dict(old.get("diagnostics", {}), **out["diagnostics"]),    # done: a run stopped
                       fingerprint="partial"),                    # later resumes from it; the site refuses it meanwhile
                  open(FIT_CACHE, "w"), indent=1, sort_keys=True)
    json.dump(out, open(FIT_CACHE, "w"), indent=1, sort_keys=True)
    print(f"wrote {FIT_CACHE}")


if __name__ == "__main__":
    main(refit_all="--all" in sys.argv[1:], smoke="--no-smoke" not in sys.argv[1:])
