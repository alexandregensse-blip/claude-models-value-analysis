// lqm_ext4.stan — the makers' biases INDEPENDENT (the maintainer's decision of 2 Nov 2026): each maker's biases are
// its own, with no reason to tie them across makers. lqm_ext3.stan (= lqm_ext2.stan reparameterised) drew each
// maker's three effect scales around common ones (log s_k = log s_0 + η · ζ_k, ζ summing to zero) and each maker's
// home effect around a common one (δ_k = δ_0 + τ_δ · zd_k); the fit of 30 Oct 2026 diverged (cost 63, quality 23)
// and its draws showed a funnel in η (η_τ from 0.002 to 1.3: the makers' scales pinned together when η is small).
// Here the tie is gone: no s_0, η, ζ (s_tau0, psi0, omega0, eta_*, zf_*), no δ_0, τ_δ, zd. Every maker k has
//   s_tau_f[k], psi_f[k], omega_f[k] ~ half-Student-t(3, 0, 2.5)  independently (the prior the common scales had)
//   delta_f[k] ~ N(0, 10²)                                        independently (the prior δ_0 had)
// Everything else is lqm_ext3's: theta, o, a, sigma, ν, κ, tau_raw, the data block, the read-outs and every name lqm.py
// and the site read (theta, level, tau, tau_raw, z1–z3, s_tau_f, psi_f, omega_f, psi2, omega3, psiC, omegaC, delta_f,
// deltaC). delta_f is now a parameter (a transformed parameter before).
//
// Magnitude and direction (kept from lqm_ext3, which mixed faster than lqm_ext2's coordinates on 30 Oct). Maker k's
// effects of one family are e = s_k · z_k with z_k ~ N(0, I_{n_k}), n_k its number of effects in that family. For every
// family and every maker with n_k ≥ 1 (uniformly: no size threshold), z_k = r_k · u_k with r_k = ‖z_k‖ ~ χ(n_k) and
// u_k uniform on S^{n_k−1}; the sampler moves in
//   la_k = log A_k = log s_k + log r_k   (unconstrained; A_k = s_k · r_k the realised magnitude the data inform)
//   r_k > 0                              with its χ(n_k) density (Stan samples log r_k)
//   y_k ∈ R^{n_k}, y_k ~ N(0, I)         u_k = y_k / ‖y_k‖: u_k uniform, ‖y_k‖ ~ χ(n_k) an auxiliary radius that
//                                         nothing else depends on
// and recovers s_k = exp(la_k − log r_k), z_k = r_k · u_k (transformed parameters). For a maker with n_k = 0 in a
// family there is no block and no r_k: la_k = log s_k. The three families (maker k of the level's model or couple):
//   ψ  publisher × model,   w = psi_f[k] · z2:   block z2 by prov2,          (la_psi, r_psi, y2);
//   ω  couple × task type,  v = omega_f[k] · z3: block z3 by prov3,          (la_omega, r_omega, y3);
//   τ  publisher × couple,  u = s_tau_f[k] · tau_raw[c] · z1, τ_c = s_tau_f[k] · tau_raw[c], tau_raw ~ N⁺(0, 1) kept
//      as it is; block z1 by prov_c[own1] (every level of the maker's couples), (la_tau, r_tau, y1).
//
// Log density of one family, maker by maker (constants dropped). The target, in s_k and z_k ∈ R^{n_k}:
//   t(s_k) + N(z_k),   t = half-Student-t(3, 0, 2.5)
// Change of variables, term by term:
//   (log s_k) → s_k                   + log s_k               (|ds/d log s| = s)
//   z_k → (r_k, u_k), polar           + (n_k − 1) · log r_k   (dz = r^{n−1} dr dσ(u)); with N(z_k) = −r_k²/2:
//                                                              r_k ~ χ(n_k), u_k uniform
//   (log s_k, log r_k) → (la_k, log r_k)  + 0                 (la = log s + log r: triangular, unit diagonal)
//   log r_k → r_k (<lower=0>)         + log r_k               (added by Stan)
//   u_k ← y_k / ‖y_k‖                 + N(y_k)                (y_k ~ N(0, I); ‖y_k‖ ~ χ(n_k) integrates out to 1)
// so the model block writes, per family:
//   Σ_k [t(s_k) + log s_k]                  over all F makers (log s_k = la_k − log r_k, or la_k when n_k = 0)
// + Σ_{k: n_k ≥ 1} [(n_k − 1) · log r_k − r_k²/2]   (+ log r_k by Stan)
// + N(y)
// For a maker without effects in a family (n_k = 0) only the first term remains: its s_k is its prior,
// half-Student-t(3, 0, 2.5), in the sampler's coordinates la_k = log s_k. Such an s_k enters no likelihood term; it
// enters only the read-outs that integrate an unknown effect over its distribution (the panel read-out `level` on the
// quality axis and lqm.py's level_new, through tau, psiC, omegaC for a couple of that maker without the effect). On
// the data of 30 Oct 2026 every maker has at least 14 effects of each family (cost: ψ 14, ω 15, τ 16 at the fewest).
//
// Compared with lqm_ext3: gone are t(s_0) + log s_0, N(ζ) − (F − 1) · log η and t(η) + log η per family, and
// δ_0's N(0, 10²), τ_δ's half-t and zd's N(0, I); the r_k, y_k terms are unchanged. n_k = 1: S^0 = {−1, +1}, u_k is a
// sign, r_k = |z_k| ~ N⁺(0, 1), (n_k − 1) log r_k = 0 (as in lqm_ext3).
//
// ——— lqm_ext2's header (the base model; its makers' paragraph is replaced by the above):
// ENCOMPASSING VARIANT: lqm.stan plus the scales of the publisher × couple (s_tau), publisher × model (psi) and
// couple × task-type (omega) effects per model maker, and a home effect per maker, delta_f, on rows a maker published
// and measured about its own models (lqm.is_home): a shift excluded from every read-out; only makers with data are
// levels.
// Latent quality (or log cost) of (model, effort) couples, fused from heterogeneous benchmarks. Method: METHODOLOGY.md §5;
// data preparation: lqm.py. For every row r (group b, couple c of model m, publisher s, task type t):
//
//   f(y_r) = o_b + a_b · (θ_c + u_{s,c} + w_{s,m} + v_{c,t}) + ε_r ,   ε_r ~ Student-t_ν(0, κ_r · h_r² · σ_b² + d_r²)
//
// θ sums to zero: no couple is a reference; the page divides by its reference couple afterwards. h_r is the noise
// shape of an empirical logit, 1/(2√(q(1−q))) at the observed proportion (1 on other scales); κ_r the estimated
// variance multiplier of an early-access run; d_r the known reading precision of the value (rounding of a printed
// number, resolution of a digitised chart, propagated through a computation). `level` (generated quantities) is the
// read-out published by the page; what one new source would report (`level_new`) is computed from the draws in lqm.py.
//
// Writing (the model is unchanged by any of it; see model/validation and the fit diagnostics):
//  * log σ_b centred in every group and log a_b centred in groups of ≥ 20 rows (non-centred elsewhere): the
//    parameterisation under which NUTS mixes on both axes;
//  * s_g (the spread of the groups' gains) sampled on its log scale with its origin at a plausible value
//    (log s_g = −0.5 ± 0.5 per unit): same prior, same density. nutpie starts every chain at random in (−2, 2) on
//    the unconstrained scale and ignores given starting points; on the plain log scale that put s_g anywhere in
//    0.14–7.4, and a chain started high stayed trapped in a low-density funnel of huge gains (log density −900 to
//    −3400 against −510), after the sources of 30 Sep 2026;
//  * effects centred within their set and mapped to rows by sparse products, the row scales as vector expressions,
//    so that stanc --O1 keeps every vector in struct-of-arrays form (−36 % per gradient; compile with --O1 and
//    STAN_NO_RANGE_CHECKS, as lqm.fit does).
functions {
  // number of effects of each maker
  vector maker_counts(array[] int mk, int F) {
    vector[F] n = rep_vector(0, F);
    for (l in 1:size(mk)) n[mk[l]] += 1;
    return n;
  }
  // the makers with at least one effect, in order
  array[] int with_effects(array[] int mk, int F) {
    vector[F] n = maker_counts(mk, F);
    int m = 0;
    for (k in 1:F) m += n[k] > 0;
    array[m] int out;
    int p = 1;
    for (k in 1:F) if (n[k] > 0) { out[p] = k; p += 1; }
    return out;
  }
  // the F × L sum-by-maker map in compressed-row form: column indices (the levels, maker by maker) …
  array[] int by_maker(array[] int mk, int F) {
    array[size(mk)] int v;
    int p = 1;
    for (k in 1:F) for (l in 1:size(mk)) if (mk[l] == k) { v[p] = l; p += 1; }
    return v;
  }
  // … and row starts
  array[] int maker_starts(array[] int mk, int F) {
    array[F] int n = rep_array(0, F);
    for (l in 1:size(mk)) n[mk[l]] += 1;
    array[F + 1] int u;
    u[1] = 1;
    for (k in 1:F) u[k + 1] = u[k] + n[k];
    return u;
  }
}
data {
  int<lower=1> N;                                  // rows
  int<lower=1> G;                                  // groups
  int<lower=2> C;                                  // couples
  int<lower=0, upper=1> cost;                      // 1 = cost axis, 0 = quality axis
  array[N] int<lower=1, upper=G> grp;
  array[N] int<lower=1, upper=C> cpl;
  vector[N] z;                                     // f(y), prescaled per group: z = (f(y) − mu_b) / sd_b
  vector<lower=0>[N] h;                            // noise shape of the row (1 unless the group is a logit)
  vector<lower=0>[N] d;                            // reading precision of the value, on the scale of z
  array[N] int<lower=0, upper=1> ea;               // early-access run
  int<lower=0> L1;                                 // publisher × couple levels
  int<lower=0> L2;                                 // publisher × model levels
  int<lower=0> L3;                                 // couple × task-type levels
  array[N] int<lower=0, upper=L1> k1;              // level of each row, 0 = none
  array[N] int<lower=0, upper=L2> k2;
  array[N] int<lower=0, upper=L3> k3;
  array[L1] int<lower=1, upper=C> own1;            // couple of each publisher × couple level (τ is per couple)
  // centring sets: an effect's mean over its publisher (u, w) or its task type (v) is confounded with the offsets
  // of that publisher's (type's) groups, which are free; the likelihood sees the effects centred within their set
  int<lower=0> S1;
  array[L1] int<lower=1, upper=max(S1, 1)> set1;
  int<lower=0> S2;
  array[L2] int<lower=1, upper=max(S2, 1)> set2;
  int<lower=0> S3;
  array[L3] int<lower=1, upper=max(S3, 1)> set3;
  vector[G] mu;
  vector<lower=0>[G] sd;
  // panel read-out (quality axis): expected score of every couple on every panel group, as that group's publisher
  // ran it; an effect the data do not contain for this couple is integrated over its distribution
  int<lower=0> P;
  array[P] int<lower=1, upper=G> pg;
  vector<lower=0>[P] pw;
  array[P, C] int<lower=0, upper=L1> r1;           // known publisher × couple level, 0 = unknown
  array[P, C] int<lower=0, upper=L2> r2;           // known publisher × model level, 0 = unknown
  array[P, C] int<lower=0, upper=L3> r3;           // known couple × task-type level, 0 = unknown
  array[P] int<lower=0, upper=1> has_v;            // 0 for a composite (task type 'mixed'): no task-type effect
  array[P] int<lower=1, upper=max(P, 1)> ptype;    // index of the panel group's task type (first panel group of it)
  int<lower=1> F;                                  // model makers
  array[C] int<lower=1, upper=F> prov_c;           // maker of each couple
  array[L2] int<lower=1, upper=F> prov2;           // maker of the model of each publisher × model level
  array[L3] int<lower=1, upper=F> prov3;           // maker of the couple of each couple × task-type level
  vector<lower=0, upper=1>[N] home;                // 1 = the maker's own publication about its own model
  int<lower=1> K;                                  // Gauss–Hermite nodes
  vector[K] ghx;
  vector[K] ghw;
}
transformed data {
  vector[N] d2 = square(d);
  int has_ea = max(ea);
  vector[N] hea = h .* to_vector(ea);              // h on early-access rows, 0 elsewhere
  array[G] int n_rows = rep_array(0, G);
  for (r in 1:N) n_rows[grp[r]] += 1;
  array[G] int cg;
  for (b in 1:G) cg[b] = n_rows[b] >= 20;
  vector[G] cgv = to_vector(cg);
  int nCG = sum(cg);
  array[nCG] int iCG;
  array[G - nCG] int iNG;
  {
    int p = 1; int q = 1;
    for (b in 1:G) if (cg[b]) { iCG[p] = b; p += 1; } else { iNG[q] = b; q += 1; }
  }
  // sparse maps, compressed-row form (Stan's 1-based csr convention). Bk: N × Lk, a single 1 in each row carrying
  // the effect (rows without it are empty: exact zero). Ak: Sk × Lk, a 1 for each member of the set (set sums).
  int nz1 = 0; int nz2 = 0; int nz3 = 0;
  for (r in 1:N) { nz1 += k1[r] > 0; nz2 += k2[r] > 0; nz3 += k3[r] > 0; }
  vector[nz1] wB1 = rep_vector(1, nz1);
  vector[nz2] wB2 = rep_vector(1, nz2);
  vector[nz3] wB3 = rep_vector(1, nz3);
  array[nz1] int vB1; array[nz2] int vB2; array[nz3] int vB3;
  array[N + 1] int uB1; array[N + 1] int uB2; array[N + 1] int uB3;
  {
    int p1 = 1; int p2 = 1; int p3 = 1;
    for (r in 1:N) {
      uB1[r] = p1; uB2[r] = p2; uB3[r] = p3;
      if (k1[r] > 0) { vB1[p1] = k1[r]; p1 += 1; }
      if (k2[r] > 0) { vB2[p2] = k2[r]; p2 += 1; }
      if (k3[r] > 0) { vB3[p3] = k3[r]; p3 += 1; }
    }
    uB1[N + 1] = p1; uB2[N + 1] = p2; uB3[N + 1] = p3;
  }
  vector[L1] wA1 = rep_vector(1, L1);
  vector[L2] wA2 = rep_vector(1, L2);
  vector[L3] wA3 = rep_vector(1, L3);
  array[L1] int vA1; array[L2] int vA2; array[L3] int vA3;
  array[S1 + 1] int uA1; array[S2 + 1] int uA2; array[S3 + 1] int uA3;
  vector[S1] n1 = rep_vector(0, S1);
  vector[S2] n2 = rep_vector(0, S2);
  vector[S3] n3 = rep_vector(0, S3);
  {
    int p = 1;
    for (s in 1:S1) { uA1[s] = p; for (i in 1:L1) if (set1[i] == s) { vA1[p] = i; p += 1; n1[s] += 1; } }
    uA1[S1 + 1] = p;
    p = 1;
    for (s in 1:S2) { uA2[s] = p; for (i in 1:L2) if (set2[i] == s) { vA2[p] = i; p += 1; n2[s] += 1; } }
    uA2[S2 + 1] = p;
    p = 1;
    for (s in 1:S3) { uA3[s] = p; for (i in 1:L3) if (set3[i] == s) { vA3[p] = i; p += 1; n3[s] += 1; } }
    uA3[S3 + 1] = p;
  }
  // panel read-out maps, pair (p, c) at position (c − 1)·P + p; index L + 1 = the padded zero (unknown effect)
  int PC = P * C;
  array[PC] int cPC; array[PC] int gPC;
  array[PC] int j1PC; array[PC] int j2PC; array[PC] int j3PC;
  vector[PC] q1PC; vector[PC] q2PC; vector[PC] q3PC;           // 1 = effect unknown for this pair: integrated over
  vector[PC] muPC; vector[PC] sdPC;
  for (c in 1:C) for (p in 1:P) {
    int i = (c - 1) * P + p;
    cPC[i] = c; gPC[i] = pg[p]; muPC[i] = mu[pg[p]]; sdPC[i] = sd[pg[p]];
    j1PC[i] = r1[p, c] > 0 ? r1[p, c] : L1 + 1;  q1PC[i] = r1[p, c] == 0;
    j2PC[i] = r2[p, c] > 0 ? r2[p, c] : L2 + 1;  q2PC[i] = r2[p, c] == 0;
    j3PC[i] = has_v[p] && r3[p, c] > 0 ? r3[p, c] : L3 + 1;  q3PC[i] = has_v[p] && r3[p, c] == 0;
  }
  vector[P] muP = mu[pg];
  vector[P] sdP = sd[pg];
  real theta_scale = 10 / sqrt(1 - 1.0 / C);
  real W = sum(pw);
  real qual = 1 - cost;
  // the makers' blocks of effects (header): maker of each level, effects per maker, the makers with effects (their
  // r), and the sum-by-maker maps
  array[L1] int mk_tau = prov_c[own1];
  vector[F] cnt_tau = maker_counts(mk_tau, F);
  vector[F] cnt_psi = maker_counts(prov2, F);
  vector[F] cnt_omega = maker_counts(prov3, F);
  int F_tau = size(with_effects(mk_tau, F));
  int F_psi = size(with_effects(prov2, F));
  int F_omega = size(with_effects(prov3, F));
  array[F_tau] int i_tau = with_effects(mk_tau, F);
  array[F_psi] int i_psi = with_effects(prov2, F);
  array[F_omega] int i_omega = with_effects(prov3, F);
  // the F × F_* map that puts the j-th maker with effects at its place i_*[j]: row i_*[j] holds column j,
  // the rows of the makers without effects are empty (exact 0)
  vector[F_tau] wS_tau = rep_vector(1, F_tau);
  vector[F_psi] wS_psi = rep_vector(1, F_psi);
  vector[F_omega] wS_omega = rep_vector(1, F_omega);
  array[F_tau] int vS_tau = linspaced_int_array(F_tau, 1, F_tau);
  array[F_psi] int vS_psi = linspaced_int_array(F_psi, 1, F_psi);
  array[F_omega] int vS_omega = linspaced_int_array(F_omega, 1, F_omega);
  array[F + 1] int uS_tau = maker_starts(i_tau, F);
  array[F + 1] int uS_psi = maker_starts(i_psi, F);
  array[F + 1] int uS_omega = maker_starts(i_omega, F);
  vector[F_tau] n_tau = cnt_tau[i_tau];
  vector[F_psi] n_psi = cnt_psi[i_psi];
  vector[F_omega] n_omega = cnt_omega[i_omega];
  vector[F] e_tau = rep_vector(0, F);
  vector[F] e_psi = rep_vector(0, F);
  vector[F] e_omega = rep_vector(0, F);
  for (k in 1:F) { e_tau[k] = cnt_tau[k] == 0; e_psi[k] = cnt_psi[k] == 0; e_omega[k] = cnt_omega[k] == 0; }
  vector[L1] wM_tau = rep_vector(1, L1);
  vector[L2] wM_psi = rep_vector(1, L2);
  vector[L3] wM_omega = rep_vector(1, L3);
  array[L1] int vM_tau = by_maker(mk_tau, F);
  array[L2] int vM_psi = by_maker(prov2, F);
  array[L3] int vM_omega = by_maker(prov3, F);
  array[F + 1] int uM_tau = maker_starts(mk_tau, F);
  array[F + 1] int uM_psi = maker_starts(prov2, F);
  array[F + 1] int uM_omega = maker_starts(prov3, F);
}
parameters {
  sum_to_zero_vector[C] theta;
  vector[G] o;
  vector[G] lg_raw;
  real<offset=-0.5, multiplier=0.5> log_s_g;           // s_g on its log scale (see the header)
  vector[L1] y1;                                     // directions of the makers' blocks of z1, z2, z3 (header)
  vector[L2] y2;
  vector[L3] y3;
  vector<lower=0>[C] tau_raw;
  vector[F] la_tau;                                  // log realised magnitude of each maker's block (header)
  vector[F] la_psi;
  vector[F] la_omega;
  vector<lower=0>[F_tau] r_tau;                      // its radius, χ(n_k), for the makers with effects
  vector<lower=0>[F_psi] r_psi;
  vector<lower=0>[F_omega] r_omega;
  vector[F] delta_f;                                 // each maker's home effect, independent (header)
  real<lower=1> nu;
  array[has_ea] real log_kappa;
  real mu_sig;
  real<lower=0> s_sig;
  vector[G] log_sigma;
}
transformed parameters {
  real<lower=0> s_g = exp(log_s_g);
  vector[G] sigma = exp(log_sigma);
  vector[G] a = exp(cgv .* lg_raw + (1 - cgv) .* (s_g * lg_raw + qual * log_sigma));   // qual = 1 − cost (0·x = 0 exactly)
  // the makers' scales s_k = A_k / r_k (log s_k = la_k − log r_k; la_k for a maker without effects, whose row of the
  // map is empty): each maker's own (header)
  vector[F] s_tau_f = exp(la_tau - csr_matrix_times_vector(F, F_tau, wS_tau, vS_tau, uS_tau, log(r_tau)));
  vector[F] psi_f = exp(la_psi - csr_matrix_times_vector(F, F_psi, wS_psi, vS_psi, uS_psi, log(r_psi)));
  vector[F] omega_f = exp(la_omega - csr_matrix_times_vector(F, F_omega, wS_omega, vS_omega, uS_omega, log(r_omega)));
  vector[C] tau = s_tau_f[prov_c] .* tau_raw;
  // z_k = r_k · y_k / ‖y_k‖ (‖y_k‖ by the sum-by-maker map; e_* = 1 for a maker without effects: never used, no NaN)
  vector[L1] z1 = ((csr_matrix_times_vector(F, F_tau, wS_tau, vS_tau, uS_tau, r_tau) + e_tau)
                   ./ sqrt(csr_matrix_times_vector(F, L1, wM_tau, vM_tau, uM_tau, square(y1)) + e_tau))[mk_tau] .* y1;
  vector[L2] z2 = ((csr_matrix_times_vector(F, F_psi, wS_psi, vS_psi, uS_psi, r_psi) + e_psi)
                   ./ sqrt(csr_matrix_times_vector(F, L2, wM_psi, vM_psi, uM_psi, square(y2)) + e_psi))[prov2] .* y2;
  vector[L3] z3 = ((csr_matrix_times_vector(F, F_omega, wS_omega, vS_omega, uS_omega, r_omega) + e_omega)
                   ./ sqrt(csr_matrix_times_vector(F, L3, wM_omega, vM_omega, uM_omega, square(y3)) + e_omega))[prov3] .* y3;
  vector[L2] psi2 = psi_f[prov2];
  vector[L3] omega3 = omega_f[prov3];
  vector[C] psiC = psi_f[prov_c];
  vector[C] omegaC = omega_f[prov_c];
  vector[C] deltaC = delta_f[prov_c];
}
model {
  {
    vector[L1] e1 = z1 .* tau[own1];
    vector[L2] e2 = z2 .* psi2;
    vector[L3] e3 = z3 .* omega3;
    vector[S1] m1 = csr_matrix_times_vector(S1, L1, wA1, vA1, uA1, e1) ./ n1;
    vector[S2] m2 = csr_matrix_times_vector(S2, L2, wA2, vA2, uA2, e2) ./ n2;
    vector[S3] m3 = csr_matrix_times_vector(S3, L3, wA3, vA3, uA3, e3) ./ n3;
    vector[N] x = theta[cpl] + deltaC[cpl] .* home
                  + csr_matrix_times_vector(N, L1, wB1, vB1, uB1, e1 - m1[set1])
                  + csr_matrix_times_vector(N, L2, wB2, vB2, uB2, e2 - m2[set2])
                  + csr_matrix_times_vector(N, L3, wB3, vB3, uB3, e3 - m3[set3]);
    real km1 = has_ea ? exp(0.5 * log_kappa[1]) - 1 : 0;   // variance multiplier of early access, minus 1
    vector[N] scale = sqrt(square(sigma[grp] .* (h + hea * km1)) + d2);
    z ~ student_t(nu, o[grp] + a[grp] .* x, scale);
  }
  theta ~ normal(0, theta_scale);
  lg_raw[iNG] ~ std_normal();
  if (cost) lg_raw[iCG] ~ normal(0, s_g); else lg_raw[iCG] ~ normal(log_sigma[iCG], s_g);
  y1 ~ std_normal();                                   // u_k uniform, ‖y_k‖ ~ χ(n_k) auxiliary (header)
  y2 ~ std_normal();
  y3 ~ std_normal();
  s_g ~ student_t(3, 0, 2.5);
  target += log_s_g;                                   // Jacobian of s_g = exp(log_s_g)
  tau_raw ~ std_normal();
  // the makers' scales, each its own (header): s_k ~ half-Student-t(3, 0, 2.5) and the Jacobian log s_k of
  // s_k → log s_k (Σ_k log s_k = Σ la − Σ log r, the makers without effects having no r); r_k ~ χ(n_k) (Stan adds
  // log r_k for <lower=0>)
  target += student_t_lupdf(s_tau_f | 3, 0, 2.5) + sum(la_tau) - sum(log(r_tau));
  target += student_t_lupdf(psi_f | 3, 0, 2.5) + sum(la_psi) - sum(log(r_psi));
  target += student_t_lupdf(omega_f | 3, 0, 2.5) + sum(la_omega) - sum(log(r_omega));
  target += dot_product(n_tau - 1, log(r_tau)) - 0.5 * dot_self(r_tau);
  target += dot_product(n_psi - 1, log(r_psi)) - 0.5 * dot_self(r_psi);
  target += dot_product(n_omega - 1, log(r_omega)) - 0.5 * dot_self(r_omega);
  delta_f ~ normal(0, 10);                           // each maker's own, as the latent qualities: weakly informative
  nu ~ gamma(2, 0.1);
  if (has_ea) log_kappa[1] ~ normal(0, 1);
  s_sig ~ student_t(3, 0, 2.5);
  log_sigma ~ normal(mu_sig, s_sig);
}
generated quantities {
  // same read-outs as recommended.stan; the panel read-out is evaluated for all (panel group, couple) pairs at once,
  // one Gauss–Hermite node at a time (vectorised inv_logit), summing the nodes in the same order as before
  vector[C] level;
  if (cost) {
    level = theta;
  } else {
    vector[L1] e1 = z1 .* tau[own1];
    vector[L2] e2 = z2 .* psi2;
    vector[L3] e3 = z3 .* omega3;
    vector[S1] m1 = csr_matrix_times_vector(S1, L1, wA1, vA1, uA1, e1) ./ n1;
    vector[S2] m2 = csr_matrix_times_vector(S2, L2, wA2, vA2, uA2, e2) ./ n2;
    vector[S3] m3 = csr_matrix_times_vector(S3, L3, wA3, vA3, uA3, e3) ./ n3;
    vector[L1 + 1] u = append_row(e1 - m1[set1], 0);
    vector[L2 + 1] w = append_row(e2 - m2[set2], 0);
    vector[L3 + 1] v = append_row(e3 - m3[set3], 0);
    vector[PC] x = theta[cPC] + u[j1PC] + w[j2PC] + v[j3PC];
    vector[PC] sV = sqrt(q1PC .* square(tau[cPC]) + q2PC .* square(psiC[cPC]) + q3PC .* square(omegaC[cPC]));
    vector[PC] oPC = o[gPC];
    vector[PC] aPC = a[gPC];
    vector[PC] e = rep_vector(0, PC);
    for (k in 1:K) e += ghw[k] * inv_logit(muPC + sdPC .* (oPC + aPC .* (x + sV * ghx[k])));
    level = log((to_matrix(e, P, C)' * pw) / W);
  }
}
