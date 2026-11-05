"""Contract and numerical controls for the frozen, single reference candidate."""
import os
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import sys
import json
import hashlib
from pathlib import Path
from dataclasses import replace, FrozenInstanceError
import numpy as np
from sklearn.preprocessing import SplineTransformer, StandardScaler
from sklearn.linear_model import Ridge

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'B1算法'))
from b1_algorithm.reference.core import ReferenceWindow, WindowCalibrationRecord
from b1_algorithm.reference.reliable import (
    FrozenEVReferenceModel, fit_ev_reference_error_model,
    predict_ev_reliable_reference, save_ev_reliable_reference_model,
    load_ev_reliable_reference_model, _features, _basis, _spline_knots, _json)

OUT = Path(__file__).resolve().parent
checks = []


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)


def rejects(name, function):
    try:
        function()
    except (ValueError, TypeError, FileExistsError, FrozenInstanceError):
        checks.append(name)
    else:
        raise AssertionError(name + ': unexpectedly accepted')


def fixture(i, level=3., task=None):
    task = float(1000 + 200*i if task is None else task)
    starts = task + np.arange(-15., 45.)
    pre = task + np.arange(-75., -15.)
    return ReferenceWindow(
        task_id='task-' + str(i), user_id='user-' + str(i), meter_id='meter-' + str(i),
        resource_type='EV', task_start_min=task, task_end_min=task+30., request_kw=1.5,
        notice_min=task-15., starts_min=starts, ends_min=starts+1.,
        pre_starts_min=pre, pre_ends_min=pre+1., pre_power_kw=np.full(60, level),
        pre_available_min=task-15., prior_mean_kw=np.full(60, level),
        prior_available_min=task-100., prior_source_count=2,
        prior_source_ids=('history-' + str(i) + '-a', 'history-' + str(i) + '-b'),
        clock_hour=12., weekday=2, calendar_available_min=task-75.,
        temperature_c=25., temperature_available_min=task-75.)


def record(w, y=None):
    return WindowCalibrationRecord(w, np.asarray(w.pre_power_kw) if y is None else y,
                                   float(np.max(w.ends_min)), True)


def unavailable(name, model, window, reason=None):
    prediction = predict_ev_reliable_reference(model, window)
    check(name, prediction.reference_status == 'unavailable')
    if reason is not None:
        check(name + ' reason', reason in ','.join(prediction.reasons))


