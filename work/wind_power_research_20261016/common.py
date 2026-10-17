"""Process-only utilities for source-specific wind research."""
from pathlib import Path
import csv,hashlib,json
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
