"""Effective-response qualification of sustained weak observed histories.

Physical change, raw accounting and original structural traces are preserved.
A negative qualification does not mean no physical action or a device fault.
"""
from pathlib import Path
from functools import lru_cache
import hashlib,json
import numpy as np
from scipy.special import expit
from . import _gap_duration as GD,_local_response as LR

def scope(case,baseline):
    s=np.asarray(case['starts_s']);inside=(s>=0)&(s<1800);y=np.asarray(case['reference_kw'])-np.asarray(case['power_kw']);median=float(np.median(y[inside]))
    return baseline[0]>0 and .075<median<.20

def infer(case,baseline,mask,probability,threshold,duration_cap):
    reject=scope(case,baseline) and baseline[0]<=duration_cap and probability<threshold
    if reject:return np.zeros(2),np.zeros(len(mask),bool),True
    return np.asarray(baseline).copy(),np.asarray(mask).copy(),False

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
