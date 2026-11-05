"""Frozen cohort dose-response queries, smoothed sensitivity and mesh thresholds.

This stores DR pseudo-outcomes rather than a new causal estimator. It cannot
predict a new individual's delivery. JSON integrity is not source authenticity.
"""
from dataclasses import dataclass, replace, asdict
from pathlib import Path
import hashlib
import json
import numpy as np
from scipy.optimize import brentq
from .continuous import (fit_continuous_effects, _config, _local_support,
                         local_linear_weights)
from .validation import numeric_array, real_scalar, user_ids, validate_task, validate_assumptions


SCHEMA = 'b1.frozen-continuous.v1'


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


@dataclass(frozen=True)
class FrozenContinuousModel:
    payload_json: str
    sha256: str


def _payload(model):
    if not isinstance(model, FrozenContinuousModel):
        raise ValueError('FrozenContinuousModel required')
    if not isinstance(model.payload_json,str) or not isinstance(model.sha256,str):
        raise ValueError('frozen payload and checksum must be strings')
    if hashlib.sha256(model.payload_json.encode('utf-8')).hexdigest() != model.sha256:
        raise ValueError('frozen model checksum mismatch')
    p = json.loads(model.payload_json)
    if not isinstance(p,dict) or p.get('schema') != SCHEMA:
        raise ValueError('unsupported frozen model schema')
    required={'X','dose','pseudo_outcome','stabilized_weight','residual','users','dose_domain',
              'reference_dose','bandwidth','configuration','task','status','metadata',
              'declared_assumptions','known_density_used','population_scope','incentive_unit','uncertainty'}
    if not required <= set(p):
        raise ValueError('incomplete frozen model payload')
    _json(p)  # Reject NaN/Infinity anywhere, including metadata.
    if type(p['known_density_used']) is not bool:
        raise ValueError('known_density_used must be an explicit boolean')
    x = numeric_array(p['X'], 'X', 2)
    d = numeric_array(p['dose'], 'dose', 1)
    xi = numeric_array(p['pseudo_outcome'], 'pseudo_outcome', 1)
    w = numeric_array(p['stabilized_weight'], 'stabilized_weight', 1)
    residual = numeric_array(p['residual'], 'residual', 1)
    groups = np.asarray(p['users'], dtype=object)
    user_ids(p['users'])
    n = len(d)
    if not 1 <= n <= 12000 or x.shape[0] != n or not 1 <= x.shape[1] <= 30 or any(len(a) != n for a in (xi,w,residual,groups)):
        raise ValueError('invalid frozen cohort dimensions')
    domain = numeric_array(p['dose_domain'], 'domain', 1)
    ref = real_scalar(p['reference_dose'], 'reference_dose')
    h = real_scalar(p['bandwidth'], 'bandwidth', positive=True)
    cfg = _config(p['configuration'])
    validate_task(p['task'])
    if domain.shape != (2,) or domain[0] < 0 or domain[1] <= domain[0] or not domain[0] <= ref <= domain[1] or h > (domain[1]-domain[0])/2:
        raise ValueError('invalid frozen domain, reference or bandwidth')
    if np.any((d <= domain[0]) | (d >= domain[1])) or np.any(w <= 0) or len(set(groups)) < 3:
        raise ValueError('invalid frozen observations')
    if p['status'] not in ('causal','association') or not isinstance(p['metadata'],dict):
        raise ValueError('invalid frozen status or metadata')
    _, confirmed, _ = validate_assumptions(p['declared_assumptions'], p['task'], p['known_density_used'])
    if (p['status'] == 'causal') != confirmed:
        raise ValueError('frozen causal status disagrees with declarations')
    return p,x,d,xi,w,residual,groups,cfg


