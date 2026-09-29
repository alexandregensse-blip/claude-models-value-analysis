"""Simulation-based calibration of lqm.fit (Talts et al. 2018).

Parameters are drawn from the model's priors (hyper-parameters held at known values, θ ~ N(0, V) with the fit's
prior set to the same V), data are simulated on a small design that has every structural feature of the real one
(two-couple groups, publishers measuring several effort levels of one model, task types including
'mixed', Student-t noise), the model is fitted, and the rank of each true θ among its posterior draws is recorded.
Uniform ranks = a correct sampler. Offsets are drawn from a wide normal and every group's noise is 1 on the quality
axis: the posterior of θ does not depend on either (flat prior on o, affine invariance with a Jeffreys prior on σ).

Usage: python3 sbc.py quality|cost [ok|tight-prior|no-model-effect] replications seed_offset
"""
import math, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import lqm

axis, mode, R, OFF = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
H = dict(sd2=0.4 ** 2, sa2=0.3 ** 2, tau2=0.4 ** 2, psi2=0.4 ** 2, om2=0.5 ** 2, m_sig=math.log(0.3), s2_sig=0.3 ** 2)
V = 4.0
MODELS = {"m0": ["low", "high", "max"], "m1": ["low", "high", "max"], "m2": ["solo"]}
COUPLES = [f"{m}@{e}" for m, es in MODELS.items() for e in es]
TASKS = ("coding", "reasoning-math", "agentic-tool", "mixed")


def simulate(rng, n_groups=60, n_pub=4):
    th = {c: 0.0 if c == "m0@high" else rng.gauss(0, V ** 0.5) for c in COUPLES}
    u, w, v, groups = {}, {}, {}, {}
    for b in range(n_groups):
        g = f"g{b}"
        k = rng.randint(2, 6)
        cs = rng.sample(COUPLES, k)
        s, t = f"s{rng.randrange(n_pub)}", rng.choice(TASKS)
        if axis == "quality":
            sig = 1.0
            mean, var_ = 0.0, H["sd2"]                                   # log a = log d (σ = 1)
        else:
            sig = math.exp(rng.gauss(H["m_sig"], H["s2_sig"] ** 0.5))
            mean, var_ = 0.0, H["sa2"]
        la = rng.gauss(mean, var_ ** 0.5)
        a, o, rows = math.exp(la), rng.gauss(0, 3), []
        for c in cs:
            m = c.split("@")[0]
            x = th[c] + u.setdefault((s, c), rng.gauss(0, H["tau2"] ** 0.5)) + w.setdefault((s, m), rng.gauss(0, H["psi2"] ** 0.5))
            if t != "mixed":
                x += v.setdefault((c, t), rng.gauss(0, H["om2"] ** 0.5))
            e = sig * rng.gauss(0, 1) / math.sqrt(rng.gammavariate(2.0, 0.5))
            rows.append(dict(couple=c, model=m, publisher=s, task=t, z=o + a * x + e, m=1.0, raw=0.0, metric="x", kind="identity"))
        groups[g] = dict(rows=rows, mu=0.0, sd=1.0, kind="identity", metric="x", family=None,
                         n_steps=None, floor=1e-4)
    return groups, th


lqm.THETA_VAR = 0.25 if mode == "tight-prior" else V
fixed = dict(H)
if mode == "no-model-effect":
    fixed["psi2"] = 1e-6                                                  # the fit ignores the publisher × model effect
ranks = []
for rep in range(R):
    rng = random.Random(OFF + rep)
    G, th = simulate(rng)
    F = lqm.fit(G, "m0@high", axis=axis, sweeps=int(os.environ.get("SBC_SWEEPS", 1200)), burn=int(os.environ.get("SBC_SWEEPS", 1200)) // 4, thin=max(1, int(os.environ.get("SBC_SWEEPS", 1200)) // 120), seed=rep, fixed=fixed)
    for c, i in F["ci"].items():
        if c != "m0@high":
            ranks.append(sum(1 for d in F["draws"] if d["th"][i] < th[c]) / len(F["draws"]))
bins = [0] * 10
for x in ranks:
    bins[min(9, int(x * 10))] += 1
n = len(ranks)
chi2 = sum((b - n / 10) ** 2 / (n / 10) for b in bins)
print(f"{axis} {mode}: n={n} ranks {bins} chi2={chi2:.1f} (5 % critical value 16.9) → {'REJECTED' if chi2 > 16.9 else 'uniform'}")
