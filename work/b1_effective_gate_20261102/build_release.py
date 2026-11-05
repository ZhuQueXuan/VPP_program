from common import *
import ast,shutil
assert read('assessment.json')['adopted']
for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
write('production_before.json',{p:h for p,h in read('freeze.json')['source_sha256'].items() if p.startswith('B1算法/')})
for path in ['B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py','B1算法/README.md','AGENTS.md']:
    target=HERE/'production_before'/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/path,target)
source=(HERE/'model.py').read_text(encoding='utf-8');tree=ast.parse(source)
functions='\n\n'.join(ast.get_source_segment(source,n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'scope','infer'})
header='''"""Effective-response qualification of sustained weak observed histories.

Physical change, raw accounting and original structural traces are preserved.
A negative qualification does not mean no physical action or a device fault.
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
    folder=Path(__file__).with_name('effective_response_models')
    meta=json.loads((folder/'manifest.json').read_text(encoding='utf-8'));raw=(folder/'verifier.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=meta['model_sha256']:raise ValueError('effective verifier hash mismatch')
    model=json.loads(raw)
    if model['features']!=426:raise ValueError('effective verifier feature schema mismatch')
    return meta,model

def verify_effective(data,baseline_result):
    meta,model=_artifacts();cfg=meta['configuration']
    case=dict(starts_s=data['starts']*60,ends_s=data['ends']*60,power_kw=data['power'],reference_kw=data['reference'],sigma=data['sigma'])
    duration=baseline_result['duration_estimates'];baseline=np.array([duration['cumulative_response_seconds'],duration['longest_continuous_response_seconds']])
    X=GD.features(case,baseline_result['reduction_interval_kw'],baseline_result['retained_duration_support_curve_kw'],baseline)[None,:]
    score=float(expit(LR.fast_predict(model,X))[0]);value,mask,rejected=infer(case,baseline,baseline_result['localized_threshold_state'],score,cfg['threshold'],cfg['duration_cap'])
    return dict(cumulative_response_seconds=float(value[0]),longest_continuous_response_seconds=float(value[1]),
        qualified=bool(value[0]>0),rejected=bool(rejected),effective_score=score,score_is_calibrated_probability=False,
        threshold=cfg['threshold'],duration_cap_seconds=cfg['duration_cap'],localized_threshold_state=mask.tolist(),
        model_sha256=meta['model_sha256'],physical_change_evidence_preserved=True,raw_points_replaced=False)
'''
folder=ROOT/'B1算法/b1_algorithm/process';out=folder/'_effective_response.py';assert not out.exists();out.write_text(header+'\n'+functions+footer,encoding='utf-8')
assets=folder/'effective_response_models';assets.mkdir(exist_ok=False);cfg=read('selected.json')['config'];shutil.copy2(HERE/f'verifier{cfg["leaves"]}.json',assets/'verifier.json')
meta=dict(schema='b1.effective-response.v1',features=426,configuration=cfg,model_sha256=sha(assets/'verifier.json'),
    target='Whether any original-criterion effective duration exists; not physical participation or device-fault truth.',
    training='Standard installed sklearn1.7.2 HGB; positive5/effective-short50/negative1 costs, scores not calibrated probabilities.',
    scope='Known-reference controlled EV histories,30min,q1.5,sigma.05,10s/1min,15min pre/post. Sustained weak median0.075..0.20kW and adopted positive duration<=cap.',
    final_assessment_sha256=sha(HERE/'assessment.json'),no_field_accuracy_claim=True,previous_version_preserved=True)
(assets/'manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
write('release_build.json',dict(files={p.relative_to(ROOT).as_posix():sha(p) for p in [out]+list(assets.glob('*'))},manifest=meta))
print('Effective response verification packaged',cfg,flush=True)
