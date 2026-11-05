"""Package exactly the frozen, independently checked functional estimator."""
from common import *
import ast,shutil

assert read('confirmation_assessment.json')['adoption_gates_pass']
before=read('freeze.json')['source_sha256']
for p,h in before.items():assert sha(ROOT/p)==h,p
write('production_before.json',{p:h for p,h in before.items() if p.startswith('B1算法/')})
for relative in ['B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py','B1算法/README.md','AGENTS.md']:
    src=ROOT/relative;dst=HERE/'production_before'/relative;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)

def functions(path,names):
    source=path.read_text(encoding='utf-8');tree=ast.parse(source)
    return '\n\n'.join(ast.get_source_segment(source,node) for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names)

header='''"""Known-reference retrospective duration calibration; observed full curves only.

Standard frozen boosted trees complement CPOP. Original input and structural
curve remain available; calibrated duration functionals do not define a new
pointwise physical curve. Existing duration_fusion is unchanged.
"""
from pathlib import Path
from functools import lru_cache
import hashlib,json
import numpy as np
from scipy.special import expit
from scipy.ndimage import uniform_filter1d
from ._duration_fusion import validate_domain,fit_duration_fusion
'''
footer='''

@lru_cache(maxsize=1)
def _artifacts():
    folder=Path(__file__).with_name('known_duration_models')
    meta=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    if meta['schema']!='b1.known-duration.v1':raise ValueError('known duration model schema mismatch')
    models={}
    for name,expected in meta['model_files'].items():
        if name not in ('cumulative.json','longest.json','event.json'):raise ValueError('unknown duration asset')
        raw=(folder/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('known duration asset hash mismatch')
        payload=json.loads(raw)
        if payload['features']!=171:raise ValueError('known duration feature schema mismatch')
        models[name]=payload
    identity=hashlib.sha256(json.dumps(meta,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return meta,models,identity

def fit_known_duration(data,original_prediction):
    validate_domain(data)
    old=fit_duration_fusion(data,original_prediction)
    case=dict(starts_s=data['starts']*60,ends_s=data['ends']*60,
              power_kw=data['power'],reference_kw=data['reference'],sigma=data['sigma'])
    X=input_features(case,original_prediction,old['prediction'])[None,:]
    meta,models,identity=_artifacts();cfg=meta['configuration']
    score=float(expit(tree_predict(models['event.json'],X))[0]);accepted=score>=cfg['event_threshold']
    delta=np.array([tree_predict(models[name],X)[0] for name in ['cumulative.json','longest.json']])
    value=refine(case,original_prediction,old['prediction'],delta,accepted,cfg['shrink'])
    return dict(cumulative_response_seconds=float(value[0]),longest_continuous_response_seconds=float(value[1]),
        retained_prediction=old['prediction'],model_id=identity,retained_model_id=old['model_id'],
        physical_change_score=score,physical_change_threshold=cfg['event_threshold'],physical_change_accepted=bool(accepted),
        score_is_calibrated_probability=False,field_fault_classification_validated=False,
        duration_estimator='full_observed_trajectory_duration_residual_calibration',
        reference_assumed_known=True,points_deleted_or_replaced_in_input=False)
'''
production=ROOT/'B1算法/b1_algorithm/process';out=production/'_known_duration.py'
assert not out.exists()
out.write_text(header+'\n'+functions(HERE/'task_model.py',{'features'})+'\n\n'+functions(HERE/'model.py',{'durations','input_features','refine'})+'\n\n'+functions(HERE/'candidate.py',{'tree_predict'})+footer,encoding='utf-8')
folder=production/'known_duration_models';folder.mkdir(exist_ok=False)
mapping={'cumulative_leaves63.json':'cumulative.json','longest_leaves63.json':'longest.json','physical_event_model.json':'event.json'}
for src,dst in mapping.items():shutil.copy2(HERE/src,folder/dst)
manifest=dict(schema='b1.known-duration.v1',configuration=read('selected.json')['config'],
    model_files={dst:sha(folder/dst) for dst in mapping.values()},features=171,
    method='CPOP plus retained duration state support, whole-trajectory physical-change evidence and direct duration residual calibration',
    validation_scope='Known reference; controlled EV ODE simulations,30min,q1.5kW,sigma0.05kW,10s/1min,15min pre/post. No field accuracy claim.',
    model_training='Standard scikit-learn1.7.2 HistGradientBoosting models; not a newly invented tree algorithm.',
    final_confirmation_sha256=sha(HERE/'confirmation_assessment.json'),
    all_initial_validation_failures_retained=True,strict_validation_screen_passed=False,
    independent_confirmation_gates_passed=True,default_policy_unchanged=True)
(folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
write('release_build.json',dict(files={p.relative_to(ROOT).as_posix():sha(p) for p in [out]+list(folder.glob('*'))},model_manifest=manifest))
print('Built frozen known duration release',flush=True)
