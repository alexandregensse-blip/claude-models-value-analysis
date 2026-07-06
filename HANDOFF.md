# HANDOFF — what's left to do

Status: data curated + verified, generator working, interactive report built (`cost-matrix.html`).
Every `@default` in the effort-assignment view has been resolved or set aside. Next passes, in priority order.

## 1. Fix the normalized matrix separability (highest priority)

`normalized.csv` still encodes the cross-model factor as a **constant across efforts** — e.g. Sonnet 4.6 = `0.60 × Opus 4.8` at *every* effort, so its per-effort ratios don't vary. This is the exact separability we decided to abandon.

- Rebuild the §2 matrix from the **per-effort measured medians** (the same data the report's "consolidated squares" already compute in `gen/build.py::consolidated`), not from a `crossmodel_factor × effort_factor` product.
- Each cell must be treated **couple-atomically**: `(model, effort)` is one indivisible node, placed by measured same-task ratio paths — never by multiplying a global model factor by a global effort factor.
- After the fix, verify: the Opus 4.8 / Sonnet 4.6 ratio should differ across low/medium/high/max (measured shows ≈0.9 low–high, ≈2.5 max on computer-use, ≈1.7 agentic), not sit at a flat 1.667.

## 2. Audit couple-atomic treatment end-to-end

Make sure no code path re-introduces model×effort separability:
- `normalized.csv` factor tables (the `crossmodel ÷Opus4.8` × `effort ÷medium` lines) — replace with per-couple values.
- §1 landscape curves in `gen/app.js`: `OFF5 / OFF4 / OFF3` apply **one shared effort-shape to all models** (calibrated on OSWorld). That is a separability assumption on the *quality* axis — flag it, and differentiate per model where data allows.
- Confirm the linking graph and ratio charts stay couple-atomic (they already are).

## 3. Corroborate the weakly-supported graph nodes

The linking graph (§3) rings each node by independent-source count: green ≥3, yellow 2, orange 1, red 0. Go find **more independent same-task sources specifically for the under-corroborated cells**:

- **Fable 5** — has **no published effort sweep at all** (Anthropic's OSWorld chart excludes it). Highest-value gap: any source measuring Fable at ≥2 efforts on one benchmark, or Fable vs another model at matched effort.
- **Haiku 4.5** low / high; **Opus 4.7** medium / xhigh; and the **low/medium cells across models** (mostly 1–2 sources).
- Prefer sources that give **same-task, multi-effort or multi-model** measurements (they create real edges). Partial data is still useful.
- When adding a source: append rows to `raw-data.csv`, keep the verified effort/thinking config (check the paper text AND the repo code — see `docs/repo-config-proof.md` for the method), then `python3 gen/build.py`.

## Also pending

- **No-think regime analysis.** Sources proven to run without extended thinking are tagged `nothink` in `raw-data.csv` and set aside from the effort ladder. They form a legitimate *separate* cost regime (cheapest) worth its own mini-analysis/column, not a point on low→max.
- **Internal validation run.** Public data caps confidence at "medium-high". A single controlled run on a real workload (same tasks across models/efforts) would anchor the whole matrix.

## Working loop

```bash
# edit gen/{build.py,app.js,body.html,style.css} and/or raw-data.csv / normalized.csv
python3 gen/build.py         # regenerates cost-matrix.html
# open cost-matrix.html in a browser to check
```
The generator is the single build path — do not hand-edit `cost-matrix.html`.
