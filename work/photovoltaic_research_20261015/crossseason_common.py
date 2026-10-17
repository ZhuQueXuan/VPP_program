"""Process-only utilities for the preregistered D055 confirmation."""
from pathlib import Path
import csv,hashlib,json,sys
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
for d in ('work/teacher_storage_brief_20261014/plot_dependencies','work/python_packages/storage_ecm_20261015','work/python_packages/pvlib_smart_20261015','work/python_packages/pv_metadata_20261015'):
    sys.path.insert(0,str(ROOT/d))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def table(p,rows):
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def read(p):
    with p.open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))
def frozen():
    p=json.loads((BASE/'crossseason_protocol_v1.json').read_text())
    assert sha(BASE/'crossseason_protocol_v1.json')=='f202ee39e8b62ff8340067b3c090e84a8a8256a52b7edc803a30cbe804f11c56'
    for a in p['frozen_artifacts'].values():assert sha(ROOT/a['path'])==a['sha256'],a
    return p