def _freeze(result, X, users, metadata):
    if result['status'] not in ('causal','association') or 'audit' not in result:
        raise ValueError('cannot freeze unsupported fit: '+_json(result.get('reasons',[])))
    audit = result['audit']; d = np.asarray(audit['dose']); xi = np.asarray(audit['pseudo_outcome'])
    h = result['diagnostics']['bandwidth']; residual = np.empty(len(d))
    for start in range(0,len(d),128):
        sl = slice(start,start+128)
        residual[sl] = xi[sl] - local_linear_weights(d,d[sl],h) @ xi
    p = dict(schema=SCHEMA, status=result['status'], method=result['method'],
        task=result['task'], incentive_unit=result['incentive_unit'], dose_domain=result['dose_domain'],
        reference_dose=result['reference_dose'], bandwidth=h, configuration=result['configuration'],
        declared_assumptions=result['declared_assumptions'], known_density_used=metadata.pop('_known_density_used',False),
        X=numeric_array(X,'X',2).tolist(), dose=d.tolist(), pseudo_outcome=xi.tolist(),
        stabilized_weight=audit['stabilized_weight'], residual=residual.tolist(),
        users=user_ids(users).tolist(), metadata=metadata,
        uncertainty='conditional sampling only; smoothing, nuisance, reference and process uncertainty not propagated',
        population_scope='fixed fitted cohort; event equal weight; no individual or new-population prediction')
    s = _json(p); model = FrozenContinuousModel(s,hashlib.sha256(s.encode('utf-8')).hexdigest())
    _payload(model)
    return model


def fit_continuous_model(X,treatment,outcome,users,*,dose_domain,reference_dose,
                         incentive_unit,task,continuous_assignment=None,assumptions=None,
                         known_density=None,config=None):
    """Fit once; all later queries use fixed pseudo-outcomes/cohort/bandwidth."""
    cfg = replace(_config(config),return_audit=True)
    result = fit_continuous_effects(X,treatment,outcome,users,dose_domain=dose_domain,
        grid=[reference_dose],reference_dose=reference_dose,incentive_unit=incentive_unit,
        task=task,continuous_assignment=continuous_assignment,assumptions=assumptions,
        known_density=known_density,config=cfg)
    return _freeze(result,X,users,{'_known_density_used':known_density is not None})


def fit_ev_factor_model(event_results,factor_records,study,*,dose_domain,reference_dose,
                        assumptions=None,known_density=None,config=None,continuous_assignment=None):
    """Same checked EV DAG/outcome/time contract as fit_ev_factor_curve."""
    from ..factors import _inputs, fit_ev_factor_curve
    data = _inputs(event_results,factor_records,study)
    result = fit_ev_factor_curve(event_results,factor_records,study,dose_domain=dose_domain,
        grid=[reference_dose],reference_dose=reference_dose,assumptions=assumptions,
        known_density=known_density,config=replace(_config(config),return_audit=True),
        continuous_assignment=continuous_assignment)
    metadata = {k:result[k] for k in ('study_design','outcome_measurement','factor_pipeline') if k in result}
    metadata['_known_density_used'] = known_density is not None
    return _freeze(result,data['X'],data['users'],metadata)


def save_continuous_model(model,path):
    _payload(model)
    with Path(path).open('x',encoding='utf-8') as f:
        f.write(_json({'payload_json':model.payload_json,'sha256':model.sha256}))


def load_continuous_model(path):
    path = Path(path)
    if path.stat().st_size > 100_000_000:
        raise ValueError('model exceeds finite size limit')
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value,dict) or set(value) != {'payload_json','sha256'}:
        raise ValueError('invalid model envelope')
    model = FrozenContinuousModel(**value); _payload(model)
    return model


