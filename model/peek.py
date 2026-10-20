#!/usr/bin/env python3
"""Provisional R̂ of a fit while it runs, read from the draws already on disk (the fit is not touched).

Plain split-R̂ over the draws every chain has written (the fit's own diagnostics, rank-normalised, come at the end
and are a little higher), the five worst parameters, the divergences. A chain left in another region shows as a
parameter whose chains disagree (R̂ far above 1, e.g. 2.0 on 20 Oct 2026): the fit can be stopped before its end.
Usage: .stan/venv/bin/python model/peek.py [quality|cost]   (default: the most recently written store)"""
import glob, os, sys
import numpy as np

RUNS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".stan", "runs")


def rhat(x):
    c, d = x.shape; h = d // 2; y = np.concatenate([x[:, :h], x[:, h:2 * h]], 0)
    B = h * y.mean(1).var(ddof=1); W = y.var(1, ddof=1).mean()
    return float(np.sqrt(((h - 1) / h * W + B / h) / W)) if W > 0 else float("nan")


def cmdstan(seg):
    chains, hdr = [], None
    for f in sorted(glob.glob(os.path.join(seg, "*.csv"))):
        rows = []
        for line in open(f):
            if line.startswith("#") or not line.strip():
                continue
            if line.startswith("lp__"):
                hdr = line.strip().split(","); continue
            p = line.strip().split(",")
            if hdr and len(p) == len(hdr):
                rows.append(p)
        chains.append(np.array(rows, float))
    n = min(len(c) for c in chains)
    if n < 100:
        return n, [], 0
    X = np.stack([c[:n] for c in chains])
    div = int(X[:, :, hdr.index("divergent__")].sum()) if "divergent__" in hdr else 0
    return n, [(hdr[i], X[:, :, i]) for i in range(len(hdr)) if not hdr[i].endswith("__")], div


def nutpie(seg):
    import zarr
    st = zarr.open(os.path.join(seg, "store"), mode="r")
    lp = st["sample_stats"]["logp"][:]
    n = min(int(np.sum(np.isfinite(c) & (c != 0))) for c in lp)
    if n < 100:
        return n, [], 0
    out = []
    for k in st["posterior"]:
        a = st["posterior"][k][:, :n]; a = a.reshape(a.shape[0], n, -1)
        out += [(f"{k}[{j}]", a[:, :, j]) for j in range(a.shape[2])]
    return n, out, int(st["sample_stats"]["diverging"][:, :n].sum())


def main():
    axis = sys.argv[1] if len(sys.argv) > 1 else ""
    runs = sorted(glob.glob(os.path.join(RUNS, f"{axis}*")), key=os.path.getmtime)
    if not runs:
        sys.exit("no store")
    seg = os.path.join(runs[-1], "seg")
    if not os.path.isdir(seg):
        sys.exit(f"{os.path.basename(runs[-1])}: no sampling in progress")
    n, params, div = (cmdstan if glob.glob(os.path.join(seg, "*.csv")) else nutpie)(seg)
    if n < 100:
        sys.exit(f"{os.path.basename(runs[-1])}: {n} draws per chain, too few")
    r = sorted(((rhat(x), k) for k, x in params), key=lambda t: -np.nan_to_num(t[0]))
    print(f"{os.path.basename(runs[-1])}: {n} draws/chain · R̂ max {r[0][0]:.4f} · >1.01 {sum(v > 1.01 for v, _ in r)} · "
          f">1.05 {sum(v > 1.05 for v, _ in r)} of {len(r)} · divergences {div} · worst "
          + ", ".join(f"{k} {v:.3f}" for v, k in r[:5]))


if __name__ == "__main__":
    main()
