"""Tests of the fit's sampler rules of 30 Oct 2026 (model/lqm.py: _run, _grow, _checks, far_chains, RunStore.drop/add,
fit's seed): an R̂ above 1.05 without a far chain continues the chains (no reset), a chain in a far region restarts
alone from a good chain's last draw (the good chains' draws kept), the far chains are looked at whatever R̂ — every
FAR["every"] iterations (warm-up included: reported there), at the end of warm-up and at every slice, on nutpie and on
CmdStan's continuations — and the far criterion on the real cases of 29–30 Oct; each fit draws its own seed, which a
stored run keeps. The sampler and the diagnostics are stubs (no Stan, no sampling): the sampler writes CmdStan-format
files whose parameter `nu` holds a chain's region (its log-density level) and whose lp__ is that level plus noise.
Negative controls: the same scenarios through _run and _grow as they were before the rules (commit 52be157: the axis
reset, the run stopped; commit 66c6fbf: a far chain seen only at a slice, the warm-up not looked at).

Needs numpy (and zarr for _grow): run with .stan/venv/bin/python data/tests/run.py sampler (or this file); skipped
without them."""
import importlib.util, json, linecache, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "..", "..", "model")
ROOT = os.path.join(HERE, "..", "..")
BEFORE = "52be157"                                                  # the last commit with the restart rule
SLICES = "66c6fbf"                                                  # far chains looked at only at a slice, R̂ > 1.05
ONE_DRAW = "7482996"             # a far verdict on one draw per chain after a restart; diagnostics crash on one draw
LEAST = 5                        # FAR["least"] in the stubs' short runs (production: 100)

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


