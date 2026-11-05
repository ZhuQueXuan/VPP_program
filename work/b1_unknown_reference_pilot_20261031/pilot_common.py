"""Local pilot paths, JSON and source identity. No old artifact mutation."""
from pathlib import Path
import hashlib,json,importlib.util
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
FACTS=ROOT/'data/B1_unknown_reference_pilot_v1_20261031'
PYTHON=ROOT/'work/ride_b1_v02_reproduction_20261029/.venv/Scripts/python.exe'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def native(v):
    if isinstance(v,np.ndarray):return v.tolist()
    if isinstance(v,np.generic):return v.item()
    if isinstance(v,dict):return {str(k):native(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [native(x) for x in v]
    return v
def write_new(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as h:json.dump(native(value),h,ensure_ascii=False,allow_nan=False,separators=(',',':'))
def load_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
def facts_path(phase,seed,variant):return FACTS/phase/f'{seed}_{variant}_facts.json'
def truth_path(phase,seed,variant):return HERE/'evaluator'/phase/f'{seed}_{variant}_truth.json'
def source_identity():
    files=[HERE/name for name in ['protocol.json','pilot_common.py','make_data.py','run.py','assess.py','reference_models.py','trend_filter.py']]
    files.extend(p for p in (ROOT/'B1算法').rglob('*') if p.is_file() and p.suffix in ('.py','.R','.json'))
    files.extend([ROOT/'work/b1_reliability_20261031/study/generator.py',ROOT/'work/b1_ev_mainline_20261030/simulation.py'])
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)}
def assert_identity(expected):
    actual=source_identity()
    if actual!=expected:raise RuntimeError('frozen source changed: '+str([k for k in set(actual)|set(expected) if actual.get(k)!=expected.get(k)]))
