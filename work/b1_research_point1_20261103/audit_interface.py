"""Independent contract fixtures for the direct-duration bridge, no fitting."""
from pathlib import Path
import copy
import json
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'B1算法'))
from b1_algorithm.factors import EVFactorStudy, _inputs
from b1_algorithm.contracts import SCHEMA, VERSION


def fixture():
    task = dict(task_id='independent-contract-fixture', user_id='fixture-user', meter_id='fixture-meter',
                start_min=0., end_min=30., request_kw=1.5, notice_min=-15., task_pre_treatment=True)
    curve = np.zeros(360)
    curve[90:95] = .5
    duration = dict(cumulative_response_seconds=60., longest_continuous_response_seconds=60.)
    process = dict(status='ok', method='B1_effective_response_refined', task_id=task['task_id'],
                   task_duration_min=30., request_kw=1.5,
                   selection_evidence=dict(meter_delta_min=1/6, policy='effective_response_refined'),
                   analysis_profile=dict(onset_fraction=.1, dwell_seconds=30., observation_pre_min=15., observation_post_min=15.),
                   features=dict(selected_curve=dict(duration),
                                 structural_curve=dict(cumulative_response_seconds=50., longest_continuous_response_seconds=50.),
                                 sources=dict(duration='gap_aware_direct_duration_calibration')),
                   duration_estimates=dict(duration), reduction_interval_kw=curve.tolist(),
                   duration_calibration=dict(duration, duration_values_changed=True), eta_raw=.05)
    event = dict(schema_version=SCHEMA, algorithm_version=VERSION, status='ok', task=task,
                 process=process, reference=dict(reference_status='provided'))
    factor = dict(task_id=task['task_id'], user_id=task['user_id'], meter_id=task['meter_id'],
                  treatment_set_min=-15., offered_incentive=.8, deadline_slack=.5, demand_urgency=-.2,
                  available_at_min=dict(offered_incentive=-15., deadline_slack=-16., demand_urgency=-16.),
                  state_as_of_min=dict(deadline_slack=-16., demand_urgency=-16.))
    return event, factor


checks = []
event, factor = fixture()
study = EVFactorStudy('independent-direct', 'yuan/kWh', outcome_source='duration_estimates')
data = _inputs([event], [factor], study)
assert data['y'].tolist() == [60.]
checks.append('direct60 accepted although structural threshold integral50')


def rejects(label, item, chosen=study):
    try:
        _inputs([item], [factor], chosen)
    except (ValueError, KeyError, TypeError):
        checks.append(label)
    else:
        raise AssertionError(label+' unexpectedly accepted')


rejects('legacy selected_curve still requires its structural integral', event,
        EVFactorStudy('independent-legacy', 'yuan/kWh', outcome_source='selected_curve'))
bad = copy.deepcopy(event)
bad['process']['duration_estimates']['cumulative_response_seconds'] = 70.
rejects('direct-feature echo mismatch rejected', bad)
bad = copy.deepcopy(event)
for where in ['duration_estimates']:
    bad['process'][where]['cumulative_response_seconds'] = 65.
bad['process']['features']['selected_curve']['cumulative_response_seconds'] = 65.
rejects('off-meter-grid65 seconds rejected', bad)
bad = copy.deepcopy(event)
bad['process']['duration_estimates']['longest_continuous_response_seconds'] = 80.
bad['process']['features']['selected_curve']['longest_continuous_response_seconds'] = 80.
rejects('longest80 exceeding cumulative60 rejected', bad)
old, _ = fixture()
old['process']['features']['selected_curve'].update(cumulative_response_seconds=50., longest_continuous_response_seconds=50.)
oldstudy = EVFactorStudy('independent-old-valid', 'yuan/kWh', outcome_source='selected_curve')
assert np.allclose(_inputs([old], [factor], oldstudy)['y'], [50.])
checks.append('legitimate legacy curve50 remains accepted')
result = dict(status='passed', checks=checks, model_fit=False,
              data='new hand-constructed API contract fixtures, not physical accuracy evidence')
with (HERE/'audit_interface_result.json').open('x', encoding='utf-8') as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
print(json.dumps(result, ensure_ascii=False))
