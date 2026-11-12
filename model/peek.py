#!/usr/bin/env python3
"""Provisional R̂ of a fit while it runs, read from the draws already on disk (the fit is not touched).

Plain split-R̂ over the draws every chain has written (the fit's own diagnostics, rank-normalised, come at the end
and are a little higher), the five worst parameters with what their index stands for (couple, group, publisher ×
couple, publisher × model, couple × task, maker), the divergences. A chain left in another region shows as a parameter
whose chains disagree (R̂ far above 1, e.g. 2.0 on 20 Oct 2026): the fit can be stopped before its end.

Usage: .stan/venv/bin/python model/peek.py [quality|cost|<run directory>] [--last N] [--no-names]
  default: the most recently written run; --last N: only each chain's N last draws; --no-names: indices only.

What it reads, read-only: the sampling run in progress (seg/: nutpie's zarr store, or CmdStan's CSV files) when there
is one, else the run's committed parts (p<k>/<var>.f64, lqm.RunStore). Its memory stays bounded whatever the size of
the run (12 Nov 2026: the former version loaded the whole store, ≈ 7 GB on the prolonged cost run, and was killed
4 times by the container's memory limit, beside the fit): the draws are read one variable, one chain and one block of
draws (≈ 16 MB) at a time, and each half-chain's mean and sum of squared deviations are accumulated block by block
(Chan's pairwise update), from which split-R̂ is the same as computed on all the draws at once, to rounding. A block
that cannot be read (a chunk being written) is read again a few times; if it still fails, the draws are cut before
it and the run says so. The draws per chain are those every chain has written: the finite log-densities (as before),
and no more than the chunks of every variable present on disk.

Indices: the store's are 0-based, Stan's 1-based; the output gives Stan's (theta[1] is the first couple). The names
come from the build's fit tables (model/fit.py's load_axis, lqm.stan_data) and are checked against the run's key
(lqm.sampling_key): when the data or code changed since the run began, the names are flagged as not guaranteed."""
import glob, json, math, os, sys, time
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_k] = "1"                     # one thread: each thread's stack and malloc arena add to the address space
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(os.path.dirname(HERE), ".stan", "runs")
BLOCK = 16 * 2 ** 20                         # bytes of draws read at a time
RETRIES, PAUSE = 5, 1.0                      # a block that fails to read (a chunk being written): read again
LEAST = 100                                  # fewer draws per chain: too few to tell


def rhat(x):
    """Split-R̂ of one parameter, its draws (chains, draws) all in memory: the reference the streaming one matches."""
    c, d = x.shape; h = d // 2; y = np.concatenate([x[:, :h], x[:, h:2 * h]], 0)
    B = h * y.mean(1).var(ddof=1); W = y.var(1, ddof=1).mean()
    return float(np.sqrt(((h - 1) / h * W + B / h) / W)) if W > 0 else float("nan")


class SplitRhat:
    """Split-R̂ of P parameters accumulated block by block: for each of the 2·C half-chains (the first and second h
    draws of the window, h = its length // 2, a last odd draw left out as rhat does), the count, mean and sum of
    squared deviations of each parameter, merged by Chan's update."""

    def __init__(self, chains, length, P):
        self.h = length // 2
        self.n = np.zeros(2 * chains)
        self.mean = np.zeros((2 * chains, P))
        self.m2 = np.zeros((2 * chains, P))

    def add(self, c, t0, x):
        """Draws t0 … t0 + len(x) − 1 of the window, of chain c: x (draws, P)."""
        for half in (0, 1):
            lo, hi = max(t0, half * self.h), min(t0 + len(x), (half + 1) * self.h)
            if hi <= lo:
                continue
            b = np.asarray(x[lo - t0:hi - t0], dtype=np.float64)
            k, nb = 2 * c + half, hi - lo
            mb = b.mean(0)
            m2b = ((b - mb) ** 2).sum(0)
            na = self.n[k]
            tot = na + nb
            delta = mb - self.mean[k]
            self.mean[k] += delta * (nb / tot)
            self.m2[k] += m2b + delta ** 2 * (na * nb / tot)
            self.n[k] = tot

    def result(self):
        h = self.h
        if not (self.n == h).all():
            raise RuntimeError(f"half-chains of {sorted(set(self.n.tolist()))} draws, {h} expected")
        with np.errstate(invalid="ignore", divide="ignore"):
            B = h * self.mean.var(0, ddof=1)
            W = (self.m2 / (h - 1)).mean(0)
            r = np.sqrt(((h - 1) / h * W + B / h) / W)
        return np.where(W > 0, r, np.nan)


