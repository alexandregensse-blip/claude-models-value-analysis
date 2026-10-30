# model — estimation

**Scope:** from the measurements to one relative quality and one relative cost per (model, effort) couple, with its
uncertainty. A change of method touches only this part (and `docs/METHODOLOGY.md`, §3–§5).

| File | Role |
|---|---|
| `lqm.py` | data preparation (groups, scales, composites, republications, effects), the samplers, the read-out |
| `lqm_ext2.stan` | the model, in Stan (since v2026.10.21; `LQM_MODEL` selects another) |
| `lqm.stan` | the model until v2026.10.20, without the makers' scales and home effects |
| `lqm_ext.stan` | an experiment of 19–20 Oct (makers' offsets not summing to zero; it did not converge) |
| `precheck.py` | the checks run before a fit (bounds, twin metrics, discordant twins, memory) |
| `peek.py` | a provisional R̂ from the draws on disk while a fit runs |
| `fit.py` | fits both axes and writes `fit-cache.json`; `--dry` builds its inputs and prints them, without sampling |
| `fit-cache.json` | **the model's only product**, read by the site |
| `validation/` | the checks reported in docs/METHODOLOGY.md (see its README) |
| `requirements-fit.txt` | the pinned fitting environment (the root README, "Refit", installs it in `.stan/`) |

## Input

The build's products (`python3 data/build.py --fit-models catalog`, see `data/BUILD.md`): `data/build/fit-quality.csv`
for the quality axis and `data/build/fit-cost.csv` for the cost axis, the rows `in` on that axis in the columns of the
former `raw-data.csv`. `lqm.load` reads each through `data/build_lqm.py`'s `load_table`, which resolves the catalogue's
group-keyed maps (`COMPOSITES`, `FAMILY_OF`) for the build's fit groups through `group-map.json` (fit group → base
group) and `group-setups.json` (fit group → setup, with its family and composite components) — the code the build's
own lqm step uses. `precheck.py` checks the rows of `data/build/data.csv` in the fit and loads the tables the same way;
`validation/` reads the tables. On the build of 29 Oct (migrated data): quality 1,608 groups, 17,705 rows, 334 couples;
cost 923 groups, 8,403 rows, 271 couples (`fit.py --dry`). `raw-data.csv` is no longer read by the model.

## Run

```bash
.stan/venv/bin/python model/fit.py --dry     # inputs, fingerprint, groups and rows per axis; no checks, no sampling
.stan/venv/bin/python model/fit.py
```

Both axes: nutpie, 6 chains × (500 + 1,800) (warm-up 500 since 30 Oct 2026), continued in the sampling process by
slices of 900 draws up to 16,200 more until the criteria hold. Each fit draws its own seed (printed, kept in the run's
manifest in `.stan/runs` and per axis in `fit-cache.json`); a run resumed after a stop keeps its seed, and the seed is
not part of an axis' data fingerprint (30 Oct 2026; a fixed seed before). The model is compiled with `stanc --O1`
and `STAN_NO_RANGE_CHECKS`.

A run stopped part-way resumes from its stored draws, each chain continued on CmdStan from its last draw with its
adapted step size and metric. A chain left in a far region (its median log-density more than max(300, 5 × the others'
spread) below the other chains', `lqm.FAR`) loses its draws and restarts alone on CmdStan from a good chain's last
draw with that chain's adapted state; the good chains are kept (rule of 30 Oct 2026, which replaced the restart of the
whole axis on CmdStan from the previous fit's draws). The chains are looked at whatever R̂ — every 250 iterations
(warm-up iteration 400, draws 300, 700, …), at the end of warm-up (its last 100 iterations) and at every slice
(`lqm._checks`; 30 Oct 2026, before only at a slice and when R̂ > 1.05); a chain far within warm-up is reported and
restarted at the end of warm-up if still far there (no clean restart before nutpie's adaptation ends). Without a far
chain an R̂ above 1.05 continues the chains. An axis whose prepared data and model code are unchanged since the cached, converged fit is
kept as it is (`--all` refits both).

## The contract with the site: `fit-cache.json`

- `inputs` — the files the fit depends on (the two fit tables and the two group maps of `data/build/`, the catalogue,
  `data/build_lqm.py`, `lqm.py`, the Stan model in use, `fit.py`), and `fingerprint`
  — SHA-256 over their paths and contents, in order. The site recomputes it and refuses a stale cache.
- `quality`, `cost` — per couple `[centre, half, publishers, [new_lo, new_hi], mcse]`, on the log scale and
  reference-free: `centre` is the posterior median of the read-out, `half` its quasi-standard error (16–84 %),
  `[new_lo, new_hi]` what one new source would report, `mcse` the Monte Carlo error of the centre.
- `seed` — per axis, the seed its fit drew (also in the axis' `diagnostics`; one number for both axes before 30 Oct
  2026).
- `diagnostics` — per axis: R̂, bulk and tail ESS, divergences, sampler statistics, what was set aside, and
  `converged` (R̂ ≤ 1.01, ESS ≥ 400, no divergence); the site refuses a fit that did not converge.
