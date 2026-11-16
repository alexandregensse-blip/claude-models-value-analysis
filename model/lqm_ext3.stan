// lqm_ext3.stan — lqm_ext2.stan REPARAMETERISED (the maintainer's decision of 30 Oct 2026). The same statistical model:
// the same joint density of lqm_ext2's parameters, the same data block, the same transformed parameters and generated
// quantities under the same names and meanings (theta, level, tau, tau_raw, z1, z2, z3, s_tau_f, psi_f, omega_f, psi2,
// omega3, psiC, omegaC, s_tau0, psi0, omega0, zf_tau, zf_psi, zf_omega, delta_f, deltaC, …), so that lqm.py and the
// site read it as lqm_ext2. Only the coordinates the sampler moves in differ, for the makers' three effect scales.
//
// Why. In lqm_ext2 maker k's effects of one family are e = s_k · z_k, z_k ~ N(0, I) (non-centred), and the data see
// only the products: s_k and all of maker k's z move together along a curved ridge (s_k up ⇔ every z of maker k down).
// On the cost axis of 29–30 Oct the scales of makers with few data (qwen) were bimodal and mixed slowly (psi_f[qwen] at
// ≈ 0.45 or ≈ 1.0; worst R̂ on eta_tau, tau, psi_f, psiC); the chains needed hundreds of draws to cross.
//
// Magnitude and direction. For every family and every maker k with n_k ≥ 1 effects of it (z_k its block, uniformly:
// no size threshold, no tuning to the data), z_k = r_k · u_k with r_k = ‖z_k‖ ~ χ(n_k) and u_k uniform on the sphere
// S^{n_k−1}. The data inform the realised magnitude A_k = s_k · r_k and the direction u_k; the sampler moves in
//   la_k = log A_k                       (unconstrained; la_k = log s_k itself for a maker with n_k = 0: no effects,
//                                         its scale from its prior only, as in lqm_ext2)
//   r_k > 0                              with its χ(n_k) density
//   y_k ∈ R^{n_k}, y_k ~ N(0, I)         u_k = y_k / ‖y_k‖ (as Stan's unit_vector): u_k uniform, and ‖y_k‖ ~ χ(n_k) an
//                                         auxiliary radius that nothing else depends on
// and recovers s_k = A_k / r_k, z_k = r_k · u_k (transformed parameters). The likelihood sees la_k and u_k only; r_k,
// and with it the scale, moves along its own axis, which the likelihood does not see.
//
// The three families (maker k of the level's model or couple):
//   ψ  publisher × model,   w = psi_f[k] · z2:   block z2 by prov2,          s_k = psi_f[k],   (la_psi, r_psi, y2);
//   ω  couple × task type,  v = omega_f[k] · z3: block z3 by prov3,          s_k = omega_f[k], (la_omega, r_omega, y3);
//   τ  publisher × couple,  u = s_tau_f[k] · tau_raw[c] · z1 (τ_c = s_tau_f[k] · tau_raw[c]): the maker's scale
//      multiplies its block of standard-normal z1 — every level of the maker's couples, block z1 by prov_c[own1] —
//      through the per-couple factor tau_raw[c] ~ N⁺(0, 1), which is kept as it is: s_k = s_tau_f[k],
//      A_k = s_tau_f[k] · ‖z1_k‖, (la_tau, r_tau, y1), tau = s_tau_f[prov_c] .* tau_raw as before. The ridge between
//      s_tau_f[k] and tau_raw (τ_c fixed) is already a straight line in the unconstrained coordinates (both on their log
//      scale); splitting tau_raw into a magnitude and a direction would leave the s_tau_f ↔ z1 ridge the data create;
//      and splitting z1 couple by couple (A_c = τ_c · ‖z1_c‖) would turn each couple with a single level (68 on cost,
//      36 on quality, 30 Oct) into a sign carried by a discontinuous direction (n = 1 below).
//
// Hyper-structure, unchanged in law: log s_k = log s_0 + η · ζ_k, ζ summing to zero over the makers with
// ζ ~ N(0, I) on that subspace (Stan's sum_to_zero_vector: free coordinates ξ ∈ R^{F−1}, ζ = V ξ with V orthonormal),
// s_0, η ~ half-Student-t(3, 0, 2.5). Here the F log scales λ = log s (from la and r) are the coordinates, η stays a
// parameter, and s_0 = exp(mean λ), ζ = (λ − mean λ) / η are recovered (s_tau0, psi0, omega0, zf_tau, zf_psi,
// zf_omega). The map (log s_0, ξ) → λ = log s_0 · 1 + η · V ξ is linear, |det| = √F · η^{F−1}.
//
// Log density of one family (constants dropped), against lqm_ext2's
//   lqm_ext2:  t(s_0) + log s_0 [<lower=0>] + t(η) + log η + N(ξ) + N(z)                      in (log s_0, log η, ξ, z)
//   here:      t(η) + log η                       η's prior and Stan's Jacobian of <lower=0>, as in lqm_ext2
//            + t(s_0) + log s_0                   s_0's prior and the Jacobian of s_0 → log s_0 = mean λ (which Stan
//                                                 added for lqm_ext2's <lower=0> s_0 and must be written here)
//            + N(ζ) − (F − 1) · log η             ζ's prior and the Jacobian of ξ → λ (1/η^{F−1}; √F is a constant)
//            + Σ_k [(n_k − 1) · log r_k − r_k²/2] z_k ~ N(0, I) in polar coordinates, dz = r^{n−1} dr dσ(u): r_k ~ χ(n_k)
//            + log r_k                            Stan's Jacobian of <lower=0> r_k
//            + N(y)                               u_k uniform; the auxiliary ‖y_k‖ ~ χ(n_k)
//   (λ_k, r_k) → (la_k = λ_k + log r_k, r_k) is triangular with a unit diagonal: no term. These coordinates map onto
//   lqm_ext2's one to one, the auxiliary radii ‖y_k‖ apart, whose χ(n_k) density is a factor of its own: integrating
//   them out gives lqm_ext2's posterior exactly. Every other term of the model is lqm_ext2's, unchanged.
//
// n_k = 1: S^0 = {−1, +1}, u_k is a sign, r_k = |z_k| ~ χ(1) = N⁺(0, 1), (n_k − 1) log r_k = 0: the formulas hold, but
// the sign changes only where y_k crosses 0, a discontinuity of the likelihood (the sampler stays valid, slow if the
// sign is well determined). On the data of 30 Oct 2026 every maker has at least 14 effects of each family (cost: ψ 14,
// ω 15, τ 16 at the fewest). n_k = 0: no block, no r_k, la_k = log s_k.
//
// ——— lqm_ext2's header, which holds for this model:
// ENCOMPASSING VARIANT (experiment, branch task/20261019-global): lqm.stan plus
//  * the scales of the publisher × couple (s_tau), publisher × model (psi) and couple × task-type (omega) effects per
//    model maker, each maker's log scale drawn around a common one (log s_f = log s_0 + eta · z_f): with eta → 0 it is
//    lqm.stan, so the data decide whether makers differ;
//  * (ext2) the makers' offsets zf_* and zd sum to zero: the common scales are the makers' geometric mean and delta0
//    their mean home effect, which removes the ridge between a common scale and the makers' mean offset (corr −0.6
//    to −0.94 in lqm_ext, 19–20 Oct); only makers with data are levels;
//  * a home effect per maker, delta_f = delta0 + tau_delta·zd_f, on rows a maker published and measured about its own
//    models (lqm.is_home): a shift excluded from every read-out; tau_delta → 0 is one effect shared by all makers.
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
  real<lower=0> eta_tau;                             // the spread of the makers' log scales around the common one
  real<lower=0> eta_psi;
  real<lower=0> eta_omega;
  vector[F] la_tau;                                  // log realised magnitude of each maker's block (header)
  vector[F] la_psi;
  vector[F] la_omega;
  vector<lower=0>[F_tau] r_tau;                      // its radius, χ(n_k), for the makers with effects
  vector<lower=0>[F_psi] r_psi;
  vector<lower=0>[F_omega] r_omega;
  real delta0;                                       // home effect: common mean …
  real<lower=0> tau_delta;                           // … and the spread of the makers' own effects around it
  sum_to_zero_vector[F] zd;
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
  // map is empty), their geometric mean s_0 and offsets ζ (header): lqm_ext2's parameters
  vector[F] s_tau_f = exp(la_tau - csr_matrix_times_vector(F, F_tau, wS_tau, vS_tau, uS_tau, log(r_tau)));
  vector[F] psi_f = exp(la_psi - csr_matrix_times_vector(F, F_psi, wS_psi, vS_psi, uS_psi, log(r_psi)));
  vector[F] omega_f = exp(la_omega - csr_matrix_times_vector(F, F_omega, wS_omega, vS_omega, uS_omega, log(r_omega)));
  real s_tau0 = exp((sum(la_tau) - sum(log(r_tau))) / F);
  real psi0 = exp((sum(la_psi) - sum(log(r_psi))) / F);
  real omega0 = exp((sum(la_omega) - sum(log(r_omega))) / F);
  vector[F] zf_tau = (la_tau - csr_matrix_times_vector(F, F_tau, wS_tau, vS_tau, uS_tau, log(r_tau)) - log(s_tau0)) / eta_tau;
  vector[F] zf_psi = (la_psi - csr_matrix_times_vector(F, F_psi, wS_psi, vS_psi, uS_psi, log(r_psi)) - log(psi0)) / eta_psi;
  vector[F] zf_omega = (la_omega - csr_matrix_times_vector(F, F_omega, wS_omega, vS_omega, uS_omega, log(r_omega)) - log(omega0)) / eta_omega;
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
  vector[F] delta_f = delta0 + tau_delta * zd;     // each maker's home effect
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
  eta_tau ~ student_t(3, 0, 2.5);
  eta_psi ~ student_t(3, 0, 2.5);
  eta_omega ~ student_t(3, 0, 2.5);
  // the makers' scales (header): s_0's prior and the Jacobian of log s_0 = mean λ; ζ's prior and the Jacobian
  // η^{−(F−1)} of ζ = (λ − mean λ) / η; r_k ~ χ(n_k) (Stan adds log r_k for <lower=0>)
  target += student_t_lupdf(s_tau0 | 3, 0, 2.5) + log(s_tau0) + std_normal_lupdf(zf_tau) - (F - 1) * log(eta_tau);
  target += student_t_lupdf(psi0 | 3, 0, 2.5) + log(psi0) + std_normal_lupdf(zf_psi) - (F - 1) * log(eta_psi);
  target += student_t_lupdf(omega0 | 3, 0, 2.5) + log(omega0) + std_normal_lupdf(zf_omega) - (F - 1) * log(eta_omega);
  target += dot_product(n_tau - 1, log(r_tau)) - 0.5 * dot_self(r_tau);
  target += dot_product(n_psi - 1, log(r_psi)) - 0.5 * dot_self(r_psi);
  target += dot_product(n_omega - 1, log(r_omega)) - 0.5 * dot_self(r_omega);
  delta0 ~ normal(0, 10);                            // as the latent qualities: weakly informative
  tau_delta ~ student_t(3, 0, 2.5);
  zd ~ std_normal();
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
