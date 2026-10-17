"""One-second M5BAT LMO1 log forecast; no command-arrival or latency claim."""
import argparse
import csv
import json
import math
from pathlib import Path

RESOURCE = Path(__file__).resolve().parents[1]


def predict(ac_t_kw, set_t_kw, mode, beta):
    if not all(math.isfinite(x) for x in (ac_t_kw, set_t_kw, beta)) or not 0 <= beta <= 1:
        raise ValueError('Finite powers and beta in [0,1] are required')
    pq = mode == 'PQ'
    return {'persistence_kw': ac_t_kw, 'setpoint_baseline_kw': set_t_kw if pq else ac_t_kw,
            'blend_kw': ac_t_kw + beta*(set_t_kw-ac_t_kw) if pq else ac_t_kw,
            'status': 'unknown_mode_persistence_fallback' if mode not in ('PQ','Stop','Silent','Wait') else 'ok'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--parameters', type=Path, default=RESOURCE/'parameters/log_power_lmo1.json')
    args = parser.parse_args()
    beta = json.loads(args.parameters.read_text(encoding='utf-8'))['beta']
    rows = []
    with args.input.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if set(reader.fieldnames or []) != {'ac_t_kw','set_t_kw','mode'}:
            raise ValueError('Input columns must be exactly ac_t_kw,set_t_kw,mode')
        for row in reader:
            rows.append({**row, **predict(float(row['ac_t_kw']), float(row['set_t_kw']), row['mode'], beta)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['ac_t_kw','set_t_kw','mode','persistence_kw',
                                              'setpoint_baseline_kw','blend_kw','status'])
        writer.writeheader()
        writer.writerows(rows)
    print(f'Saved {len(rows)} log forecasts: {args.output}')


if __name__ == '__main__':
    main()
