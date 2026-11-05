"""Fixed, pre-notice EV reference forecasting from completed non-event records.

The prefix level is an offset, not a fitted feature.  Four centered 15-minute
prefix means interact with a fixed cubic horizon spline; the centered observed
historical mean supplies one additional shape feature.  This is a forecast for
the declared training population, not identification of an actual event's
counterfactual.  JSON checksums establish integrity, not source authenticity.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re
from collections.abc import Sequence

import numpy as np
from scipy.interpolate import BSpline
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from .core import (ReferenceWindow, ReferencePrediction, WindowCalibrationRecord,
                   _array, _number, _integer, _identifier, _validated, _unavailable)


SCHEMA = 'b1.ev-reliable-reference.v1'
METHOD = 'ev_prefix_centered_ridge'
PARAMS = dict(ridge_alpha=10.0, spline_knots=5, spline_degree=3,
              spline_include_bias=False, spline_extrapolation='error')
RELATIVE_STARTS = tuple(float(x) for x in range(-15, 45))
FEATURE_NAMES = tuple(
    ['horizon_spline_' + str(j) for j in range(6)] +
    ['prefix_block_' + str(k) + '_x_spline_' + str(j)
     for k in range(4) for j in range(6)] + ['historical_centered_shape_kw'])
_FIXED_SPLINE_KNOTS = (-58.75, -44.0, -29.25, -14.5, .25, 15.0,
                       29.75, 44.5, 59.25, 74.0, 88.75)
LIMITATION = ('Fixed pooled non-event forecast; actual-event counterfactual '
              'identification and uncertainty coverage are not established.')
_PAYLOAD_KEYS = {'schema', 'method', 'params', 'feature_names', 'task_signature',
                 'relative_starts_min', 'prefix_contract', 'fit_cutoff_min',
                 'seed', 'training_users', 'training_records', 'training_digest',
                 'n_training_rows', 'spline_knots', 'scaler_mean', 'scaler_scale',
                 'coefficients', 'intercept', 'limitation'}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON field: ' + key)
        result[key] = value
    return result


def _read_json(value):
    def invalid_constant(value):
        raise ValueError('nonfinite JSON constant: ' + value)
    return json.loads(value, object_pairs_hook=_pairs,
                      parse_constant=invalid_constant)


@dataclass(frozen=True)
class FrozenEVReferenceModel:
    """Immutable native parameters; no fitted Python objects or pickle."""
    payload_json: str
    sha256: str

    @property
    def model_id(self):
        return 'evref-' + self.sha256[:20] if isinstance(self.sha256, str) else None

    @property
    def fit_cutoff_min(self):
        return _payload(self)['fit_cutoff_min']

    @property
    def training_users(self):
        return tuple(_payload(self)['training_users'])

    @property
    def training_records(self):
        return tuple(_payload(self)['training_records'])


def _spline_knots():
    # Exact SplineTransformer(n_knots=5, degree=3, knots='uniform',
    # include_bias=False) knots on fixed midpoints [-14.5,44.5].
    # Keeping these native numbers avoids even fitting a basis during queries.
    return np.asarray(_FIXED_SPLINE_KNOTS)


def _basis(knots):
    knots = np.asarray(knots, dtype=float)
    n = len(knots) - PARAMS['spline_degree'] - 1
    result = BSpline(knots, np.eye(n), PARAMS['spline_degree'],
                     extrapolate=False)(np.asarray(RELATIVE_STARTS) + .5)
    return result[:, :-1]  # SplineTransformer(include_bias=False).


def _payload(model):
    if not isinstance(model, FrozenEVReferenceModel):
        raise ValueError('FrozenEVReferenceModel required')
    if (not isinstance(model.payload_json, str) or len(model.payload_json) > 2_000_000
            or not isinstance(model.sha256, str)
            or re.fullmatch('[0-9a-f]{64}', model.sha256) is None):
        raise ValueError('invalid frozen model payload/checksum')
    if hashlib.sha256(model.payload_json.encode('utf-8')).hexdigest() != model.sha256:
        raise ValueError('frozen reference checksum mismatch')
    p = _read_json(model.payload_json)
    if not isinstance(p, dict) or set(p) != _PAYLOAD_KEYS:
        raise ValueError('frozen reference fields mismatch')
    if _json(p) != model.payload_json:
        raise ValueError('frozen reference payload must use canonical finite JSON')
    if (p['schema'] != SCHEMA or p['method'] != METHOD
            or _json(p['params']) != _json(PARAMS) or p['feature_names'] != list(FEATURE_NAMES)
            or _json(p['task_signature']) != _json(dict(resource_type='EV', W_min=30.0,
                                            q_kw=1.5, notice_lead_min=15.0,
                                            meter_min=1.0))
            or _json(p['relative_starts_min']) != _json(list(RELATIVE_STARTS))
            or _json(p['prefix_contract']) != _json(dict(relative_start_min=-75.0,
                                             relative_end_min=-15.0,
                                             block_minutes=15, anchor='mean60'))
            or p['limitation'] != LIMITATION):
        raise ValueError('frozen reference algorithm/domain mismatch')
    _number(p['fit_cutoff_min'], 'artifact fit cutoff')
    seed = _integer(p['seed'], 'artifact seed')
    if not 0 <= seed < 2**31:
        raise ValueError('artifact seed outside nonnegative int32 range')
    for key in ('training_users', 'training_records'):
        values = p[key]
        if not isinstance(values, list) or not values:
            raise ValueError('artifact ' + key + ' must be a nonempty list')
        for value in values:
            _identifier(value, key)
        if len(set(values)) != len(values):
            raise ValueError('artifact duplicate ' + key)
    if p['training_users'] != sorted(p['training_users']):
        raise ValueError('artifact training users must use canonical sorted order')
    if len(p['training_users']) > len(p['training_records']):
        raise ValueError('artifact training identity counts inconsistent')
    if (not isinstance(p['training_digest'], str)
            or re.fullmatch('[0-9a-f]{64}', p['training_digest']) is None):
        raise ValueError('artifact training digest invalid')
    rows = _integer(p['n_training_rows'], 'artifact training rows')
    if rows != 60 * len(p['training_records']):
        raise ValueError('artifact training rows/records mismatch')
    knots = _array(p['spline_knots'], 'artifact spline knots')
    expected = _spline_knots()
    if knots.shape != expected.shape or not np.array_equal(knots, expected):
        raise ValueError('artifact spline knots differ from fixed horizon basis')
    for key in ('scaler_mean', 'scaler_scale', 'coefficients'):
        a = _array(p[key], 'artifact ' + key)
        if a.shape != (len(FEATURE_NAMES),):
            raise ValueError('artifact ' + key + ' feature shape mismatch')
        if key == 'scaler_scale' and np.any(a <= 0):
            raise ValueError('artifact scaler scale must be positive')
    _number(p['intercept'], 'artifact intercept')
    return p


def _features(window, basis):
    a = _validated(window)
    if window.resource_type != 'EV':
        raise ValueError('EV ReferenceWindow required')
    if (not np.isclose(a['end'] - a['task'], 30.0, rtol=0, atol=1e-9)
            or not np.isclose(a['request'], 1.5, rtol=0, atol=1e-9)
            or not np.isclose(a['lead'], 15.0, rtol=0, atol=1e-9)):
        raise ValueError('supported EV task is W30/q1.5/notice15 minutes only')
    expected = a['task'] + np.asarray(RELATIVE_STARTS)
    if (a['s'].shape != (60,) or not np.allclose(a['s'], expected, rtol=0, atol=1e-9)
            or not np.allclose(a['e'], expected + 1.0, rtol=0, atol=1e-9)):
        raise ValueError('prediction requires exact task-relative [-15,45] one-minute grid')
    pre_s = _array(window.pre_starts_min, 'prefix starts')
    pre_e = _array(window.pre_ends_min, 'prefix ends')
    pre = _array(window.pre_power_kw, 'prefix power')
    use = (pre_s >= a['notice'] - 60.0 - 1e-9) & (pre_e <= a['notice'] + 1e-9)
    prefix = pre[use]
    if prefix.shape != (60,):
        raise ValueError('complete last 60-minute pre-notice prefix required')
    if _number(window.pre_available_min, 'prefix available') < pre_e[-1] - 1e-9:
        raise ValueError('prefix cannot be available before its last measurement endpoint')
    anchor = float(np.mean(prefix))
    centered = np.mean(prefix.reshape(4, 15), axis=1) - anchor
    prior = _array(window.prior_mean_kw, 'prior mean power')
    shape = prior - np.mean(prior)
    x = np.column_stack([basis] + [basis * block for block in centered] + [shape])
    if x.shape != (60, len(FEATURE_NAMES)) or not np.isfinite(x).all():
        raise ValueError('nonfinite or incorrectly shaped centered reference features')
    available = max(_number(getattr(window, name), name) for name in
                    ('pre_available_min', 'prior_available_min',
                     'calendar_available_min', 'temperature_available_min'))
    return x, anchor, a, available


def fit_ev_reference_error_model(records: Sequence[WindowCalibrationRecord],
                                 fit_cutoff_min, seed=0):
    """Fit the single predeclared model on completed, declared non-event labels.

    Training windows precede the fitted model, so their own notices need not be
    later than fit_cutoff_min.  Prediction enforces the opposite availability
    check against each new query's notice.  No current event or truth field is
    an input to this function.
    """
    cutoff = _number(fit_cutoff_min, 'fit cutoff')
    seed = _integer(seed, 'seed')
    if not 0 <= seed < 2**31:
        raise ValueError('seed outside supported nonnegative int32 range')
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)) or not records:
        raise ValueError('nonempty sequence of non-event training records required')
    knots = _spline_knots()
    basis = _basis(knots)
    xs, ys, users, ids = [], [], set(), []
    digest = hashlib.sha256()
    for record in records:
        if not isinstance(record, WindowCalibrationRecord) or record.non_event is not True:
            raise ValueError('declared non-event WindowCalibrationRecord required')
        x, anchor, a, _ = _features(record.window, basis)
        y = _array(record.observed_non_event_power_kw, 'observed non-event power')
        if y.shape != (60,):
            raise ValueError('non-event target/prediction grid shape mismatch')
        available = _number(record.target_available_min, 'target available')
        if available > cutoff + 1e-9 or available < a['e'][-1] - 1e-9:
            raise ValueError('all non-event label endpoints must be completed and available by fit cutoff')
        if a['notice'] > cutoff + 1e-9:
            raise ValueError('training prefix unavailable at fit cutoff')
        w = record.window
        if w.task_id in ids:
            raise ValueError('duplicate non-event training task_id')
        users.add(w.user_id)
        ids.append(w.task_id)
        xs.append(x)
        ys.append(y - anchor)
        digest.update(_json(dict(task_id=w.task_id, user_id=w.user_id,
                                 meter_id=w.meter_id, resource_type=w.resource_type,
                                 task_start_min=a['task'], target_available_min=available,
                                 prior_source_ids=list(w.prior_source_ids),
                                 x=x.tolist(), anchor=anchor, y=y.tolist())).encode('utf-8'))
    x, y = np.concatenate(xs), np.concatenate(ys)
    scaler = StandardScaler().fit(x)
    reg = Ridge(alpha=10.0, fit_intercept=True, solver='cholesky').fit(scaler.transform(x), y)
    p = dict(schema=SCHEMA, method=METHOD, params=PARAMS,
             feature_names=list(FEATURE_NAMES),
             task_signature=dict(resource_type='EV', W_min=30.0, q_kw=1.5,
                                 notice_lead_min=15.0, meter_min=1.0),
             relative_starts_min=list(RELATIVE_STARTS),
             prefix_contract=dict(relative_start_min=-75.0, relative_end_min=-15.0,
                                  block_minutes=15, anchor='mean60'),
             fit_cutoff_min=cutoff, seed=seed, training_users=sorted(users),
             training_records=ids, training_digest=digest.hexdigest(),
             n_training_rows=len(y), spline_knots=knots.tolist(),
             scaler_mean=scaler.mean_.tolist(), scaler_scale=scaler.scale_.tolist(),
             coefficients=reg.coef_.tolist(), intercept=float(reg.intercept_),
             limitation=LIMITATION)
    payload = _json(p)
    model = FrozenEVReferenceModel(payload, hashlib.sha256(payload.encode('utf-8')).hexdigest())
    _payload(model)
    return model


def predict_ev_reliable_reference(model, window: ReferenceWindow):
    """Query without refitting; failures preserve an explicit unavailable status."""
    try:
        p = _payload(model)
        x, anchor, a, inputs_available = _features(window, _basis(p['spline_knots']))
        if p['fit_cutoff_min'] > a['notice'] + 1e-9:
            raise ValueError('reference model fitted after query notice')
        prediction = (anchor + ((x - np.asarray(p['scaler_mean'])) /
                                np.asarray(p['scaler_scale'])) @
                      np.asarray(p['coefficients']) + p['intercept'])
        if not np.isfinite(prediction).all():
            raise ValueError('nonfinite reference prediction')
        if np.any(prediction < 0):
            raise ValueError('negative reference prediction; no clipping is applied')
        starts, ends = a['s'].copy(), a['e'].copy()
        for ar in (starts, ends, prediction):
            ar.setflags(write=False)
        role = 'seen_training_user' if window.user_id in p['training_users'] else 'unseen_user'
        return ReferencePrediction(
            'available', window.task_id, window.user_id, window.meter_id, METHOD,
            model.model_id, max(p['fit_cutoff_min'], inputs_available), starts, ends,
            prediction, (), role, window_band_eta=None,
            task_start_min=a['task'], task_end_min=a['end'],
            request_kw=a['request'], notice_min=a['notice'])
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        return _unavailable(window, METHOD, model, str(exc))


def save_ev_reliable_reference_model(model, path):
    """Create one new native JSON file; refuse overwriting an existing artifact."""
    p = _payload(model)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope = dict(payload=p, checksum_sha256=model.sha256, model_id=model.model_id)
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(_json(envelope) + '\n')
    return dict(path=str(path), model_id=model.model_id, checksum_sha256=model.sha256)


def load_ev_reliable_reference_model(path):
    """Load checked native coefficients only; no executable deserialization."""
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError('missing or oversized local JSON reference artifact')
    envelope = _read_json(path.read_text(encoding='utf-8'))
    if not isinstance(envelope, dict) or set(envelope) != {'payload', 'checksum_sha256', 'model_id'}:
        raise ValueError('reference artifact envelope fields mismatch')
    model = FrozenEVReferenceModel(_json(envelope['payload']), envelope['checksum_sha256'])
    _payload(model)
    if envelope['model_id'] != model.model_id:
        raise ValueError('reference artifact model_id mismatch')
    return model
