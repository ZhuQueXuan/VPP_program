"""Legal completed EV histories and fixed six-dimensional representations.

Histories describe earlier measured responses. They are optional pre-treatment
covariates for B1 factor studies, never this event's post-treatment controls or
an authorization/capacity prediction. Encoders use train histories only.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import warnings

import numpy as np

from .contracts import number, task_contract

SCHEMA = 'b1.ev-history.v1'
MODEL_SCHEMA = 'b1.ev-history-encoder.v1'
METHODS = ('stats6', 'pca6', 'ae6')
SUMMARY_NAMES = ('mean_eta', 'last_eta', 'mean_cumulative_fraction',
                 'mean_longest_fraction', 'mean_post_rebound_ratio', 'eta_trend_per_event')


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()


def prepare_ev_history(records, current_task, *, required_events=3, cutoff_min=None):
    """Return the latest three legal completed 30min/1min raw event histories.

    Every supplied record is validated, including records older than the three
    selected. Missing history returns ``insufficient_history`` with null arrays;
    malformed/future/cross-object records raise ValueError rather than being
    silently discarded. ``observed_available_at_min`` must cover the entire
    supplied observation window. Reference predictions retain their own strict
    pre-notice binding to each original historical task.
    """
    from .api import _prepare_event
    from .process.api import prepare, _features

    if type(required_events) is not int or required_events != 3:
        raise ValueError('this finite encoder requires exactly three historical events')
    if not isinstance(records, (list, tuple)):
        raise ValueError('history records must be an ordered list or tuple')
    current = task_contract(current_task)
    if not np.isclose(current['end_min'] - current['start_min'], 30., atol=1e-9, rtol=0):
        raise ValueError('this history representation supports current 30-minute EV tasks only')
    cutoff = current['notice_min'] if cutoff_min is None else number(cutoff_min, 'history cutoff_min')
    if cutoff > current['notice_min'] + 1e-9:
        raise ValueError('history cutoff cannot be later than the current notice')
    seen = set()
    rows = []
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError('each historical event must be a mapping')
        context = _prepare_event(record)
        historical = context['task']
        if historical['user_id'] != current['user_id'] or historical['meter_id'] != current['meter_id']:
            raise ValueError('historical user and meter must match the current task')
        if historical['task_id'] == current['task_id'] or historical['task_id'] in seen:
            raise ValueError('historical task IDs must be unique and exclude the current event')
        seen.add(historical['task_id'])
        available = number(record.get('observed_available_at_min'), 'history observed_available_at_min')
        if available < float(context['e'][-1]) - 1e-9 or available > cutoff + 1e-9:
            raise ValueError('all observed history endpoints must be completed and available by cutoff')
        if historical['end_min'] > cutoff + 1e-9 or historical['start_min'] >= current['start_min'] - 1e-9:
            raise ValueError('current and future events cannot be historical controls')
        data = prepare(**context['request'])
        if not np.isclose(data['W'], 30., atol=1e-9, rtol=0) or not np.isclose(data['delta'], 1., atol=1e-9, rtol=0):
            raise ValueError('three complete one-minute 30-minute historical EV tasks required')
        # Six summaries and the raw90 vector share exactly this measured source.
        # No CPOP/RIDE fit or evaluator response is consulted.
        features = _features(data, data['y'])['raw_observed']
        request = (data['starts'] >= -1e-9) & (data['ends'] <= data['W'] + 1e-9)
        raw = data['y'][request] / data['q']
        if raw.shape != (30,):
            raise ValueError('complete thirty-bin historical request required')
        energy = data['q'] * data['W'] / 60.
        event = [number(features['Y'], 'history eta'),
                 number(features['cumulative_response_seconds'], 'history cumulative duration') / 1800.,
                 number(features['longest_continuous_response_seconds'], 'history longest duration') / 1800.,
                 number(features['post_rebound_kwh'], 'history rebound') / energy]
        rows.append(dict(task=historical, start=float(context['s'][0]), end=float(context['e'][-1]),
                         available=available, raw=raw, features=event,
                         input_digest=_digest(dict(task=historical, starts=context['s'].tolist(),
                             ends=context['e'].tolist(), power=context['p'].tolist(),
                             reference=context['b'].tolist(), observed_available_at_min=available)),
                         reference_method=context['reference']['method'],
                         reference_model_id=context['reference']['model_id']))
    rows.sort(key=lambda row: row['task']['start_min'])
    if any(a['end'] > b['start'] + 1e-9 for a, b in zip(rows, rows[1:])):
        raise ValueError('historical observed windows must be disjoint; duplicates are not new history')
    base = dict(schema_version=SCHEMA, current_task=current, cutoff_min=float(cutoff),
                required_events=required_events, supplied_events=len(rows), raw=None, summary=None,
                known_at_min=None, provenance=[], summary_names=list(SUMMARY_NAMES),
                current_event_outcome_used=False, process_refit_used=False,
                interpretation='optional measured past-response covariates; not causal identification or capacity')
    if len(rows) < required_events:
        return dict(base, status='insufficient_history', reason='three complete legally available events required',
                    available_events=len(rows), fallback='C0 current pre-treatment conditions only')
    selected = rows[-required_events:]
    a = np.asarray([r['features'] for r in selected], dtype=float)
    summary = [float(a[:, 0].mean()), float(a[-1, 0]), float(a[:, 1].mean()),
               float(a[:, 2].mean()), float(a[:, 3].mean()), float((a[-1, 0] - a[0, 0]) / 2.)]
    provenance = [dict(task_id=r['task']['task_id'], user_id=r['task']['user_id'], meter_id=r['task']['meter_id'],
                       task_start_min=r['task']['start_min'], task_end_min=r['task']['end_min'],
                       observation_start_min=r['start'], observation_end_min=r['end'],
                       observed_available_at_min=r['available'], input_digest=r['input_digest'],
                       reference_method=r['reference_method'], reference_model_id=r['reference_model_id']) for r in selected]
    result = dict(base, status='ok', raw=np.concatenate([r['raw'] for r in selected]).tolist(), summary=summary,
                  known_at_min=float(max(r['available'] for r in selected)), provenance=provenance,
                  available_events=len(rows), selected_events=3)
    result['prepared_digest'] = _digest(result)
    return result


def _vector(values, size, label):
    original = np.asarray(values, dtype=object)
    if original.shape != (size,):
        raise ValueError(label + ' has an invalid shape')
    return np.asarray([number(v, label) for v in original], dtype=float)


def _prepared(row):
    if not isinstance(row, Mapping) or row.get('schema_version') != SCHEMA or row.get('status') != 'ok':
        raise ValueError('a successful prepare_ev_history result is required; insufficient history must fall back explicitly')
    if row.get('prepared_digest') != _digest({k: v for k, v in row.items() if k != 'prepared_digest'}):
        raise ValueError('prepared history checksum changed; prepare it again from bound raw records')
    raw = _vector(row.get('raw'), 90, 'raw history')
    summary = _vector(row.get('summary'), 6, 'summary history')
    current = task_contract(row.get('current_task'))
    known = number(row.get('known_at_min'), 'known_at_min')
    cutoff = number(row.get('cutoff_min'), 'cutoff_min')
    if known > cutoff + 1e-9 or cutoff > current['notice_min'] + 1e-9:
        raise ValueError('prepared history availability exceeds the current notice')
    if row.get('current_event_outcome_used') is not False or row.get('process_refit_used') is not False:
        raise ValueError('prepared history must retain its no-current-outcome and no-refit declaration')
    provenance = row.get('provenance')
    if not isinstance(provenance, list) or len(provenance) != 3:
        raise ValueError('three-event history provenance is required')
    return raw, summary, current


@dataclass(frozen=True)
class EVHistoryEncoder:
    """Immutable JSON-native model; encoding never mutates fitted parameters."""
    payload_json: str
    sha256: str

    @property
    def model_id(self):
        return 'ev-history-' + self.sha256

    @property
    def method(self):
        return _model_state(self)['method']


def _model_state(model):
    if not isinstance(model, EVHistoryEncoder):
        raise ValueError('EVHistoryEncoder required')
    if not isinstance(model.payload_json, str) or not isinstance(model.sha256, str):
        raise ValueError('invalid immutable history model')
    state = json.loads(model.payload_json)
    if not isinstance(state, dict) or _digest(state) != model.sha256 or state.get('schema_version') != MODEL_SCHEMA or state.get('method') not in METHODS:
        raise ValueError('history model checksum/schema/method mismatch')
    return state


def fit_ev_history_encoder(prepared_histories, *, method='stats6', seed=0):
    """Fit one fixed encoder on declared training histories, without targets.

    PCA and the small tanh autoencoder use the same standardized raw90 source.
    The AE architecture/60 epochs match the existing finite D123 candidate;
    reconstruction quality is diagnostic and does not establish B1 value.
    """
    if method not in METHODS:
        raise ValueError('method must be stats6, pca6, or ae6')
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError('seed must be an integer in [0,2**32-1]')
    if not isinstance(prepared_histories, (list, tuple)) or len(prepared_histories) < 6:
        raise ValueError('at least six prepared training histories required')
    checked = [_prepared(row) for row in prepared_histories]
    if len({x[2]['task_id'] for x in checked}) != len(checked):
        raise ValueError('duplicate current tasks do not provide independent training history rows')
    raw = np.asarray([x[0] for x in checked]); summary = np.asarray([x[1] for x in checked])
    source = summary if method == 'stats6' else raw
    mean = source.mean(0); scale = source.std(0); scale[scale < 1e-12] = 1.
    z = (source - mean) / scale
    training_users = sorted({x[2]['user_id'] for x in checked})
    state = dict(schema_version=MODEL_SCHEMA, method=method, seed=seed, input_dimensions=90,
                 output_dimensions=6, mean=mean.tolist(), scale=scale.tolist(),
                 training_histories=len(checked), training_users=training_users,
                 training_source_digest=_digest([dict(current_task=r['current_task'], provenance=r['provenance'])
                                                for r in prepared_histories]),
                 trained_on_outcomes=False, fitted_to_history_reconstruction_only=method == 'ae6',
                 warnings=[], provenance_scope='caller-supplied training histories only; no validation/test fit')
    if method == 'pca6':
        from sklearn.decomposition import PCA
        pca = PCA(n_components=6, svd_solver='full').fit(z)
        state.update(components=pca.components_.tolist(), pca_center=pca.mean_.tolist(),
                     explained_variance_ratio=pca.explained_variance_ratio_.tolist())
    elif method == 'ae6':
        from sklearn.neural_network import MLPRegressor
        ae = MLPRegressor(hidden_layer_sizes=(24, 6, 24), activation='tanh', solver='adam',
                          alpha=.001, learning_rate_init=.003, batch_size=min(128, len(z)),
                          max_iter=60, tol=0., n_iter_no_change=61, early_stopping=False, random_state=seed)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            ae.fit(z, z)
        state.update(coefs=[x.tolist() for x in ae.coefs_], intercepts=[x.tolist() for x in ae.intercepts_],
                     epochs=int(ae.n_iter_), parameters=sum(x.size for x in ae.coefs_ + ae.intercepts_),
                     loss_curve=[float(x) for x in ae.loss_curve_], warnings=[str(w.message) for w in caught],
                     train_standardized_reconstruction_mse=float(np.mean((ae.predict(z) - z)**2)))
    # JSON construction rejects nonfinite fit output before a model is exposed.
    payload = _canonical(state)
    return EVHistoryEncoder(payload, _digest(state))


def encode_ev_history(model, prepared_history):
    """Encode one legally prepared history using frozen train-only parameters."""
    state = _model_state(model)
    raw, summary, _ = _prepared(prepared_history)
    source = summary if state['method'] == 'stats6' else raw
    mean = _vector(state.get('mean'), len(source), 'model mean')
    scale = _vector(state.get('scale'), len(source), 'model scale')
    if np.any(scale <= 0):
        raise ValueError('history model requires positive scales')
    z = (source - mean) / scale
    if state['method'] == 'pca6':
        components = np.asarray(state.get('components'), dtype=float)
        if components.shape != (6, 90) or not np.isfinite(components).all():
            raise ValueError('invalid PCA model dimensions or values')
        z = components @ (z - _vector(state.get('pca_center'), 90, 'PCA center'))
    elif state['method'] == 'ae6':
        coefs = state.get('coefs'); intercepts = state.get('intercepts')
        if not isinstance(coefs, list) or len(coefs) != 4 or not isinstance(intercepts, list) or len(intercepts) != 4:
            raise ValueError('complete four-layer AE parameters required')
        for i, shape in enumerate(((90, 24), (24, 6))):
            matrix = np.asarray(coefs[i], dtype=float)
            if matrix.shape != shape or not np.isfinite(matrix).all():
                raise ValueError('invalid encoder layer dimensions or values')
            z = np.tanh(z @ matrix + _vector(intercepts[i], shape[1], 'AE intercept'))
    result = _vector(z, 6, 'encoded history').tolist()
    return dict(schema_version=MODEL_SCHEMA, status='ok', method=state['method'], model_id=model.model_id,
                values=result, dimensions=6, known_at_min=prepared_history['known_at_min'],
                current_task_id=prepared_history['current_task']['task_id'],
                training_user_overlap=prepared_history['current_task']['user_id'] in state['training_users'],
                causal_claim=False)


def save_ev_history_encoder(model, path):
    """Save JSON with a canonical content checksum; never deserialize pickle."""
    state = _model_state(model)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8') as stream:
        json.dump(dict(schema_version=MODEL_SCHEMA, sha256=model.sha256, state=state),
                  stream, ensure_ascii=False, indent=2, allow_nan=False)


def load_ev_history_encoder(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(value, dict) or value.get('schema_version') != MODEL_SCHEMA:
        raise ValueError('invalid history encoder file schema')
    model = EVHistoryEncoder(_canonical(value.get('state')), value.get('sha256'))
    _model_state(model)
    return model