def local_linear_derivative_weights(dose,points,bandwidth):
    """Exact derivative of the fitted Gaussian local-linear mean, not its slope."""
    u = (dose[None,:]-points[:,None])/bandwidth; k = np.exp(-.5*u*u)
    s = [(k*u**j).sum(1) for j in range(4)]
    ds = [s[1]/bandwidth,(s[2]-s[0])/bandwidth,(s[3]-2*s[1])/bandwidth]
    denominator = s[0]*s[2]-s[1]**2
    if np.any(denominator<=1e-12): raise ValueError('local design singular or absent')
    da = ds[0]*s[2]+s[0]*ds[2]-2*s[1]*ds[1]
    t = s[2][:,None]-s[1][:,None]*u
    dt = ds[2][:,None]-ds[1][:,None]*u+s[1][:,None]/bandwidth
    weights = k*t/denominator[:,None]
    return k*(u*t/bandwidth+dt)/denominator[:,None]-weights*da[:,None]/denominator[:,None]


def _band(weights,xi,residual,users,cfg):
    estimate = weights@xi
    unique,inverse = np.unique(users,return_inverse=True); G=len(unique)
    sums = np.zeros((G,len(weights)))
    np.add.at(sums,inverse,(weights*residual[None,:]).T)
    sums *= np.sqrt(G/(G-1)); se = np.sqrt((sums*sums).sum(0)); active=se>1e-14
    rng=np.random.default_rng(cfg.seed+73); maximum=[]
    for start in range(0,cfg.n_boot,128):
        draws=rng.standard_normal((min(128,cfg.n_boot-start),G))@sums
        maximum.extend(np.max(abs(draws[:,active])/se[active],axis=1).tolist() if active.any() else [0.]*len(draws))
    critical=float(np.quantile(maximum,1-cfg.alpha))
    return dict(estimate=estimate.tolist(),standard_errors=se.tolist(),lower=(estimate-critical*se).tolist(),
        upper=(estimate+critical*se).tolist(),critical=critical,nominal_level=1-cfg.alpha,
        kind='conditional_sampling_band_on_requested_finite_grid',cluster_count=G,bootstrap_draws=cfg.n_boot,
        full_chain_uncertainty_propagated=False,unsmoothed_causal_coverage_validated=False)


def query_continuous_model(model,grid):
    p,x,d,xi,w,residual,users,cfg = _payload(model)
    a=numeric_array(grid,'grid',1); lo,hi=p['dose_domain']; ref=p['reference_dose']; h=p['bandwidth']
    if not 1<=len(a)<=301 or np.any(np.diff(a)<=0) or np.any((a<lo)|(a>hi)):
        raise ValueError('1..301 strictly increasing in-domain query amounts required')
    points=np.r_[ref,a[~np.isclose(a,ref,atol=1e-12,rtol=0)]]
    mapping=np.array([int(np.argmin(abs(points-v))) for v in a])
    diagnostics,failed=_local_support(x,d,users,points,h,w,cfg)
    out=dict(schema='b1.frozen-query.v1',status=p['status'],model_id=model.sha256,refitted=False,
        task=p['task'],incentive_unit=p['incentive_unit'],metadata=p['metadata'],
        population_scope=p['population_scope'],uncertainty=p['uncertainty'],
        diagnostics=dict(by_dose=diagnostics,unsupported_doses=failed),curve=None,sensitivity=None,inference=None)
    if failed:
        out.update(status='unsupported',reason='insufficient_local_support'); return out
    L=local_linear_weights(d,points,h); mean=L@xi
    band=_band(L-L[[0]],xi,residual,users,cfg)
    for name in ('estimate','standard_errors','lower','upper'):band[name]=np.asarray(band[name])[mapping].tolist()
    derivative=local_linear_derivative_weights(d,a,h)
    out['curve']=dict(incentive_values=a.tolist(),reference_incentive=ref,mean_outcomes=mean[mapping].tolist(),
        contrasts=(mean-mean[0])[mapping].tolist(),outcome_unit=p['task']['outcome_unit'],shape_constraint='none',
        incentive_unit=p['incentive_unit'],task_duration_min=p['task']['window_minutes'][1]-p['task']['window_minutes'][0],
        request_kw=p['task']['q_kw'],
        interpretation='causal conditional on declarations' if p['status']=='causal' else 'standardized association')
    out['sensitivity']=dict(incentive_values=a.tolist(),values=(derivative@xi).tolist(),
        unit=p['task']['outcome_unit']+'/'+p['incentive_unit'],estimand='derivative of frozen smoothed mean',
        inference=_band(derivative,xi,residual,users,cfg) if p['status']=='causal' else None)
    if p['status']=='causal':out['inference']=band
    return out