def lqm_before(commit=BEFORE):
    """model/lqm.py as of a commit (BEFORE by default), loaded as a module of its own (None when git cannot give it)."""
    try:
        src = subprocess.run(["git", "-C", ROOT, "show", f"{commit}:model/lqm.py"], capture_output=True, text=True,
                             check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    d = tempfile.mkdtemp(prefix="lqm-before-")
    path = os.path.join(d, "lqm_before.py")
    open(path, "w").write(src)
    spec = importlib.util.spec_from_file_location("lqm_" + commit, path)
    m = importlib.util.module_from_spec(spec)
    linecache.cache[path] = (len(src), None, src.splitlines(True), path)  # its source and module, for sampling_key
    sys.modules[spec.name] = m
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

    def __init__(self, L, regions, div=None, stop_far=None, jump=None, lp_first=None):
        import numpy as np
        self.L, self.regions, self.div, self.calls, self.resets = L, regions, div or {}, [], 0
        self.lp_first = lp_first or {}       # call number → {chain: the log-density of its first draw}
        self.stop_far = stop_far             # the first run stops at its first draw on these far chains (as _grow
        self.jump = jump or {}               # does at the end of warm-up); jump: call number → {chain: new level}
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

    def sample(self, data, axis, st, seed, seg, inits=None, adapted=None, draws=None, grow=False, say=None):
        import numpy as np
        C, n = st["chains"], draws or st["samples"]
        first = st["engine"] == "nutpie" and adapted is None
        if first and self.stop_far:
            n = 1
        level = (list(self.regions) if first else
                 [d["nu"] for d in inits] if inits else list(self.rng.normal(1900, 50, C)))   # cold: anywhere near
        for c, v in self.jump.get(len(self.calls), {}).items():
            level[c] = v
        first_lp = self.lp_first.get(len(self.calls), {})
        self.calls.append(dict(engine=st["engine"], chains=C, draws=n, inits=inits, adapted=adapted, seed=seed))
        if first and self.stop_far:
            info = json.load(open(os.path.join(seg, "seg.json")))
            json.dump(dict(info, stop=1, draws=1, far=self.stop_far, far_at="end of warm-up"),
                      open(os.path.join(seg, "seg.json"), "w"))
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
                    lp = first_lp[c] if i == 0 and c in first_lp else level[c] + self.rng.normal(0, 30)
                    f.write(f"{lp},0.9,0.1,5,31,{dv},0,{t},{-t},{level[c]}\n")

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


def run(L, regions, div=None, **kw):
    """_run of module L on a scenario, in a temporary store: (posterior in memory, stub, store manifest)."""
    stub = Stub(L, regions, div, **kw)
    store = L.RunStore(tempfile.mkdtemp(prefix="lqm-stub-"))
    far = getattr(L, "FAR", {})                                      # 52be157 has none
    saved = dict(far)
    stub.said = []
    try:
        if "least" in far:
            far["least"] = LEAST
        post = L._run(store, {}, "cost", dict(ST), 7, stub.said.append)
        return post.in_memory(), stub, json.loads(json.dumps(store.manifest))
    finally:
        far.clear()
        far.update(saved)
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


def nutpie_store(lp, div=None, warm=None):
    """A finished nutpie store (zarr) with the given log-densities (chains, draws), and of warm-up (chains, iterations)."""
    import numpy as np, zarr
    d = tempfile.mkdtemp(prefix="lqm-zarr-")
    C, n = lp.shape
    g = zarr.open_group(d, mode="w")
    p, s = g.create_group("posterior"), g.create_group("sample_stats")
    p.create_array("nu", shape=(C, n), chunks=(1, n), dtype="f8")[:] = lp
    for k, v in (("logp", lp), ("n_steps", np.full((C, n), 31.0)), ("step_size", np.full((C, n), 0.1)),
                 ("diverging", np.zeros((C, n), bool) if div is None else div)):
        s.create_array(k, shape=(C, n), chunks=(1, n), dtype=v.dtype)[:] = v
    if warm is not None:
        g.create_group("warmup_sample_stats").create_array("logp", shape=warm.shape, chunks=(1, warm.shape[1]),
                                                           dtype="f8")[:] = warm
    return d


class Finished:
    is_finished = True

    def wait(self):
        pass

    def abort(self):
        pass


def levels(regions, n, seed=3):
    """Log-densities (chains, n) around each chain's level."""
    import numpy as np
    return np.array(regions, float)[:, None] + np.random.default_rng(seed).normal(0, 30, (len(regions), n))


def grow(L, lp, warm=None, wu=10, every=None, far=None):
    """_grow of module L (the code now) on a finished store, the diagnostics stubbed: (its result, what it reported).
    wu = the warm-up's length; every, far = changes to FAR."""
    stub = Stub(L, GOOD)
    saved = dict(L.FAR)
    said = []
    d = nutpie_store(lp, warm=warm)
    try:
        L.FAR.update(dict(far or {}, least=LEAST, **({"every": every} if every else {})))
        return L._grow(Finished(), d, wu, 60, 180, 30, said.append), said
    finally:
        L.FAR.clear()
        L.FAR.update(saved)
        stub.restore()
        shutil.rmtree(d, ignore_errors=True)


def grow_slices(lp, warm=None):
    """_grow as of SLICES (66c6fbf) on the same store: the draws it kept."""
    B = lqm_before(SLICES)
    if B is None:
        raise AssertionError("SKIP negative control: git cannot show the code of " + SLICES)
    stub = Stub(B, GOOD)
    d = nutpie_store(lp, warm=warm)
    try:
        return B._grow(Finished(), d, 60, 180, 30)
    finally:
        stub.restore()
        shutil.rmtree(d, ignore_errors=True)


FAR5 = [1890, 1900, -4600, 1910, 1895, 1905]                        # chain 2 as chain 5 of 30 Oct (seed 13)


@test
def grow_runs_on_without_a_far_chain():
    """nutpie in process (_grow): with R̂ 1.08 and no far chain, in warm-up or after, the run is not stopped at the
    planned 60 draws but runs on to the check where the criteria hold (120), as with the code of 66c6fbf (no far chain:
    nothing changes), and with checks every 40 iterations too. Negative control: _grow before the rule (52be157) stops
    the slow-mixing run at 60."""
    need("numpy", "zarr")
    import numpy as np
    L = lqm_now()
    slow, warm = levels(GOOD, 180), levels(GOOD, 10, seed=4)
    eq(grow(L, slow, warm)[0], (120, [], None), "no far chain: runs on to the criteria")
    eq(grow_slices(slow, warm), 120, "the code of 66c6fbf: the same")
    eq(grow(L, slow, warm, every=40)[0], (120, [], None), "no far chain, checks every 40 iterations: the same")
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


@test
def grow_far_at_the_end_of_warmup():
    """A chain far through warm-up (chain 2 at −4,600 against +1,900, as chain 5 of 30 Oct): the run stops at the end
    of warm-up, at its first draw, judged on the last FAR["warmup"] warm-up iterations, for _run to restart the chain
    then. Negative control: the code of 66c6fbf, which does not look at warm-up, runs on to the planned 60 draws."""
    need("numpy", "zarr")
    L = lqm_now()
    lp, warm = levels(FAR5, 180), levels(FAR5, 10, seed=4)
    (stop, far, at), _ = grow(L, lp, warm)
    eq((stop, far, at), (1, [2], "end of warm-up (its last 100 iterations)"), "stopped at the first draw")
    eq(grow_slices(lp, warm), 60, "negative control: the code of 66c6fbf waits for the planned draws")


@test
def grow_far_within_warmup_reported_then_restarted():
    """Checks every 40 iterations over a warm-up of 100 (iterations 40 and 80), judged on the last 30: a chain far at
    iteration 40 is reported there and does not stop the run (no clean restart before the adaptation ends); still far
    at the end of warm-up, it stops the run then. A chain far at iteration 40 that has come back by the end of warm-up
    does not stop it."""
    need("numpy", "zarr")
    L = lqm_now()
    (stop, far, _), said = grow(L, levels(FAR5, 180), levels(FAR5, 100, seed=4), wu=100, every=40,
                                far=dict(warmup=30))
    eq((stop, far), (1, [2]), "restarted at the end of warm-up")
    eq([m.split(":")[0] for m in said], ["chain(s) [2] in a far region at warm-up iteration 40",
                                        "chain(s) [2] in a far region at warm-up iteration 80"], "reported at 40 and 80")
    back = levels(GOOD, 100, seed=4)
    back[2, :45] = -4600
    (stop, far, _), said = grow(L, levels(GOOD, 180), back, wu=100, every=40, far=dict(warmup=30))
    eq((stop, far, len(said)), (120, [], 1), "back by the end of warm-up: reported at 40, not restarted")


@test
def grow_far_every_400_iterations():
    """A chain that leaves for a far region after warm-up (chain 3 from draw 12 on): checked every 40 iterations
    (warm-up 10: draws 30, 70, …, between the slices 60, 90, …), the run stops at draw 30, before the first slice.
    Negative control: the code of 66c6fbf stops at the planned 60 draws."""
    need("numpy", "zarr")
    L = lqm_now()
    lp, warm = levels(GOOD, 180), levels(GOOD, 10, seed=4)
    lp[3, 12:] -= 7000
    (stop, far, at), _ = grow(L, lp, warm, every=40)
    eq((stop, far, at), (30, [3], "draw 30 (iteration 40)"), "stopped at the first check every 40 iterations")
    eq(grow(L, lp, warm, every=400)[0][:2], (60, [3]), "every 400 iterations: the first slice is the first check")
    eq(grow_slices(lp, warm), 60, "negative control: the code of 66c6fbf, at the slice")


@test
def checks_of_a_production_run():
    """The checks of a production run (warm-up 500, every 250 iterations, slices of 900 from 1,800): warm-up
    iteration 250, the end of warm-up, draws 250, 500, 750, …, 1,750, the slice at 1,800, 2,000, 2,250, 2,500, 2,700 (slice)…"""
    L = lqm_now()
    st = L.SAMPLER["cost"]
    eq((st["warmup"], L.SAMPLER["quality"]["warmup"], L.FAR["every"]), (500, 500, 250), "warm-up 500, every 250")
    c = L._checks(st["warmup"], st["samples"], st["samples"] + st["extend_max"], st["extend"])
    eq(c[:14], [(-250, "warm-up"), (1, "end of warm-up"), (250, "far"), (500, "far"), (750, "far"), (1000, "far"),
                 (1250, "far"), (1500, "far"), (1750, "far"), (1800, "slice"), (2000, "far"), (2250, "far"), (2500, "far"),
                 (2700, "slice")], "the first checks")
    eq(c[-1], (18000, "slice"), "the last")
    eq([d for d in (250, 300, 500, 1800, 2000) if L._is_mark(500, d)], [250, 500, 2000], "CmdStan's checks: the same grid")


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
    sum-to-zero vector re-centred, not θ alone (zd, and in lqm_ext2.stan zf_tau, zf_psi, zf_omega: Stan refuses a
    sum above 1e-8; the makers' zd is a sum-to-zero parameter of lqm_ext2.stan and lqm_ext3.stan alike).
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
    post = L.Posterior({"zd": [z], "theta": [th]}, {})
    for M, want in ((L, True), (B, False)):
        d0 = M._last_draws(post)[0]
        eq((abs(sum(d0["theta"])) < 1e-12, abs(sum(d0["zd"])) < 1e-12), (True, want),
           "re-centred" if want else "negative control: the code before leaves zd off zero")


@test
def far_at_the_end_of_warmup_restarted_then():
    """_run on a nutpie run that stopped at its first draw on a far chain (as _grow does at the end of warm-up): the
    chain's draw dropped, it restarts on CmdStan from good chain 0's draw with chain 0's adapted state, and the six
    chains then draw the planned 60 together (no check of the criteria on a single draw), then continue by slices to
    the criteria. Negative control: without the stop, the same far chain is restarted at the planned 60 draws only."""
    need("numpy")
    L = lqm_now()
    post, stub, man = run(L, FAR5, stop_far=[2])
    eq([(c["engine"], c["chains"], c["draws"]) for c in stub.calls],
       [("nutpie", 6, 1), ("cmdstan", 1, 1), ("cmdstan", 5, 59), ("cmdstan", 1, 59), ("cmdstan", 5, 30),
        ("cmdstan", 1, 30), ("cmdstan", 5, 30), ("cmdstan", 1, 30)], "restarted at the first draw, then all six")
    r = stub.calls[1]
    eq((round(r["inits"][0]["nu"]), r["adapted"]["step_size"]), (1890, [0.1]), "from chain 0, with its state")
    eq((man["parts"][0]["dropped"], man["parts"][1]["far"], man["parts"][1]["at"], "far_seen" in man["parts"][0]),
       ([dict(chains=[2], draws=1)], [2], "end of warm-up", False), "dropped at the first draw")
    eq((post.shape("theta")[:2], post.stats["far_restarted"], post.stats["far_at"]), ((6, SLOW), 1, "end of warm-up"),
       "120 draws, one chain restarted at the end of warm-up")
    post0, stub0, man0 = run(L, FAR5)
    eq((man0["parts"][0]["dropped"], man0["parts"][1]["at"]), ([dict(chains=[2], draws=60)], "draw 60"),
       "negative control: no stop at the end of warm-up, the far chain seen at the planned draws")


@test
def no_far_chain_nothing_changes():
    """With the six chains in one region the run is drawn exactly as by the code of 66c6fbf: the same segments, the
    same draws (the checks every 250 iterations find nothing and cut nothing)."""
    need("numpy")
    import numpy as np
    L = lqm_now()
    B = lqm_before(SLICES)
    if B is None:
        raise AssertionError("SKIP: git cannot show the code of " + SLICES)
    post, stub, man = run(L, GOOD)
    post0, stub0, man0 = run(B, GOOD)
    eq([(c["engine"], c["chains"], c["draws"]) for c in stub.calls],
       [(c["engine"], c["chains"], c["draws"]) for c in stub0.calls], "the same segments")
    eq(np.allclose(post.chains("theta"), post0.chains("theta")), True, "the same draws")
    eq((len(man["parts"]), post.stats["far_restarted"], post.stats["extensions"]), (1, 0, 2), "one part, two slices")


@test
def far_on_a_cmdstan_continuation_every_400():
    """A chain that leaves for a far region while the chains continue on CmdStan (chain 3 in the first continuation,
    from draw 60): with checks every 40 iterations (warm-up 10: draws 70, 110, …; judged here on the last 20 draws) the
    continuation is cut at draw 70, where the far chain is found and restarted from a good chain's last draw. Negative
    control: the code of 66c6fbf draws the whole slice, to 90, before it sees the chain."""
    need("numpy")
    L = lqm_now()
    B = lqm_before(SLICES)
    out = []
    for M in (L, B):
        if M is None:
            raise AssertionError("SKIP negative control: git cannot show the code of " + SLICES)
        saved = dict(M.FAR)
        try:
            M.FAR.update(draws=20, **({"every": 40} if "every" in M.FAR else {}))
            post, stub, man = run(M, GOOD, jump={1: {3: -5100}})
        finally:
            M.FAR.clear()
            M.FAR.update(saved)
        out.append((man, stub))
    man, stub = out[0]
    eq([(c["engine"], c["chains"], c["draws"]) for c in stub.calls][:4],
       [("nutpie", 6, 60), ("cmdstan", 6, 10), ("cmdstan", 1, 70), ("cmdstan", 5, 20)], "cut at 70, restarted there")
    eq((man["parts"][0]["dropped"], man["parts"][1]["at"]), ([dict(chains=[3], draws=70)], "draw 70"), "at draw 70")
    eq(out[1][0]["parts"][0]["dropped"], [dict(chains=[3], draws=90)], "negative control: seen at the slice, 90")


@test
def seed_drawn_per_fit_kept_by_its_run():
    """Each fit draws its own seed (lqm._new_seed), records it in its run's manifest and in post.stats; a fit of the same
    sampling key — a run resumed after a stop, or summarised again — keeps the stored run's seed, whatever seed is
    given or drawn; a changed key (other settings) draws a new one. The seed is not part of the sampling key, nor of
    fit.py's axis fingerprint. Negative control: the key of 66c6fbf changes with the seed (a stored run would be thrown
    away by a new seed)."""
    need("numpy")
    L = lqm_now()
    saved = dict(RUNS=L.RUNS, stan_data=L.stan_data, _new_seed=L._new_seed, _save_inits=L._save_inits)
    runs = tempfile.mkdtemp(prefix="lqm-runs-")
    seeds = iter([111, 222, 333])
    stub = Stub(L, GOOD)
    try:
        L.RUNS, L.stan_data, L._new_seed = runs, lambda groups, axis: ({}, {}), lambda: next(seeds)
        said = []
        post, _ = L.fit({}, "cost", settings=dict(ST), keep=True, save_inits=False, log=said.append)
        eq((post.stats["seed"], stub.calls[0]["seed"], said[0]), (111, 111, "cost: seed 111 (new run)"), "drawn")
        path = os.path.join(runs, os.listdir(runs)[0])
        man = json.load(open(os.path.join(path, "manifest.json")))
        eq(man["seed"], 111, "in the run's manifest")
        man["parts"][0]["planned"] = man["parts"][0]["draws"] + 30          # a run stopped before its last slice
        json.dump(man, open(os.path.join(path, "manifest.json"), "w"))
        n = len(stub.calls)
        post, _ = L.fit({}, "cost", seed=999, settings=dict(ST), keep=True, save_inits=False, log=said.append)
        eq((post.stats["seed"], "cost: seed 111 (the stored run's)" in said), (111, True),
           "resumed with the stored run's seed")
        eq([c["seed"] for c in stub.calls[n:]], [111 + 1_000_000 + len(man["parts"][0]["seeds"])],
           "its continuation's seed derived from it")
        post, _ = L.fit({}, "cost", settings=dict(ST, extend=31), keep=True, save_inits=False)
        eq(post.stats["seed"], 222, "another key: a new seed")
        eq(L.sampling_key({}, "cost", dict(ST)) == L.sampling_key({}, "cost", dict(ST)), True, "no seed in the key")
    finally:
        stub.restore()
        for k, v in saved.items():
            setattr(L, k, v)
        shutil.rmtree(runs, ignore_errors=True)
    import ast

    def fingerprint_names(src):                                      # the names fit.py's axis_fingerprint uses
        fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "axis_fingerprint")
        return {x.id for x in ast.walk(fn) if isinstance(x, ast.Name)} | {x.arg for x in ast.walk(fn)
                                                                          if isinstance(x, ast.keyword)}
    eq({"seed", "SEED"} & fingerprint_names(open(os.path.join(MODEL, "fit.py")).read()), set(),
       "fit.py: no seed in the axis fingerprint")
    try:
        old = subprocess.run(["git", "-C", ROOT, "show", f"{SLICES}:model/fit.py"], capture_output=True, text=True,
                             check=True).stdout
        eq({"seed", "SEED"} & fingerprint_names(old), {"seed", "SEED"}, "negative control: fit.py of 66c6fbf has it")
    except (OSError, subprocess.CalledProcessError):
        pass
    B = lqm_before(SLICES)
    if B is None:
        raise AssertionError("SKIP negative control: git cannot show the code of " + SLICES)
    eq(B.sampling_key({}, "cost", dict(ST), 1) == B.sampling_key({}, "cost", dict(ST), 2), False,
       "negative control: the key of 66c6fbf changes with the seed")



# The last 100 warm-up iterations written in every chain (236–335) of the run of 30 Oct 12:19–12:28 (cost, seed 13,
# .stan/runs/cost-09c6f7df29d60555), log-density rounded to the unit; chain 5 (index 4) far
WARMUP_30_OCT = [
    [2066, 2054, 2094, 2030, 2096, 1983, 2003, 1982, 1903, 1836, 1861, 1815, 1827, 1731, 1689, 1694, 1788, 1784, 1886,
     1857, 1762, 1835, 1901, 1967, 1920, 1939, 1887, 1875, 1854, 1995, 2005, 2067, 2261, 2153, 2188, 2088, 2046, 2091,
     1929, 2006, 2146, 2173, 2117, 2013, 2045, 1990, 1920, 1937, 1936, 1814, 1784, 1865, 1853, 1869, 1818, 1868, 1819,
     1799, 1787, 1687, 1743, 1782, 1779, 1857, 1801, 1799, 1791, 1737, 1865, 1783, 1784, 1800, 1796, 1807, 1833, 1908,
     1810, 1893, 1858, 1840, 1829, 1865, 1928, 1960, 1859, 1897, 1886, 1995, 1906, 1968, 1834, 1928, 1829, 1765, 1857,
     1866, 1801, 1789, 1689, 1741],
    [2002, 1975, 1992, 2007, 1968, 2089, 2150, 2028, 1992, 1979, 1919, 2072, 2106, 2177, 2196, 2224, 2230, 2208, 2152,
     2174, 2125, 2107, 2110, 2135, 2149, 2140, 2045, 1967, 1946, 1922, 2077, 2018, 1860, 1900, 1911, 1933, 1990, 2009,
     2004, 2080, 2010, 2066, 2035, 2007, 2000, 2039, 2020, 2101, 2072, 1960, 1975, 1951, 2068, 2024, 2019, 1987, 2009,
     2027, 1976, 1821, 1839, 1948, 1930, 1932, 2075, 2160, 2094, 2014, 1969, 1987, 2079, 2119, 2027, 1975, 1893, 1885,
     1941, 1992, 1976, 1981, 2089, 2001, 2049, 2074, 1962, 1840, 1872, 1832, 1879, 1934, 1926, 1880, 1954, 1891, 1922,
     1949, 1943, 1935, 1928, 1835],
    [1944, 1977, 1887, 1979, 1960, 2101, 2047, 1947, 2027, 1950, 1911, 1888, 1814, 1973, 1970, 1954, 1901, 1908, 1970,
     2055, 1906, 1895, 1861, 1802, 1696, 1699, 1835, 1763, 1662, 1732, 1807, 1778, 1883, 1852, 1828, 1863, 1957, 1942,
     1875, 2014, 2103, 2162, 2124, 2050, 2026, 2108, 1951, 2087, 2096, 2040, 2083, 2078, 1967, 1973, 1930, 1894, 1854,
     1917, 1987, 1955, 2019, 2063, 2029, 2053, 2085, 2168, 2096, 1981, 2009, 1941, 1936, 1941, 2078, 2093, 2146, 2089,
     1888, 1933, 1868, 1932, 1908, 1783, 1851, 1968, 1937, 1951, 1971, 1992, 1990, 1920, 1776, 1801, 1673, 1722, 1777,
     1904, 1911, 1936, 1782, 1845],
    [1806, 1723, 1747, 1820, 1804, 1813, 1731, 1731, 1806, 1715, 1776, 1765, 1835, 1858, 1875, 1757, 1731, 1738, 1840,
     1874, 1824, 1883, 1963, 2058, 2115, 2043, 2029, 2105, 2045, 2089, 2008, 1980, 1996, 2015, 2066, 2086, 2053, 1965,
     1954, 1915, 1847, 1850, 1928, 1826, 1750, 1805, 1859, 1812, 1815, 1762, 1874, 1892, 1823, 1823, 1865, 1808, 1925,
     1835, 1675, 1666, 1608, 1664, 1832, 1888, 1855, 1831, 1878, 1799, 1789, 1862, 1861, 1973, 2036, 1921, 1883, 1872,
     1783, 1778, 1937, 1889, 1985, 1834, 1891, 1918, 1823, 1898, 1782, 1831, 1730, 1846, 1828, 1875, 1877, 1790, 1638,
     1639, 1747, 1805, 1795, 1915],
    [-4550, -4593, -4578, -4637, -4613, -4613, -4613, -4598, -4544, -4551, -4547, -4621, -4698, -4707, -4689, -4654,
     -4637, -4639, -4611, -4639, -4563, -4588, -4632, -4695, -4688, -4679, -4594, -4639, -4692, -4717, -4644, -4702,
     -4585, -4649, -4645, -4679, -4599, -4577, -4542, -4563, -4608, -4642, -4574, -4501, -4495, -4467, -4538, -4527,
     -4544, -4590, -4469, -4496, -4568, -4568, -4511, -4599, -4611, -4644, -4649, -4597, -4593, -4678, -4629, -4626,
     -4612, -4616, -4595, -4573, -4524, -4559, -4681, -4667, -4665, -4539, -4575, -4581, -4545, -4571, -4615, -4629,
     -4606, -4544, -4458, -4486, -4430, -4382, -4421, -4552, -4549, -4487, -4339, -4402, -4379, -4415, -4399, -4471,
     -4544, -4685, -4663, -4599],
    [2038, 2032, 1995, 1885, 1913, 1897, 1982, 2002, 2040, 2087, 2047, 2002, 1891, 1847, 1917, 1955, 1900, 1769, 1726,
     1738, 1770, 1808, 1923, 1854, 1814, 1844, 1866, 1849, 1727, 1717, 1767, 1841, 1823, 1865, 1843, 1816, 1786, 1760,
     1813, 1874, 1722, 1708, 1777, 1740, 1798, 1882, 1813, 1820, 1756, 1705, 1741, 1684, 1740, 1690, 1739, 1751, 1785,
     1798, 1781, 1899, 1805, 1858, 1830, 1870, 1919, 1847, 1886, 1968, 2039, 1972, 1924, 1853, 1923, 1990, 1992, 1900,
     1882, 1864, 1806, 1794, 1810, 1854, 1754, 1722, 1792, 1825, 1856, 1804, 1821, 1908, 1850, 1820, 1876, 1718, 1819,
     1726, 1735, 1730, 1751, 1818],
]


TODAY = os.path.join(ROOT, ".stan", "runs", "cost-09c6f7df29d60555", "seg", "store")


@test
def far_criterion_on_the_warmup_of_30_oct():
    """The warm-up of 30 Oct 12:19–12:28 (cost, seed 13, nutpie, warm-up 600 stopped at ~350): chain 5 (index 4) at
    −4,600 against +1,800–2,000 from iteration ~150 on. far_chains on the last 100 warm-up iterations flags chain 5 and no
    other — on iterations 236–335 (in this file) and, where the store is kept, at every iteration from 67 to the last
    written; on the archived store of 29 Oct seed 12 (warm-up 600), chains 4 and 5 from iteration 80 on. Negative
    control: in the first iterations (64) good chains are flagged too: the warm-up's first check, at 400, is past them."""
    need("numpy")
    import numpy as np
    L = lqm_now()
    eq(L.far_chains(np.asarray(WARMUP_30_OCT, float)), [4], "iterations 236–335")
    for root, want, first, n0 in ((TODAY, [4], 67, 336), (os.path.join(ROOT, ARCHIVE), [3, 4], 80, 600)):
        if not os.path.isdir(root):
            continue
        need("zarr")
        import zarr
        g = zarr.open_group(root, mode="r")
        n = L._nutpie_warmup_written(g, root)
        lp = np.asarray(g["warmup_sample_stats"]["logp"][:, :n])
        eq(n, n0 if root == TODAY else 600, "warm-up iterations written")
        eq({tuple(L.far_chains(lp[:, max(0, i - 100):i])) for i in range(first, n + 1)}, {tuple(want)}, root)
        if root == TODAY:
            eq(L.far_chains(lp[:, :64]) != [4], True, "negative control: the first iterations flag good chains too")


# The fit of 30 Oct 2026 14:57–15:10 (.stan/fit-prod.log, store .stan/runs/cost-8c4130a43f050029): chain 4 far at
# warm-up iteration 250 and at the end of warm-up, restarted from chain 0's last draw; each chain's one draw after the
# restart (chains 0–3 and 5 of the first run, then the restarted chain: lp__ at chain 0's point), as stored.
LP_14_57 = [2068.84218755, 1984.97788353, 2050.87489373, 1930.66183226, 1714.1020961, 2068.8422]
REGIONS_14_57 = [1900, 1905, 1895, 1910, -4600, 1898]


@test
def restart_then_continued_not_judged_on_one_draw():
    """The sequence of 30 Oct 14:57: chain 4 far at the end of warm-up, the run stopped at its first draw, chain 4
    restarted on CmdStan from chain 0's last draw; the six chains' one draw each are those of the real store, on which
    the far criterion flags good chain 5 (index 4 once chain 4 is dropped: 1,714 against the others' 2,051). No verdict
    on fewer than FAR["least"] draws of each chain's own: the five good chains (nutpie's adapted state) and the
    restarted one go on together on CmdStan from their last draws to the planned 60, then by slices to the criteria,
    and the run says why it ended. Negative control: the code of 7482996 judges the one draw, finds chain 4 far, and
    stops the run at one draw per chain."""
    need("numpy")
    import numpy as np
    L = lqm_now()
    lp = np.asarray(LP_14_57)[:, None]
    eq((L.far_chains(lp), L._far(lp)), ([4], []), "the stored draw: far by the criterion, no verdict on one draw")
    eq(L._far(np.repeat(lp, 99, axis=1)), [], "nor on 99 draws (FAR['least'] 100)")
    eq(L._far(np.repeat(lp, 100, axis=1)), [4], "a verdict from 100 draws on")
    first = {**dict(enumerate(LP_14_57[:4])), 4: -4600.0, 5: LP_14_57[4]}       # the first run's draw, chain 4 far
    kw = dict(stop_far=[4], lp_first={0: first, 1: {0: LP_14_57[5]}})
    post, stub, man = run(L, REGIONS_14_57, **kw)
    eq(np.allclose(post.lp()[:, 0], LP_14_57), True, "the six first draws as in the store of 14:57")
    eq([(c["engine"], c["chains"], c["draws"], c["adapted"] is not None) for c in stub.calls],
       [("nutpie", 6, 1, False), ("cmdstan", 1, 1, True), ("cmdstan", 5, 59, True), ("cmdstan", 1, 59, True),
        ("cmdstan", 5, 30, True), ("cmdstan", 1, 30, True), ("cmdstan", 5, 30, True), ("cmdstan", 1, 30, True)],
       "restarted at the first draw, then all six on CmdStan to 60, then by slices of 30")
    eq(stub.calls[2]["adapted"]["step_size"], [0.1, 0.11, 0.12, 0.13, 0.15], "the good chains with their own state")
    eq([round(d["nu"]) for d in stub.calls[2]["inits"]], [1900, 1905, 1895, 1910, 1898], "from their last draws")
    eq(([p["draws"] for p in man["parts"]], man["parts"][1]["far"], man["parts"][1]["source"]), ([SLOW, SLOW], [4], [0]),
       "120 draws per chain, chain 4 restarted from chain 0")
    eq((post.stats["far_restarted"], post.stats["stopped"]), (1, "criteria met"), "converged, and says so")
    eq(any("not restarted" in m for m in stub.said), False, "no far verdict after the restart")
    B = lqm_before(ONE_DRAW)
    if B is None:
        raise AssertionError("SKIP negative control: git cannot show the code of " + ONE_DRAW)
    post0, stub0, man0 = run(B, REGIONS_14_57, **kw)
    eq(([p["draws"] for p in man0["parts"]], len(stub0.calls)), ([1, 1], 2),
       "negative control: the code of 7482996 stops the run at one draw per chain")
    eq([m.split(": ", 1)[1] for m in stub0.said if "not restarted" in m],
       ["chain(s) [4] in a far region, not restarted (a far chain was restarted already)"],
       "negative control: on good chain 5, as in the log of 14:57")


@test
def far_again_after_a_restart_stops_with_its_reason():
    """After a restart a chain far again at a check (good chain 1 leaves for −9,000 in the parts' first continuation)
    stops the run, unconverged (once per run), and the run records why: post.stats["stopped"]."""
    need("numpy")
    L = lqm_now()
    post, stub, man = run(L, FAR5, stop_far=[2], jump={2: {1: -9000}})
    eq([p["draws"] for p in man["parts"]], [60, 60], "stopped at the planned 60")
    eq(post.stats["stopped"], "chain(s) [1] in a far region at draw 60, not restarted (a far chain was restarted "
       "already)", "the reason")


@test
def diagnostics_of_a_run_stopped_at_one_draw():
    """The real diagnostics (ArviZ) on six chains of one draw each: R̂ undefined (None), ESS 0, not converged — no
    crash; the same with every draw alike. Negative control: the code of 7482996 raises 'cannot convert float NaN to
    integer', as the fit of 14:57 did."""
    need("numpy", "arviz")
    import numpy as np
    L = lqm_now()
    rng = np.random.default_rng(5)
    mk = lambda M, x: M.Posterior({"level": [x], "theta": [rng.normal(size=(1, 6, 4))],
                                   "lp__": [np.asarray(LP_14_57)[None, :]]},
                                  dict(divergences=0, max_treedepth_hits=None, leapfrog_mean=1023.0))
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for x in (rng.normal(size=(1, 6, 3)), np.ones((1, 6, 3))):
            diag, mcse = L.diagnostics(mk(L, x))
            eq((diag["rhat_max"], diag["ess_bulk_min"], diag["ess_tail_min"], diag["rhat_max_level"],
                diag["ess_bulk_min_level"], L.converged(diag)), (None, 0, 0, None, 0, False), "undefined, unconverged")
            eq((len(mcse), json.loads(json.dumps(diag))["draws"]), (3, 6), "one MCSE per level; JSON-safe")
        B = lqm_before(ONE_DRAW)
        if B is None:
            raise AssertionError("SKIP negative control: git cannot show the code of " + ONE_DRAW)
        try:
            B.diagnostics(mk(B, rng.normal(size=(1, 6, 3))))
            raise AssertionError("negative control: the code of 7482996 did not crash")
        except ValueError as e:
            eq(str(e), "cannot convert float NaN to integer", "negative control")


if __name__ == "__main__":
    fails = skips = 0
    for t in TESTS:
        try:
            t()
            print(f"ok    {t.__name__}")
        except AssertionError as e:
            skip = str(e).startswith("SKIP")
            skips, fails = skips + skip, fails + (not skip)
            print(f"{'skip' if skip else 'FAIL'}  {t.__name__}: {e}")
    print(f"\n{len(TESTS) - fails - skips} passed, {fails} failed, {skips} skipped")
    sys.exit(1 if fails else 0)
