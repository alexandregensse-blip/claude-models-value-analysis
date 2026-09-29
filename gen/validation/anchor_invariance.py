"""The anchor is a display choice. Fit with two different anchors; re-express the second fit relative to the first
anchor; the values must agree within Monte Carlo error.

Usage: python3 anchor_invariance.py fit_anchor1.pkl fit_anchor2.pkl"""
import math, pickle, sys
A, B = (pickle.load(open(p, "rb")) for p in sys.argv[1:3])
a1 = A["F"]["anchor"]
ref = B["S"][a1]["value"]
d = sorted((abs(math.log(B["S"][c]["value"] / ref / A["S"][c]["value"])), c) for c in A["S"] if A["S"][c]["published"])
print(f"{A['F']['axis']}: anchor {a1} vs {B['F']['anchor']} → median gap {100 * d[len(d) // 2][0]:.2f} %, "
      f"max {100 * d[-1][0]:.2f} % ({d[-1][1]})")
