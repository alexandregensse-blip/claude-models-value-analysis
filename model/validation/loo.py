"""Leave-one-out predictive score of a fitted axis, without refitting (PSIS-LOO, Vehtari, Gelman & Gabry 2017): the
pointwise log-likelihood of every row is computed from the stored draws, ArviZ smooths the importance weights, and
the expected log predictive density (elpd) with its standard error compares two models fitted on the same rows.
Rows whose Pareto k exceeds 0.7 are reported (their LOO value is unreliable: a refit without them would be needed).

Usage, in the Stan environment, from the repository root:
  LQM_MODEL=lqm     .stan/venv/bin/python model/validation/loo.py quality out-current.json
  LQM_MODEL=lqm_ext .stan/venv/bin/python model/validation/loo.py quality out-ext.json
  python3 model/validation/loo.py --compare out-current.json out-ext.json"""
import json, os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def pointwise(axis, thin=3):
    import numpy as np
    sys.path[:0] = [os.path.join(ROOT, "model"), os.path.join(ROOT, "data")]
    import lqm
    from catalog import MODEL_ORDER
    field = "score" if axis == "quality" else "cost_usd"
    groups, _, _ = lqm.load(os.path.join(ROOT, "raw-data.csv"), MODEL_ORDER, field=field)
    data, maps = lqm.stan_data(groups, axis)
    st = lqm.SAMPLER[axis]
    key = lqm.sampling_key(data, axis, st, 11)
    path = os.path.join(lqm.RUNS, f"{axis}-{key[:16]}")
    store = lqm.RunStore(path, key)                                  # the fit's own key: nothing is wiped
    if not store.parts:
        sys.exit(f"!! no stored draws for this data and model at {path}: fit the axis first")
    post = store.posterior()
    V = lambda k: np.asarray(post.chains(k), float)[:, ::thin]       # (chains, draws, …)
    th, o, a, sig = V("theta"), V("o"), V("a"), V("sigma")
    z1, z2, z3, nu = V("z1"), V("z2"), V("z3"), V("nu")
    tau = V("tau")
    psi2 = V("psi2") if "psi2" in post.names else V("psi")[..., None] * np.ones(z2.shape[-1])
    om3 = V("omega3") if "omega3" in post.names else V("omega")[..., None] * np.ones(z3.shape[-1])
    own1 = np.asarray(data["own1"], int) - 1
    cs = {k: np.asarray(data[k], int) for k in ("set1", "set2", "set3")}

    def centred(E, sets):
        for s in np.unique(sets):
            E[..., sets == s] -= E[..., sets == s].mean(axis=-1, keepdims=True)
        return E
    e1 = centred(z1 * tau[..., own1], cs["set1"]) if len(own1) else np.zeros(z1.shape)
    e2 = centred(z2 * psi2, cs["set2"])
    e3 = centred(z3 * om3, cs["set3"])
    grp, cpl = np.asarray(data["grp"]) - 1, np.asarray(data["cpl"]) - 1
    k1, k2, k3 = (np.asarray(data[k]) for k in ("k1", "k2", "k3"))
    pad = lambda E: np.concatenate([E, np.zeros(E.shape[:-1] + (1,))], axis=-1)   # level 0 → the zero at the end
    x = th[..., cpl] + pad(e1)[..., k1 - 1] + pad(e2)[..., k2 - 1] + pad(e3)[..., k3 - 1]
    if "deltaC" in post.names:
        x = x + V("deltaC")[..., cpl] * np.asarray(data["home"], float)
    h, d, ea = (np.asarray(data[k], float) for k in ("h", "d", "ea"))
    km1 = np.exp(0.5 * V("log_kappa")[..., 0]) - 1 if "log_kappa" in post.names and max(data["ea"]) else 0.0
    if np.ndim(km1): km1 = km1[..., None]
    scale = np.sqrt((sig[..., grp] * (h + h * ea * km1)) ** 2 + d ** 2)
    m = o[..., grp] + a[..., grp] * x
    zr = (np.asarray(data["z"], float) - m) / scale
    n = nu[..., None]
    ll = (np.vectorize(math.lgamma)((n + 1) / 2) - np.vectorize(math.lgamma)(n / 2) - 0.5 * np.log(n * math.pi)
          - np.log(scale) - (n + 1) / 2 * np.log1p(zr ** 2 / n))
    names = maps["names"]
    rows = [(names[b], x_["couple"], x_["publisher"]) for b, g in enumerate(names) for x_ in groups[g]["rows"]]
    return ll, rows


def main(axis, out):
    import numpy as np, arviz as az
    ll, rows = pointwise(axis)
    res = az.loo(az.from_dict({"log_likelihood": {"y": ll}, "posterior": {"_": ll[..., 0]}}), pointwise=True, var_name="y")
    k = np.asarray(res.pareto_k)
    elpd_i = np.asarray(res.elpd_i).ravel(); k = k.ravel()
    json.dump(dict(model=os.environ.get("LQM_MODEL", "lqm"), axis=axis, elpd=float(res.elpd), se=float(res.se),
                   p_loo=float(res.p), k_over_07=int((k > 0.7).sum()), rows=[list(r) for r in rows],
                   elpd_i=[float(v) for v in elpd_i], pareto_k=[float(v) for v in k]), open(out, "w"))
    print(f"{axis} {os.environ.get('LQM_MODEL', 'lqm')}: elpd_loo {res.elpd:.1f} ± {res.se:.1f}, p_loo {res.p:.1f}, "
          f"rows with Pareto k > 0.7: {(k > 0.7).sum()} of {len(k)}")


def compare(a, b):
    import numpy as np
    A, B = json.load(open(a)), json.load(open(b))
    assert A["rows"] == B["rows"], "the two fits do not hold the same rows"
    d = np.asarray(B["elpd_i"]) - np.asarray(A["elpd_i"])
    print(f"{B['model']} − {A['model']}: Δelpd {d.sum():.1f} ± {math.sqrt(len(d)) * d.std():.1f} "
          f"(positive: {B['model']} predicts left-out rows better)")
    for prov in ("anthropic",):                                      # the same difference on the Claude rows alone
        sel = np.array([r[1].split("-")[0] in ("opus", "sonnet", "haiku", "fable") for r in A["rows"]])
        print(f"  on Claude rows ({sel.sum()}): Δelpd {d[sel].sum():.1f} ± {math.sqrt(sel.sum()) * d[sel].std():.1f}; "
              f"on the others ({(~sel).sum()}): {d[~sel].sum():.1f} ± {math.sqrt((~sel).sum()) * d[~sel].std():.1f}")


if __name__ == "__main__":
    if sys.argv[1] == "--compare":
        compare(sys.argv[2], sys.argv[3])
    else:
        main(sys.argv[1], sys.argv[2])
