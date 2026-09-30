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
}
parameters {
  sum_to_zero_vector[C] theta;
  vector[G] o;
  vector[G] lg_raw;
  real<offset=-0.5, multiplier=0.5> log_s_g;           // s_g on its log scale (see the header)
  vector[L1] z1;
  vector[L2] z2;
  vector[L3] z3;
  vector<lower=0>[C] tau_raw;
  real<lower=0> s_tau;
  real<lower=0> psi;
  real<lower=0> omega;
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
  vector[C] tau = s_tau * tau_raw;
}
model {
  {
    vector[L1] e1 = z1 .* tau[own1];
    vector[L2] e2 = z2 * psi;
    vector[L3] e3 = z3 * omega;
    vector[S1] m1 = csr_matrix_times_vector(S1, L1, wA1, vA1, uA1, e1) ./ n1;
    vector[S2] m2 = csr_matrix_times_vector(S2, L2, wA2, vA2, uA2, e2) ./ n2;
    vector[S3] m3 = csr_matrix_times_vector(S3, L3, wA3, vA3, uA3, e3) ./ n3;
    vector[N] x = theta[cpl]
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
  z1 ~ std_normal();
  z2 ~ std_normal();
  z3 ~ std_normal();
  s_g ~ student_t(3, 0, 2.5);
  target += log_s_g;                                   // Jacobian of s_g = exp(log_s_g)
  tau_raw ~ std_normal();
  s_tau ~ student_t(3, 0, 2.5);
  psi ~ student_t(3, 0, 2.5);
  omega ~ student_t(3, 0, 2.5);
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
    vector[L2] e2 = z2 * psi;
    vector[L3] e3 = z3 * omega;
    vector[S1] m1 = csr_matrix_times_vector(S1, L1, wA1, vA1, uA1, e1) ./ n1;
    vector[S2] m2 = csr_matrix_times_vector(S2, L2, wA2, vA2, uA2, e2) ./ n2;
    vector[S3] m3 = csr_matrix_times_vector(S3, L3, wA3, vA3, uA3, e3) ./ n3;
    vector[L1 + 1] u = append_row(e1 - m1[set1], 0);
    vector[L2 + 1] w = append_row(e2 - m2[set2], 0);
    vector[L3 + 1] v = append_row(e3 - m3[set3], 0);
    vector[PC] x = theta[cPC] + u[j1PC] + w[j2PC] + v[j3PC];
    vector[PC] sV = sqrt(q1PC .* square(tau[cPC]) + q2PC * square(psi) + q3PC * square(omega));
    vector[PC] oPC = o[gPC];
    vector[PC] aPC = a[gPC];
    vector[PC] e = rep_vector(0, PC);
    for (k in 1:K) e += ghw[k] * inv_logit(muPC + sdPC .* (oPC + aPC .* (x + sV * ghx[k])));
    level = log((to_matrix(e, P, C)' * pw) / W);
  }
}
