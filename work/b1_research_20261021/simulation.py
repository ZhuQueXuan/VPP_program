"""Synthetic EV SCM. No empirical calibration; hidden variables never returned to learner."""
from pathlib import Path
import numpy as np
from scipy.special import expit


def curve(x, w, accepted, delay, noise_rng):
    horizon = 3600 + 1800 * (x + 1)
    pmax = 3.5 + .75 * (x + 1)
    edges = np.r_[np.arange(0, horizon, 10.), horizon]
    dt = np.diff(edges)
    left = edges[:-1]
    ref = np.full(len(dt), 3.)
    power = ref.copy()
    opening = (.4 + .2 * (x + 1)) * (.8 + .2 * w * w)
    action = (left >= 600 + delay) & (left < 1800)
    if accepted:
        power[action] -= 1.5 * opening
    debt = np.dot(ref - power, dt)
    remaining = debt
    for j in np.flatnonzero(left >= 1800):
        extra = min(pmax - 3, max(0., remaining) / dt[j])
        power[j] += extra
        remaining -= extra * dt[j]
        if remaining <= 1e-10:
            break
    measured = power + noise_rng.normal(0, .05, len(dt))
    # Factual Y is ALWAYS integrated from public observations, never latent action formula.
    overlap = np.maximum(0, np.minimum(edges[1:], 1800) - np.maximum(left, 600))
    y = np.dot(ref - measured, overlap) / 1800
    return dict(edges=edges, reference=ref, power=power, measured=measured,
                y=y, debt=debt, remaining=remaining, horizon=horizon, pmax=pmax,
                demand=3*horizon/3600)


def generate(protocol, raw_root, process_root):
    seeds = protocol['replicate_seeds']
    names = list(protocol['scenarios'])
    n = protocol['users'] * protocol['events_per_user']
    shape = (len(seeds), len(names), n)
    arrays = {k: np.empty(shape) for k in ('D', 'Y', 'user', 'split')}
    arrays['X'] = np.empty(shape + (2,))
    panel = []
    checks = dict(events=0, max_energy_error_kwh=0., max_bound_violation_kw=0.,
                  minimum_remaining_kws=0., maximum_remaining_kws=0.)
    for ri, seed in enumerate(seeds):
        rng = np.random.default_rng(seed)
        user = np.repeat(np.arange(protocol['users']), protocol['events_per_user'])
        x, w = rng.uniform(-1, 1, (2, n))
        u = rng.uniform(-1, 1, protocol['users'])[user]
        v, assignment = rng.uniform(size=(2, n))
        delays = 10 * rng.integers(0, 7, n)
        shuffled = rng.permutation(protocol['users'])
        user_split = np.empty(protocol['users'], dtype=int)
        user_split[shuffled[:144]] = 0
        user_split[shuffled[144:192]] = 1
        user_split[shuffled[192:]] = 2
        split = user_split[user]
        for si, name in enumerate(names):
            beta = protocol['scenarios'][name]
            prob = expit(1.2*x + .8*w) if name.startswith('observed') else np.full(n, .5)
            d = (assignment < prob).astype(int)
            accepted = v < expit(-.5 + .7*x - .6*w + beta*d + .8*u)
            # Same external noise stream for scenario variants; variants stay in same split.
            noise_rng = np.random.default_rng(seed + 900000)
            y = np.empty(n)
            for j in range(n):
                c = curve(x[j], w[j], accepted[j], delays[j], noise_rng)
                y[j] = c['y']
                err = abs(np.dot(c['power'], np.diff(c['edges'])) / 3600 - c['demand'])
                violation = max(0., -float(c['power'].min()), float(c['power'].max()-c['pmax']))
                checks['events'] += 1
                checks['max_energy_error_kwh'] = max(checks['max_energy_error_kwh'], err)
                checks['max_bound_violation_kw'] = max(checks['max_bound_violation_kw'], violation)
                checks['maximum_remaining_kws'] = max(checks['maximum_remaining_kws'], abs(c['remaining']))
                if ri == 0 and j < 12:
                    panel.append((si, j, x[j], w[j], int(accepted[j]), delays[j], c))
            arrays['D'][ri, si] = d
            arrays['Y'][ri, si] = y
            arrays['user'][ri, si] = user
            arrays['split'][ri, si] = split
            arrays['X'][ri, si] = np.c_[x, w]
    assert checks['max_energy_error_kwh'] < 1e-10 and checks['max_bound_violation_kw'] < 1e-10
    raw_root.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(raw_root/'main_observations.npz', **arrays)
    padded = {k: np.full((len(panel), 721 if k == 'time_edges_s' else 720), np.nan)
              for k in ('time_edges_s', 'reference_kw', 'power_star_kw', 'power_obs_kw')}
    meta = []
    for pi, (si,j,x,w,a,delay,c) in enumerate(panel):
        for key, src in [('time_edges_s','edges'),('reference_kw','reference'),
                         ('power_star_kw','power'),('power_obs_kw','measured')]:
            padded[key][pi,:len(c[src])] = c[src]
        meta.append([si,j,x,w,a,delay,c['horizon'],c['pmax'],c['demand'],c['y']])
    np.savez_compressed(process_root/'evaluator_curves.npz', **padded, meta=np.array(meta))
    # Public observed panel is separate; no noiseless curves/action labels available to extractors.
    np.savez_compressed(raw_root/'observed_curve_panel.npz',
                        time_edges_s=padded['time_edges_s'], reference_kw=padded['reference_kw'],
                        power_obs_kw=padded['power_obs_kw'], indices=np.array(meta)[:,:2])
    return checks
