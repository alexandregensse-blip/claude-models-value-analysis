"""Tests of the fit's sampler rule of 30 Oct 2026 (model/lqm.py: _run, _grow, far_chains, RunStore.drop/add): an R̂
above RESTART_RHAT without a far chain continues the chains (no reset), a chain in a far region restarts alone from a
good chain's last draw (the good chains' draws kept), and the far criterion on the real cases of 29–30 Oct. The sampler
and the diagnostics are stubs (no Stan, no sampling): the sampler writes CmdStan-format files whose parameter `nu`
holds a chain's region (its log-density level) and whose lp__ is that level plus noise. Negative controls: the same
scenarios through _run and _grow as they were before the rule (commit 52be157) reset the axis / stop the run.

Needs numpy (and zarr for _grow): run with .stan/venv/bin/python data/tests/run.py sampler; skipped without them."""
import importlib.util, json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "..", "..", "model")
ROOT = os.path.join(HERE, "..", "..")
BEFORE = "52be157"                                                  # the last commit with the restart rule

TESTS = []


def test(f):
    f.__name__ = "sampler_" + f.__name__
    TESTS.append(f)
    return f


def eq(got, want, what=""):
    if got != want:
        raise AssertionError(f"{what}: got {got!r}, want {want!r}")


def need(*mods):
    for m in mods:
        try:
            __import__(m)
        except ImportError:
            raise AssertionError(f"SKIP: needs {m} (run with .stan/venv/bin/python)")


def lqm_now():
    sys.path.insert(0, MODEL)
    import lqm
    return lqm


