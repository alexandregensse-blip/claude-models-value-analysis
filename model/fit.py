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
both axes regardless. Each axis' draws stay on disk (.stan/runs, lqm.RunStore) until its sampling inputs change: a fit
stopped part-way (out of memory, container restarted) resumes from them, and a change to the code that reads the draws
is summarised again without sampling. The checks of model/precheck.py run first (a score beyond its label's bound stops the run; the
same runs under two metrics are reported; a 3-minute smoke fit of the quality axis must reach R̂ ≤ 1.5); `--no-smoke`
skips the smoke fit. The two axes run one after the other (lqm.PARALLEL_AXES)."""
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


AXES = (("cost", "cost_usd"), ("quality", "score"))


def fit_axis(axis, field, old, refit_all=False):
    """One axis: (values, diagnostics), or the cached ones when its model data and code are unchanged."""
    t = time.time()
    groups, report, republished = lqm.load(os.path.join(ROOT, "raw-data.csv"), MODEL_ORDER, field=field)
    afp = axis_fingerprint(lqm.stan_data(groups, axis)[0])
    od = old.get("diagnostics", {}).get(axis, {})
    if not refit_all and od.get("data_fingerprint") == afp and od.get("converged") and axis in old:
        print(f"{axis}: unchanged since the cached fit, kept", flush=True)
        return old[axis], od
    post, maps = lqm.fit(groups, axis, seed=SEED, keep=True, log=lambda m: print(m, flush=True))
    S, diag = lqm.summarise(post, maps, groups, lqm.stan_data(groups, axis)[0], seed=SEED)
    values = {c: [round(v["centre"], 5), round(v["half"], 5), v["publishers"], [round(x, 5) for x in v["new_source"]],
                  round(v["mcse"], 6)] + ([[round(x, 5) for x in v["theta"]]] if "theta" in v else [])
              for c, v in sorted(S.items())}
    diag.update(groups=len(groups), rows=sum(len(g["rows"]) for g in groups.values()), set_aside=dict(report),
                republished=[list(p) for p in republished],
                unpublished=sorted(c for c, v in S.items() if not v["published"]),
                converged=lqm.converged(diag), seconds=round(time.time() - t), data_fingerprint=afp)
    print(f"{axis}: {json.dumps(diag)}", flush=True)
    return values, diag


def main(refit_all=False, smoke=True):
    """Both axes, one after the other — or at the same time, each in a process of its own, when lqm.PARALLEL_AXES and
    the machine has a core for every chain of both. Each axis is written to the cache as soon as it is done, so a run
    stopped later resumes from it."""
    import precheck, subprocess, tempfile
    if precheck.main(run_smoke=smoke):                               # data errors, then a 3-minute smoke fit
        sys.exit("!! pre-fit checks failed (model/precheck.py): the fit is not started")
    out = dict(inputs=INPUTS, fingerprint=fingerprint(), seed=SEED, sampler=lqm.SAMPLER, diagnostics={})
    try:
        old = json.load(open(FIT_CACHE))
    except (OSError, ValueError):
        old = {}

    def keep(axis, values, diag):
        out[axis], out["diagnostics"][axis] = values, diag
        json.dump(dict(old, **{k: v for k, v in out.items() if k not in ("diagnostics", "fingerprint")},
                       diagnostics=dict(old.get("diagnostics", {}), **out["diagnostics"]),
                       fingerprint="partial"),                    # the site refuses a partial cache
                  open(FIT_CACHE, "w"), indent=1, sort_keys=True)

    parallel = lqm.PARALLEL_AXES and (os.cpu_count() or 1) >= sum(lqm.SAMPLER[a]["chains"] for a, _ in AXES)
    if parallel:
        tmp = tempfile.mkdtemp(prefix="lqm-fit-")
        procs = {a: subprocess.Popen([sys.executable, __file__, "--axis", a, os.path.join(tmp, a + ".json")]
                                     + (["--all"] if refit_all else [])) for a, _ in AXES}
        for a, p in procs.items():
            p.wait()
        for a, _ in AXES:                                            # an axis whose process failed stays as it was
            try:
                keep(a, *json.load(open(os.path.join(tmp, a + ".json"))))
            except (OSError, ValueError):
                print(f"!! {a}: its fit did not finish (exit {procs[a].returncode})", flush=True)
    else:
        for a, f in AXES:
            keep(a, *fit_axis(a, f, old, refit_all))
    if all(a in out for a, _ in AXES):
        json.dump(out, open(FIT_CACHE, "w"), indent=1, sort_keys=True)
        print(f"wrote {FIT_CACHE}")
    else:
        sys.exit("!! the fit is incomplete: model/fit-cache.json holds the finished axes only (partial)")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--axis" in args:                                             # one axis, in a process of its own (main())
        a = args[args.index("--axis") + 1]; dest = args[args.index("--axis") + 2]
        try:
            old = json.load(open(FIT_CACHE))
        except (OSError, ValueError):
            old = {}
        json.dump(fit_axis(a, dict(AXES)[a], old, "--all" in args), open(dest, "w"))
    else:
        main(refit_all="--all" in args, smoke="--no-smoke" not in args)
