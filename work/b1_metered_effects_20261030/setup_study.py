from pathlib import Path
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import copy,hashlib,importlib.util,json,sys
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'B1算法'))
sys.path.insert(0,str(ROOT/'work/b1_mainline_20261029/causal'))
import b1_algorithm
from b1_algorithm.effects import fit_effects,EffectConfig
from b1_algorithm.effects.core import aipw_scores
from simulation import generate
spec=importlib.util.spec_from_file_location('b1_algorithm._metered_candidate',HERE/'prototype.py')
metered=importlib.util.module_from_spec(spec);sys.modules[spec.name]=metered;spec.loader.exec_module(metered)
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
LEVELS=np.arange(7)*.4

def panel(seed,scenario,n_users=600):
    a=generate(seed,scenario,n_users=n_users,events_per_user=6)
    x=a['X'];g=a['groups'];rng=np.random.default_rng(seed+54321)
    baseline=3+.35*x[:,0]+.2*x[:,1]+.15*x[:,2]+.1*x[:,0]**2+.12*rng.normal(size=n_users)[g]
    reference=2.75+.2*x[:,0]+.2*x[:,1]
    assert np.min(baseline[:,None]-a['potential'])>0.,'physical margin required without clipping'
    z=a['y']-baseline;predicted_eta=a['y']+reference-baseline
    users=[f'user-{u}' for u in g];records=[]
    for i,power in enumerate(-1.5*z):
        start=1000000.+i*120
        task=dict(task_id=f'event-{i}',user_id=users[i],meter_id='meter-'+users[i],
            start_min=start,end_min=start+30.,notice_min=start-15.,request_kw=1.5,task_pre_treatment=True)
        records.append(dict(task=task,starts_min=start+np.arange(30.),ends_min=start+np.arange(1.,31.),power_kw=np.full(30,power)))
    return a,baseline,reference,z,predicted_eta,users,records

def assumptions(scenario):
    return dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,same_outcome_definition=True,
        conditional_exchangeability=None if scenario=='rct_positive' else True,randomized_assignment=scenario=='rct_positive')

def task_context(outcome='eta_raw'):
    return dict(task_id='common_task30min1p5kw',outcome_name=outcome,outcome_unit='ratio',window_minutes=[0.,30.],
        q_kw=1.5,target_population='supplied_event_population',task_pre_treatment=True,
        reference_status='evaluation_branch',reference_uncertainty='not_propagated')
