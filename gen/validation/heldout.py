"""Held-out prediction. Scores in % from groups of ≥ 4 couples are split in five folds; each fold is removed, the
model refitted without it, and the removed scores predicted (posterior mean of the predicted score, with the
publisher, publisher × model and task-type effects when the fit knows them). Baseline: the ratio method — a couple's
consolidated score ratio to the anchor (weighted median over benchmarks) times the group's mean ratio level.

Usage: python3 heldout.py DATA.csv GEN_DIR   (GEN_DIR = the folder holding build.py and lqm.py)"""
import collections, csv, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, sys.argv[2])
import build as B, lqm, ratio_baseline as RB
DATA = sys.argv[1]; MODELS = list(B.MX)
rows = list(csv.DictReader(open(DATA))); hdr = list(rows[0].keys())
data = [r for r in rows if r["group"] and not r["group"].startswith("#") and r["model"] in B.MX and r["effort"] in lqm.EFFORTS
        and RB.num(r["score"]) is not None]
cells = collections.defaultdict(list)
for r in data: cells[(r["group"], f'{r["model"]}@{r["effort"]}')].append(r)
per_group = collections.Counter(g for g, _ in cells)
keys = sorted(k for k in cells if per_group[k[0]] >= 4 and cells[k][0]["score_metric"].endswith("%"))
random.Random(5).shuffle(keys)
err = collections.defaultdict(list)
for f in range(5):
    hold = set(keys[f::5]); keep = lambda r: (r["group"], f'{r["model"]}@{r["effort"]}') not in hold
    tmp = os.path.join(HERE, "heldout_tmp"); os.makedirs(tmp, exist_ok=True); path = os.path.join(tmp, "raw-data.csv")
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=hdr); w.writeheader()
        for r in rows:
            if not (r["group"] and not r["group"].startswith("#")) or keep(r): w.writerow(r)
    QG = RB.ratio_grid("score", path, MODELS, "opus-5@high")
    Q = {f"{m}@{e}": v[0] for m, es in QG.items() for e, v in es.items()}
    level = collections.defaultdict(list)
    for (g, c), rs in cells.items():
        if (g, c) not in hold and c in Q:
            s = sum(RB.num(x["score"]) for x in rs) / len(rs)
            if s > 0: level[g].append(math.log(s) - math.log(Q[c]))
    G, _, _ = lqm.load(path, MODELS)
    F = lqm.fit(G, "opus-5@high", sweeps=1200, burn=400, seed=f)
    idx = {e: {k: i for i, k in enumerate(F["levels"][e])} for e in lqm.EFFECTS}; bi = {g: i for i, g in enumerate(F["names"])}
    for (g, c) in hold:
        obs = sum(RB.num(x["score"]) for x in cells[(g, c)]) / len(cells[(g, c)])
        if not (c in Q and level[g] and g in G and c in F["ci"]): continue
        base = math.exp(sum(level[g]) / len(level[g])) * Q[c]
        b = bi[g]; GG = G[g]; x0 = cells[(g, c)][0]; pub = lqm.PUBLISHER_OF.get(x0["source"], x0["source"])
        ks = {"pub_couple": (pub, c), "pub_model": (pub, x0["model"]), "couple_task": (c, x0["task_type"])}
        preds = []
        for d in F["draws"][::2]:
            x = d["th"][F["ci"][c]] + sum(d["ef"][e][idx[e][k]] for e, k in ks.items() if k in idx[e])
            q = lqm._score(GG, d["o"][b], d["a"][b], x)
            n = GG["n_steps"]; p = (q * (n + 1) - 0.5) / n
            preds.append(100 * min(max(p, 0.0), 1.0))
        err["ratio method"].append(abs(base - obs)); err["fused model"].append(abs(sum(preds) / len(preds) - obs))
    print("fold", f, flush=True)
q = lambda xs, p: sorted(xs)[int(p * (len(xs) - 1))]
for k, e in err.items():
    print(f"{k:13s} n={len(e)} median {q(e, .5):.2f} pt · mean {sum(e) / len(e):.2f} pt · 90th percentile {q(e, .9):.2f} pt")
