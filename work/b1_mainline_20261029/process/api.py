"""Research API; package-safe imports, fixed supported domain and provenance."""
from functools import lru_cache
from pathlib import Path
import importlib
import importlib.util
import sys
import numpy as np
try:
    from .models import fit
except ImportError:  # direct script context only
    from models import fit

@lru_cache(maxsize=1)
def _originals():
    work=Path(__file__).resolve().parents[2]
    spec=importlib.util.spec_from_file_location('_b1_process_frozen_f0_api',work/'b1_research_20261021/features.py')
    f0=importlib.util.module_from_spec(spec);spec.loader.exec_module(f0)
    source=work/'ride_b1_v02_reproduction_20261029/source/ride_b1/ride'
    name='_b1_process_original_ride_api'
    if name not in sys.modules:
        pkg_spec=importlib.util.spec_from_file_location(name,source/'__init__.py',submodule_search_locations=[str(source)])
        pkg=importlib.util.module_from_spec(pkg_spec);sys.modules[name]=pkg;pkg_spec.loader.exec_module(pkg)
    identify=importlib.import_module(name+'.identify')
    template=importlib.import_module(name+'.template')
    return f0,identify,template

def features(y,delta):
    f0,_,_=_originals()
    s=np.arange(-15,45-1e-8,delta);t=np.r_[s,s[-1]+delta]*60
    result=f0.extract(t,np.full(len(s),3.),3-np.asarray(y),t0=0,t1=1800,q=1.5,
                      dwell_samples=max(1,int(np.ceil(.5/delta-1e-9))))
    value=lambda key:None if result[key] is None else float(result[key][1])
    return dict(onset_s=value('onset_interval_s'),target_s=value('target_interval_s'),
                recovery_s=result['power_recovery_time_s'],stage=result['stage'])

def ride_fit(y,delta,sigma):
    _,identify,template=_originals()
    s=np.arange(-15,45-1e-8,delta)
    event=identify.EventInput(s=s,e=s+delta,r=y,q=1.5,W=30,obs_end=45,a_max=1.5,b_max=1,
                              sigma=sigma,sB=0,delta=delta,is_ev=1,event_id=0)
    out=identify.identify_event(event,structures=(0,1,2),n_starts=3,ci_method='none',lr_crit=None,seed=711)
    if not out['A_hat']:return np.zeros(len(y)),dict(ride_structure=0)
    theta=np.array([out[f'th_{key}'] for key in template.PARAM_NAMES_M2])
    return 1.5*template.interval_average(theta,30,s,s+delta),dict(ride_structure=int(out['struct']))

def fit_average_process(starts,ends,power,reference,sigma,*,method):
    s,e,p,b=(np.asarray(v,float) for v in (starts,ends,power,reference))
    if s.ndim!=1 or len(s)<4 or e.shape!=s.shape or p.shape!=s.shape or b.shape!=s.shape:
        raise ValueError('matching 1D interval and power arrays required')
    if not all(np.isfinite(v).all() for v in (s,e,p,b)) or np.any(e<=s):
        raise ValueError('missing or nonfinite input is unavailable; no silent interpolation')
    delta=float(e[0]-s[0])
    if not any(np.isclose(delta,d,atol=1e-9,rtol=0) for d in [1/6,1.,15.]):
        raise ValueError('supported meter widths:10 seconds,1 minute,15 minutes')
    expected=np.arange(-15,45-1e-8,delta)
    if s.shape!=expected.shape or not np.allclose(s,expected,atol=1e-8,rtol=0) or not np.allclose(e,s+delta,atol=1e-8,rtol=0):
        raise ValueError('supported retrospective window:-15..45min; request0..30min; no extrapolation')
    if isinstance(sigma,(bool,np.bool_)) or not np.isscalar(sigma) or not np.isfinite(sigma) or sigma<=0:
        raise ValueError('positive declared noise in kW required')
    residual=b-p
    if method=='grid_average':
        curve,model=fit(residual,delta,float(sigma),True)
        name='finite_grid_interval_average_v1'
        assumptions='continuous piecewise-linear curve; frozen finite candidate grid and at-most-four slope changes'
    elif method=='task_template':
        curve,model=ride_fit(residual,delta,float(sigma))
        name='ride_task_template_average_v1'
        assumptions='delay-ramp-hold-release model; optional rectangular dropout and rebound; BIC detection, no calibrated LR or CI claim'
    else:raise ValueError('method must explicitly name grid_average or task_template')
    mask=(s>=-1e-9)&(s<30-1e-9)
    return dict(method=name,template_assumptions=assumptions,reduction_interval_kw=curve.tolist(),
                observed_features=features(curve,delta),eta_raw=float(np.sum(residual[mask]*delta)/(1.5*30)),
                reference_status='provided_reference_or_estimate; validity_not_inferred',
                physical_timing=None,physical_timing_status='not_identified_by_this_API',
                uncertainty_status='no_process_confidence_interval_claim',
                request_kw=1.5,request_minutes=[0,30],model=model)
