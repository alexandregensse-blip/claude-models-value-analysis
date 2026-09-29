"""Two fits of the same axis (fit.py): Kendall τ between their centres, median and largest move, published couples.
Usage: python3 model/validation/compare.py reference.pkl|model/fit-cache.json variant.pkl"""
import itertools, math, pickle, sys
def read(p, axis=None):
    """A fit.py pickle, or the production cache (model/fit-cache.json) read for the axis of the other file."""
    if p.endswith(".json"):
        import json
        d = json.load(open(p))
        return dict(axis=axis, S={c: dict(centre=v[0], published=v[2] >= 2) for c, v in d[axis].items()})
    return pickle.load(open(p, "rb"))


paths = sys.argv[1:3]
B = read(paths[1]) if not paths[1].endswith(".json") else None
A = read(paths[0], axis=B["axis"] if B else None)
B = B or read(paths[1], axis=A["axis"])
cs = [c for c in A["S"] if c in B["S"] and A["S"][c]["published"] and B["S"][c]["published"]]
# centres are on the log scale with an origin set by each fit's couples: compare them after removing the mean shift
a = {c: A["S"][c]["centre"] for c in cs}; b = {c: B["S"][c]["centre"] for c in cs}
shift = sorted(b[c] - a[c] for c in cs)[len(cs) // 2]
p = [(a[x] - a[y]) * (b[x] - b[y]) for x, y in itertools.combinations(cs, 2)]
tau = sum(1 if v > 0 else -1 if v < 0 else 0 for v in p) / len(p)
d = sorted((abs(b[c] - shift - a[c]), c) for c in cs)
print(f"{A['axis']}: τ = {tau:.3f} · median move {100 * d[len(d) // 2][0]:.1f} % · largest {100 * d[-1][0]:.1f} % ({d[-1][1]})")
