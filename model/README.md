# model — estimation

**Scope:** from the measurements to one relative quality and one relative cost per (model, effort) couple, with its
uncertainty. A change of method touches only this part (and `docs/METHODOLOGY.md`, §3–§5).

| File | Role |
|---|---|
| `lqm.py` | data preparation (groups, scales, composites, republications, effects), the samplers, the read-out |
| `lqm.stan` | the model, in Stan |
| `fit.py` | fits both axes and writes `fit-cache.json` |
| `fit-cache.json` | **the model's only product**, read by the site |
| `validation/` | the checks reported in docs/METHODOLOGY.md (see its README) |
| `requirements-fit.txt` | the pinned fitting environment (the root README, "Refit", installs it in `.stan/`) |

## Run

```bash
.stan/venv/bin/python model/fit.py
```

Quality: nutpie, 4 chains × (1,000 + 20,000). Cost: CmdStan, 4 chains × (500 + 4,500), started from the last draws of
the previous fit (`.stan/inits-cost.json`; 1,000 warm-up iterations without it). The model is compiled with
`stanc --O1` and `STAN_NO_RANGE_CHECKS`.

Each axis is checked against the validity criteria as soon as it is sampled, within a budget of 10 minutes per axis:
a chain left in another region (R̂ > 1.05) restarts the axis on CmdStan from the previous fit's last draws; too few
effective draws continue the same chains (last state, adapted step size and metric, no new warm-up) until the
criteria hold or the budget is spent. An axis whose prepared data and model code are unchanged since the cached,
converged fit is kept as it is (`--all` refits both).

## The contract with the site: `fit-cache.json`

- `inputs` — the files the fit depends on (data file, catalogue, `lqm.py`, `lqm.stan`, `fit.py`), and `fingerprint`
  — SHA-256 over their paths and contents, in order. The site recomputes it and refuses a stale cache.
- `quality`, `cost` — per couple `[centre, half, publishers, [new_lo, new_hi], mcse]`, on the log scale and
  reference-free: `centre` is the posterior median of the read-out, `half` its quasi-standard error (16–84 %),
  `[new_lo, new_hi]` what one new source would report, `mcse` the Monte Carlo error of the centre.
- `diagnostics` — per axis: R̂, bulk and tail ESS, divergences, sampler statistics, what was set aside, and
  `converged` (R̂ ≤ 1.01, ESS ≥ 400, no divergence); the site refuses a fit that did not converge.