def find_incentive_threshold(model,*,target_contrast,search_domain,mesh_step):
    """Resolution-limited first-crossing search, with possible nonmonotonicity.

    Candidate cells describe the conditional finite mesh only. They are NOT a
    confidence set for the continuous causal threshold or an optimal price.
    """
    target=real_scalar(target_contrast,'target_contrast',positive=True)
    span=numeric_array(search_domain,'search_domain',1); step=real_scalar(mesh_step,'mesh_step',positive=True)
    if span.shape!=(2,) or span[1]<=span[0]:raise ValueError('increasing search domain required')
    n=int(np.ceil((span[1]-span[0])/step))+1
    if n>301:raise ValueError('threshold mesh exceeds301 points; choose a coarser step')
    a=np.linspace(*span,n); result=query_continuous_model(model,a)
    out=dict(schema='b1.threshold.v1',status='unsupported',model_id=model.sha256,
        target_contrast=target,search_domain=span.tolist(),mesh_max_width=float(np.diff(a).max()),
        point_crossings=[],candidate_cells=[],first_point_crossing=None,not_reached_possible=None,
        continuous_threshold_coverage_validated=False,optimal_price=False,
        interpretation='frozen smoothed contrast; crossings/candidates resolved only on declared mesh',
        uncertainty=result['uncertainty'],query_status=result['status'])
    if result['status']=='unsupported':
        out['unsupported_doses']=result['diagnostics']['unsupported_doses']; return out
    p,_,d,xi,_,_,_,_=_payload(model); ref=p['reference_dose']; h=p['bandwidth']
    base=float((local_linear_weights(d,np.array([ref]),h)@xi)[0])
    def f(v):return float((local_linear_weights(d,np.array([v]),h)@xi)[0]-base-target)
    y=np.asarray(result['curve']['contrasts'])-target
    if y[0]>=0:
        out['first_point_crossing']=float(a[0]); out['left_censored_at_search_start']=True
    for j in range(len(a)-1):
        if y[j]<0<=y[j+1]:
            root=float(brentq(f,a[j],a[j+1],xtol=1e-10))
            out['point_crossings'].append(dict(dose=root,bracket=[float(a[j]),float(a[j+1])]))
    if out['first_point_crossing'] is None and out['point_crossings']:
        out['first_point_crossing']=out['point_crossings'][0]['dose']
    if out['point_crossings']:
        _,x,_,_,w,_,users,cfg=_payload(model)
        _,failed=_local_support(x,d,users,np.asarray([c['dose'] for c in out['point_crossings']]),h,w,cfg)
        if failed:
            out.update(status='unsupported',unsupported_doses=failed,point_crossings=[],first_point_crossing=None)
            return out
    out['status']='point_reached' if out['first_point_crossing'] is not None else 'point_not_reached_on_mesh'
    if result['inference'] is not None:
        lower=np.asarray(result['inference']['lower']); upper=np.asarray(result['inference']['upper'])
        # First possibly reached grid location, until a prior grid point is
        # definitely reached. No claim about behavior between mesh locations.
        prior_definite=False
        for j in range(len(a)):
            if upper[j]>=target and not prior_definite:
                out['candidate_cells'].append([float(a[max(0,j-1)]),float(a[j])])
            if lower[j]>=target:prior_definite=True
        out['not_reached_possible']=not bool(np.any(lower>=target))
        out['candidate_kind']='conditional finite-grid first-hit candidates, not continuous-threshold CI'
    return out
