// Latent quality (or log cost) of (model, effort) couples, fused from heterogeneous benchmarks. Method: METHODOLOGY.md §5;
// data preparation: lqm.py. For every row r (group b, couple c of model m, publisher s, task type t):
//
//   f(y_r) = o_b + a_b · (θ_c + u_{s,c} + w_{s,m} + v_{c,t}) + ε_r ,   ε_r ~ Student-t_ν(0, κ_r · h_r² · σ_b²)
//
// θ sums to zero: no couple is a reference, the reference couple of the page is a divisor applied afterwards.
// h_r is the shape of the sampling noise of an empirical logit, 1/(2·√(q(1−q))) at the observed proportion q (1 on
// other scales); κ_r the variance multiplier of an early-access run, estimated.
functions {
  // log of the Mills ratio of the standard normal, log(Phi_c(b)) + b^2/2, stable for any b
  real log_mills(real b) {
    if (b < 25) return std_normal_lccdf(b) + 0.5 * square(b);
    real ib2 = inv_square(b);
    return -log(b) - 0.5 * log(2 * pi()) + log1p(-ib2 + 3 * square(ib2) - 15 * ib2 * square(ib2));
  }
  vector centre_within(vector e, array[] int set, int S) {   // e minus the mean of its set
    vector[S] tot = rep_vector(0, S);
    vector[S] n = rep_vector(0, S);
    for (i in 1:num_elements(e)) {
      tot[set[i]] += e[i];
      n[set[i]] += 1;
    }
    vector[num_elements(e)] out;
    for (i in 1:num_elements(e)) out[i] = e[i] - tot[set[i]] / n[set[i]];
    return out;
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
  vector<lower=0>[G] noise_floor;                  // σ_b never below the metric's resolution
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
  vector[G] log_floor = log(noise_floor);
  int has_ea = max(ea);
  // Parameterisation (the model is unchanged), both axes: noise log σ_b centred in every group (in non-centred form
  // μ_σ, s_σ move every σ_b — and on the quality axis, through a_b = exp(s_g·lg_b + log σ_b), every gain, which the
  // data pin); gain log a_b centred in data-rich groups (≥ 20 rows), non-centred elsewhere.
  array[G] int n_rows = rep_array(0, G);
  for (r in 1:N) n_rows[grp[r]] += 1;
  array[G] int cg;
  array[G] int cs;
  for (b in 1:G) {
    cg[b] = n_rows[b] >= 20;
    cs[b] = 1;
  }
  vector[G] cgv = to_vector(cg);
  vector[G] csv = to_vector(cs);
  int nCG = sum(cg);
  int nCS = sum(cs);
  array[nCG] int iCG;
  array[G - nCG] int iNG;
  array[nCS] int iCS;
  array[G - nCS] int iNS;
  {
    int p = 1; int q = 1;
    for (b in 1:G) if (cg[b]) { iCG[p] = b; p += 1; } else { iNG[q] = b; q += 1; }
    p = 1; q = 1;
    for (b in 1:G) if (cs[b]) { iCS[p] = b; p += 1; } else { iNS[q] = b; q += 1; }
  }
  array[N] int j1;
  array[N] int j2;
  array[N] int j3;
  for (r in 1:N) {                                 // index L + 1 = a padded zero: the row carries no such effect
    j1[r] = k1[r] == 0 ? L1 + 1 : k1[r];
    j2[r] = k2[r] == 0 ? L2 + 1 : k2[r];
    j3[r] = k3[r] == 0 ? L3 + 1 : k3[r];
  }
  real theta_scale = 10 / sqrt(1 - 1.0 / C);       // marginal sd 10 for every component of a sum-to-zero vector
}
parameters {
  sum_to_zero_vector[C] theta;
  vector[G] o;                                     // group offset, flat prior
  vector[G] lg_raw;                                // cg=0: non-centred log gain; cg=1: log a_b itself
  real<lower=0> s_g;
  vector[L1] z1;                                   // non-centred effects
  vector[L2] z2;
  vector[L3] z3;
  vector<lower=0>[C] tau_raw;                      // τ_c = s_τ · τ̃_c (non-centred)
  real<lower=0> s_tau;
  real<lower=0> psi;
  real<lower=0> omega;
  real<lower=1> nu;
  array[has_ea] real log_kappa;
  real mu_sig;
  real<lower=0> s_sig;
  vector<lower=0>[G] ls_ex;                        // excess over the floor bound: cs=0: η_b − b_b (non-centred); cs=1: log σ_b − log floor_b
}
transformed parameters {
  vector[G] log_sigma = log_floor + (csv + (1 - csv) * s_sig) .* ls_ex;
  vector[G] sigma = exp(log_sigma);
  vector[G] a = exp(cgv .* lg_raw + (1 - cgv) .* (cost ? s_g * lg_raw : s_g * lg_raw + log_sigma));
  vector[C] tau = s_tau * tau_raw;
}
model {
  vector[L1 + 1] u = append_row(centre_within(z1 .* tau[own1], set1, S1), 0);
  vector[L2 + 1] w = append_row(centre_within(z2 * psi, set2, S2), 0);
  vector[L3 + 1] v = append_row(centre_within(z3 * omega, set3, S3), 0);
  vector[N] x = theta[cpl] + u[j1] + w[j2] + v[j3];
  vector[N] scale = sigma[grp] .* h;
  if (has_ea)
    for (r in 1:N)
      if (ea[r]) scale[r] *= exp(0.5 * log_kappa[1]);
  z ~ student_t(nu, o[grp] + a[grp] .* x, scale);

  theta ~ normal(0, theta_scale);
  lg_raw[iNG] ~ std_normal();
  if (cost) lg_raw[iCG] ~ normal(0, s_g); else lg_raw[iCG] ~ normal(log_sigma[iCG], s_g);
  z1 ~ std_normal();
  z2 ~ std_normal();
  z3 ~ std_normal();
  // weakly informative half-Student-t(3, 0, 2.5) priors on every standard deviation (Gelman 2006; the brms default,
  // Bürkner 2017); unit 1 = one typical benchmark noise on the θ scale (quality), a factor e (cost, log gains)
  s_g ~ student_t(3, 0, 2.5);
  tau_raw ~ std_normal();
  s_tau ~ student_t(3, 0, 2.5);
  psi ~ student_t(3, 0, 2.5);
  omega ~ student_t(3, 0, 2.5);
  nu ~ gamma(2, 0.1);                              // Juárez & Steel (2010)
  if (has_ea) log_kappa[1] ~ normal(0, 1);         // centred on no inflation
  // noise pooled across groups on their standardised scale (invariant to any affine change of a metric):
  // log σ_b ~ N(μ_σ, s_σ²) truncated at the floor; μ_σ flat
  s_sig ~ student_t(3, 0, 2.5);
  {
    // truncated N(μ_σ, s_σ²) on log σ_b, b_b = (log floor_b − μ_σ)/s_σ, written without cancelling infinities:
    // log φ(b + e) − log Φc(b) = −e (b + e/2) − log M(b)   (constant −½ log 2π dropped)
    vector[G] bnd = (log_floor - mu_sig) / s_sig;
    vector[G] e = csv .* ls_ex / s_sig + (1 - csv) .* ls_ex;
    for (b in 1:G) target += -e[b] * (bnd[b] + 0.5 * e[b]) - log_mills(bnd[b]);
    target += -nCS * log(s_sig);                   // centred groups: density of log σ_b = (1/s_σ) × density of η_b
  }
}
generated quantities {
  // read-out on the log scale, per couple. Quality: log of the expected score averaged over the panel.
  // Cost: θ (log cost on a task of typical elasticity; effects have mean 0 on the log scale).
  vector[C] level;
  // what one NEW source would report for the couple on the same read-out: fresh publisher × couple, publisher ×
  // model and (per task type) couple × task-type effects drawn from their laws; no reference couple involved
  vector[C] level_new;
  if (cost) {
    level = theta;
    for (c in 1:C)
      level_new[c] = theta[c] + normal_rng(0, tau[c]) + normal_rng(0, psi) + normal_rng(0, omega);
  } else {
    vector[L1 + 1] u = append_row(centre_within(z1 .* tau[own1], set1, S1), 0);
    vector[L2 + 1] w = append_row(centre_within(z2 * psi, set2, S2), 0);
    vector[L3 + 1] v = append_row(centre_within(z3 * omega, set3, S3), 0);
    real W = sum(pw);
    for (c in 1:C) {
      real s = 0;
      for (p in 1:P) {
        int b = pg[p];
        real x = theta[c];
        real V = 0;
        if (r1[p, c] > 0) x += u[r1[p, c]]; else V += square(tau[c]);
        if (r2[p, c] > 0) x += w[r2[p, c]]; else V += square(psi);
        if (has_v[p]) {
          if (r3[p, c] > 0) x += v[r3[p, c]]; else V += square(omega);
        }
        real e = 0;
        for (k in 1:K)
          e += ghw[k] * inv_logit(mu[b] + sd[b] * (o[b] + a[b] * (x + sqrt(V) * ghx[k])));
        s += pw[p] * e;
      }
      level[c] = log(s / W);
    }
    {
      vector[P] vt;
      for (c in 1:C) {
        real un = normal_rng(0, tau[c]);
        real wn = normal_rng(0, psi);
        real s = 0;
        for (p in 1:P) vt[p] = has_v[p] ? normal_rng(0, omega) : 0;
        for (p in 1:P) {
          int b = pg[p];
          s += pw[p] * inv_logit(mu[b] + sd[b] * (o[b] + a[b] * (theta[c] + un + wn + vt[ptype[p]])));
        }
        level_new[c] = log(s / W);
      }
    }
  }
}