def lqm_before():
    """model/lqm.py as of BEFORE, loaded as a module of its own (None when git cannot give it)."""
    try:
        src = subprocess.run(["git", "-C", ROOT, "show", f"{BEFORE}:model/lqm.py"], capture_output=True, text=True,
                             check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    d = tempfile.mkdtemp(prefix="lqm-before-")
    path = os.path.join(d, "lqm_before.py")
    open(path, "w").write(src)
    spec = importlib.util.spec_from_file_location("lqm_before", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.STAN_FILE = lqm_now().STAN_FILE                                # its parameter names
    m.INITS = os.path.join(d, "inits-{axis}.json")                   # no previous fit: a cold start
    shutil.rmtree(d, ignore_errors=True)
    return m


SLOW = 120                       # the stub's R̂: 1.08 below SLOW draws per chain (slow mixing), 1.005 from it on
ST = dict(engine="nutpie", chains=6, warmup=10, samples=60, target_accept=0.9, extend=30, extend_max=120)


class Stub:
    """The sampler and diagnostics of one scenario, patched into a module L (lqm now or before). regions = each chain's
    log-density level in the first run; div = draws marked divergent per chain of the first run."""

    def __init__(self, L, regions, div=None):
        import numpy as np
        self.L, self.regions, self.div, self.calls, self.resets = L, regions, div or {}, [], 0
        self.rng = np.random.default_rng(1)
        self.saved = {k: getattr(L, k) for k in ("_sample", "diagnostics", "_read_nutpie")}
        reset = L.RunStore.reset
        self.saved_reset = reset

        def counted(store):
            self.resets += 1
            return reset(store)
        L._sample, L.diagnostics, L._read_nutpie = self.sample, self.diagnostics, L._read_cmdstan
        L.RunStore.reset = counted

    def restore(self):
        for k, v in self.saved.items():
            setattr(self.L, k, v)
        self.L.RunStore.reset = self.saved_reset

    def sample(self, data, axis, st, seed, seg, inits=None, adapted=None, draws=None, grow=False):
        import numpy as np
        C, n = st["chains"], draws or st["samples"]
        first = st["engine"] == "nutpie" and adapted is None
        level = (self.regions if first else
                 [d["nu"] for d in inits] if inits else list(self.rng.normal(1900, 50, C)))   # cold: anywhere near
        self.calls.append(dict(engine=st["engine"], chains=C, draws=n, inits=inits, adapted=adapted))
        cols = "lp__,accept_stat__,stepsize__,treedepth__,n_leapfrog__,divergent__,energy__,theta.1,theta.2,nu"
        for c in range(C):
            with open(os.path.join(seg, f"stub-{seed}_{c + 1}.csv"), "w") as f:
                f.write(f"# stub\n{cols}\n")
                if adapted is None:                                  # CmdStan writes its adaptation after the header
                    f.write(f"# Step size = {round(0.1 + 0.01 * c, 2)}\n# Diagonal elements of inverse mass matrix:\n"
                            f"# {1 + c},{2 + c},{3 + c}\n")
                th = (inits[c]["theta"] if inits else [0.0, 0.0])
                for i in range(n):
                    dv = int(first and i < self.div.get(c, 0))
                    t = th[0] + self.rng.normal(0, 0.1)
                    f.write(f"{level[c] + self.rng.normal(0, 30)},0.9,0.1,5,31,{dv},0,{t},{-t},{level[c]}\n")

    def diagnostics(self, post):
        import numpy as np
        lp = post.lp() if hasattr(post, "lp") else None
        if lp is None:                                               # the code before: lp__ is not stored
            lp = post.chains("nu")
        C, n = lp.shape
        med = np.median(lp, axis=1)
        rhat = 1.4 if med.max() - med.min() > 1000 else 1.08 if n < SLOW else 1.005
        ess = 1000 if rhat < 1.01 else 40
        return dict(rhat_max=rhat, ess_bulk_min=ess, ess_tail_min=ess, divergences=post.stats["divergences"] or 0,
                    draws=C * n, worst_rhat=[]), None


def run(L, regions, div=None):
    """_run of module L on a scenario, in a temporary store: (posterior in memory, stub, store manifest, the first
    run's lp__ per chain as the stub wrote it)."""
    stub = Stub(L, regions, div)
    store = L.RunStore(tempfile.mkdtemp(prefix="lqm-stub-"))
    try:
        post = L._run(store, {}, "cost", dict(ST), 7, lambda *a: None)
        return post.in_memory(), stub, json.loads(json.dumps(store.manifest))
    finally:
        stub.restore()
        shutil.rmtree(store.path, ignore_errors=True)


def first_draws(L, regions, div=None):
    """The first run's draws alone (each chain's nu and theta), for comparing with what a rule kept."""
    import numpy as np
    stub = Stub(L, regions, div)
    store = L.RunStore(tempfile.mkdtemp(prefix="lqm-stub-"))
    try:
        seg = store.begin(engine="nutpie", seed=7, chains=6, draws=ST["samples"], part=None, adapted=None)
        stub.sample({}, "cost", ST, 7, seg)
        store.commit()
        p = store.posterior()
        return np.array(p.chains("theta"))
    finally:
        stub.restore()
        shutil.rmtree(store.path, ignore_errors=True)


GOOD = [1890, 1900, 1910, 1895, 1905, 1898]
FARS = [1890, 1900, -27300, 1910, 1895, 1905]                         # chain 2 in a far region (29 Oct, seed 12)


@test
def slow_mixing_continued_not_reset():
    """(a) R̂ 1.08 with the six chains in one region: the chains are continued on CmdStan from their last draws with
    their adapted state, by slices of 30 up to the criteria (120 draws), never reset; the first run's draws are the
    first draws of the result. Negative control: _run before the rule resets the axis and samples it again from a cold
    start (the first draws are not kept)."""
    need("numpy")
    import numpy as np
    L = lqm_now()
    post, stub, man = run(L, GOOD)
    eq(stub.resets, 0, "no reset")
    eq([(c["engine"], c["chains"], c["draws"], c["adapted"] is not None) for c in stub.calls],
       [("nutpie", 6, 60, False), ("cmdstan", 6, 30, True), ("cmdstan", 6, 30, True)], "nutpie, then two slices")
    eq([round(d["nu"]) for d in stub.calls[1]["inits"]], GOOD, "each chain continued from its own last draw")
    eq(len(man["parts"]), 1, "one part")
    eq(post.shape("theta")[:2], (6, SLOW), "120 draws per chain")
    eq(np.allclose(post.chains("theta")[:, :60], first_draws(L, GOOD)), True, "the first run's draws kept")
    eq((post.stats["extensions"], post.stats["far_restarted"]), (2, 0), "two extensions, no restart")
    B = lqm_before()
    if B is None:
        raise AssertionError("SKIP negative control: git cannot show the code before the rule")
    post0, stub0, _ = run(B, GOOD)
    eq(stub0.resets, 1, "negative control: the rule before resets the axis")
    eq((stub0.calls[1]["engine"], stub0.calls[1]["inits"], stub0.calls[1]["adapted"]), ("cmdstan", None, None),
       "negative control: and samples it again, cold")
    eq(np.allclose(post0.chains("theta")[:, :60], first_draws(B, GOOD)), False,
       "negative control: the first run's draws are lost")


@test
def far_chain_restarted_from_a_good_chain():
    """(b) Chain 2 at −27,300 against +1,900 (with 10 divergent draws): its draws are dropped and it restarts on
    CmdStan, without warm-up, from the last draw of good chain 0 with chain 0's step size and metric; the five good
    chains' draws are kept as drawn, the far chain's divergences go with it, then all six continue together up to the
    criteria. Negative controls: the slow-mixing scenario restarts no chain (test a); _run before the rule resets the
    axis (the good chains' draws lost)."""
    need("numpy")
    import numpy as np
    L = lqm_now()
    post, stub, man = run(L, FARS, div={2: 10})
    eq(stub.resets, 0, "no reset")
    eq([(c["engine"], c["chains"], c["draws"]) for c in stub.calls],
       [("nutpie", 6, 60), ("cmdstan", 1, 60), ("cmdstan", 5, 30), ("cmdstan", 1, 30), ("cmdstan", 5, 30),
        ("cmdstan", 1, 30)], "nutpie; the far chain restarted up to 60; both parts continued by slices")
    r = stub.calls[1]
    first = first_draws(L, FARS, div={2: 10})
    eq((round(r["inits"][0]["nu"]), r["adapted"]["step_size"], r["adapted"]["inv_metric"]), (1890, [0.1], [[1, 2, 3]]),
       "restarted from chain 0's last draw, with chain 0's adapted state")
    eq(np.allclose(r["inits"][0]["theta"], first[0, -1] - first[0, -1].mean()), True, "chain 0's last θ (centred)")
    eq([(p["chains"], p["draws"]) for p in man["parts"]], [(5, SLOW), (1, SLOW)], "the good chains, the restarted one")
    eq((man["parts"][0]["dropped"], man["parts"][1]["far"], man["parts"][1]["source"]),
       ([dict(chains=[2], draws=60)], [2], [0]), "what was dropped and where it restarted from")
    eq(np.allclose(post.chains("theta")[:5, :60], first[[0, 1, 3, 4, 5]]), True, "the good chains' draws kept")
    eq(np.median(post.lp()[5]) > 1700, True, "the restarted chain in the region")
    eq((post.stats["divergences"], post.stats["far_restarted"]), (0, 1), "the far chain's divergences dropped")
    eq(man["parts"][0]["adapted"]["step_size"], [0.1, 0.11, 0.13, 0.14, 0.15], "the good chains' adapted state")
    B = lqm_before()
    if B is None:
        raise AssertionError("SKIP negative control: git cannot show the code before the rule")
    post0, stub0, _ = run(B, FARS, div={2: 10})
    eq(stub0.resets, 1, "negative control: the rule before resets the axis")
    eq(np.allclose(post0.chains("theta")[[0, 1, 3, 4, 5], :60], first[[0, 1, 3, 4, 5]]), False,
       "negative control: the good chains' draws lost")


@test
def drop_is_per_chain_and_resumable():
    """RunStore.drop keeps the other chains' draws, adapted state and per-chain statistics; a part added with starting
    points and no draw (a stop right after the far chain's drop) is sampled from them when _run resumes the store."""
    need("numpy")
    import numpy as np
    L = lqm_now()
    stub = Stub(L, FARS, div={2: 10})
    store = L.RunStore(tempfile.mkdtemp(prefix="lqm-stub-"))
    try:
        seg = store.begin(engine="nutpie", seed=7, chains=6, draws=60, part=None, adapted=None)
        stub.sample({}, "cost", ST, 7, seg)
        store.commit()
        before = store.posterior().chains("theta")
        eq(store.parts[0]["stats"]["chain"]["divergences"], [0, 0, 10, 0, 0, 0], "divergences per chain")
        post = store.posterior()
        start = L._last_draws(post)[0]
        store.drop(0, [2])
        eq((store.parts[0]["chains"], store.parts[0]["stats"]["divergences"]), (5, 0), "chain 2 and its divergences out")
        eq(np.allclose(store.posterior().chains("theta"), before[[0, 1, 3, 4, 5]]), True, "the others as drawn")
        eq(os.path.isdir(os.path.join(store.path, "p0")), False, "the old directory removed")
        store.add("cmdstan", 1, 60, dict(step_size=[0.1], inv_metric=[[1, 2, 3]]), [start], far=[2], source=[0])
        again = L.RunStore(store.path)                               # the same store, read again (a resumed run)
        stub.calls.clear()
        post = L._run(again, {}, "cost", dict(ST), 7, lambda *a: None)
        eq((stub.calls[0]["chains"], stub.calls[0]["draws"], round(stub.calls[0]["inits"][0]["nu"])), (1, 60, 1890),
           "the planned part sampled from its starting point")
        eq(post.shape("theta")[:2], (6, SLOW), "then continued with the others")
    finally:
        stub.restore()
        shutil.rmtree(store.path, ignore_errors=True)


def nutpie_store(lp, div=None):
    """A finished nutpie store (zarr) with the given log-densities (chains, draws)."""
    import numpy as np, zarr
    d = tempfile.mkdtemp(prefix="lqm-zarr-")
    C, n = lp.shape
    g = zarr.open_group(d, mode="w")
    p, s = g.create_group("posterior"), g.create_group("sample_stats")
    p.create_array("nu", shape=(C, n), chunks=(1, n), dtype="f8")[:] = lp
    for k, v in (("logp", lp), ("n_steps", np.full((C, n), 31.0)), ("step_size", np.full((C, n), 0.1)),
                 ("diverging", np.zeros((C, n), bool) if div is None else div)):
        s.create_array(k, shape=(C, n), chunks=(1, n), dtype=v.dtype)[:] = v
    return d


class Finished:
    is_finished = True

    def wait(self):
        pass

    def abort(self):
        pass


@test
def grow_runs_on_without_a_far_chain():
    """nutpie in process (_grow): with R̂ 1.08 and no far chain the run is not stopped at the planned 60 draws but runs
    on to the check where the criteria hold (120); with a far chain it stops at the first check (60), for _run to
    restart that chain. Negative control: _grow before the rule stops the slow-mixing run at 60."""
    need("numpy", "zarr")
    import numpy as np
    L = lqm_now()
    rng = np.random.default_rng(3)
    slow = np.array(GOOD, float)[:, None] + rng.normal(0, 30, (6, 180))
    far = np.array(FARS, float)[:, None] + rng.normal(0, 30, (6, 180))
    stub = Stub(L, GOOD)
    try:
        for lp, want, what in ((slow, 120, "no far chain: runs on to the criteria"),
                               (far, 60, "a far chain: stops at the first check")):
            d = nutpie_store(lp)
            try:
                eq(L._grow(Finished(), d, 60, 180, 30), want, what)
            finally:
                shutil.rmtree(d, ignore_errors=True)
    finally:
        stub.restore()
    B = lqm_before()
    if B is None:
        raise AssertionError("SKIP negative control: git cannot show the code before the rule")
    stub = Stub(B, GOOD)
    B._NutpieDraws.lp = lambda self: np.asarray(self.g["sample_stats"]["logp"][:, :self.n])
    d = nutpie_store(slow)
    try:
        eq(B._grow(Finished(), d, 60, 180, 30), 60, "negative control: the rule before stops the slow run")
    finally:
        stub.restore()
        shutil.rmtree(d, ignore_errors=True)


# The real cases: each chain's log-density as the fit's report (.stan/fit-report.log) logged it every 2–3 minutes,
# one draw per chain per line, during the sampling phase (draws, not warm-up), and the archived nutpie store of seed 12
CASES = {
    # 29 Oct, seed 11, four chains: one at −2,900 against +2,050 (commit afd1a78; its store was not kept): the two
    # levels logged, as four chains of 200 draws around them
    "cost 29 Oct seed 11": ([2050, 2050, 2050, -2900], [3]),
    # 29 Oct 22:59, seed 12 (the archived store's first 16 draws: medians 1,888, 1,817, 1,900, −27,307, 450, 1,907)
    "cost 29 Oct seed 12": ([[1910], [1825], [1842], [-27309], [499], [1887]], [3, 4]),
    # 29–30 Oct, seed 13, nutpie: 20 lines from 23:15 to 23:58 (R̂ 1.081, all six in one region)
    "cost 29–30 Oct seed 13": (
        [[1892, 1878, 1870, 1869, 1940, 1907, 1929, 1887, 2044, 1901, 1798, 1899, 1895, 1971, 1835, 1891, 1915, 1848,
          1837, 1836],
         [2146, 1855, 2010, 1877, 1995, 1921, 1854, 1869, 1843, 1878, 1899, 2033, 1902, 2031, 1897, 1811, 2013, 1852,
          1848, 1934],
         [1906, 1823, 1841, 1935, 1894, 1948, 1895, 1888, 1950, 1881, 1888, 1832, 1909, 1816, 1916, 1919, 1866, 1875,
          1936, 2082],
         [1839, 1845, 1903, 1885, 1822, 1926, 1850, 1986, 1892, 1891, 1842, 1911, 1966, 1828, 1894, 1935, 2054, 1885,
          1905, 1877],
         [1901, 1899, 1931, 1940, 1922, 1909, 1819, 1932, 1933, 1958, 1910, 1967, 1895, 1915, 1873, 1884, 2116, 1876,
          1957, 1918],
         [1931, 1854, 1859, 1923, 1845, 1954, 1906, 1948, 2088, 1848, 1898, 1881, 1896, 1808, 1925, 1945, 1948, 1985,
          1840, 1823]], []),
    # 29–30 Oct, quality, nutpie: 10 lines from 01:54 to 02:14 (R̂ 1.41: chain 5 at −69,800)
    "quality 29–30 Oct": (
        [[-5113, -5143, -5110, -5133, -5054, -5081, -5093, -5106, -5084, -5069],
         [-5129, -5082, -5063, -5138, -5129, -5155, -5064, -5217, -5122, -5195],
         [-5034, -5058, -5138, -5101, -5048, -5058, -5109, -5139, -5159, -5150],
         [-5106, -5161, -5229, -5113, -5061, -5126, -5025, -5129, -5151, -5070],
         [-69827, -69830, -69818, -69809, -69792, -69790, -69785, -69788, -69780, -69780],
         [-5102, -5160, -5104, -5154, -5150, -5120, -5156, -5099, -5114, -5109]], [4]),
    # 30 Oct, quality, CmdStan (converged, R̂ 1.0067): 10 lines from 05:06 to 05:29
    "quality 30 Oct CmdStan": (
        [[-5061.1, -5018.9, -5006.8, -5358.1, -5181.0, -5094.6, -5255.2, -5141.5, -5098.7, -5365.2],
         [-5023.9, -5342.1, -5215.1, -5071.1, -5062.3, -5003.7, -5120.8, -5041.5, -5193.9, -4992.3],
         [-5007.8, -5172.9, -5198.5, -5407.4, -5213.2, -5156.4, -5141.9, -4873.4, -5037.5, -5199.3],
         [-5212.2, -4998.0, -5199.6, -4957.2, -5153.9, -5038.9, -5071.4, -5079.7, -4988.0, -5141.0],
         [-5345.6, -5049.9, -5181.8, -5152.9, -5335.6, -5155.1, -5151.9, -4911.9, -5118.6, -5181.1],
         [-5024.7, -5163.6, -4986.1, -5077.5, -5176.6, -5214.7, -5200.6, -5116.6, -5054.7, -5106.7]], []),
}
ARCHIVE = os.path.join(ROOT, ".stan", "archive", "cost-6fef64d38d6b598d", "seg", "store")


@test
def far_criterion_on_the_real_cases():
    """(c) far_chains flags the far chains of 29 Oct (seed 11: −2,900 against +2,050; seed 12: −27,300 and +450
    against +1,880; quality: −69,800 against −5,100) and none of the slow but single-region cost run of 29–30 Oct
    (medians 1,892–1,916) nor of the converged quality run. Negative controls: a fixed bar of 20 (no floor, no
    spread term) flags two good chains of the converged quality run; a floor of 1,500 misses chain 5 of seed 12
    (1,343 below the others); the other chains' standard deviation instead of their median absolute deviation misses
    it too (the other far chain widens it)."""
    need("numpy")
    import numpy as np
    L = lqm_now()
    rng = np.random.default_rng(5)
    for name, (lp, want) in CASES.items():
        lp = np.asarray(lp, float)
        if lp.ndim == 1:
            lp = lp[:, None] + rng.normal(0, 55, (len(lp), 200))
        eq(L.far_chains(lp), want, name)
    if os.path.isdir(ARCHIVE):                                       # the store itself, where it is kept
        need("zarr")
        import zarr
        g = zarr.open_group(ARCHIVE, mode="r")
        n = L._nutpie_written(g, ARCHIVE)
        eq((n, L.far_chains(np.asarray(g["sample_stats"]["logp"][:, :n]))), (16, [3, 4]), "the archived store")
    saved = dict(L.FAR)
    try:
        L.FAR.update(lp=20, spread=0)
        eq(L.far_chains(np.asarray(CASES["quality 30 Oct CmdStan"][0], float)), [2, 4],
           "negative control: a fixed bar of 20 flags good chains")
        L.FAR.update(lp=1500, spread=5)
        eq(L.far_chains(np.asarray(CASES["cost 29 Oct seed 12"][0], float)), [3],
           "negative control: a floor of 1,500 misses chain 5")
    finally:
        L.FAR.clear()
        L.FAR.update(saved)
    m = np.median(np.asarray(CASES["cost 29 Oct seed 12"][0], float), axis=1)
    o = np.delete(m, 4)
    eq(np.median(o) - m[4] > max(300, 5 * np.std(o)), False, "negative control: a standard deviation misses chain 5")


@test
def restart_inputs_accepted_by_cmdstan():
    """Two things a far chain's restart needs from CmdStan, found on a real short run (30 Oct): a one-chain run's CSV
    file has no _<n> suffix (lqm_ext2-<time>.csv), and a starting point read from CSV draws (6 digits) must have every
    sum-to-zero vector re-centred, not θ alone (zf_tau, zf_psi, zf_omega, zd: Stan refuses a sum above 1e-8).
    Negative controls: the code before reads no one-chain file (an error) and re-centres θ alone."""
    need("numpy")
    import numpy as np
    L = lqm_now()
    d = tempfile.mkdtemp(prefix="lqm-csv-")
    try:
        with open(os.path.join(d, "lqm_ext2-20261030054738.csv"), "w") as f:
            f.write("# one chain\nlp__,accept_stat__,stepsize__,treedepth__,n_leapfrog__,divergent__,energy__,nu\n")
            f.write("1900,0.9,0.1,5,31,0,0,3\n1901,0.9,0.1,5,31,0,0,4\n")
        info = dict(chains=1, adapted=dict(step_size=[0.1], inv_metric=[[1.0]]))
        shapes, write = L._read_cmdstan(d, info)
        files = {v: open(os.path.join(d, v + ".f64"), "w+b") for v in shapes}
        n, stats, _ = write(files)
        for f in files.values():
            f.close()
        eq((n, sorted(shapes), stats["chain"]["leapfrog_sum"]), (2, ["lp__", "nu"], [62.0]), "one chain read")
        B = lqm_before()
        if B is None:
            raise AssertionError("SKIP negative control: git cannot show the code before the rule")
        try:
            B._read_cmdstan(d, info)
            raise AssertionError("negative control: the code before read the one-chain file")
        except AttributeError:
            pass
    finally:
        shutil.rmtree(d, ignore_errors=True)
    z = np.array([[[0.300001, -0.1, -0.2]]])                         # (draws, chains, F): sums to 1e-6
    th = np.array([[[1.000001, -1.0]]])
    post = L.Posterior({"zf_tau": [z], "theta": [th]}, {})
    for M, want in ((L, True), (B, False)):
        d0 = M._last_draws(post)[0]
        eq((abs(sum(d0["theta"])) < 1e-12, abs(sum(d0["zf_tau"])) < 1e-12), (True, want),
           "re-centred" if want else "negative control: the code before leaves zf_tau off zero")
