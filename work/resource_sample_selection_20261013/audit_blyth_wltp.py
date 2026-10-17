"""Source admission only: read workbook dimensions correctly; no model or errors."""
from pathlib import Path
import csv
import hashlib
import json
import math
import openpyxl

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'work/resource_sample_selection_20261013/downloads/blyth_ecm_20261015'
target = OUT / 'wltp_source_rows.csv'
assert not target.exists()
workbook = OUT / 'author/research/lab_data/MLP001_wltp_25degC.xlsx'
wb = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
sheet = wb['record']
declared_dimension = sheet.calculate_dimension()
sheet.reset_dimensions()  # workbook incorrectly declares A1:A1
rows = sheet.iter_rows(values_only=True)
header = next(rows)
pos = {v: i for i, v in enumerate(header)}
counts = {'rows': 0, 'duplicate_time_rows': 0, 'negative_dt': 0, 'nonfinite': 0, 'missing_second_gaps': 0}
previous = None
ranges = {key: [math.inf, -math.inf] for key in ['time_s','current_discharge_A','voltage_V','temperature_C']}
with target.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['source_row','time_s','current_discharge_A','voltage_V','temperature_C','step_type'])
    writer.writeheader()
    for n, row in enumerate(rows, 2):
        h, m, s = map(int, row[pos['Total Time']].split(':'))
        time = h*3600 + m*60 + s
        values = {'time_s': time, 'current_discharge_A': -float(row[pos['Current(A)']]),
                  'voltage_V': float(row[pos['Voltage(V)']]), 'temperature_C': float(row[pos['T1(℃)']])}
        counts['rows'] += 1
        counts['nonfinite'] += int(not all(math.isfinite(v) for v in values.values()))
        if previous is not None:
            counts['duplicate_time_rows'] += int(time == previous)
            counts['negative_dt'] += int(time < previous)
            counts['missing_second_gaps'] += max(time - previous - 1, 0)
        previous = time
        for k, v in values.items():
            ranges[k][0] = min(ranges[k][0], v)
            ranges[k][1] = max(ranges[k][1], v)
        writer.writerow({'source_row': n, **values, 'step_type': row[pos['Step Type']]})
with (OUT / 'author/try_me/wltp.csv').open(encoding='utf-8', newline='') as f:
    drive = list(csv.DictReader(f))
receipt = {'status': 'source_audit_only_no_model_run', 'declared_dimension': declared_dimension,
           'actual_header': header, 'counts': counts, 'ranges': ranges,
           'drivecycle': {'rows': len(drive), 'first': drive[0], 'last': drive[-1]},
           'source_sha256': hashlib.sha256(workbook.read_bytes()).hexdigest(),
           'rows_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
(OUT / 'admission_01.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(receipt, ensure_ascii=False, indent=2))
