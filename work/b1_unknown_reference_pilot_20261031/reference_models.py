"""Fixed internal reference-model pilot; no process or effect model changes.

Prediction reads reference_window only. Labels are accepted solely by fit_model
from explicitly non-dispatched, non-announced non_event records. GP prediction
uses stored native numeric arrays, never pickle. All methods share the same
eight training horizons, feature map, training-only scaler and prefix offset.
"""
from __future__ import annotations

import os
for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_key] = '1'

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import numbers
import sys

import lightgbm as lgb
import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / 'B1算法') not in sys.path:
    sys.path.insert(0, str(ROOT / 'B1算法'))
from b1_algorithm.reference.core import ReferenceWindow, _validated

SCHEMA = 'b1.unknown-reference-pilot.v1'
HORIZONS = (0, 8, 16, 25, 34, 43, 51, 59)
FEATURE_NAMES = tuple(['prefix15_centered_' + str(i) for i in range(4)] + [
    'historical_centered_shape_kw', 'horizon_fraction', 'clock_sin',
    'clock_cos', 'weekday_sin', 'weekday_cos', 'temperature_c'])


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(',', ':'))


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _number(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real):
        raise ValueError(name + ' must be a real number, not bool/string')
    value = float(value)
    if not np.isfinite(value):
        raise ValueError(name + ' must be finite')
    return value


def _array(value, name, shape):
    raw = np.asarray(value, dtype=object)
    if raw.shape != shape or any(isinstance(v, (bool, np.bool_)) or
            not isinstance(v, numbers.Real) for v in raw.flat):
        raise ValueError(name + ' has invalid numeric type or shape')
    result = np.asarray(value, dtype=float)
    if not np.isfinite(result).all():
        raise ValueError(name + ' must be finite')
    return result


def candidate_specs():
    """Internal prediction candidates, not formal downstream baselines."""
    return [dict(id='lgbm_leaves7', family='lightgbm', num_leaves=7),
            dict(id='lgbm_leaves15', family='lightgbm', num_leaves=15),
            dict(id='gp_rbf07', family='gaussian_process', length_scale=.7),
            dict(id='gp_rbf15', family='gaussian_process', length_scale=1.5)]


def _spec(value):
    if isinstance(value, str):
        matches = [v for v in candidate_specs() if v['id'] == value]
    elif isinstance(value, dict):
        matches = [v for v in candidate_specs() if _json(v) == _json(value)]
    else:
        matches = []
    if len(matches) != 1:
        raise ValueError('one exact predeclared candidate spec required')
    return matches[0]


def _features(fact):
    """No access to factual power, response labels, dose or evaluator truth."""
    if not isinstance(fact, dict) or not isinstance(fact.get('reference_window'), dict):
        raise ValueError('fact with reference_window mapping required')
    w = fact['reference_window']
    try:
        window = ReferenceWindow(**w)
    except (TypeError, ValueError) as exc:
        raise ValueError('invalid reference window') from exc
    a = _validated(window)
    if (window.resource_type != 'EV' or abs(a['end'] - a['task'] - 30) > 1e-9
            or abs(a['request'] - 1.5) > 1e-9 or abs(a['lead'] - 15) > 1e-9):
        raise ValueError('pilot supports EV W30/q1.5/notice15 only')
    s = _array(w['starts_min'], 'starts', (60,))
    e = _array(w['ends_min'], 'ends', (60,))
    expected = a['task'] + np.arange(-15., 45.)
    if not np.allclose(s, expected, rtol=0, atol=1e-9) or not np.allclose(e, expected+1, rtol=0, atol=1e-9):
        raise ValueError('exact one-minute task-relative [-15,45] grid required')
    ps = np.asarray(w['pre_starts_min'], dtype=float)
    pe = np.asarray(w['pre_ends_min'], dtype=float)
    prefix_all = _array(w['pre_power_kw'], 'prefix', ps.shape)
    use = (ps >= a['notice']-60-1e-9) & (pe <= a['notice']+1e-9)
    prefix = prefix_all[use]
    if prefix.shape != (60,):
        raise ValueError('complete 60-minute legal prefix required')
    if _number(w['pre_available_min'], 'prefix availability') < pe[-1]-1e-9:
        raise ValueError('prefix cannot be available before its final measurement')
    offset = float(np.mean(prefix))
    centered = prefix.reshape(4, 15).mean(axis=1)-offset
    prior = _array(w['prior_mean_kw'], 'historical mean', (60,))
    shape = prior-prior.mean()
    midpoint = np.arange(60, dtype=float)+.5
    clock = float(w['clock_hour']) + (midpoint-15)/60.
    weekday = float(w['weekday'])
    x = np.column_stack([np.tile(centered, (60, 1)), shape,
        midpoint/60., np.sin(2*np.pi*clock/24), np.cos(2*np.pi*clock/24),
        np.full(60, np.sin(2*np.pi*weekday/7)),
        np.full(60, np.cos(2*np.pi*weekday/7)),
        np.full(60, float(w['temperature_c']))])
    if x.shape != (60, len(FEATURE_NAMES)) or not np.isfinite(x).all():
        raise ValueError('nonfinite feature map')
    identity = dict(task_id=w['task_id'], user_id=w['user_id'], meter_id=w['meter_id'],
                    notice_min=a['notice'], task_start_min=a['task'], final_endpoint_min=float(e[-1]))
    return x, offset, identity


