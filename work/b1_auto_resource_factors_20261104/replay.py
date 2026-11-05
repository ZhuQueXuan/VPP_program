"""Replay the same candidate generator on real EV and heat-pump records."""
import argparse
import gzip
import hashlib
import json
import zipfile
from collections import Counter
from datetime import timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd

from candidates import Field, Observation, WINDOW, generate_candidates


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ACN = ROOT/'data/ACN_real_user_benchmark_v1_20261102'
ACN_METADATA = ROOT/'work/b1_real_training_data_20261102/source_documents/acn_official_Caltech_2020.json'
HEAT = ROOT/'work/b1_response_factors_20261104/raw/heat.zip'
RULES = HERE/'candidates.py'

# Source descriptors say what was measured, with no candidate feature names.
EV_FIELDS = (
    Field('Charging Current (A)', 'state', 'current', 'A', 'session'),
    Field('Voltage (V)', 'state', 'voltage', 'V', 'session'),
    Field('Power (kW)', 'state', 'power', 'kW', 'session'),
    Field('Energy Delivered (kWh)', 'state', 'energy', 'kWh', 'session'),
    Field('Actual Pilot (A)', 'command', 'current', 'A', 'session'),
    Field('kWhRequested', 'target', 'energy', 'kWh', 'session'),
    Field('requestedDeparture', 'deadline', 'time', 'datetime', 'session'),
)
HEAT_FIELDS = (
    Field('t_in', 'state', 'temperature', 'degC', 'indoor_air'),
    Field('t_set', 'target', 'temperature', 'degC', 'indoor_air'),
    Field('t_out', 'state', 'temperature', 'degC', 'outdoor_air'),
    Field('t_dhw', 'state', 'temperature', 'degC', 'domestic_hot_water'),
    Field('hp_p', 'state', 'power', 'W', 'heat_pump'),
)


def meter_observations(frame, fields, cutoff):
    window = frame.loc[cutoff-WINDOW:cutoff+timedelta(minutes=5), [field.name for field in fields]]
    # Ignore ambiguous duplicated values at the same instant, keeping unrelated fields.
    if window.index.has_duplicates:
        by_time = window.groupby(level=0)
        window = by_time.first().where(by_time.nunique() <= 1)
    return [Observation(name, timestamp, timestamp, float(value))
            for name in window for timestamp, value in window[name].dropna().items()]


def ev_events():
    manifest = json.loads((ACN/'training_sessions.json').read_text(encoding='utf8'))
    official = json.loads(ACN_METADATA.read_text(encoding='utf8'))['_items']
    source = {row['sessionID']: row for row in official}
    earliest = {}
    for row in sorted(manifest, key=lambda item: (parsedate_to_datetime(source[item['session_id']]['connectionTime']),
                                                  item['session_id'])):
        earliest.setdefault(row['user_group'], row)
    for row in earliest.values():
        session = source[row['session_id']]
        cutoff = pd.Timestamp(parsedate_to_datetime(session['connectionTime']))+timedelta(minutes=30)
        samples = []
        for revision in session['userInputs'] or []:
            if not revision['modifiedAt']:
                continue
            changed = parsedate_to_datetime(revision['modifiedAt'])
            for field in EV_FIELDS[-2:]:
                value = revision[field.name]
                if value is not None:
                    value = parsedate_to_datetime(value) if field.role == 'deadline' else float(value)
                    samples.append(Observation(field.name, changed, changed, value))
        try:
            with gzip.open(ROOT/row['local'], 'rt', encoding='utf8') as stream:
                meter = pd.read_csv(stream, index_col=0)
        except (OSError, EOFError):
            issue = 'unreadable_meter_file'
        else:
            meter.index = pd.to_datetime(meter.index, utc=True, format='mixed')
            samples.extend(meter_observations(meter.sort_index(), EV_FIELDS[:-2], cutoff))
            issue = None
        yield row['session_id'], row['user_group'], cutoff, samples, issue


def heat_events():
    columns = ['time_full', 'hh_id', 'intervention_dummy', 'elapsed_time_inter', 'unique_index']
    with zipfile.ZipFile(HEAT) as archive, archive.open('experiment_data.dta') as stream:
        data = pd.read_stata(stream, columns=columns+[field.name for field in HEAT_FIELDS])
    data.index = pd.to_datetime(data['time_full'], utc=True, format='mixed')
    for household, rows in data.sort_index().groupby('hh_id'):
        starts = rows.loc[(rows.intervention_dummy == 1) & (rows.elapsed_time_inter == 0), 'unique_index']
        for cutoff, event in starts.items():
            yield str(int(event)), str(int(household)), cutoff, meter_observations(rows, HEAT_FIELDS, cutoff), None


def write_json(path, payload):
    with path.open('x', encoding='utf8') as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay(resource, fields, events):
    rows = []
    generated, unavailable, missing_reasons = Counter(), Counter(), Counter()
    for event_id, group_id, cutoff, observations, issue in events:
        result = generate_candidates(fields, observations, cutoff)
        prefix_only = [row for row in observations if row.available_at < cutoff]
        assert result == generate_candidates(fields, reversed(prefix_only), cutoff)
        generated.update(result['features'].keys())
        unavailable.update(result['missing'].keys())
        missing_reasons.update(result['missing'].values())
        rows.append(dict(event_id=event_id, group_id=group_id, source_issue=issue, **result))
    assert len(rows) == len({row['event_id'] for row in rows})
    assert all(generated[key]+unavailable[key] == len(rows) for key in generated.keys() | unavailable.keys())
    summary = dict(events=len(rows), groups=len({row['group_id'] for row in rows}),
                   generated=dict(sorted(generated.items())), unavailable=dict(sorted(unavailable.items())),
                   missing_reasons=dict(missing_reasons), source_issues=dict(Counter(row['source_issue'] for row in rows if row['source_issue'])))
    write_json(HERE/f'{resource}.json', dict(rule_sha256=digest(RULES), summary=summary, rows=rows))
    print(json.dumps(summary, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('resource', choices=('ev', 'heat'))
    resource = parser.parse_args().resource
    freeze_path = HERE/'freeze.json'
    if resource == 'ev':
        replay('ev', EV_FIELDS, ev_events())
        write_json(freeze_path, dict(rule_sha256=digest(RULES), ev_result_sha256=digest(HERE/'ev.json'),
                                    ev_cutoff='connection plus 30 minutes, an analysis anchor'))
    else:
        freeze = json.loads(freeze_path.read_text(encoding='utf8'))
        if digest(RULES) != freeze['rule_sha256'] or digest(HERE/'ev.json') != freeze['ev_result_sha256']:
            raise ValueError('Rules or EV output changed after freeze')
        replay('heat', HEAT_FIELDS, heat_events())


if __name__ == '__main__':
    main()
