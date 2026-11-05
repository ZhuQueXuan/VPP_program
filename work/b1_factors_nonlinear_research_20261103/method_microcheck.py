"""Mathematical feasibility checks, not an estimator-performance experiment.

Independent equation implementation; no downloaded author code is executed.
Uses only new constructed arrays and analytic integrals, never prior datasets.
"""
from pathlib import Path
import json
import hashlib
import math
import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.optimize import brentq

HERE = Path(__file__).resolve().parent


def kernel(z):
    return .75 * (1-z*z) * (np.abs(z) <= 1)


def score(d, y, m_at_a, beta_at_a, observed_density, a, h):
    z = (d-a)/h
    return beta_at_a + z*kernel(z)/(h*h*.2*observed_density)*(y-m_at_a-(d-a)*beta_at_a)


def mu(d, x):
    return 350 + 85*d + 45*d*d + 30*x[0] + 35*d*x[1] + 25*x[1]*x[1]


def beta(a, x):
    return 85 + 90*a + 35*x[1]


def density(d, x):
    lam = .4*x[0]-.3*x[1]
    if abs(lam) < 1e-10:
        return np.ones_like(d)/2.4
    return lam*np.exp(lam*d)/np.expm1(2.4*lam)


# Eq(8): nonuniform assignment density at the observed treatment.
rng = np.random.default_rng(90321001)
n = 97
x = rng.uniform(-1, 1, (n, 2))
d = rng.uniform(.01, 2.39, n)
y = mu(d, x.T) + rng.normal(0, 3, n)
grid = np.array([.4, .73, 1.17, 1.65, 2.])
h = .24
vector = []
scalar = []
for a in grid:
    q = score(d, y, mu(a, x.T), beta(a, x.T), density(d, [0., 0.]), a, h)
    vector.append(float(q.mean()))
    acc = 0.
    for i in range(n):
        z = (d[i]-a)/h
        k = .75*(1-z*z) if abs(z) <= 1 else 0.
        residual = y[i]-mu(a, x[i])-(d[i]-a)*beta(a, x[i])
        acc += beta(a, x[i]) + z*k*residual/(h*h*.2*(1/2.4))
    scalar.append(acc/n)
max_scalar_error = float(np.max(np.abs(np.array(vector)-scalar)))
assert max_scalar_error < 1e-10

# Exact integration check: correct density rescues a misspecified flat mean.
# For this quadratic conditional mean, symmetric compact-kernel bias is zero.
z, w = leggauss(80)
quadrature = []
for a in grid:
    dt = a+h*z
    xi = np.array([.6, -.4])
    p = density(dt, xi)
    true_derivative = float(beta(a, xi))
    correct_mean = score(dt, mu(dt, xi), mu(a, xi), beta(a, xi), p, a, h)
    flat_mean = score(dt, mu(dt, xi), np.zeros_like(dt), np.zeros_like(dt), p, a, h)
    oracle_value = float(np.sum(w*h*p*correct_mean) + true_derivative*(1-np.sum(w*h*p)))
    flat_value = float(np.sum(w*h*p*flat_mean))
    # RA beta contributes for all d, including d outside the kernel support.
    assert abs(oracle_value-true_derivative) < 1e-9
    assert abs(flat_value-true_derivative) < 1e-9
    quadrature.append(dict(amount=float(a), analytic=true_derivative,
                           oracle_mean=oracle_value, flat_mean_correct_density=flat_value))

# Same query must not change when unrelated plotting amounts are inserted.
query_a = .73
q1 = score(d, y, mu(query_a, x.T), beta(query_a, x.T), np.full(n, 1/2.4), query_a, h).mean()
extra_grid = np.sort(np.r_[grid, .51, .92, 1.93])
q2 = [score(d, y, mu(a, x.T), beta(a, x.T), np.full(n, 1/2.4), a, h).mean()
      for a in extra_grid][int(np.flatnonzero(extra_grid == query_a)[0])]
assert abs(q1-q2) < 1e-12

# Observational equivalence with disjoint subgroup support.
# Both worlds give identical outcome distributions on observed support.
# The smooth bump changes only the unobserved high-dose outcomes of X=0.
def bump(a):
    a = np.asarray(a)
    return np.where(a > 1., np.exp(-1/np.maximum(a-1., 1e-15)**2), 0.)


def conditional(a, group, world):
    return 250+200*np.asarray(a) + (450*bump(a)*(1-group) if world == 'B' else 0.)


obs0 = np.linspace(0., 1., 201)
obs1 = np.linspace(1.4, 2.4, 201)
max_observed_difference = max(float(np.max(abs(conditional(obs0, 0, 'A')-conditional(obs0, 0, 'B')))),
                              float(np.max(abs(conditional(obs1, 1, 'A')-conditional(obs1, 1, 'B')))))
assert max_observed_difference == 0.
mean_curve = lambda a, world: .5*(conditional(a, 0, world)+conditional(a, 1, world))
curve_grid = np.linspace(0., 2.4, 241)
gap = float(np.max(abs(mean_curve(curve_grid, 'A')-mean_curve(curve_grid, 'B'))))
target = 650.
roots = {world: float(brentq(lambda a: mean_curve(a, world)-target, 0, 2.4)) for world in ['A', 'B']}
assert abs(roots['A']-roots['B']) > .1

result = dict(
    status='passed_mathematical_microchecks_only', source_equation='Zhang-Chen arXiv2501.06969v2 Eq8',
    kernel='Epanechnikov .75*(1-u^2), compact support [-1,1], kappa2=1/5',
    trained_models=0, experimental_sample_generation=False, old_test_files_read=False,
    first_block_or_production_modified=False,
    vector_scalar_max_difference=max_scalar_error,
    analytic_integral_checks=quadrature, arbitrary_query_insertion_difference=float(abs(q1-q2)),
    unidentified_support_example=dict(observed_world_difference=max_observed_difference,
        population_curve_max_difference_seconds=gap, target_seconds=target, target_crossings=roots,
        interpretation='identical observed conditional distributions allow different population curves and thresholds; no empirical accuracy claim'),
    scope='formula and identification feasibility; not a fitted benchmark, discovery result or confidence coverage study',
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
)
with (HERE/'method_microcheck.json').open('x', encoding='utf-8') as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
print(json.dumps(result, ensure_ascii=False))
