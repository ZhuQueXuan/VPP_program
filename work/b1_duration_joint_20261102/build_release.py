from common import *
import ast,shutil
assert read('assessment.json')['adopted']
for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
write('production_before.json',{p:h for p,h in read('freeze.json')['source_sha256'].items() if p.startswith('B1算法/')})
for p in ['B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py','B1算法/README.md','AGENTS.md']:
    dst=HERE/'production_before'/p;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/p,dst)
source=(HERE/'model.py').read_text(encoding='utf-8');tree=ast.parse(source)
functions='\n\n'.join(ast.get_source_segment(source,node) for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in {'gap_features','features','refine'})
header='''"""Gap-aware duration feature calibration over full known-reference observations.

Keeps adopted event decisions, localization and raw accounting. Standard frozen
HGB models estimate two duration functionals; this does not define a new power
curve or physical transition timing.
"""
from pathlib import Path
from functools import lru_cache
import hashlib,json
import numpy as np
from scipy.ndimage import uniform_filter1d
from . import _known_duration as KD,_local_response as LR
'''
footer='''

@lru_cache(maxsize=1)
def _artifacts():
    folder=Path(__file__).with_name('gap_duration_models')
    meta=json.loads((folder/'manifest.json').read_text(encoding='utf-8'));models={}
    for name,expected in meta['model_files'].items():
        raw=(folder/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('gap duration model hash mismatch')
        model=json.loads(raw)
        if model['features']!=426:raise ValueError('gap duration feature schema mismatch')
        models[name]=model
    return meta,models

def fit_gap_duration(data,baseline_result):
    meta,models=_artifacts();cfg=meta['configuration']
    case=dict(starts_s=data['starts']*60,ends_s=data['ends']*60,power_kw=data['power'],reference_kw=data['reference'],sigma=data['sigma'])
    old=baseline_result['duration_estimates'];baseline=[old['cumulative_response_seconds'],old['longest_continuous_response_seconds']]
    X=features(case,baseline_result['reduction_interval_kw'],baseline_result['retained_duration_support_curve_kw'],baseline)[None,:]
    prediction=[LR.fast_predict(models[name],X)[0] for name in ['cumulative.json','longest.json']]
    value=refine(case,baseline,prediction,cfg['mix'],cfg['head'])
    return dict(cumulative_response_seconds=float(value[0]),longest_continuous_response_seconds=float(value[1]),
        model_sha256=meta['model_files'],duration_values_changed=bool(np.any(abs(value-np.asarray(baseline))>1e-8)),
        task_decision_changed=bool((value[0]>0)!=(baseline[0]>0)),localized_mask_changed=False,raw_points_replaced=False)
'''
production=ROOT/'B1算法/b1_algorithm/process';out=production/'_gap_duration.py';assert not out.exists();out.write_text(header+'\n'+functions+footer,encoding='utf-8')
folder=production/'gap_duration_models';folder.mkdir(exist_ok=False);cfg=read('selected.json')['config']
mapping={f'cumulative{cfg["leaves"]}.json':'cumulative.json',f'{cfg["head"]}{cfg["leaves"]}.json':'longest.json'}
for src,dst in mapping.items():shutil.copy2(HERE/src,folder/dst)
meta=dict(schema='b1.gap-duration.v1',configuration=cfg,features=426,model_files={dst:sha(folder/dst) for dst in mapping.values()},
    method='Gap-aware direct cumulative/longest feature calibration with feasible joint bounds; standard HGB, no new solver claim.',
    selected_head=cfg['head'],validation_scope='Known-reference controlled EV ODE simulations,30min,q1.5,sigma.05,10s/1min,15minpre/post; no field claim.',
    classification_localization_and_raw_energy_unchanged=True,default_policy_unchanged=True,
    final_assessment_sha256=sha(HERE/'assessment.json'))
(folder/'manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
write('release_build.json',dict(files={p.relative_to(ROOT).as_posix():sha(p) for p in [out]+list(folder.glob('*'))},manifest=meta))
print('Gap-aware duration release packaged',cfg,flush=True)
