"""Known truth. Synthetic scores are drawn on the real design (same groups, couples, publishers) from known latent
qualities (synthetic_truth.json), under three kinds of benchmark: proportional to quality (score ratios exact by
construction), logistic (binomial scores on 50–500 tasks), and a mix of logistic, Elo, power and saturating shapes.
The model is refitted and its θ compared with the truth after the best affine map (θ is identified up to its unit):
  distortion = RMS error / spread of the truth · wrong pairs = share of couple pairs put in the wrong order ·
  coverage   = share of pairs whose true difference lies in the 16–84 % posterior interval of θ_i − θ_j (target 68 %) ·
  qv coverage = same with the quasi-standard errors ±√(q_i + q_j) the page draws (target 68 %).
The score-ratio consolidation is scored the same way (distortion, wrong pairs).

Usage: .stan/venv/bin/python model/validation/synthetic.py [WARMUP] [SAMPLES]"""
import csv, itertools, json, math, os, random, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, ".."))
import lqm, ratio_baseline as RB
from catalog import MODEL_ORDER
WARM, SAMP = (int(x) for x in (sys.argv[1:3] + ["1000", "1000"][len(sys.argv[1:3]):]))
L = json.load(open(os.path.join(HERE, "synthetic_truth.json")))["truth"]
rows = list(csv.DictReader(open(os.path.join(lqm.ROOT, "raw-data.csv")))); hdr = list(rows[0].keys())
data = [r for r in rows if r["group"] and not r["group"].startswith("#") and r["model"] in MODEL_ORDER
        and r["effort"] in lqm.EFFORTS and RB.num(r["score"]) is not None]
sig = lambda x: 1 / (1 + math.exp(-x))


def make(scn, seed):
    rng = random.Random(seed); U = {}; out = []; link = {}
    for g in sorted({r["group"] for r in data}):
        k = {"ratio": 1.0, "irt": 0.0}.get(scn, rng.random())
        if scn == "ratio":  link[g] = ("ratio", rng.uniform(20, 60))
        elif k < .5:        link[g] = ("irt", math.exp(rng.gauss(math.log(4), .5)), rng.uniform(-3, 3.5), rng.randint(50, 500))
        elif k < .65:       link[g] = ("elo", rng.uniform(1200, 1600), rng.uniform(200, 800))
        elif k < .85:       link[g] = ("pow", rng.uniform(10, 50), math.exp(rng.gauss(0, .6)))
        else:               link[g] = ("sat", rng.uniform(.5, 3))
    for r in data:
        c = f'{r["model"]}@{r["effort"]}'; s = lqm.PUBLISHER_OF.get(r["source"], r["source"])
        if c not in L: continue
        if (s, c) not in U: U[(s, c)] = rng.gauss(0, .03)
        x = L[c] + U[(s, c)]; lk = link[r["group"]]
        if lk[0] == "ratio":  v = lk[1] * math.exp(x) * math.exp(rng.gauss(0, .02)); met = "score%"
        elif lk[0] == "irt":
            p = sig(lk[1] * x + lk[2]); n = lk[3]; v = 100 * sum(rng.random() < p for _ in range(n)) / n; met = "score%"
        elif lk[0] == "elo":  v = lk[1] + lk[2] * x + rng.gauss(0, 10); met = "elo"
        elif lk[0] == "pow":  v = min(100, lk[1] * math.exp(lk[2] * x) * math.exp(rng.gauss(0, .03))); met = "score%"
        else:                 v = min(max(100 * (1 - math.exp(-lk[1] * math.exp(x))) + rng.gauss(0, 1), 0), 100); met = "score%"
        rr = dict(r); rr["score"] = f"{v:.4f}"; rr["score_metric"] = met; out.append(rr)
    d = os.path.join(HERE, "synthetic_tmp", f"{scn}_{seed}"); os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "raw-data.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=hdr); w.writeheader(); [w.writerow(r) for r in out]
    return os.path.join(d, "raw-data.csv")


def affine(cs, est):
    x = np.array([L[c] for c in cs]); y = np.array([est[c] for c in cs])
    lam, alpha = np.polyfit(x, y, 1)
    return x, y, lam, alpha


def scores(cs, est):
    x, y, lam, alpha = affine(cs, est)
    dist = np.sqrt(np.mean((y - alpha - lam * x) ** 2)) / abs(lam) / np.std(x)
    pairs = [(i, j) for i, j in itertools.combinations(range(len(cs)), 2) if abs(x[i] - x[j]) > .02]
    wrong = sum((x[i] - x[j]) * (y[i] - y[j]) < 0 for i, j in pairs) / len(pairs)
    return dist, wrong, lam


for scn in ("ratio", "irt", "mix"):
    path = make(scn, 1)
    QG = RB.ratio_grid("score", path, list(MODEL_ORDER), "opus-5@high")
    base = {f"{m}@{e}": math.log(v[0]) for m, es in QG.items() for e, v in es.items() if f"{m}@{e}" in L}
    bd, bw, _ = scores(sorted(base), base)
    G, _, _ = lqm.load(path, list(MODEL_ORDER))
    mcmc, maps = lqm.fit(G, "quality", seed=1, save_inits=False, settings=dict(
        engine="cmdstan", chains=4, warmup=WARM, warmup_cold=WARM, samples=SAMP, adapt_delta=0.9, max_treedepth=10))
    T = mcmc.var("theta")
    cs = [c for c in maps["couples"] if c in L]; idx = [maps["ci"][c] for c in cs]; T = T[:, idx]
    est = {c: float(np.median(T[:, k])) for k, c in enumerate(cs)}
    d, w, lam = scores(cs, est)
    qv, _, _ = lqm.quasi_variances(T)
    cov = qcov = n = 0
    for i, j in itertools.combinations(range(len(cs)), 2):
        true = lam * (L[cs[i]] - L[cs[j]]); D = T[:, i] - T[:, j]
        lo, hi = np.quantile(D, [0.16, 0.84]); cov += lo <= true <= hi
        qcov += abs(np.median(D) - true) <= math.sqrt(qv[i] + qv[j]); n += 1
    diag, _ = lqm.diagnostics(mcmc)
    print(f"{scn:6s} fused: distortion {d:.3f} · wrong pairs {100 * w:.1f} % · coverage {100 * cov / n:.0f} % · "
          f"qv coverage {100 * qcov / n:.0f} % · R̂ max {diag['rhat_max']} · divergences {diag['divergences']}"
          f"  |  ratio: distortion {bd:.3f} · wrong pairs {100 * bw:.1f} %", flush=True)
