"""Prepare reviewable package files; does not touch production before gates pass."""
from common import *
import ast,shutil

def source_functions(path,names):
    text=path.read_text(encoding='utf-8');tree=ast.parse(text)
    return '\n\n'.join(ast.get_source_segment(text,node) for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names)

def main():
    out=HERE/'staging';out.mkdir(exist_ok=False);assets=out/'duration_models';assets.mkdir()
    cfg=read('selected_config.json')
    shutil.copyfile(HERE/cfg['quantile_model'],assets/'quantile.json');shutil.copyfile(HERE/cfg['state_model'],assets/'state.json')
    metadata=dict(schema='b1.duration-fusion.v1',configuration=cfg,model_files={name:sha(assets/name) for name in ['quantile.json','state.json']},
        training='Synthetic latent power and threshold states,1792case variants; not field-calibrated fault labels',
        method='Standard degree0/1 segmentation features, quantile/state boosting, original-CPOP event and short-structure safeguards',
        validation_scope='Controlled known-reference EV30min,q1.5kW,sigma.05,1min/10s,pre/post15min. No field/100ms or unknown-reference validation.',
        detector='Exactly preserves original CPOP threshold-positive task status; no claim of lower task false alarms',
        uncertainty='No validated process confidence interval or probability calibration claim')
    with (assets/'manifest.json').open('x',encoding='utf-8') as f:json.dump(metadata,f,ensure_ascii=False,indent=2)
    header='''"""Retrospective duration fusion; frozen synthetic model, explicit bounded domain.

Original measurements/accounting and default policy are preserved. This is a
domain-specific composition of standard models, not a new universal detector.
"""
from pathlib import Path
from functools import lru_cache
import hashlib,json
import numpy as np
from scipy.ndimage import uniform_filter1d,minimum_filter1d,maximum_filter1d
from scipy.special import expit

'''
    body=source_functions(HERE/'candidates.py',{'fit_segments'})+'\n\n'+source_functions(HERE/'learned.py',{'features','predict_model'})+'\n\n'+source_functions(HERE/'fusion.py',{'reconcile'})
    body=body.replace('def fit_segments(','def _segment_fit(').replace('def features(','def _model_features(').replace('def predict_model(','def _tree_predict(').replace('def reconcile(','def _reconcile(')
    orchestration='''

@lru_cache(maxsize=1)
def _artifacts():
    folder=Path(__file__).with_name('duration_models')
    meta=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    if meta.get('schema')!='b1.duration-fusion.v1':raise ValueError('duration model schema mismatch')
    models={}
    for name,expected in meta['model_files'].items():
        if name not in ('quantile.json','state.json'):raise ValueError('unknown duration model file')
        raw=(folder/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('duration model hash mismatch')
        value=json.loads(raw)
        if value.get('features')!=42:raise ValueError('duration model feature schema mismatch')
        models[name]=value
    identity=hashlib.sha256(json.dumps(meta,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return meta,models,identity

def validate_domain(data):
    checks={'W':30.,'q':1.5,'sigma':.05}
    for key,expected in checks.items():
        if not np.isclose(data[key],expected,atol=1e-9,rtol=0):raise ValueError('duration_fusion domain requires '+key+'='+str(expected))
    if not any(np.isclose(data['delta'],v,atol=1e-9,rtol=0) for v in (1.,1/6)):
        raise ValueError('duration_fusion requires1min or10s observed intervals')
    profile=data['profile']
    for key,expected in [('observation_pre_min',15.),('observation_post_min',15.),('onset_fraction',.1),('target_fraction',.9),('recovery_fraction',.1),('dwell_seconds',30.)]:
        if not np.isclose(getattr(profile,key),expected,atol=1e-9,rtol=0):raise ValueError('duration_fusion domain requires '+key+'='+str(expected))

def fit_duration_fusion(data,original_prediction):
    validate_domain(data)
    meta,models,identity=_artifacts();cfg=meta['configuration']
    original=np.asarray(original_prediction,float)
    if original.shape!=data['y'].shape or not np.isfinite(original).all():raise ValueError('complete original CPOP curve required')
    base=_segment_fit(data['y'],data['sigma'],cfg['beta'],0.)
    X=_model_features(data['y'],base['prediction'],data['sigma'],data['delta']*60)
    quantile=_tree_predict(models['quantile.json'],X)*data['sigma']
    probability=expit(_tree_predict(models['state.json'],X))
    pred,decision=_reconcile(original,quantile,probability,data['starts']*60,data['sigma'],cfg['threshold'],cfg['band_sigma'],cfg['change_cap'],cfg['preserve_gaps'])
    use=(data['starts']>=0)&(data['starts']<30)
    if not np.isfinite(pred).all() or bool(np.any(pred[use]>=.15))!=bool(np.any(original[use]>=.15)):
        raise ValueError('duration fusion violated original task-evidence contract')
    return dict(prediction=pred,model_id=identity,decision=decision,
        curve_role='threshold_state_reconciled_curve; original CPOP structural curve retained separately',
        training_domain=meta['validation_scope'],probability_calibrated=False,
        task_detection='original_CPOP_threshold_positive_unchanged',points_deleted_or_replaced_in_input=False)
'''
    with (out/'_duration_fusion.py').open('x',encoding='utf-8') as f:f.write(header+body+orchestration)
    write('staging_receipt.json',dict(files={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()},production_modified=False))
    print('production files staged, not installed',flush=True)
if __name__=='__main__':main()
