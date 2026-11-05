import json,hashlib
from pathlib import Path
import numpy as np
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1];RAW=ROOT/'data/B1_B3_continuity_v1_20261028'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def write(p,obj):
    def convert(x):
        if isinstance(x,np.generic):return x.item()
        if isinstance(x,np.ndarray):return x.tolist()
        raise TypeError(type(x).__name__)
    text=json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False,default=convert);p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:f.write(text)

def integrity():
    f=read(BASE/'source_freeze.json')
    repair=read(BASE/'corrective_identity.json') if (BASE/'corrective_identity.json').exists() else {}
    for group,root in [('source',BASE),('protected',ROOT)]:
        for n,h in f[group].items():
            if group=='source' and n in repair.get('source',{}):
                item=repair['source'][n];assert item['before_sha256']==h and sha(BASE/item['preserved_original'])==h,n;h=item['after_sha256']
            assert sha(root/n)==h,n
    return f
