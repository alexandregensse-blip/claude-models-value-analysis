# Validation

Scripts that reproduce the checks reported in `METHODOLOGY.md`. Run them from the repository root with the Stan
environment (`.stan/venv/bin/python`, see the README); each run stays under 20 minutes on two cores.

| Script | Check | Command |
|---|---|---|
| `heldout.py` | Held-out prediction: one fifth of the percentage scores removed, refitted, predicted, five times; compared with the score-ratio baseline; coverage of the 16–84 % predictive interval. | `.stan/venv/bin/python gen/validation/heldout.py` |
| `synthetic.py` | Known truth: synthetic scores on the real design under proportional, logistic and mixed benchmarks; distortion of the recovered scale, pairs in the wrong order, coverage of the posterior and quasi-standard-error intervals. | `.stan/venv/bin/python gen/validation/synthetic.py` |
| `fit.py` | Fits one axis and saves its summary, optionally without one publisher. | `.stan/venv/bin/python gen/validation/fit.py cost 11 c.pkl - anthropic` |
| `compare.py` | Two fits of one axis: Kendall τ, median and largest move (sensitivity, Monte Carlo error). | `python3 gen/validation/compare.py c_all.pkl c_drop.pkl` |
| `ratio_baseline.py` | The score-ratio consolidation, kept only as the baseline of `heldout.py` and `synthetic.py`. | — |

`synthetic_truth.json` holds the known latent qualities the synthetic data are drawn from.
