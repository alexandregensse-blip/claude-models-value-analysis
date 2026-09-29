# Validation

Scripts that reproduce the checks reported in `METHODOLOGY.md`. Pure standard library; run from this folder.

| Script | Check | Command |
|---|---|---|
| `fit.py` | Fits one axis and saves the posterior summary used by the scripts below. | `python3 fit.py quality opus-5@high 11 q.pkl` |
| `heldout.py` | Held-out prediction: one fifth of the percentage scores removed, refitted, predicted, five times; compared with the score-ratio baseline. | `python3 heldout.py ../../raw-data.csv ..` |
| `synthetic.py` | Known truth: synthetic scores on the real design under proportional, logistic and mixed benchmarks; distortion of the recovered scale. | `python3 synthetic.py` |
| `sbc.py` | Simulation-based calibration of the sampler, with deliberately wrong fits as negative controls. | `python3 sbc.py quality ok 40 9000` · `python3 sbc.py quality tight-prior 30 9500` · `python3 sbc.py cost ok 40 9000` |
| `band_coverage.py` | Share of the ratios observed in the data (couple ÷ reference, same group) inside the band. | `python3 band_coverage.py q.pkl` |
| `anchor_invariance.py` | Fit with another couple fixed at 0, divide back, compare. | `python3 fit.py quality opus-5.5@high 12 q2.pkl && python3 anchor_invariance.py q.pkl q2.pkl` |
| `compare.py` | Two fits of one axis: Kendall τ, median and largest move (sensitivity, Monte Carlo error). | `python3 compare.py q.pkl other.pkl` |
| `ratio_baseline.py` | The score-ratio consolidation, kept only as the baseline of `heldout.py` and `synthetic.py`. | — |

`sbc.py` reads `SBC_SWEEPS` from the environment (default 1200; the reported runs used 2400).
