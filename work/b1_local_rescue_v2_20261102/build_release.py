"""Package the independently confirmed additive local detector, preserving old routes."""
from common import *
import ast,shutil

assert read('assessment.json')['adopted']
before=read('freeze.json')['source_sha256']
for p,h in before.items():assert sha(ROOT/p)==h,p
write('production_before.json',{p:h for p,h in before.items() if p.startswith('B1算法/')})
for relative in ['B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py','B1算法/README.md','AGENTS.md']:
    dst=HERE/'production_before'/relative;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/relative,dst)
def functions(path,names):
    source=path.read_text(encoding='utf-8');tree=ast.parse(source)
    return '\n\n'.join(ast.get_source_segment(source,node) for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names)
header='''"""Local raw-trajectory short-response rescue for known-reference historical tasks.

Add localized evidence to the adopted duration method. Original meter values,
raw energy and original structural curve remain unchanged. Standard frozen HGB,
two-sided pulse scan and fusion; no new CPOP solver or fault-truth guarantee.
"""
from pathlib import Path
from functools import lru_cache
import hashlib,json
import numpy as np
from scipy.special import expit
from scipy.ndimage import median_filter
from . import _duration_fusion as DF
'''
footer='''

@lru_cache(maxsize=1)
def _artifacts():
    folder=Path(__file__).with_name('local_response_models')
    meta=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    raw=(folder/'local.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=meta['model_sha256']:raise ValueError('local response model hash mismatch')
    payload=json.loads(raw)
    if payload['features']!=50:raise ValueError('local response feature schema mismatch')
    return meta,payload

def intervals(mask,starts,step):
    edge=np.diff(np.r_[False,mask,False].astype(int))
    return [[float(starts[a]),float(starts[b-1]+step)] for a,b in zip(np.flatnonzero(edge==1),np.flatnonzero(edge==-1))]

def fit_local_response(data,baseline_result):
    meta,model=_artifacts();cfg=meta['configuration']
    case=dict(starts_s=data['starts']*60,ends_s=data['ends']*60,power_kw=data['power'],reference_kw=data['reference'],sigma=data['sigma'])
    probability=expit(fast_predict(model,raw_features(case)))
    features=baseline_result['features']['selected_curve']
    baseline=[features['cumulative_response_seconds'],features['longest_continuous_response_seconds']]
    support=baseline_result['retained_duration_support_curve_kw'];physical=baseline_result['selection_evidence']['physical_change_score']
    mask,value,added=rescue(case,support,baseline,physical,probability,cfg['threshold'],cfg['z_threshold'],cfg['amplitude_margin_sigma'])
    return dict(cumulative_response_seconds=float(value[0]),longest_continuous_response_seconds=float(value[1]),
        localized_threshold_state=mask.tolist(),localized_response_intervals_seconds=intervals(mask,case['starts_s'],data['delta']*60),
        rescued_response_intervals_seconds=intervals(added,case['starts_s'],data['delta']*60),
        rescued_bins=int(sum(added)),duration_source='local_rescue_mask' if baseline[0]<=0 and added.any() else 'adopted_direct_duration_calibration',
        model_sha256=meta['model_sha256'],raw_input_points_replaced=False)
'''
production=ROOT/'B1算法/b1_algorithm/process';out=production/'_local_response.py';assert not out.exists()
source=header+'\n'+functions(HERE/'raw_features.py',{'raw_features'})+'\n\n'+functions(HERE/'evaluate.py',{'fast_predict'})+'\n\n'+functions(HERE/'local_model.py',{'durations','rescue'})+footer
out.write_text(source,encoding='utf-8');folder=production/'local_response_models';folder.mkdir(exist_ok=False)
cfg=read('selected.json')['config'];shutil.copy2(HERE/(cfg['model']+'.json'),folder/'local.json')
manifest=dict(schema='b1.local-response.v1',configuration=cfg,features=50,model_sha256=sha(folder/'local.json'),
    training='Standard sklearn1.7.2 HGB;50 independent raw-observation multiscale features. No CPOP,shape/seed/condition/truth in input.',
    operating_scope='Known reference,30min,q1.5kW,sigma.05,10s/1min,15minpre/post,default physical criterion; quiet-background weak pulse rescue1..60s.',
    final_assessment_sha256=sha(HERE/'assessment.json'),no_field_accuracy_claim=True,
    retained_duration_functionals_distinct_from_localized_mask=True,global_default_unchanged=True)
(folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
write('release_build.json',dict(files={p.relative_to(ROOT).as_posix():sha(p) for p in [out]+list(folder.glob('*'))},manifest=manifest))
print('Local detector packaged',cfg,flush=True)
