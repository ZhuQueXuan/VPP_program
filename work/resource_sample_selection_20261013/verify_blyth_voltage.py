"""Independent stdlib check of source alignment, metrics, and fixed-run replay."""
from pathlib import Path
import csv
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'work/resource_sample_selection_20261013/downloads/blyth_ecm_20261015'

def main():
    last_source = {}
    with (BASE / 'wltp_source_rows.csv').open(newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            last_source[int(row['time_s'])] = row
    counts = 0
    errors = {'B_R0': [], 'B_2RC': []}
    worst = {}
    algebra_max = 0.0
    source_max = 0.0
    with (BASE / 'BL_BLYTH_VOLTAGE_20261015_01/predictions.csv').open(newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            t = float(row['time_s'])
            assert t == counts
            source = last_source[counts]
            source_max = max(source_max, abs(float(source['voltage_V'])-float(row['measured_voltage_V'])),
                             abs(float(source['current_discharge_A'])-float(row['current_discharge_A'])))
            algebra_max = max(algebra_max, abs(float(row['B_R0_voltage_V']) - float(row['vrc1_V'])
                                               - float(row['vrc2_V']) - float(row['B_2RC_voltage_V'])))
            for name in errors:
                error = (float(row[name+'_voltage_V'])-float(source['voltage_V']))*1000
                errors[name].append(error)
                if name not in worst or abs(error)>worst[name][0]:
                    worst[name]=(abs(error),t,float(row['current_discharge_A']))
            counts += 1
    assert counts == len(last_source) == 79058
    assert source_max < 1e-12 and algebra_max < 1e-12
    saved = json.loads((BASE / 'BL_BLYTH_VOLTAGE_20261015_01/metrics.json').read_text())
    metric_differences = {}
    for name, values in errors.items():
        n = len(values)
        sorted_abs = sorted(abs(v) for v in values)
        index = .95*(n-1)
        lower = math.floor(index)
        fraction = index-lower
        p95 = sorted_abs[lower] + fraction*(sorted_abs[min(lower+1,n-1)]-sorted_abs[lower])
        metrics = {'mae_mV': math.fsum(abs(x) for x in values)/n,
                   'rmse_mV': math.sqrt(math.fsum(x*x for x in values)/n),
                   'bias_mV': math.fsum(values)/n, 'max_abs_mV': worst[name][0],
                   'p95_abs_mV': p95, 'count': n, 'worst_time_s': worst[name][1],
                   'worst_current_A': worst[name][2]}
        for key, value in metrics.items():
            diff = abs(value - saved[name][key])
            assert diff < 1e-9, (name, key, diff)
            metric_differences[name+'.'+key] = diff
    first = BASE / 'BL_BLYTH_VOLTAGE_20261015_01/predictions.csv'
    second = BASE / 'BL_BLYTH_VOLTAGE_20261015_02/predictions.csv'
    replay = {'status': 'not_yet_complete'}
    if second.exists():
        assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()
        replay = {'status': 'identical_file_sha256', 'sha256': hashlib.sha256(first.read_bytes()).hexdigest()}
    # Verify existing household results/protocols and current presentation were not modified.
    old = ROOT / 'work/resource_sample_selection_20261013/downloads/rwth_home_endpoint_evidence_20261015/preservation_before_01.json'
    previous = json.loads(old.read_text(encoding='utf-8'))['preserved_files']
    sample_root = ROOT / 'work/resource_sample_selection_20261013'
    preserved = 0
    for relative, expected in previous.items():
        path = sample_root / relative
        if not path.exists():
            path = ROOT / relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, str(path)
        preserved += 1
    current = json.loads((BASE / 'presentation_preservation_before.json').read_text(encoding='utf-8'))
    for relative, expected in current.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    receipt = {'status': 'passed', 'source_seconds': len(last_source), 'predictions': counts,
               'source_alignment_max_diff': source_max, 'voltage_identity_max_diff_V': algebra_max,
               'max_metric_difference_mV': max(metric_differences.values()), 'metric_differences': metric_differences,
               'replay': replay, 'old_preserved_files': preserved, 'current_presentation_preserved': len(current),
               'scope': 'Checks computation and preservation, not SOC truth or physical accuracy'}
    target = BASE / ('verification_final.json' if second.exists() else 'verification_metrics_01.json')
    assert not target.exists()
    target.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))

if __name__ == '__main__':
    main()
