"""Deterministic checks of arguments, not a performance experiment."""
from pathlib import Path
import importlib.util
import json
import numpy as np

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT.parent / 'ride_b1_v02_reproduction_20261029/source/ride_b1/ride/template.py'
spec = importlib.util.spec_from_file_location('original_ride_template', TEMPLATE)
template = importlib.util.module_from_spec(spec)
spec.loader.exec_module(template)

# The original RIDE operator: distinct template timings yield identical coarse records.
theta_a = np.array([1., 2., 1., 3., 2., 0., 0.])
theta_b = np.array([2., 2., 1., 3., 2., 0., 0.])
starts = np.array([-15., 0., 15.])
ends = starts + 15.
avg_a = template.interval_average(theta_a, 15., starts, ends)
avg_b = template.interval_average(theta_b, 15., starts, ends)
np.testing.assert_allclose(avg_a, avg_b, atol=1e-12, rtol=0)
ta = template.timing(theta_a, 15.)
tb = template.timing(theta_b, 15.)
assert float(ta['t_start']) != float(tb['t_start'])

# In a bin straddling onset, the point interpretation differs from the actual mean.
cross_s = np.array([0.])
cross_e = np.array([2.])
mean_cross = template.interval_average(theta_a, 15., cross_s, cross_e)
point_cross = template.point_sample(theta_a, 15., cross_s, cross_e)
np.testing.assert_allclose(mean_cross, [.125])
np.testing.assert_allclose(point_cross, [0.])
# Within a linear segment, midpoint and average coincide.
linear_s, linear_e = np.array([1.2]), np.array([2.8])
np.testing.assert_allclose(template.interval_average(theta_a, 15., linear_s, linear_e),
                           template.point_sample(theta_a, 15., linear_s, linear_e))

# Fixed task: reference error maps directly to delivery-ratio error.
q_kw, bias_kw, hours = 1.5, .15, .5
ratio_error = bias_kw * hours / (q_kw * hours)
assert abs(ratio_error - .1) < 1e-12

# With a common pre-treatment reference, relative treatment contrasts cancel it.
reference = np.array([3., 4.])
p_zero, p_one = np.array([2.8, 3.7]), np.array([2.5, 3.2])
denominator = np.array([1.5, 2.])
np.testing.assert_allclose((reference-p_one)/denominator - (reference-p_zero)/denominator,
                           (p_zero-p_one)/denominator)

result = {
    'kind': 'deterministic_argument_checks_not_performance_evidence',
    'reference_error_example': {'q_kw': q_kw, 'bias_kw': bias_kw, 'ratio_error': ratio_error},
    'crossing_bin': {'average': mean_cross.tolist(), 'midpoint': point_cross.tolist()},
    'coarse_nonidentifiability': {
        'theta_a': theta_a.tolist(), 'theta_b': theta_b.tolist(),
        'starts_minutes': starts.tolist(), 'ends_minutes': ends.tolist(),
        'observations_a': avg_a.tolist(), 'observations_b': avg_b.tolist(),
        'timings_a': {k: float(ta[k]) for k in ('t_start', 't90', 't_rec')},
        'timings_b': {k: float(tb[k]) for k in ('t_start', 't90', 't_rec')},
        'same_observations': True, 'different_physical_timings': True,
    },
    'common_reference_cancellation_verified': True,
    'all_assertions_passed': True,
}
(ROOT/'argument_checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
