"""Prospective extension of the retained continuous-compensation simulation family.

New confirmation includes a higher-variance positive-duration mechanism and a two-peak signal.
All values are simulated. This changes the response/assignment mechanisms of
the earlier logistic/Beta simulation family; it is not an independent physical
generator or evidence of a field compensation effect. This module generates
no samples and writes no files on import.
"""

import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.special import betaincinv, expit


T = 1800.0
NAMES = ['deadline_slack', 'demand_urgency', 'negative_control']
KINDS = (
    'randomized_saturation', 'observed_saturation', 'nonmonotone',
    'zero_effect', 'sigmoidal', 'assignment_mixture', 'noisy_nonmonotone', 'two_peak',
)


def signal(a, kind):
    """Return the predeclared continuous signal and its analytic derivative."""
    a = np.asarray(a, dtype=float)
    if kind in ('randomized_saturation', 'observed_saturation'):
        scale = 2.4 / (1.0 - np.exp(-3.0))
        return scale * (1.0 - np.exp(-a / 0.8)), scale / 0.8 * np.exp(-a / 0.8)
    if kind in ('nonmonotone', 'noisy_nonmonotone'):
        return 2.0 * np.sin(np.pi * a / 2.4), 2.0 * np.pi / 2.4 * np.cos(np.pi * a / 2.4)
    if kind == 'two_peak':
        return 1.25 + 0.9*np.sin(4*np.pi*a/2.4) + 0.35*a, 0.9*(4*np.pi/2.4)*np.cos(4*np.pi*a/2.4) + 0.35
    if kind == 'zero_effect':
        return np.zeros_like(a), np.zeros_like(a)
    if kind == 'sigmoidal':
        z = expit(4.0 * (a - 1.2))
        return 2.4 * z, 9.6 * z * (1.0 - z)
    if kind == 'assignment_mixture':
        return 1.8 * np.sin(1.4 * a) + 0.35 * a, 2.52 * np.cos(1.4 * a) + 0.35
    raise ValueError('Unknown predeclared mechanism: ' + str(kind))


def mean_parts(a, l, u, h, kind):
    s, ds = signal(a, kind)
    p = expit(-1.15 + 0.85 * s * (1.0 + 0.3 * l) + 0.35 * l - 0.45 * u + 0.20 * h)
    mu = expit(-0.55 + 0.65 * s + 0.3 * l - 0.2 * u + 0.15 * h)
    full = expit(-3.0 + 0.5 * s)
    dp = p * (1.0 - p) * 0.85 * (1.0 + 0.3 * l) * ds
    dmu = mu * (1.0 - mu) * 0.65 * ds
    dfull = full * (1.0 - full) * 0.5 * ds
    return p, mu, full, dp, dmu, dfull


def generate(seed, kind, users=240, events=2):
    """Generate a cohort; equal seeds denote paired mechanism variants.

    Every primitive random draw is made in the same order before evaluating
    any mechanism. Beta fractions use a shared uniform through the inverse
    CDF, so changing Beta shape parameters does not alter a rejection sampler's
    RNG consumption and destroy the intended pairing.
    """
    if kind not in KINDS:
        raise ValueError('Unknown predeclared mechanism: ' + str(kind))
    rng = np.random.default_rng(seed)
    g = np.repeat(np.arange(users), events)
    n = len(g)
    x = rng.uniform(-1.0, 1.0, (n, 3))
    h = rng.uniform(-0.6, 0.6, users)[g]
    uniform_amount = rng.uniform(0.0, 2.4, n)
    assignment_noise = rng.normal(size=n)
    mixture_sign = np.where(rng.random(n) < 0.5, -1.0, 1.0)
    response_uniform = rng.random(n)
    full_uniform = rng.random(n)
    beta_uniform = rng.random(n)

    z = 0.5 * x[:, 0] - 0.4 * x[:, 1] + 1.25 * assignment_noise
    if kind == 'assignment_mixture':
        z = z + 0.65 * mixture_sign
    a = uniform_amount if kind == 'randomized_saturation' else 2.4 * expit(z)
    p, mu, full, _, _, _ = mean_parts(a, x[:, 0], x[:, 1], h, kind)
    concentration = 5.0 if kind == 'noisy_nonmonotone' else 20.0
    beta_fraction = betaincinv(concentration * mu, concentration * (1.0 - mu), beta_uniform)
    fraction = np.where(response_uniform < p, np.where(full_uniform < full, 1.0, beta_fraction), 0.0)
    return dict(
        seed=int(seed), mechanism=kind, covariate_names=NAMES,
        X=x.tolist(), treatment=a.tolist(), outcome=(T * fraction).tolist(),
        users=[f'stability-{seed}-user{j:04d}' for j in g],
        known_density=np.full(n, 1.0 / 2.4).tolist() if kind == 'randomized_saturation' else None,
        reference_status='new simulation, no field compensation labels',
        pairing='same-seed mechanisms share exogenous draws and users; not independent replications',
        adjustment_roles=dict(deadline_slack='pre-treatment confounder under observed assignment',
                              demand_urgency='pre-treatment confounder under observed assignment',
                              negative_control='independent diagnostic, not a required confounder'),
        latent_h_role='shared-user outcome heterogeneity independent of compensation assignment',
    )


def population(points, kind, nodes=15, derivative=0):
    """Integrate the all-user potential mean or analytic amount derivative.

    L,U are independent Uniform[-1,1], and H is Uniform[-.6,.6]. The third
    observed negative control does not enter the outcome, so it integrates out.
    """
    if derivative not in (0, 1):
        raise ValueError('Only the mean and its first analytic derivative are defined')
    points = np.atleast_1d(np.asarray(points, dtype=float))
    z, w = leggauss(nodes)
    l, u, h = np.meshgrid(z, z, 0.6 * z, indexing='ij')
    wl, wu, wh = np.meshgrid(w, w, w, indexing='ij')
    l, u, h = l.ravel(), u.ravel(), h.ravel()
    weight = (wl * wu * wh).ravel() / 8.0
    values = []
    for a in points:
        p, mu, full, dp, dmu, dfull = mean_parts(a, l, u, h, kind)
        positive_mean = full + (1.0 - full) * mu
        if derivative:
            positive_derivative = dfull * (1.0 - mu) + (1.0 - full) * dmu
            value = T * (dp * positive_mean + p * positive_derivative)
        else:
            value = T * p * positive_mean
        values.append(float(weight @ value))
    return np.asarray(values)


def truth(points, kind, reference=0.3, nodes=15):
    points = np.atleast_1d(np.asarray(points, dtype=float))
    mean = population(points, kind, nodes=nodes)
    reference_mean = float(population([reference], kind, nodes=nodes)[0])
    return dict(
        incentive_values=points.tolist(), reference_incentive=float(reference),
        mean=mean.tolist(), contrasts=(mean - reference_mean).tolist(),
        derivative=population(points, kind, nodes=nodes, derivative=1).tolist(),
        outcome_unit='seconds', quadrature_nodes_per_axis=int(nodes),
        derivative_method='analytic signal and logistic-chain derivative, integrated independently',
    )
