from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,platform
ROOT=Path(__file__).resolve().parent
receipt=ROOT/'main_freeze.json'
if receipt.exists():raise RuntimeError('main protocol already frozen')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
paths=[ROOT/n for n in ['protocol.json','models.py','run_process.py','cpop_batch.R','check_methods.py']]
work=ROOT.parents[1]
protected=[work/'b1_research_20261021/features.py',work/'b1_fullcycle_features_20261026/methods.py']
protected+=list((work/'ride_b1_v02_reproduction_20261029/source/ride_b1').rglob('*.py'))
out=dict(utc=datetime.now(timezone.utc).isoformat(),python=platform.python_version(),
         protocol_and_code={str(p.relative_to(ROOT)):sha(p) for p in paths},
         original_sources={str(p):sha(p) for p in protected},
         main_command='python run_process.py prepare --mode main',
         pilot_status='separate development seeds completed; no outcome-based parameter selection')
receipt.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'frozen':True,'protected_original_files':len(protected),'main_test_variants':960}))
