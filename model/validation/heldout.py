"""Held-out prediction. Percentage scores of groups with ≥ 4 couples are split in five folds; each fold is removed from
the data file, the model refitted without it, and the removed scores predicted: the posterior mean of the expected
score (known publisher, publisher × model and task-type effects used, unknown ones drawn from their law) and the
16–84 % posterior predictive interval (noise included), whose coverage should be near 68 %. Baseline: the score-ratio
consolidation (ratio_baseline.py) times the group's mean ratio level.

Usage: .stan/venv/bin/python model/validation/heldout.py [WARMUP] [SAMPLES]"""
import collections, csv, math, os, random, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, ".."))
import lqm, ratio_baseline as RB
from catalog import MODEL_ORDER
WARM, SAMP = (int(x) for x in (sys.argv[1:3] + ["1000", "1000"][len(sys.argv[1:3]):]))
DATA = os.path.join(lqm.ROOT, "raw-data.csv"); MODELS = list(MODEL_ORDER)
rows = list(csv.DictReader(open(DATA))); hdr = list(rows[0].keys())
G0, _, _ = lqm.load(DATA, MODELS)
eligible = {g for g, G in G0.items() if "~" not in g and not any(h.startswith(g + "~") for h in G0)
            and G["kind"] == "logit" and len({x["couple"] for x in G["rows"]}) >= 4}
data = [r for r in rows if r["group"] in eligible and r["model"] in MODEL_ORDER and r["effort"] in lqm.EFFORTS
        and RB.num(r["score"]) is not None and r["score_metric"].endswith("%")]
cells = collections.defaultdict(list)
for r in data: cells[(r["group"], f'{r["model"]}@{r["effort"]}')].append(r)
keys = sorted(cells); random.Random(5).shuffle(keys)
err, cover = collections.defaultdict(list), []
for f in range(5):
    hold = set(keys[f::5])
    tmp = os.path.join(HERE, "heldout_tmp"); os.makedirs(tmp, exist_ok=True); path = os.path.join(tmp, "raw-data.csv")
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=hdr); w.writeheader()
        for r in rows:
            if (r["group"], f'{r["model"]}@{r["effort"]}') not in hold: w.writerow(r)
    QG = RB.ratio_grid("score", path, MODELS, "opus-5@high")
    Q = {f"{m}@{e}": v[0] for m, es in QG.items() for e, v in es.items()}
    level = collections.defaultdict(list)
    for (g, c), rs in cells.items():
        if (g, c) not in hold and c in Q:
            s = sum(RB.num(x["score"]) for x in rs) / len(rs)
            if s > 0: level[g].append(math.log(s) - math.log(Q[c]))
    G, _, _ = lqm.load(path, MODELS)
    # the production sampler: nutpie, restarted on CmdStan from the production fit's last draws if a chain is stuck
    mcmc, maps = lqm.fit(G, "quality", seed=f, save_inits=False, settings=dict(warmup=WARM, samples=SAMP))
    todo = [(g, c) for (g, c) in sorted(hold) if g in G and c in maps["ci"] and c in Q and level[g]]
    preds = lqm.predict(mcmc, maps, G, [dict(group=g, couple=c, publisher=lqm.PUBLISHER_OF.get(cells[(g, c)][0]["source"],
                        cells[(g, c)][0]["source"]), task=cells[(g, c)][0]["task_type"]) for g, c in todo], thin=2, seed=f)
    for (g, c), (mean_f, pred_f) in zip(todo, preds):
        obs = sum(RB.num(x["score"]) for x in cells[(g, c)]) / len(cells[(g, c)])
        n = G[g]["n_steps"]; bnd = lqm.bound(cells[(g, c)][0]["score_metric"])
        to_pct = lambda y: 100 * np.clip(((1 / (1 + np.exp(-y))) * (n + 1) - 0.5) / n, 0, 1)
        err["ratio method"].append(abs(math.exp(sum(level[g]) / len(level[g])) * Q[c] - obs))
        err["fused model"].append(abs(float(np.mean(to_pct(mean_f))) - obs))
        # predictive interval: noise shape h at the predicted proportion (the observation is not used)
        q = 1 / (1 + np.exp(-mean_f)); h = 0.5 / np.sqrt(q * (1 - q))
        y = mean_f + (pred_f - mean_f) * h
        lo, hi = np.quantile(to_pct(y), [0.16, 0.84]); cover.append(lo <= 100 * obs / bnd <= hi)
    print("fold", f, flush=True)
q = lambda xs, p: sorted(xs)[int(p * (len(xs) - 1))]
for k, e in err.items():
    print(f"{k:13s} n={len(e)} median {q(e, .5):.2f} pt · mean {sum(e) / len(e):.2f} pt · 90th percentile {q(e, .9):.2f} pt")
print(f"16–84 % predictive interval covers {100 * sum(cover) / len(cover):.0f} % of {len(cover)} held-out scores (target 68 %)")
