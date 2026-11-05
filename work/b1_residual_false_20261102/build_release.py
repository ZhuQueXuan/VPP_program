from common import *
import ast,shutil
assert read('confirmation_decision.json')['adopted']
for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
for p,h in read('confirmation_freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
write('production_before.json',read('protected_before.json'))
for path in ['B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py','B1算法/README.md','AGENTS.md']:
    target=HERE/'production_before'/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/path,target)
source=(HERE/'model.py').read_text(encoding='utf-8');tree=ast.parse(source)
functions='\n\n'.join(ast.get_source_segment(source,n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'extra_features','scope','infer'})
header='''"""Multiscale observation evidence for effective-response qualification.
Keeps original measurements, physical evidence, structural traces and accounting.
This estimates criterion attainment, not fault identity or physical participation.
"""
from pathlib import Path
from functools import lru_cache
import hashlib,json
import numpy as np
from scipy.special import expit
from . import _gap_duration as GD,_local_response as LR
'''
footer='''

@lru_cache(maxsize=1)
def _artifacts():
    folder=Path(__file__).with_name('response_evidence_models')
    meta=json.loads((folder/'manifest.json').read_text(encoding='utf-8'));raw=(folder/'verifier.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=meta['model_sha256']:raise ValueError('response evidence model hash mismatch')
    model=json.loads(raw)
    if model['features']!=527:raise ValueError('response evidence feature schema mismatch')
    return meta,model

def features(case,baseline_result):
    # Previous qualification may already be negative. Reproduce its descriptor
    # from the preserved gap proposal rather than relabel zeroed duration as raw.
    proposal=baseline_result['duration_calibration']
    baseline=[proposal['cumulative_response_seconds'],proposal['longest_continuous_response_seconds']]
    prior=GD.features(case,baseline_result['reduction_interval_kw'],baseline_result['retained_duration_support_curve_kw'],baseline)
    return np.r_[prior,extra_features(case)].astype(np.float32)

def verify_observed(data,baseline_result):
    meta,model=_artifacts();cfg=meta['configuration']
    case=dict(starts_s=data['starts']*60,ends_s=data['ends']*60,power_kw=data['power'],reference_kw=data['reference'],sigma=data['sigma'])
    duration=baseline_result['duration_estimates'];baseline=np.array([duration['cumulative_response_seconds'],duration['longest_continuous_response_seconds']])
    X=features(case,baseline_result)[None,:]
    score=float(expit(LR.fast_predict(model,X))[0]);value,mask,rejected=infer(case,baseline,baseline_result['localized_threshold_state'],score,cfg['quiet_threshold'],cfg['weak_threshold'])
    return dict(cumulative_response_seconds=float(value[0]),longest_continuous_response_seconds=float(value[1]),qualified=bool(value[0]>0),rejected=bool(rejected),effective_score=score,score_is_calibrated_probability=False,
        quiet_threshold=cfg['quiet_threshold'],weak_threshold=cfg['weak_threshold'],localized_threshold_state=mask.tolist(),model_sha256=meta['model_sha256'],physical_change_evidence_preserved=True,raw_points_replaced=False)
'''
folder=ROOT/'B1算法/b1_algorithm/process';out=folder/'_response_qualification.py';assert not out.exists();out.write_text(header+'\n'+functions+footer,encoding='utf-8')
assets=folder/'response_evidence_models';assets.mkdir(exist_ok=False);cfg=read('selected.json')['config'];shutil.copy2(HERE/f'verifier{cfg["leaves"]}.json',assets/'verifier.json')
meta=dict(schema='b1.multiscale-effective-evidence.v1',features=527,configuration=cfg,model_sha256=sha(assets/'verifier.json'),
    target='Any original-criterion effective duration, not physical action or fault label.',training='Installed sklearn1.7.2 HGB, effective positives5/short50/negative1. Scores not calibrated.',
    scope='Known-reference EV histories30min,q1.5,sigma.05,10s/1min,15min pre/post. Already-positive task with observed median<0.20kW.',
    no_raw_replacement_or_minimum_action_duration=True,previous_version_preserved=True,no_field_accuracy_claim=True,final_assessment_sha256=sha(HERE/'confirmation_decision.json'),initial_gate_failure_preserved=True,one_fixed_independent_confirmation=True)
(assets/'manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
write('release_build.json',dict(files={p.relative_to(ROOT).as_posix():sha(p) for p in [out]+list(assets.glob('*'))},manifest=meta))
print('Multiscale effective qualification packaged',cfg,flush=True)