class Torn(Exception):
    """A block of draws that could not be read after RETRIES attempts: the draws are cut at `at`."""

    def __init__(self, at, why):
        super().__init__(why)
        self.at = at


def _retry(read, at):
    for i in range(RETRIES):
        try:
            return read()
        except Exception as e:                                       # a chunk being written: decode error, short file
            if i == RETRIES - 1:
                raise Torn(at, f"{type(e).__name__}: {e}")
            time.sleep(PAUSE)


# ---------------------------------------------------------------- the three sources
def nutpie(seg, last=None):
    """nutpie's zarr store in seg/store: (draws per chain, window, [(name, R̂ array)], divergences, notes)."""
    import zarr
    zarr.config.set({"threading.max_workers": 1, "async.concurrency": 4})   # few threads (see the imports)
    try:
        import numcodecs.blosc as blosc
        blosc.set_nthreads(1); blosc.use_threads = False
    except (ImportError, AttributeError):
        pass
    root = os.path.join(seg, "store")
    st = zarr.open_group(root, mode="r")
    notes = []
    lp = st["sample_stats"]["logp"]
    n = min(int(np.sum(np.isfinite(x) & (x != 0))) for x in (np.asarray(lp[c]) for c in range(lp.shape[0])))
    post = st["posterior"]
    names = list(post)
    on_disk = min(_chunks_present(root, post[k]) for k in names)    # no chunk read as its fill value (NaN)
    if on_disk < n:
        notes.append(f"{n - on_disk} draws per chain whose chunks are not all on disk yet left out")
        n = on_disk
    while True:
        if n < LEAST:
            return n, (0, n), [], 0, notes
        w0 = n - min(n, last) if last else 0
        try:
            out = []
            for k in names:
                a = post[k]
                C, P = a.shape[0], math.prod(a.shape[2:]) if a.ndim > 2 else 1
                acc = SplitRhat(C, n - w0, P)
                ch = a.chunks[1]
                step = max(ch, BLOCK // (8 * P) // ch * ch)
                for c in range(C):
                    for d0 in range(w0 // ch * ch, n, step):
                        lo, hi = max(d0, w0), min(n, d0 + step)
                        x = _block(a, c, lo, hi, ch)
                        acc.add(c, lo - w0, x.reshape(hi - lo, P))
                out.append((k, acc.result(), a.ndim > 2))
            try:
                div = _retry(lambda: int(np.asarray(st["sample_stats"]["diverging"][:, w0:n]).sum()), n)
            except Torn as e:                                        # the result stands without them
                div = None
                notes.append(f"divergences unreadable ({e})")
            return n, (w0, n), out, div, notes
        except Torn as e:
            notes.append(f"a chunk at draw {e.at} could not be read ({e}): the draws cut there")
            n = min(n - 1, e.at)


def _block(a, c, lo, hi, ch):
    """Draws lo … hi − 1 of chain c of a zarr array; a block that fails to read is read again chunk by chunk, to cut
    the draws at the first chunk that fails (Torn)."""
    try:
        return _retry(lambda: np.asarray(a[c, lo:hi], dtype=np.float64), lo)
    except Torn:
        for j0 in range(lo // ch * ch, hi, ch):
            _retry(lambda: np.asarray(a[c, max(lo, j0):min(hi, j0 + ch)]), j0)
        return _retry(lambda: np.asarray(a[c, lo:hi], dtype=np.float64), lo)     # all chunks read: once more


def _chunks_present(root, a):
    """Draws per chain of a (chains, draws, …) array whose chunks are all on disk from the first, in every chain."""
    d = os.path.join(root, a.path, "c")
    out = []
    for c in range(a.shape[0]):
        have = set(os.listdir(os.path.join(d, str(c)))) if os.path.isdir(os.path.join(d, str(c))) else set()
        j = 0
        while str(j) in have:
            j += 1
        out.append(min(a.shape[1], j * a.chunks[1]))
    return min(out)


def cmdstan(seg, last=None):
    """CmdStan's CSV files in seg/ (a continuation or a far chain's restart): two passes over each file, the first
    counting its complete rows, the second accumulating them block by block."""
    files = sorted(glob.glob(os.path.join(seg, "*.csv")))

    def rows(f):
        hdr = None
        for line in open(f):
            if line.startswith("#") or not line.strip():
                continue
            if line.startswith("lp__"):
                hdr = line.strip().split(","); continue
            p = line.strip().split(",")
            if hdr and len(p) == len(hdr):
                yield hdr, p
    counts, hdr = [], None
    for f in files:
        k = 0
        for hdr, _ in rows(f):
            k += 1
        counts.append(k)
    n = min(counts) if counts else 0
    if n < LEAST or hdr is None:
        return n, (0, n), [], 0, []
    w0 = n - min(n, last) if last else 0
    keep = [i for i, h in enumerate(hdr) if not h.endswith("__")]
    dv = hdr.index("divergent__") if "divergent__" in hdr else None
    acc, div, size = SplitRhat(len(files), n - w0, len(keep)), 0, max(1, BLOCK // (8 * len(hdr)))
    for c, f in enumerate(files):
        buf, t = [], 0
        for _, p in rows(f):
            if t >= n:
                break
            if t >= w0:
                buf.append(p)
            t += 1
            if len(buf) == size or (t == n and buf):
                x = np.array(buf, float)
                acc.add(c, t - len(buf) - w0, x[:, keep])
                div += int(x[:, dv].sum()) if dv is not None else 0
                buf = []
    r = acc.result()
    return n, (w0, n), [(hdr[i], r[j:j + 1], None) for j, i in enumerate(keep)], div, []


def parts(run, last=None):
    """The run's committed parts (p<k>/<var>.f64, laid out (draws, chains, *shape)): read by blocks of draws with
    plain file reads (no memory map: a mapping counts in full against an address-space limit)."""
    m = json.load(open(os.path.join(run, "manifest.json")))
    P_ = [p for p in m["parts"] if p.get("chains")]
    if not P_:
        return 0, (0, 0), [], 0, []
    n = min(p["draws"] for p in P_)
    notes = [] if len({p["draws"] for p in P_}) == 1 else [f"parts of {sorted({p['draws'] for p in P_})} draws: the "
                                                           f"first {n} of each"]
    if n < LEAST:
        return n, (0, n), [], 0, notes
    w0 = n - min(n, last) if last else 0
    chains = sum(p["chains"] for p in P_)
    out = []
    for v, shape in m["shapes"].items():
        if v == "lp__" or not math.prod(shape):
            continue
        P = math.prod(shape)
        acc, c0 = SplitRhat(chains, n - w0, P), 0
        for p in P_:
            C = p["chains"]
            step = max(1, BLOCK // (8 * P * C))
            with open(os.path.join(run, p.get("dir", f"p{m['parts'].index(p)}"), v + ".f64"), "rb") as f:
                for d0 in range(w0, n, step):
                    d1 = min(n, d0 + step)
                    f.seek(d0 * C * P * 8)
                    x = np.frombuffer(f.read((d1 - d0) * C * P * 8), dtype=np.float64).reshape(d1 - d0, C, P)
                    for c in range(C):
                        acc.add(c0 + c, d0 - w0, x[:, c, :])
                    try:                                             # leave the page cache to the fit
                        os.posix_fadvise(f.fileno(), d0 * C * P * 8, (d1 - d0) * C * P * 8, os.POSIX_FADV_DONTNEED)
                    except (AttributeError, OSError):
                        pass
            c0 += C
        out.append((v, acc.result(), len(shape) > 0))
    div = sum((p["stats"].get("divergences") or 0) for p in P_)
    if last:
        notes.append("divergences: of all the draws (the manifest counts them per part)")
    return n, (w0, n), out, div, notes


# ---------------------------------------------------------------- names
def labels(axis, run):
    """Variable → the labels of its indices (0-based list), and a warning when the run's key is not the one of the
    current data and code ('' when it is)."""
    sys.path.insert(0, HERE)
    import fit, lqm
    groups, _, _ = fit.load_axis(axis)
    data, maps = lqm.stan_data(groups, axis)
    key = lqm.sampling_key(data, axis, lqm.SAMPLER[axis])[:16]
    warn = "" if os.path.basename(run.rstrip("/")).endswith(key) else \
        f"names not guaranteed: the current data and code give the key {key}, not the run's"
    couples, names, lv = maps["couples"], maps["names"], maps["levels"]
    model_of = {c: lqm.LINE.get(c.split("@")[0], c.split("@")[0]) for c in couples}
    fi = {f: i for i, f in enumerate(lqm.PROVIDERS + ("other",))}
    if lqm.EXT_PRESENT:
        here = {lqm.provider(model_of[c]) for c in couples}
        fi = {f: i for i, f in enumerate(f for f in lqm.PROVIDERS + ("other",) if f in here)}
    makers = sorted(fi, key=fi.get)
    prov_c = [fi[lqm.provider(model_of[c])] for c in couples]

    def with_effects(mk):                                            # the Stan model's with_effects (0-based)
        return [makers[k] for k in sorted(set(mk))]
    by_dim = {}
    by_dim.update({v: couples for v in ("theta", "tau_raw", "tau", "psiC", "omegaC", "deltaC", "level")})
    by_dim.update({v: [f"group {g}" for g in names] for v in ("o", "lg_raw", "log_sigma", "sigma", "a")})
    by_dim.update({v: [f"{s} × {c}" for s, c in lv["pub_couple"]] for v in ("y1", "z1")})
    by_dim.update({v: [f"{s} × {mo}" for s, mo in lv["pub_model"]] for v in ("y2", "z2", "psi2")})
    by_dim.update({v: [f"{c} × {t}" for c, t in lv["couple_task"]] for v in ("y3", "z3", "omega3")})
    by_dim.update({v: [f"maker {f}" for f in makers]
                   for v in ("la_tau", "la_psi", "la_omega", "delta_f", "s_tau_f", "psi_f", "omega_f")})
    by_dim["r_tau"] = [f"maker {f}" for f in with_effects([prov_c[couples.index(c)] for _, c in lv["pub_couple"]])]
    by_dim["r_psi"] = [f"maker {f}" for f in with_effects([fi[lqm.provider(mo)] for _, mo in lv["pub_model"]])]
    by_dim["r_omega"] = [f"maker {f}" for f in with_effects([prov_c[couples.index(c)] for c, _ in lv["couple_task"]])]
    return by_dim, warn


def stan_name(v, j, vector):
    """The parameter's name in Stan's 1-based indexing: a 0-based index j of the store."""
    return f"{v}[{j + 1}]" if vector else v


# ---------------------------------------------------------------- main
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    last, names = None, True
    if "--last" in argv:
        i = argv.index("--last"); last = int(argv[i + 1]); del argv[i:i + 2]
    if "--no-names" in argv:
        argv.remove("--no-names"); names = False
    target = argv[0] if argv else ""
    if target and os.path.isdir(target):
        run = os.path.abspath(target)
    else:
        runs = sorted(glob.glob(os.path.join(RUNS, f"{target}*")), key=os.path.getmtime)
        if not runs:
            sys.exit("no store")
        run = runs[-1]
    seg = os.path.join(run, "seg")
    if os.path.isdir(seg) and (glob.glob(os.path.join(seg, "*.csv")) or os.path.isdir(os.path.join(seg, "store"))):
        src, (n, (w0, w1), out, div, notes) = "seg", (cmdstan if glob.glob(os.path.join(seg, "*.csv")) else nutpie)(
            seg, last)
    elif os.path.exists(os.path.join(run, "manifest.json")):
        src, (n, (w0, w1), out, div, notes) = "parts", parts(run, last)
    else:
        sys.exit(f"{os.path.basename(run)}: no draws")
    tag = os.path.basename(run)
    if w1 - w0 < LEAST:
        sys.exit(f"{tag}: {w1 - w0} draws per chain, too few" + "".join(f" · {x}" for x in notes))
    r = sorted(((float(v), k, j, vec) for k, R, vec in out for j, v in enumerate(R)),
               key=lambda t: -np.nan_to_num(t[0]))
    lab, warn = {}, ""
    axis = next((a for a in ("quality", "cost") if tag.startswith(a + "-")), None)
    if names and axis:
        try:
            lab, warn = labels(axis, run)
        except Exception as e:                                       # the names are a help, not the result
            warn = f"names unavailable ({type(e).__name__}: {e})"

    def show(v, k, j, vec):
        if vec is None:                                              # CmdStan's own name: theta.12 (1-based)
            base, _, i = k.partition(".")
            name, j = (f"{base}[{i}]", int(i) - 1) if i.isdigit() else (k, None)
            k = base
        else:
            name = stan_name(k, j, vec)
        what = lab.get(k)
        tail = f" ({what[j]})" if what is not None and j is not None and j < len(what) else ""
        return f"{name}{tail} {v:.3f}"
    window = f"draws {w0 + 1}–{w1} of {n}" if last else f"{n} draws/chain"
    print(f"{tag} [{src}]: {window} · R̂ max {r[0][0]:.4f} · >1.01 {sum(v > 1.01 for v, *_ in r)} · "
          f">1.05 {sum(v > 1.05 for v, *_ in r)} of {len(r)} · divergences {div}")
    print("worst: " + "; ".join(show(*t) for t in r[:5]))
    for x in notes + ([warn] if warn else []):
        print(f"note: {x}")
    return dict(n=n, window=(w0, w1), rhat=[(v, k, j) for v, k, j, _ in r], divergences=div, notes=notes)


if __name__ == "__main__":
    main()
