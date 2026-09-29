"""Fit one axis and save the reference-free summary, for compare.py.

Usage: .stan/venv/bin/python gen/validation/fit.py quality|cost SEED OUT.pkl [DATA.csv] [DROP_PUBLISHER]
DROP_PUBLISHER removes every row of one publisher before the fit (sensitivity)."""
import csv, os, pickle, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, ".."))
import build as B, lqm
axis, seed, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
data = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else os.path.join(B.ROOT, "raw-data.csv")
if len(sys.argv) > 5:                                              # sensitivity: without one publisher
    rows = list(csv.DictReader(open(data)))
    tmp = os.path.join(tempfile.mkdtemp(), "raw-data.csv")
    with open(tmp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader()
        w.writerows(r for r in rows if lqm.PUBLISHER_OF.get(r["source"], r["source"]) != sys.argv[5])
    data = tmp
groups, report, republished = lqm.load(data, list(B.MX), field="cost_usd" if axis == "cost" else "score")
t = time.time()
post, maps = lqm.fit(groups, axis, seed=seed, save_inits=False)
S, diag = lqm.summarise(post, maps, groups, lqm.stan_data(groups, axis)[0], seed=seed)
pickle.dump(dict(axis=axis, S=S, diag=diag, report=dict(report)), open(out, "wb"))
print(f"{axis}: {time.time() - t:.0f}s, R-hat max {diag['rhat_max']}, converged {lqm.converged(diag)}")
