#!/usr/bin/env python3
"""Fits the latent-quality model (lqm.py, lqm.stan) on both axes and writes gen/fit-cache.json, which the page build
reads. Run in the Stan environment:  .stan/venv/bin/python gen/fit.py

The cache holds, per couple and axis, reference-free values on the log scale — [centre, quasi-standard error,
publishers, new-source 16–84 % interval] — with the fit's diagnostics. A fit that misses the convergence criteria (lqm.CONVERGED) is written with
converged = false, and the build refuses it."""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lqm
from build import FIT, FIT_CACHE, MX, ROOT, fit_fingerprint


def main():
    out = dict(fingerprint=fit_fingerprint(), settings=FIT, diagnostics={})
    for axis, field in (("cost", "cost_usd"), ("quality", "score")):
        t = time.time()
        groups, report, republished = lqm.load(os.path.join(ROOT, "raw-data.csv"), list(MX), field=field)
        mcmc, maps = lqm.fit(groups, axis, chains=FIT["chains"], warmup=FIT["warmup"], samples=FIT["samples"],
                             seed=FIT["seed"], adapt_delta=FIT["adapt_delta"])
        S, diag = lqm.summarise(mcmc, maps, groups)
        out[axis] = {c: [round(v["centre"], 5), round(v["half"], 5), v["publishers"], [round(x, 5) for x in v["new_source"]]]
                     for c, v in sorted(S.items())}
        diag.update(groups=len(groups), rows=sum(len(g["rows"]) for g in groups.values()), set_aside=dict(report),
                    republished=[list(p) for p in republished],
                    unpublished=sorted(c for c, v in S.items() if not v["published"]),
                    converged=lqm.converged(diag), seconds=round(time.time() - t))
        out["diagnostics"][axis] = diag
        print(f"{axis}: {json.dumps(diag)}", flush=True)
    json.dump(out, open(FIT_CACHE, "w"), indent=1, sort_keys=True)
    print(f"wrote {FIT_CACHE}")


if __name__ == "__main__":
    main()