@dataclass
class PilotReferenceModel:
    metadata: dict
    scaler_mean: np.ndarray
    scaler_scale: np.ndarray
    booster: object = None
    gp_train_x: np.ndarray | None = None
    gp_alpha: np.ndarray | None = None


def _check_model(model):
    if not isinstance(model, PilotReferenceModel) or model.metadata.get('schema') != SCHEMA:
        raise ValueError('pilot reference model required')
    _spec(model.metadata['spec'])
    if model.metadata.get('feature_names') != list(FEATURE_NAMES) or model.metadata.get('training_horizons') != list(HORIZONS):
        raise ValueError('model feature/training lattice mismatch')
    _number(model.metadata['fit_cutoff_min'], 'fit cutoff')
    for field in ('training_users', 'training_task_ids'):
        values = model.metadata[field]
        if not isinstance(values, list) or values != sorted(set(values)) or not values or any(not isinstance(v, str) or not v for v in values):
            raise ValueError('invalid training identity ledger')
    mean = _array(model.scaler_mean, 'scaler mean', (len(FEATURE_NAMES),))
    scale = _array(model.scaler_scale, 'scaler scale', (len(FEATURE_NAMES),))
    if np.any(scale <= 0):
        raise ValueError('positive scaler scale required')
    if model.metadata['spec']['family'] == 'lightgbm':
        if model.booster is None:
            raise ValueError('native tree model missing')
    else:
        n = model.metadata['training_rows']
        _array(model.gp_train_x, 'GP train features', (n, len(FEATURE_NAMES)))
        _array(model.gp_alpha, 'GP alpha', (n,))
    return mean, scale


def fit_model(facts, spec, fit_cutoff_min, seed=0):
    spec = _spec(spec)
    cutoff = _number(fit_cutoff_min, 'fit cutoff')
    if type(seed) is not int or not 0 <= seed < 2**31:
        raise ValueError('nonnegative int32 seed required')
    if not isinstance(facts, (tuple, list)) or not facts:
        raise ValueError('nonempty facts required')
    xs, ys, ledger, users, task_ids, physical = [], [], [], set(), set(), set()
    for fact in facts:
        if fact.get('non_event') is not True or fact.get('task_dispatched') is not False or fact.get('incentive_signal_announced') is not False:
            raise ValueError('explicit non-dispatched, non-announced non_event labels required')
        x, offset, identity = _features(fact)
        y = _array(fact.get('power_kw'), 'non-event observed power', (60,))
        if np.any(y < 0):
            raise ValueError('nonnegative observed training power required')
        available = _number(fact.get('availability', {}).get('power_records_available_at_min'), 'training label availability')
        if available < identity['final_endpoint_min']-1e-9 or available > cutoff+1e-9 or identity['notice_min'] > cutoff+1e-9:
            raise ValueError('all training labels and features must complete before fit cutoff')
        key = (identity['meter_id'], identity['task_start_min'])
        if identity['task_id'] in task_ids or key in physical:
            raise ValueError('duplicate training task or renamed physical task')
        task_ids.add(identity['task_id']); users.add(identity['user_id']); physical.add(key)
        xs.append(x[list(HORIZONS)]); ys.append((y-offset)[list(HORIZONS)])
        ledger.append(dict(**identity, label_available_min=available,
            prior_source_ids=list(fact['reference_window']['prior_source_ids']),
            all_features=x.tolist(), offset=offset, observed_non_event=y.tolist()))
    x, y = np.concatenate(xs), np.concatenate(ys)
    scaler = StandardScaler().fit(x)
    z = scaler.transform(x)
    metadata = dict(schema=SCHEMA, spec=spec, seed=seed, fit_cutoff_min=cutoff,
        feature_names=list(FEATURE_NAMES), training_horizons=list(HORIZONS),
        training_users=sorted(users), training_task_ids=sorted(task_ids),
        training_rows=len(y), training_records=len(facts),
        training_label_completion_max_min=max(v['label_available_min'] for v in ledger),
        training_notice_max_min=max(v['notice_min'] for v in ledger),
        training_digest=_sha(_json(ledger).encode('utf-8')),
        task_signature=dict(resource_type='EV', W_min=30, q_kw=1.5, notice_lead_min=15, meter_min=1),
        offset='mean_complete_60min_prefix_before_notice',
        target='observed_explicit_non_event_power_minus_prefix_offset',
        prediction_reads='reference_window_only',
        training_user_overlap_allowed=False, negative_predictions='raise_no_clipping',
        innovation='fixed internal prediction candidates; not a new forecasting algorithm')
    model = PilotReferenceModel(metadata, scaler.mean_.copy(), scaler.scale_.copy())
    if spec['family'] == 'lightgbm':
        params = dict(n_estimators=100, learning_rate=.05, num_leaves=spec['num_leaves'],
            min_child_samples=20, reg_lambda=1., random_state=seed, n_jobs=1,
            verbosity=-1, deterministic=True, force_col_wise=True)
        reg = lgb.LGBMRegressor(**params).fit(z, y)
        model.booster = reg.booster_
        metadata['engine_params'] = params
    else:
        kernel = ConstantKernel(.04, constant_value_bounds='fixed') * RBF(
            spec['length_scale'], length_scale_bounds='fixed') + WhiteKernel(.0025, noise_level_bounds='fixed')
        reg = GaussianProcessRegressor(kernel=kernel, optimizer=None, normalize_y=False,
            alpha=0., random_state=seed).fit(z, y)
        model.gp_train_x = reg.X_train_.copy()
        model.gp_alpha = reg.alpha_.copy()
        metadata['engine_params'] = dict(amplitude=.04, length_scale=spec['length_scale'],
            white_noise_variance=.0025, alpha=0., optimizer=None, normalize_y=False)
        independent = (.04 * RBF(spec['length_scale'])(z, model.gp_train_x)) @ model.gp_alpha
        if not np.allclose(independent, reg.predict(z), rtol=0, atol=1e-13):
            raise AssertionError('native GP numeric-array prediction differs from fitted estimator')
    _check_model(model)
    return model


