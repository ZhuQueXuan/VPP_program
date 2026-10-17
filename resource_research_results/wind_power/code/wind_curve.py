"""Fixed statistical wind-power curve evaluation; Python standard library only.

Input is contemporaneous published mean wind, NOT a future forecast. Parameters
describe the six studied units in mixed observed conditions, not available power.
"""
import bisect
import math


def evaluate(parameters, unit, wind_mps):
    if isinstance(unit, bool) or str(unit) not in parameters['units']:
        raise ValueError('unit must identify one of the six calibrated units')
    if isinstance(wind_mps, bool):
        raise ValueError('wind_mps must be a finite nonnegative number')
    v = float(wind_mps)
    if not math.isfinite(v) or v < 0:
        raise ValueError('wind_mps must be a finite nonnegative number')
    p = parameters['units'][str(unit)]
    xs, ys = p['knot_wind_mps'], p['knot_power_kW']
    j = bisect.bisect_right(xs, v)
    if j == 0:
        y = ys[0]
    elif j == len(xs):
        y = ys[-1]
    else:
        w = (v-xs[j-1])/(xs[j]-xs[j-1])
        y = ys[j-1]+w*(ys[j]-ys[j-1])
    bin_id = math.floor(v/parameters['bin_width_mps'])
    counts = dict(zip(p['bin_ids'], p['bin_counts']))
    return {
        'power_kW': y,
        'outside_training_wind': v < p['training_wind_min_mps'] or v > p['training_wind_max_mps'],
        'outside_knot_centres': v < xs[0] or v > xs[-1],
        'training_bin_count': counts.get(bin_id, 0),
        'rare_or_unseen_bin': counts.get(bin_id, 0) < 20,
    }


def baselines(parameters, unit, wind_mps):
    v = float(wind_mps)
    p = parameters['units'][str(unit)]
    a, b = p['B_LINEAR']; c, d = p['B_CUBIC']
    return {'B_LINEAR': a+b*v, 'B_CUBIC': c+d*v**3}
