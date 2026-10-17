"""Freeze a limited public-parameter experiment before evaluating any errors."""
from pathlib import Path
import csv
import datetime
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'work/resource_sample_selection_20261013/downloads/blyth_ecm_20261015'
PROTOCOL = Path(__file__).with_name('blyth_voltage_protocol_v1.json')
assert not PROTOCOL.exists()
for name in ['MLP001_params.csv', 'MLP001_ocv.csv']:
    source = OUT / 'author/research/processed_data' / name
    target = OUT / ('25C_' + name)
    assert not target.exists()
    with source.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        selected = [row for row in reader if float(row['Temperature_degC']) == 25]
    with target.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(selected)

files = ['author/research/scripts/model.py', 'author/research/lab_data/MLP001_wltp_25degC.xlsx',
         'author/research/processed_data/MLP001_params.csv', 'author/research/processed_data/MLP001_ocv.csv',
         '25C_MLP001_params.csv', '25C_MLP001_ocv.csv', 'wltp_source_rows.csv']
protocol = {
    'id': 'BLYTH_VOLTAGE_20261015_V1',
    'frozen_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'status_at_freeze': 'not_executed',
    'purpose': 'Public-parameter 2RC conditional voltage benchmark; not full paper reproduction or capacity identification',
    'author_commit': 'b60bf6ea91aa89bc2504be9589246c12d77c1fc3',
    'lineage': 'Published parameters are fitted from pulse data; author WLTP is a reference validation experiment, not a new independent confirmation set',
    'known_prior': ['Read author scripts, parameter ranges and source quality, no model prediction errors computed',
                    'Author demo uses SOC0 .99 and cropped tail; this protocol does not use that demo',
                    'Author paper build references separate single-temperature files absent from fixed tree; extracted 25C rows of public combined tables are not asserted identical'],
    'data': {'raw_rows': 395302, 'time_start_s': 0, 'time_end_s': 79057,
             'time_resolution': 'integer seconds with duplicate rows; actual subsecond times unknown',
             'current': 'Use original ordered duplicate-time source arrays via numpy.interp, positive discharge; do not deduplicate input',
             'voltage_reference': 'At every integer second 0..79057 inclusive, last raw voltage in source order; original duplicates remain preserved',
             'demo_csv': 'Not used; current differs from raw workbook by up to .7790062 A under last-row alignment',
             'temperature': 'Use author 25C isothermal assumption; measured 23.7..26.1C only context'},
    'parameters': {'capacity_Ah': 2.132, 'initial_soc': 1.0, 'temperature_C': 25.0,
                   'initial_vrc_V': [0.0, 0.0], 'thermal_mass': 'infinity',
                   'soc_parameter_domain': [0.05, 1.01], 'temperature_domain': [25.0, 25.0],
                   'lookup': 'Author model uses PCHIP in SOC for extracted single-temperature tables; no extrapolation'},
    'solver': {'method': 'RK45', 'max_step_s': 2.0, 'atol': 1e-5, 'rtol': 1e-5,
               'evaluation_times': 'all integer seconds; t_eval does not change adaptive stepping',
               't_max_s': 79057.0},
    'methods': {'B_2RC': 'Unmodified author TheveninModel',
                'B_R0': 'Same current, OCV, capacity, SOC trajectory and R0; remove only RC polarization terms; no measurement feedback'},
    'metrics': ['voltage MAE mV', 'voltage RMSE mV', 'signed bias mV', 'max absolute error mV',
                'absolute error p95 mV', 'valid/required count', 'worst timestamp and current'],
    'decision': {'comparison': '2RC adds benchmark evidence only if full finite coverage and lower MAE and RMSE than R0',
                 'absolute_usefulness': 'No use-case absolute error tolerance justified yet; no field deployment or 90% acceptance claim',
                 'stop': 'One frozen evaluation; no tuning SOC, parameters, time alignment, window or method after errors. If solver/domain fails, report failure without crop/clip/extrapolation'},
    'reproducibility': {'rerun_max_abs_voltage_difference_V': 1e-10,
                        'independent_metric_tolerance_mV': 1e-9,
                        'meaning': 'Numerical reproducibility tolerances only, not physical accuracy'},
    'non_claims': ['online SOC accuracy', 'estimated capacity or SOH', 'unknown future power forecast',
                   'thermal dynamics', 'charging validation', 'transfer to system01 or M5BAT', 'VPP deliverable capacity'],
    'input_sha256': {p: hashlib.sha256((OUT / p).read_bytes()).hexdigest() for p in files}
}
PROTOCOL.write_text(json.dumps(protocol, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'protocol': str(PROTOCOL), 'sha256': hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()}))
