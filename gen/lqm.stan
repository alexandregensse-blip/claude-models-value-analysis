// Latent quality (or log cost) of (model, effort) couples, fused from heterogeneous benchmarks. See lqm.py and
// METHODOLOGY.md §5. For every row r (group b, couple c of model m, publisher s, task type t):
//
//   f(y_r) = o_b + a_b · (θ_c + u_{s,c} + w_{s,m} + v_{c,t}) + ε_r ,   ε_r ~ Student-t₄(0, m_r · σ_b²)
//
// θ sums to zero: no couple is a reference. The unit of θ is set by the gain prior (mean log gain 0).
data {
  int<lower=1> N;                                  // rows
  int<lower=1> G;                                  // groups
  int<lower=2> C;                                  // couples
  int<lower=0, upper=1> cost;                      // 1 = cost axis, 0 = quality axis
  array[N] int<lower=1, upper=G> grp;
  array[N] int<lower=1, upper=C> cpl;
  vector[N] z;                                     // f(y), prescaled per group (the model is affine-invariant)
  vector<lower=0>[N] m;                            // variance multiplier: 3 for an early-access run, else 1
  int<lower=0> L1;                                 // publisher × couple levels
  int<lower=0> L2;                                 // publisher × model levels
  int<lower=0> L3;                                 // couple × task-type levels
  array[N] int<lower=0, upper=L1> k1;              // level of each row, 0 = none
  array[N] int<lower=0, upper=L2> k2;
  array[N] int<lower=0, upper=L3> k3;
  array[L1] int<lower=1, upper=C> own1;            // couple of each publisher × couple level (τ² is per couple)
  vector<lower=0>[G] noise_floor;                  // σ_b never below the metric's resolution
  // panel read-out (quality axis): the groups a quality is read on, their weights and their prescaling
  vector<lower=0>[G] panel_w;                      // 0 outside the panel
  vector[G] mu;
  vector<lower=0>[G] sd;
}
transformed data {
  vector[N] sm = sqrt(m);
  vector[G] log_floor = log(noise_floor);
  array[N] int j1;
  array[N] int j2;
  array[N] int j3;
  for (r in 1:N) {                                 // index L + 1 = a padded zero: the row carries no such effect
    j1[r] = k1[r] == 0 ? L1 + 1 : k1[r];
    j2[r] = k2[r] == 0 ? L2 + 1 : k2[r];
    j3[r] = k3[r] == 0 ? L3 + 1 : k3[r];
  }
  real W = sum(panel_w);
}
parameters {
  sum_to_zero_vector[C] theta;
  vector[G] o;                                     // group offset, flat prior
  vector[G] lg;                                    // quality: log discrimination log(a/σ); cost: log gain log a
  vector<lower=log_floor>[G] log_sigma;
  vector[L1] z1;                                   // non-centred effects
  vector[L2] z2;
  vector[L3] z3;
  vector<lower=0>[C] tau2;
  real<lower=0> beta;
  real<lower=0> psi2;
  real<lower=0> om2;
  real<lower=0> s2g;                               // s_d² (quality) or s_a² (cost)
  array[cost] real mu_sig;
  array[cost] real<lower=0> s2_sig;
}
transformed parameters {
  vector[G] sigma = exp(log_sigma);
  vector[G] a = cost ? exp(lg) : exp(lg + log_sigma);
}
model {
  vector[L1 + 1] u = append_row(z1 .* sqrt(tau2[own1]), 0);
  vector[L2 + 1] w = append_row(z2 * sqrt(psi2), 0);
  vector[L3 + 1] v = append_row(z3 * sqrt(om2), 0);
  vector[N] x = theta[cpl] + u[j1] + w[j2] + v[j3];
  z ~ student_t(4, o[grp] + a[grp] .* x, sigma[grp] .* sm);

  theta ~ normal(0, 10);
  z1 ~ std_normal();
  z2 ~ std_normal();
  z3 ~ std_normal();
  tau2 ~ inv_gamma(2, beta);
  beta ~ exponential(20);                          // mean 0.05
  psi2 ~ inv_gamma(1, 0.01);
  om2 ~ inv_gamma(1, 0.01);
  s2g ~ inv_gamma(1, 0.25);
  lg ~ normal(0, sqrt(s2g));
  if (cost) {                                      // log σ_b ~ N(μ_σ, s_σ²) truncated at the floor; μ_σ flat
    s2_sig[1] ~ inv_gamma(1, 0.25);
    log_sigma ~ normal(mu_sig[1], sqrt(s2_sig[1]));
    target += -normal_lccdf(log_floor | mu_sig[1], sqrt(s2_sig[1]));
  }
  // quality: Jeffreys 1/σ above the floor = flat on log σ (nothing to add)
}
generated quantities {
  // read-out on the log scale, per couple: quality = log of the mean predicted score over the panel;
  // cost = θ (log cost on a task of typical elasticity). Ratios between couples are differences of `level`.
  vector[C] level;
  if (cost) {
    level = theta;
  } else {
    for (c in 1:C) {
      real s = 0;
      for (b in 1:G)
        if (panel_w[b] > 0)
          s += panel_w[b] * inv_logit(mu[b] + sd[b] * (o[b] + a[b] * theta[c]));
      level[c] = log(s / W);
    }
  }
}
