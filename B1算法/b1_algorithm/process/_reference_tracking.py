"""Retrospective reference-error tracking for the existing duration extractor.

The task starts at0. Observed[-15,0) intervals calibrate a smooth error trajectory;
task-period and rebound measurements never enter that calibration. The original
notice-time reference, raw observations and energy accounting remain available.
"""
from pathlib import Path
from functools import lru_cache
import json,hashlib
import numpy as np
from ._duration_fusion import validate_domain,fit_duration_fusion

@lru_cache(maxsize=1)
def _model():
    raw=Path(__file__).with_name('reference_tracking_model.json').read_bytes()
    return json.loads(raw),hashlib.sha256(raw).hexdigest()

def prepare_tracking(data):
    validate_domain(data)
    if not np.isclose(data['delta'],1.,atol=1e-9,rtol=0):raise ValueError('reference tracking currently supports native1min meters')
    model,identity=_model();observed=data['y'][:15]
    bias=(observed-model['mean'])/model['scale']@np.asarray(model['coef']).T+model['intercept']
    return dict(data,native_y=data['y']-bias,reference_error_prediction=bias,reference_tracking_model=identity)

def complete_tracking(data,native,base,backend):
    from .api import _result,_features
    original=native.get(base,{})
    if original.get('status')!='ok':
        return dict(status='unavailable',method='CPOP_reference_tracked_duration',reason='original_CPOP_unavailable',
                    features=None,eta_raw=None,selection_evidence={},physical_timing=None,uncertainty_status='unavailable',backend=backend)
    corrected=dict(data,y=data['native_y'],reference=data['reference']-data['reference_error_prediction'])
    original=dict(original,prediction=np.asarray(original['prediction'],float))
    fitted=fit_duration_fusion(corrected,original['prediction'])
    result=_result(data,original['prediction'],'ok','CPOP_reference_tracked_duration','pre_actuation_error_tracking_then_retained_duration',
        dict(policy='reference_tracked_duration',n_bins=len(data['y']),tracking_model=data['reference_tracking_model'],
            calibration_window_task_relative_minutes=[-15,0],uses_response_period_for_tracking=False,uses_rebound_for_tracking=False,
            reference_at_notice_changed=False,tracking_role='retrospective process nuisance; assumes instructed actuation starts at0',
            **{k:v for k,v in fitted.items() if k!='prediction'}),backend)
    refined=_features(corrected,fitted['prediction'])['selected_curve']
    for key in ['cumulative_response_seconds','longest_continuous_response_seconds']:result['features']['selected_curve'][key]=refined[key]
    result['features']['sources']=dict(duration='conditional_reference_error_tracking_then_frozen_duration_fusion',
        other_process_features='original_CPOP_on_same_conditionally_corrected_residual',accounting='raw_observed_interval_integral')
    result['duration_state_curve_kw']=[float(v) for v in fitted['prediction']]
    result['duration_state_curve_role']='threshold-state representation for duration only; not physical meter data'
    result['reference_error_interval_kw']=[float(v) for v in data['reference_error_prediction']]
    result['conditional_reference_interval_kw']=[float(v) for v in corrected['reference']]
    result['conditional_reference_role']='retrospective process estimate, not an available-at-notice forecast'
    return result
