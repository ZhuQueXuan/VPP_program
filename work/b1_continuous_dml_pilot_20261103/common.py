import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import json,hashlib,datetime,sys
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.effects import continuous as CT
def native(v):
    if isinstance(v,np.ndarray):return v.tolist()
    if isinstance(v,np.generic):return v.item()
    if isinstance(v,dict):return {k:native(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [native(x) for x in v]
    return v
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(name,value):
    p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(native(value),f,ensure_ascii=False,indent=2,allow_nan=False)
def verify_freeze(name='freeze.json'):
    for p,h in read(HERE/name)['files'].items():assert sha(ROOT/p)==h,p
DOMAIN=(0.,2.4);GRID=np.linspace(.3,2.1,31);T=1800.
ASSUMPTIONS=dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,same_outcome_definition=True,conditional_exchangeability=True,randomized_assignment=False)
TASK=dict(task_id='continuous-duration-common30min',outcome_name='cumulative_response_seconds',outcome_unit='seconds',target_population='declared_synthetic_EV_population_all_events',window_minutes=[0.,30.],q_kw=1.5,task_pre_treatment=True,reference_status='provided',reference_uncertainty='not_propagated')
