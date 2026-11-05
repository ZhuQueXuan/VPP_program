"""Generate candidate factors from typed observations as of an event cutoff."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isfinite
from statistics import fmean


@dataclass(frozen=True)
class Field:
    name: str
    role: str
    quantity: str
    unit: str
    scope: str


@dataclass(frozen=True)
class Observation:
    field: str
    measured_at: datetime
    available_at: datetime
    value: float | datetime


WINDOW = timedelta(minutes=30)
MIN_SPAN = WINDOW / 2


def generate_candidates(fields, observations, cutoff):
    """Use observations strictly available before cutoff for a single resource and event."""
    fields = {field.name: field for field in fields}
    eligible = {name: [] for name in fields}
    for row in observations:
        if row.field not in fields:
            raise ValueError(f'Unknown field {row.field}')
        if row.available_at < row.measured_at:
            raise ValueError(f'Availability precedes measurement for {row.field}')
        if row.available_at < cutoff:
            eligible[row.field].append(row)

    features, missing = {}, {}

    def emit(kind, names, unit, value, source):
        key = '|'.join((kind, *names))
        if value is None:
            missing[key] = source
            return
        features[key] = dict(value=value, unit=unit, fields=list(names), observations=len(source),
                             measured_at=max(row.measured_at for row in source).isoformat(),
                             available_at=max(row.available_at for row in source).isoformat())

    latest = {}
    for name, field in fields.items():
        if field.role not in ('state', 'target', 'deadline'):
            continue
        rows = sorted(eligible[name], key=lambda row: (row.measured_at, row.available_at))
        if field.role == 'state':
            rows = [row for row in rows if cutoff-WINDOW <= row.measured_at]
        if field.role == 'deadline':
            remaining = (rows[-1].value-cutoff).total_seconds()/60 if rows else None
            if remaining is not None and remaining >= 0:
                emit('remaining_minutes', (name,), 'min', remaining, rows[-1:])
            else:
                emit('remaining_minutes', (name,), 'min', None, 'no_available_future_deadline')
            continue
        if rows and not all(isfinite(row.value) for row in rows):
            raise ValueError(f'Nonfinite observation for {name}')
        if rows:
            latest[name] = rows[-1]
        emit('latest', (name,), field.unit, rows[-1].value if rows else None,
             rows[-1:] if rows else 'no_available_observation')
        if field.role == 'state':
            span = rows[-1].measured_at-rows[0].measured_at if rows else timedelta(0)
            enough = len(rows) >= 2 and span >= MIN_SPAN
            emit('mean_30min', (name,), field.unit, fmean(row.value for row in rows) if enough else None,
                 rows if enough else 'insufficient_history_span')
            emit('change_30min', (name,), field.unit, rows[-1].value-rows[0].value if enough else None,
                 [rows[0], rows[-1]] if enough else 'insufficient_history_span')

    states = [field for field in fields.values() if field.role == 'state']
    for target in (field for field in fields.values() if field.role == 'target'):
        matching = [state for state in states if (state.quantity, state.unit, state.scope) ==
                    (target.quantity, target.unit, target.scope)]
        for state in matching:
            names = (target.name, state.name)
            if all(name in latest for name in names):
                goal, actual = (latest[name] for name in names)
                emit('target_minus_state', names, target.unit, goal.value-actual.value, [goal, actual])
            else:
                emit('target_minus_state', names, target.unit, None, 'target_or_state_unavailable')
    return dict(cutoff=cutoff.isoformat(), features=features, missing=missing)
