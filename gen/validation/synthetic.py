import csv, os, random, math, collections, sys, pickle, itertools
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import build as B, lqm, ratio_baseline as RB
PUBLISHER = lqm.PUBLISHER_OF; EFFOK = lqm.EFFORTS
SP = os.path.dirname(os.path.abspath(__file__))
import json
CACHE = json.load(open(os.path.join(SP, "..", "fit-cache.json")))   # truth = the published quality grid
L = {f"{m}@{e}": math.log(v[0]) for m, es in CACHE["quality"].items() for e, v in es.items()}            # true log-quality = current LQM estimate
rows = [r for r in csv.DictReader(open(os.path.join(B.ROOT, "raw-data.csv")))]; hdr = list(rows[0].keys())
data = [r for r in rows if r["group"] and not r["group"].startswith("#") and r["model"] in B.MX
        and r["effort"] in EFFOK and RB.num(r["score"]) is not None]
sig = lambda x: 1 / (1 + math.exp(-x))

def make(scn, seed):
    rng = random.Random(seed); U = {}; out = []
    link = {}
    for g in sorted({r["group"] for r in data}):
        if scn == "ratio":
            link[g] = ("ratio", rng.uniform(20, 60))
        elif scn == "irt":
            link[g] = ("irt", math.exp(rng.gauss(math.log(4), .5)), rng.uniform(-3, 3.5), rng.randint(50, 500))
        else:
            k = rng.random()
            if k < .5:   link[g] = ("irt", math.exp(rng.gauss(math.log(4), .5)), rng.uniform(-3, 3.5), rng.randint(50, 500))
            elif k < .65: link[g] = ("elo", rng.uniform(1200, 1600), rng.uniform(200, 800))
            elif k < .85: link[g] = ("pow", rng.uniform(10, 50), math.exp(rng.gauss(0, .6)))
            else:        link[g] = ("sat", rng.uniform(.5, 3))
    for r in data:
        c = f'{r["model"]}@{r["effort"]}'; s = PUBLISHER.get(r["source"], r["source"])
        if c not in L: continue
        if (s, c) not in U: U[(s, c)] = rng.gauss(0, .03)
        x = L[c] + U[(s, c)]; lk = link[r["group"]]
        if lk[0] == "ratio":   v = lk[1] * math.exp(x) * math.exp(rng.gauss(0, .02)); met = "score%"
        elif lk[0] == "irt":
            p = sig(lk[1] * x + lk[2]); n = lk[3]; v = 100 * sum(rng.random() < p for _ in range(n)) / n; met = "score%"
        elif lk[0] == "elo":   v = lk[1] + lk[2] * x + rng.gauss(0, 10); met = "elo"
        elif lk[0] == "pow":   v = min(100, lk[1] * math.exp(lk[2] * x) * math.exp(rng.gauss(0, .03))); met = "score%"
        else:                  v = 100 * (1 - math.exp(-lk[1] * math.exp(x))) + rng.gauss(0, 1); v = min(max(v, 0), 100); met = "score%"
        rr = dict(r); rr["score"] = f"{v:.4f}"; rr["score_metric"] = met; out.append(rr)
    d = os.path.join(SP, "synthetic_tmp", f"{scn}_{seed}"); os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "raw-data.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=hdr); w.writeheader(); [w.writerow(r) for r in out]
    return d

def metrics(est):
    cs = [c for c in est if c in L]
    x = [L[c] for c in cs]; y = [est[c] for c in cs]
    lam = sum(a * b for a, b in zip(x, y)) / sum(a * a for a in x)     # scale-only fit (anchor fixed at 0)
    rm = (sum((b - lam * a) ** 2 for a, b in zip(x, y)) / len(x)) ** .5 / abs(lam)
    sx = (sum(a * a for a in x) / len(x)) ** .5
    pe = [(i, j) for i, j in itertools.combinations(range(len(cs)), 2) if abs(x[i] - x[j]) > .02]
    wrong = sum(1 for i, j in pe if (x[i] - x[j]) * (y[i] - y[j]) < 0)
    lad = collections.defaultdict(list)
    for c in cs: lad[c.split("@")[0]].append(c)
    ORD = ["low", "medium", "high", "xhigh", "max"]
    inv_ = sum(1 for m, l in lad.items() for a, b in itertools.combinations(sorted(l, key=lambda c: ORD.index(c.split("@")[1]) if "@solo" not in c else 0), 2)
               if (L[b] - L[a]) * (est[b] - est[a]) < 0)
    return dict(lam=lam, dist=rm / sx, wrong=wrong / len(pe), inv=inv_, n=len(cs))

R = collections.defaultdict(list)
for scn in ("ratio", "irt", "mix"):
    for seed in (1,):
        d = make(scn, seed)
        QG = RB.ratio_grid("score", os.path.join(d, "raw-data.csv"), list(B.MX), "opus-5@high")
        R[(scn, "actuel")].append(metrics({f"{m}@{e}": math.log(v[0]) for m, es in QG.items() for e, v in es.items()}))
        G, _, _ = lqm.load(os.path.join(d, "raw-data.csv"), list(B.MX))
        F = lqm.fit(G, "opus-5@high", sweeps=1200, burn=400, seed=seed); S = lqm.summarise(F, every=3)
        R[(scn, "fused")].append(metrics({c: math.log(v["value"]) for c, v in S.items()}))
        print(scn, seed, "done", flush=True)
pickle.dump(dict(R), open(os.path.join(SP, "synthetic.pkl"), "wb"))
for (scn, m), v in R.items():
    f = lambda k: sum(x[k] for x in v) / len(v)
    print(f"{scn:8s} {m:12s} dist {f('dist'):.3f} paires {100*f('wrong'):.1f}% inversions {f('inv'):.1f}")
