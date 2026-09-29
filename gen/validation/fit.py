"""Fit one axis and save the posterior summary, for the other scripts of this folder.

Usage: python3 fit.py quality|cost REFERENCE_COUPLE SEED OUT.pkl [DATA.csv] [CHAINS] [SWEEPS] [BURN]
Example: python3 fit.py quality opus-5@high 11 q.pkl"""
import os, pickle, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, ".."))
import build as B, lqm
axis, ref, seed, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
data = sys.argv[5] if len(sys.argv) > 5 else os.path.join(B.ROOT, "raw-data.csv")
chains, sweeps, burn = (int(x) for x in (sys.argv[6:9] + ["4", "6000", "2000"][len(sys.argv[6:9]):]))
groups, report, republished = lqm.load(data, list(B.MX), field="cost_usd" if axis == "cost" else "score")
t = time.time()
F = lqm.fit_chains(groups, ref, axis=axis, chains=chains, sweeps=sweeps, burn=burn, seed=seed)
S = lqm.summarise(F)
pickle.dump(dict(S=S, report=dict(report), republished=republished, F=F), open(out, "wb"))
print(f"{axis}: {time.time() - t:.0f}s, R-hat max {max(v['rhat'] for v in S.values() if v['rhat'] == v['rhat']):.3f}")