def main():
    midpoint = (np.arange(-15., 45.) + .5)[:, None]
    transformer = SplineTransformer(n_knots=5, degree=3, knots='uniform',
                                    include_bias=False, extrapolation='error').fit(midpoint)
    check('native knots equal sklearn', np.array_equal(_spline_knots(), transformer.bsplines_[0].t))
    check('native B-spline equals sklearn', np.array_equal(_basis(_spline_knots()), transformer.transform(midpoint)))

    constant = [record(fixture(i, level=2.+i)) for i in range(3)]
    model = fit_ev_reference_error_model(constant, 1500.)
    query = fixture(20, level=4., task=5000.)
    pred = predict_ev_reliable_reference(model, query)
    check('constant reference exact', pred.reference_status == 'available' and np.array_equal(pred.reference_kw, np.full(60, 4.)))
    check('identity binding', (pred.task_id, pred.user_id, pred.meter_id) == (query.task_id, query.user_id, query.meter_id))
    check('time/task binding', (pred.task_start_min, pred.task_end_min, pred.request_kw, pred.notice_min, pred.available_at_min) == (5000., 5030., 1.5, 4985., 4985.))
    check('no fabricated uncertainty', pred.window_band_eta is None and pred.pointwise_noise_sigma_kw is None and pred.counterfactual_identified is False)
    check('readonly result arrays', all(not a.flags.writeable for a in (pred.starts_min, pred.ends_min, pred.reference_kw)))
    check('unseen role', pred.role == 'unseen_user')
    check('legal seen-user query allowed', predict_ev_reliable_reference(model, replace(query, user_id='user-0')).role == 'seen_training_user')

    # Vary centered prefix blocks and historical shapes without simulator fields.
    rich = []
    for i in range(12):
        w = fixture(i, level=3.+.05*i)
        pattern = np.repeat(np.asarray([-.3, .1, .3, -.1])*(1.+i/10.), 15)
        prior = np.asarray(w.prior_mean_kw) + np.linspace(-.4, .4, 60)*(1.+i/12.)
        w = replace(w, pre_power_kw=np.asarray(w.pre_power_kw)+pattern, prior_mean_kw=prior)
        x, anchor, _, _ = _features(w, _basis(_spline_knots()))
        y = anchor + x @ np.linspace(-.06, .08, x.shape[1]) + .03
        rich.append(record(w, y))
    fitted = fit_ev_reference_error_model(rich, 3300., seed=17)
    x = np.concatenate([_features(r.window, _basis(_spline_knots()))[0] for r in rich])
    y = np.concatenate([np.asarray(r.observed_non_event_power_kw)-np.mean(r.window.pre_power_kw) for r in rich])
    scaler = StandardScaler().fit(x)
    reg = Ridge(alpha=10., fit_intercept=True, solver='cholesky').fit(scaler.transform(x), y)
    payload = json.loads(fitted.payload_json)
    check('full-grid Ridge coefficients exact', np.array_equal(payload['coefficients'], reg.coef_))
    check('Ridge intercept exact', payload['intercept'] == float(reg.intercept_))
    check('all 60 rows per training record', payload['n_training_rows'] == 720)
    rich_query = replace(query, pre_power_kw=np.asarray(rich[4].window.pre_power_kw), prior_mean_kw=np.asarray(rich[4].window.prior_mean_kw))
    result = predict_ev_reliable_reference(fitted, rich_query)
    shifted_query = replace(rich_query, pre_power_kw=np.asarray(rich_query.pre_power_kw)+2.75,
                            prior_mean_kw=np.asarray(rich_query.prior_mean_kw)+2.75)
    shifted = predict_ev_reliable_reference(fitted, shifted_query)
    check('query level translation equivariant', np.allclose(shifted.reference_kw-result.reference_kw, 2.75, atol=2e-14, rtol=0))
    shifted_records = [record(replace(r.window, pre_power_kw=np.asarray(r.window.pre_power_kw)+2.75,
                                      prior_mean_kw=np.asarray(r.window.prior_mean_kw)+2.75),
                              np.asarray(r.observed_non_event_power_kw)+2.75) for r in rich]
    shifted_model = fit_ev_reference_error_model(shifted_records, 3300., seed=17)
    shifted_refit = predict_ev_reliable_reference(shifted_model, shifted_query)
    check('training level translation equivariant', np.allclose(shifted_refit.reference_kw-result.reference_kw, 2.75, atol=2e-13, rtol=0))
    check('seed does not random-search model', predict_ev_reliable_reference(fit_ev_reference_error_model(rich, 3300., 18), rich_query).reference_kw.tolist() == result.reference_kw.tolist())

    # Training completion is checked relative to fitting, not historical notice.
    check('completed earlier notice training valid', model.fit_cutoff_min > constant[0].window.notice_min)
    rejects('future label cutoff rejected', lambda: fit_ev_reference_error_model(constant, 1200.))
    rejects('label before last endpoint rejected', lambda: fit_ev_reference_error_model([replace(constant[0], target_available_min=1000.)], 1500.))
    rejects('event label rejected', lambda: fit_ev_reference_error_model([replace(constant[0], non_event=False)], 1500.))
    rejects('numeric pseudo bool label rejected', lambda: fit_ev_reference_error_model([replace(constant[0], non_event=1)], 1500.))
    rejects('duplicate task rejected', lambda: fit_ev_reference_error_model([constant[0], constant[0]], 1500.))
    rejects('empty records rejected', lambda: fit_ev_reference_error_model([], 1500.))
    rejects('bool cutoff rejected', lambda: fit_ev_reference_error_model(constant, True))
    rejects('string seed rejected', lambda: fit_ev_reference_error_model(constant, 1500., '0'))
    rejects('nonfinite target rejected', lambda: fit_ev_reference_error_model([replace(constant[0], observed_non_event_power_kw=[float('nan')]*60)], 1500.))
    unavailable('model after notice rejected', model, fixture(20, task=1400.), 'after query notice')
    unavailable('post-notice prefix rejected', model, replace(query, pre_starts_min=np.asarray(query.pre_starts_min)+1., pre_ends_min=np.asarray(query.pre_ends_min)+1.), 'post-notice')
    unavailable('missing prefix bin rejected', model, replace(query, pre_starts_min=query.pre_starts_min[1:], pre_ends_min=query.pre_ends_min[1:], pre_power_kw=query.pre_power_kw[1:]))
    unavailable('prefix pre-endpoint availability rejected', model, replace(query, pre_available_min=4984.), 'before its last measurement')
    unavailable('future prior rejected', model, replace(query, prior_available_min=4986.))
    unavailable('self prior rejected', model, replace(query, prior_source_ids=(query.task_id, 'other')))
    unavailable('duplicate prior identity rejected', model, replace(query, prior_source_ids=('history', 'history')))
    unavailable('blank identity rejected', model, replace(query, meter_id=' '))
    unavailable('numeric identity rejected', model, replace(query, user_id=12))
    unavailable('string numeric input rejected', model, replace(query, pre_power_kw=['4']*60))
    unavailable('bool array input rejected', model, replace(query, prior_mean_kw=[True]*60))
    unavailable('nonfinite input rejected', model, replace(query, pre_power_kw=[float('inf')]*60))
    unavailable('wrong resource rejected', model, replace(query, resource_type='AC'))
    unavailable('wrong W rejected', model, replace(query, task_end_min=5020.))
    unavailable('wrong q rejected', model, replace(query, request_kw=3.))
    unavailable('wrong grid rejected', model, replace(query, starts_min=query.starts_min[:-1], ends_min=query.ends_min[:-1], prior_mean_kw=query.prior_mean_kw[:-1]))
    unavailable('nonwindow rejected', model, None)
    unavailable('wrong model type rejected', object(), query)
    unavailable('bad frozen sha type rejected', FrozenEVReferenceModel(model.payload_json, None), query)
    negative = fit_ev_reference_error_model([record(fixture(0), np.full(60, -1.))], 1500.)
    unavailable('negative prediction unavailable without clipping', negative, replace(query, pre_power_kw=np.full(60, 3.)), 'negative reference')
    rejects('frozen model immutable', lambda: setattr(model, 'sha256', 'x'))

    artifact = OUT / 'control_model.json'
    save_ev_reliable_reference_model(fitted, artifact)
    loaded = load_ev_reliable_reference_model(artifact)
    check('save load immutable bytes', loaded == fitted)
    check('save load predictions exact', np.array_equal(predict_ev_reliable_reference(loaded, rich_query).reference_kw, result.reference_kw))
    rejects('existing artifact not overwritten', lambda: save_ev_reliable_reference_model(fitted, artifact))
    tampered = json.loads(artifact.read_text(encoding='utf-8'))
    tampered['payload']['intercept'] += .1
    bad_path = OUT / 'control_tampered_model.json'
    bad_path.write_text(json.dumps(tampered), encoding='utf-8')
    rejects('tampered artifact checksum rejected', lambda: load_ev_reliable_reference_model(bad_path))
    for key, value in [('coefficients', [True]*31), ('scaler_scale', [0.]*31), ('fit_cutoff_min', True),
                       ('task_signature', dict(resource_type='EV', W_min=30., q_kw=1.5, notice_lead_min=15., meter_min=True))]:
        p = json.loads(fitted.payload_json)
        p[key] = value
        raw = _json(p)
        bad = FrozenEVReferenceModel(raw, hashlib.sha256(raw.encode()).hexdigest())
        unavailable('rechecksummed invalid ' + key + ' rejected', bad, query)
    duplicate_path = OUT / 'control_duplicate_fields.json'
    duplicate_path.write_text('{"payload":{},"payload":{}}', encoding='utf-8')
    rejects('duplicate JSON fields rejected', lambda: load_ev_reliable_reference_model(duplicate_path))
    nonfinite_path = OUT / 'control_nonfinite.json'
    nonfinite_path.write_text('{"payload":NaN}', encoding='utf-8')
    rejects('nonfinite JSON rejected', lambda: load_ev_reliable_reference_model(nonfinite_path))

    receipt = dict(status='passed', n_checks=len(checks), checks=checks,
                   module_sha256=hashlib.sha256((ROOT/'B1算法/b1_algorithm/reference/reliable.py').read_bytes()).hexdigest(),
                   scope='synthetic contract/numerical controls only; no main-study data or performance claims')
    with (OUT/'control_receipt.json').open('x', encoding='utf-8') as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(dict(status='passed', n_checks=len(checks), module_sha256=receipt['module_sha256'])))


if __name__ == '__main__':
    main()
