"""Fit one axis and save the reference-free summary, for compare.py.

Usage: .stan/venv/bin/python model/validation/fit.py quality|cost SEED OUT.pkl [DATA.csv] [DROP_PUBLISHER]
DATA.csv: the axis' fit table of the build (data/build/fit-quality.csv or fit-cost.csv) unless given ('-' = default).
DROP_PUBLISHER removes every row of one publisher before the fit (sensitivity)."""
import csv, os, pickle, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [os.path.join(HERE, ".."), os.path.join(HERE, "..", "..", "data")]
import lqm, build_lqm
from catalog import MODEL_ORDER
axis, seed, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
data = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else build_lqm.table(axis)   # the axis' fit table
if len(sys.argv) > 5:                                              # sensitivity: without one publisher
    rows = list(csv.DictReader(open(data)))
    tmp = os.path.join(tempfile.mkdtemp(), os.path.basename(build_lqm.table(axis)))
    with open(tmp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader()
        w.writerows(r for r in rows if lqm.PUBLISHER_OF.get(r["source"], r["source"]) != sys.argv[5])
    data = tmp
groups, report, republished = build_lqm.load_table(lqm, axis, list(MODEL_ORDER), path=data)   # group maps: data/build
t = time.time()
post, maps = lqm.fit(groups, axis, seed=seed, save_inits=False)
S, diag = lqm.summarise(post, maps, groups, lqm.stan_data(groups, axis)[0], seed=seed)
pickle.dump(dict(axis=axis, S=S, diag=diag, report=dict(report)), open(out, "wb"))
print(f"{axis}: {time.time() - t:.0f}s, R-hat max {diag['rhat_max']}, converged {lqm.converged(diag)}")
