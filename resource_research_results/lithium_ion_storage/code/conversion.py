"""M5BAT steady-state AC -> DC conversion using frozen per-unit efficiencies."""
import argparse
import csv
import json
import math
from pathlib import Path

RESOURCE = Path(__file__).resolve().parents[1]


def predict(unit_id, direction, ac_mean_kw, steady_state_confirmed, parameters):
    """Positive discharge, negative charge; returns prediction and scope status."""
    result = {'dc_predicted_kw': None, 'status': 'unavailable', 'outside_fit_power_support': None}
    if not math.isfinite(ac_mean_kw):
        return dict(result, status='invalid_nonfinite_power')
    if not steady_state_confirmed:
        return dict(result, status='steady_state_not_confirmed')
    if direction not in ('charge', 'discharge'):
        return dict(result, status='unsupported_direction')
    if (direction == 'charge' and ac_mean_kw >= 0) or (direction == 'discharge' and ac_mean_kw <= 0):
        return dict(result, status='power_direction_mismatch')
    parameter = next((p for p in parameters if p['unit_id'] == unit_id and p['direction'] == direction), None)
    if parameter is None or parameter['status'] != 'ok':
        return dict(result, status='no_valid_parameter_for_unit_direction')
    eta = float(parameter['eta'])
    if not math.isfinite(eta) or not 0 < eta <= 1:
        return dict(result, status='invalid_efficiency')
    outside = not parameter['fit_min_abs_ac_kw'] <= abs(ac_mean_kw) <= parameter['fit_max_abs_ac_kw']
    prediction = ac_mean_kw * eta if direction == 'charge' else ac_mean_kw / eta
    return {'dc_predicted_kw': prediction, 'status': 'outside_fit_power_support' if outside else 'ok',
            'outside_fit_power_support': outside}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--parameters', type=Path, default=RESOURCE/'parameters/conversion_m5bat.json')
    args = parser.parse_args()
    parameters = json.loads(args.parameters.read_text(encoding='utf-8'))
    rows = []
    with args.input.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        required = ['unit_id', 'direction', 'ac_mean_kw', 'steady_state_confirmed']
        if set(reader.fieldnames or []) != set(required):
            raise ValueError('Input columns must be exactly: '+', '.join(sorted(required)))
        for row in reader:
            flag = row['steady_state_confirmed'].lower()
            if flag not in ('true', 'false', '1', '0'):
                raise ValueError('steady_state_confirmed must be true/false/1/0')
            rows.append({**row, **predict(row['unit_id'], row['direction'], float(row['ac_mean_kw']),
                                        flag in ('true', '1'), parameters)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(required)+['dc_predicted_kw','status','outside_fit_power_support'])
        writer.writeheader()
        writer.writerows(rows)
    print(f'Saved {len(rows)} conversion results: {args.output}')


if __name__ == '__main__':
    main()
