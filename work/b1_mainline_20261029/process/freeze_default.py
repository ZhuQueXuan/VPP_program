from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'supplement_native_default'
if (OUT/'freeze.json').exists():raise RuntimeError('already frozen')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
items=[OUT/'protocol.json',ROOT/'cpop_default_batch.R',ROOT/'main/cpop_input.csv',ROOT/'main/all_metrics.csv']
(OUT/'freeze.json').write_text(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),
    sha256={str(p):sha(p) for p in items},no_new_data=True,no_parameter_search=True),indent=2),encoding='utf-8')
print('default-grid fairness supplement frozen')