def predict_model(model, facts):
    mean, scale = _check_model(model)
    if not isinstance(facts, (list, tuple)) or not facts:
        raise ValueError('nonempty prediction facts required')
    xs, offsets, identities = [], [], []
    for fact in facts:
        x, offset, identity = _features(fact)
        if model.metadata['fit_cutoff_min'] > identity['notice_min']+1e-9:
            raise ValueError('model fitted after query notice')
        if identity['user_id'] in model.metadata['training_users']:
            raise ValueError('query users must be disjoint from training users')
        xs.append(x); offsets.append(offset); identities.append(identity)
    if len({v['task_id'] for v in identities}) != len(identities) or len({(v['meter_id'], v['task_start_min']) for v in identities}) != len(identities):
        raise ValueError('duplicate prediction task or physical window')
    z = (np.concatenate(xs)-mean)/scale
    if model.metadata['spec']['family'] == 'lightgbm':
        residual = np.asarray(model.booster.predict(z, num_threads=1), dtype=float)
    else:
        p = model.metadata['engine_params']
        residual = (p['amplitude'] * RBF(p['length_scale'])(z, model.gp_train_x)) @ model.gp_alpha
    prediction = residual.reshape(len(facts), 60) + np.asarray(offsets)[:, None]
    if not np.isfinite(prediction).all() or np.any(prediction < 0):
        raise ValueError('nonfinite or negative reference prediction; no clipping or hidden fallback')
    return prediction


def save_model(model, directory):
    _check_model(model)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'model.json'
    treepath = directory / 'tree.txt'
    if path.exists() or treepath.exists():
        raise FileExistsError('refuse to overwrite an existing model artifact')
    value = dict(metadata=model.metadata, scaler_mean=model.scaler_mean.tolist(),
                 scaler_scale=model.scaler_scale.tolist())
    if model.metadata['spec']['family'] == 'lightgbm':
        model.booster.save_model(str(treepath))
        value.update(tree_file='tree.txt', tree_sha256=_sha(treepath.read_bytes()))
    else:
        value.update(gp_train_x=model.gp_train_x.tolist(), gp_alpha=model.gp_alpha.tolist())
    payload = _json(value)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(_json(dict(payload_json=payload, sha256=_sha(payload.encode('utf-8')))))
    return path


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def load_model(path):
    path = Path(path)
    if path.stat().st_size > 20_000_000:
        raise ValueError('oversized model artifact')
    envelope = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_pairs)
    if set(envelope) != {'payload_json', 'sha256'} or _sha(envelope['payload_json'].encode('utf-8')) != envelope['sha256']:
        raise ValueError('model envelope/checksum mismatch')
    value = json.loads(envelope['payload_json'], object_pairs_hook=_pairs)
    family = _spec(value['metadata']['spec'])['family']
    common = {'metadata', 'scaler_mean', 'scaler_scale'}
    expected = common | ({'tree_file', 'tree_sha256'} if family == 'lightgbm' else {'gp_train_x', 'gp_alpha'})
    if set(value) != expected:
        raise ValueError('model payload fields mismatch')
    model = PilotReferenceModel(value['metadata'], np.asarray(value['scaler_mean'], float),
                                np.asarray(value['scaler_scale'], float))
    if family == 'lightgbm':
        if value['tree_file'] != 'tree.txt':
            raise ValueError('unsafe tree file name')
        treepath = path.parent / 'tree.txt'
        if _sha(treepath.read_bytes()) != value['tree_sha256']:
            raise ValueError('native tree checksum mismatch')
        model.booster = lgb.Booster(model_file=str(treepath))
    else:
        model.gp_train_x = np.asarray(value['gp_train_x'], float)
        model.gp_alpha = np.asarray(value['gp_alpha'], float)
    _check_model(model)
    return model
