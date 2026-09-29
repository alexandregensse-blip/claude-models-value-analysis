"""Two fits of the same axis: Kendall τ between their values, median and largest move (published couples).
Usage: python3 compare.py reference.pkl variant.pkl"""
import itertools, math, pickle, sys
A, B = (pickle.load(open(p, "rb")) for p in sys.argv[1:3])
cs = [c for c in A["S"] if c in B["S"] and A["S"][c]["published"] and B["S"][c]["published"]]
a = {c: math.log(A["S"][c]["value"]) for c in cs}; b = {c: math.log(B["S"][c]["value"]) for c in cs}
p = [(a[x] - a[y]) * (b[x] - b[y]) for x, y in itertools.combinations(cs, 2)]
tau = sum(1 if v > 0 else -1 if v < 0 else 0 for v in p) / len(p)
d = sorted((abs(a[c] - b[c]), c) for c in cs)
print(f"{A['F']['axis']}: τ = {tau:.3f} · median move {100 * d[len(d) // 2][0]:.1f} % · largest {100 * d[-1][0]:.1f} % ({d[-1][1]}: "
      f"{A['S'][d[-1][1]]['value']:.3f} → {B['S'][d[-1][1]]['value']:.3f})")
