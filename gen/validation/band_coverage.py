"""Does the band cover what benchmarks actually report? For every group that measured the anchor, the observed
ratio couple ÷ anchor (scores on the quality axis, costs on the cost axis) is compared with the couple's band.
In-sample, so optimistic; the target is the band's nominal 68 %.

Usage: python3 band_coverage.py fit.pkl"""
import collections, math, pickle, sys
R = pickle.load(open(sys.argv[1], "rb"))
F, S = R["F"], R["S"]
A = F["anchor"]
hits, far = collections.Counter(), collections.Counter()
for g in F["names"]:
    rows = F["groups"][g]["rows"]
    ref = [x["raw"] for x in rows if x["couple"] == A]
    if not ref or min(ref) <= 0:
        continue
    ref = sum(ref) / len(ref)
    for x in rows:
        c = x["couple"]
        if c == A or x["raw"] <= 0 or not S[c]["published"]:
            continue
        ratio = x["raw"] / ref
        lo, hi = S[c]["band"]
        inside = lo <= ratio <= hi
        hits["all"] += inside; hits["n"] += 1
        if abs(math.log(S[c]["value"])) > 0.2:                          # couples well away from the anchor
            far["in"] += inside; far["n"] += 1
print(f"{F['axis']}: {hits['all']}/{hits['n']} = {100 * hits['all'] / hits['n']:.0f} % inside the band"
      + (f" · away from the anchor: {far['in']}/{far['n']} = {100 * far['in'] / max(far['n'], 1):.0f} %" if far["n"] else ""))
