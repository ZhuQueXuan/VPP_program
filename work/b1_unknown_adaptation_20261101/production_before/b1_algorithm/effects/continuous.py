"""Continuous incentive effects: Kennedy DR pseudo-outcomes and local lines.

The established method is shared with RIDE's continuous branch. This independent
implementation uses a declared domain, user folds, bounded density models and
explicit support failures. It imposes neither linear nor monotone dose effects.
"""
from dataclasses import dataclass,asdict,fields
from collections.abc import Mapping
import json
import numpy as np
from scipy.special import logit
from scipy.stats import norm
from sklearn.preprocessing import PolynomialFeatures,StandardScaler,SplineTransformer
from sklearn.linear_model import Ridge
from .validation import (ContractError,fail,numeric_array,user_ids,real_scalar,integer,
                         text,validate_task,validate_assumptions)
from .core import group_folds


@dataclass(frozen=True)
class ContinuousEffectConfig:
    n_folds: int = 3
    n_boot: int = 399
    alpha: float = .05
    seed: int = 0
    bandwidth: float | None = None
    spline_knots: int = 6
    ridge_alpha: float = .1
    min_unique_doses: int = 20
    min_local_events: int = 25
    min_local_users: int = 15
    min_local_ess: float = 20.
    max_stabilized_weight: float = 30.
    max_weighted_smd: float = .5
    return_audit: bool = False


def _config(value):
    if value is None:value=ContinuousEffectConfig()
    if isinstance(value,Mapping):
        if set(value)-{f.name for f in fields(ContinuousEffectConfig)}:fail('unknown_config','config','Unknown continuous configuration fields.')
        value=ContinuousEffectConfig(**value)
    if not isinstance(value,ContinuousEffectConfig):fail('invalid_config','config','ContinuousEffectConfig required.')
    for name,lo,hi in [('n_folds',2,10),('n_boot',99,10000),('seed',0,2**32-1),('spline_knots',3,12),
                       ('min_unique_doses',20,100000),('min_local_events',5,100000),('min_local_users',3,100000)]:
        integer(getattr(value,name),'config.'+name,lo,hi)
    for name in ('ridge_alpha','min_local_ess','max_stabilized_weight','max_weighted_smd','alpha'):
        real_scalar(getattr(value,name),'config.'+name,positive=True)
    if value.bandwidth is not None:real_scalar(value.bandwidth,'config.bandwidth',positive=True)
    if not 0<value.alpha<1 or not 0<value.max_weighted_smd<=1:fail('invalid_config','config','Invalid alpha or balance tolerance.')
    if not isinstance(value.return_audit,(bool,np.bool_)):fail('invalid_config','config.return_audit','Boolean required.')
    return value


def local_linear_weights(dose,points,bandwidth):
    """Equivalent Gaussian local-linear weights; reproduce constants and lines."""
    u=(dose[None,:]-points[:,None])/bandwidth
    k=np.exp(-.5*u*u)
    s0=k.sum(1);s1=(k*u).sum(1);s2=(k*u*u).sum(1)
    denominator=s0*s2-s1*s1
    if np.any(denominator<=1e-12):raise ValueError('local design singular or absent')
    return k*(s2[:,None]-s1[:,None]*u)/denominator[:,None]


def _marginal_logit_density(query,means,sd,lo,hi):
    result=np.empty(len(query));u=(query-lo)/(hi-lo)
    for i in range(0,len(query),128):
        result[i:i+128]=norm.pdf(logit(u[i:i+128,None]),means[None,:],sd).mean(1)/((hi-lo)*u[i:i+128]*(1-u[i:i+128]))
    return result


def _design(x,b):
    return np.column_stack([x,b,(x[:,:,None]*b[:,None,:]).reshape(len(x),-1)])


def _marginal_prediction(reg,x_mean,spline,dose):
    x=np.broadcast_to(x_mean,(len(dose),len(x_mean)))
    return reg.predict(_design(x,spline.transform(dose[:,None])))


def _dr_pseudo_outcome(y,mu,marginal_mu,conditional_density,marginal_density):
    return (y-mu)*marginal_density/conditional_density+marginal_mu


def _crossfit(x,d,y,users,cfg,domain,known_density):
    lo,hi=domain;span=hi-lo;n=len(y);folds=group_folds(users,cfg.n_folds,cfg.seed)
    xi=np.empty(n);stabilized=np.empty(n);mu_observed=np.empty(n);density=np.empty(n)
    models=[]
    for fold in np.unique(folds):
        train=folds!=fold;test=~train
        if train.sum()<50 or np.unique(d[train]).size<cfg.min_unique_doses:raise ValueError('insufficient continuous training data in a user fold')
        poly=PolynomialFeatures(2,include_bias=False)
        xt=poly.fit_transform(x[train]);xe=poly.transform(x[test])
        scaler=StandardScaler().fit(xt);xt=scaler.transform(xt);xe=scaler.transform(xe)
        knots=np.linspace(lo,hi,cfg.spline_knots)[:,None]
        spline=SplineTransformer(knots=knots,degree=3,include_bias=False,extrapolation='error').fit(np.array([[lo],[hi]]))
        bt=spline.transform(d[train,None]);be=spline.transform(d[test,None])
        model=Ridge(alpha=cfg.ridge_alpha).fit(_design(xt,bt),y[train])
        mu=model.predict(_design(xe,be));marginal=_marginal_prediction(model,xt.mean(0),spline,d[test])
        if known_density is not None:
            # Only a declared uniform randomized design is accepted in v1;
            # its conditional and marginal densities are both exactly1/span.
            conditional=known_density[test];marginal_density=conditional.copy()
        else:
            # A bounded logit-normal assignment model; residual scale is from
            # inner user-held-out predictions, never from query outcomes.
            z=logit((d[train]-lo)/span);train_users=users[train]
            inner=group_folds(train_users,2,cfg.seed+int(fold)+130)
            residual=np.empty(len(z))
            for k in (0,1):
                inner_model=Ridge(alpha=cfg.ridge_alpha).fit(xt[inner!=k],z[inner!=k])
                residual[inner==k]=z[inner==k]-inner_model.predict(xt[inner==k])
            sd=float(np.sqrt(np.mean(residual**2)))
            if not np.isfinite(sd) or sd<.05:raise ValueError('assignment nearly deterministic; conditional density unsupported')
            dm=Ridge(alpha=cfg.ridge_alpha).fit(xt,z)
            u=(d[test]-lo)/span
            conditional=norm.pdf(logit(u),dm.predict(xe),sd)/(span*u*(1-u))
            marginal_density=_marginal_logit_density(d[test],dm.predict(xt),sd,lo,hi)
        if not np.isfinite(conditional).all() or np.any(conditional<=0):raise ValueError('nonpositive or nonfinite assignment density')
        weights=marginal_density/conditional
        if not np.isfinite(weights).all() or np.max(weights)>cfg.max_stabilized_weight:
            raise ValueError('extreme stabilized density weights; no silent capping or trimming')
        xi[test]=_dr_pseudo_outcome(y[test],mu,marginal,conditional,marginal_density)
        stabilized[test]=weights;mu_observed[test]=mu;density[test]=conditional
        models.append((int(test.sum()),model,xt.mean(0),spline))
    return xi,stabilized,folds,models,mu_observed,density


def _local_support(x,d,users,points,h,stabilized,cfg):
    sd=np.maximum(x.std(0),1e-8);mean=x.mean(0);diagnostics=[];failed=[]
    for a in points:
        local=abs(d-a)<=h
        w=np.exp(-.5*((d-a)/h)**2)*stabilized
        ess=float(w.sum()**2/(w@w))
        smd=float(np.max(abs(np.average(x,axis=0,weights=w)-mean)/sd))
        row=dict(dose=float(a),local_events=int(local.sum()),local_users=len(set(users[local])),effective_events=ess,max_weighted_smd=smd)
        diagnostics.append(row)
        if row['local_events']<cfg.min_local_events or row['local_users']<cfg.min_local_users or ess<cfg.min_local_ess or smd>cfg.max_weighted_smd:
            failed.append(float(a))
    return diagnostics,failed


def _conditional_band(d,xi,users,points,h,cfg):
    L=local_linear_weights(d,points,h)
    fitted=np.empty(len(d))
    for i in range(0,len(d),128):fitted[i:i+128]=local_linear_weights(d,d[i:i+128],h)@xi
    residual=xi-fitted
    contrast=L-L[[0]];estimate=contrast@xi
    unique,inverse=np.unique(users,return_inverse=True);G=len(unique)
    sums=np.zeros((G,len(points)))
    np.add.at(sums,inverse,(contrast*residual[None,:]).T)
    sums*=np.sqrt(G/(G-1));se=np.sqrt((sums*sums).sum(0));active=se>1e-14
    rng=np.random.default_rng(cfg.seed+73);maximum=[]
    for start in range(0,cfg.n_boot,128):
        draws=rng.standard_normal((min(128,cfg.n_boot-start),G))@sums
        maximum.extend(np.max(abs(draws[:,active])/se[active],axis=1).tolist() if active.any() else [0.]*len(draws))
    critical=float(np.quantile(maximum,1-cfg.alpha))
    return L@xi,dict(contrasts=estimate.tolist(),standard_errors=se.tolist(),lower=(estimate-critical*se).tolist(),
        upper=(estimate+critical*se).tolist(),critical=critical,nominal_level=1-cfg.alpha,bootstrap_draws=cfg.n_boot,
        cluster_count=G,inference_unit='original_user',kind='conditional_sampling_band',
        smoothing_bias_corrected=False,nuisance_estimation_uncertainty_propagated=False,
        coverage_for_unsmoothed_causal_curve_validated=False)


def fit_continuous_effects(X,treatment,outcome,users,*,dose_domain,grid=None,reference_dose=None,
                           incentive_unit,task,continuous_assignment=None,assumptions=None,known_density=None,config=None):
    """Predict mean response at any supported continuous offered incentive value.

    Different rows are comparable completed events, not changing prices inside
    one event. known_density is the ex-ante conditional density at each observed
    dose. V1 accepts known density only for randomized uniform assignment.
    A zero-incentive atom plus a continuous component needs another model.
    """
    result=dict(schema_version='b1.continuous-effects.v1',method='Kennedy_DR_local_linear',status='invalid_input',
        reasons=[],task=None,causal_curve=None,standardized_association=None,inference=None,comparators=None,
        diagnostics=None,shape_constraint='none',new_causal_estimator=False,
        uncertainty=dict(scope='conditional_sampling_only',reference_process_uncertainty_propagated=False))
    try:
        x=numeric_array(X,'X',2);d=numeric_array(treatment,'treatment',1);y=numeric_array(outcome,'outcome',1);groups=user_ids(users)
        if not len(y) or not(len(x)==len(d)==len(y)==len(groups)) or x.shape[1]<1:fail('event_count_mismatch','inputs','Nonempty matching event arrays and pre-treatment covariates required.')
        if len(y)>12000 or x.shape[1]>30:fail('finite_computation_domain','inputs','This implementation supports up to12000 events and30 covariates per call.')
        cfg=_config(config);context=validate_task(task);unit=text(incentive_unit,'incentive_unit')
        if continuous_assignment is not True:fail('continuous_design_declaration','continuous_assignment','Explicitly declare a continuous assignment model; many distinct amounts alone do not prove it.')
        domain=numeric_array(dose_domain,'dose_domain',1)
        if domain.shape!=(2,) or domain[0]<0 or domain[1]<=domain[0]:fail('dose_domain','dose_domain','Declare finite nonnegative [lower,upper] incentive bounds.')
        lo,hi=domain;span=hi-lo
        # Pure continuous design: endpoints have probability zero. Repeated zero
        # rewards are a mixed discrete/continuous design, not an ordinary density.
        if np.any((d<=lo)|(d>=hi)):fail('continuous_design','treatment','Observed doses must be inside declared bounds; atoms/endpoints need a mixed-design estimator.')
        if len(np.unique(d))<cfg.min_unique_doses:fail('discrete_design','treatment','Too few unique incentives for continuous estimation; use the discrete AIPW interface.')
        if np.unique(groups).size<max(cfg.n_folds*2,cfg.min_local_users):fail('insufficient_users','users','Insufficient independent users.')
        reference=lo if reference_dose is None else real_scalar(reference_dose,'reference_dose')
        requested=np.linspace(lo,hi,81) if grid is None else numeric_array(grid,'grid',1)
        if not len(requested) or len(requested)>301 or np.any(np.diff(requested)<=0):fail('prediction_grid','grid','Use1..301 increasing continuous query amounts.')
        if reference<lo or reference>hi or np.any((requested<lo)|(requested>hi)):fail('no_extrapolation','grid','Query amounts and reference must stay inside declared support.')
        h=1.06*float(np.std(d))*len(np.unique(groups))**(-.2) if cfg.bandwidth is None else float(cfg.bandwidth)
        if not 0<h<=span/2:fail('bandwidth','config.bandwidth','Bandwidth must be positive and at most half the incentive span.')
        density=None if known_density is None else numeric_array(known_density,'known_density',1)
        if density is not None and (density.shape!=d.shape or np.any(density<=0)):fail('invalid_density','known_density','Positive ex-ante density required for every observed incentive.')
        if density is not None and (not np.allclose(density,1/span,rtol=1e-8,atol=1e-10) or not isinstance(assumptions,Mapping) or assumptions.get('randomized_assignment') is not True):
            fail('unsupported_known_design','known_density','V1 known-density input requires declared randomized Uniform(lower,upper), with density1/span; otherwise use estimated logit-normal GPS.')
        declared,confirmed,missing=validate_assumptions(assumptions,context,density is not None)
        # Put the exact reference first for paired contrast inference, then map
        # back to requested grid. No interpolation between plotted points.
        points=np.r_[reference,requested[~np.isclose(requested,reference,atol=1e-12,rtol=0)]]
        mapping=np.array([int(np.argmin(abs(points-a))) for a in requested])
        xi,weights,folds,models,mu,pdf=_crossfit(x,d,y,groups,cfg,domain,density)
        diagnostics,failed=_local_support(x,d,groups,points,h,weights,cfg)
        result.update(task=context,configuration=asdict(cfg),incentive_unit=unit,dose_domain=domain.tolist(),reference_dose=float(reference),
            declared_assumptions=declared,unconfirmed_assumptions=missing,causal_assumptions_confirmed=confirmed,
            continuous_assignment_declared=True,diagnostics=dict(passed=not failed,by_dose=diagnostics,unsupported_doses=failed,events=len(y),users=len(set(groups)),
                unique_doses=len(np.unique(d)),max_stabilized_weight=float(weights.max()),bandwidth=h,
                user_fold_integrity=True,diagnostics_are_not_identification_proof=True))
        if failed:
            result.update(status='unsupported',reasons=[dict(code='insufficient_local_support',detail='Some query amounts lack comparable supported observations; no full curve reported.')]);return result
        mean,band=_conditional_band(d,xi,groups,points,h,cfg)
        def curve(values):
            return dict(incentive_values=requested.tolist(),reference_incentive=float(reference),
                mean_outcomes=values[mapping].tolist(),contrasts=(values-values[0])[mapping].tolist(),
                outcome_unit=context['outcome_unit'],incentive_unit=unit,task_duration_min=context['window_minutes'][1]-context['window_minutes'][0],
                request_kw=context['q_kw'],weighting='event_equal_weight',continuous_query_evaluated_directly=True,
                boundary_values_are_one_sided_smooth_limits=True,shape_constraint='none')
        plugin=sum(count*_marginal_prediction(model,xmean,spline,points) for count,model,xmean,spline in models)/len(y)
        raw=local_linear_weights(d,points,h)@y
        line=np.linalg.lstsq(np.column_stack([np.ones(len(d)),d]),xi,rcond=None)[0]
        result['comparators']=dict(plugin_shared_outcome=curve(plugin),unadjusted_local_linear=curve(raw),
                                   straight_line_same_pseudo_outcome=curve(line[0]+line[1]*points))
        point=curve(mean)
        if confirmed:
            for key in ('contrasts','standard_errors','lower','upper'):band[key]=np.asarray(band[key])[mapping].tolist()
            result.update(status='causal',causal_curve=point,inference=band)
        else:result.update(status='association',standardized_association=point,reasons=[dict(code='causal_assumptions_unconfirmed',detail=', '.join(missing))])
        if cfg.return_audit:result['audit']=dict(dose=d.tolist(),pseudo_outcome=xi.tolist(),stabilized_weight=weights.tolist(),
            outcome_prediction=mu.tolist(),observed_dose_density=pdf.tolist(),fold_by_event=folds.tolist())
        json.dumps(result,allow_nan=False)
        return result
    except (ContractError,ValueError,TypeError,OverflowError,np.linalg.LinAlgError) as exc:
        result.update(status='invalid_input' if isinstance(exc,ContractError) else 'unsupported',
            reasons=[exc.reason if isinstance(exc,ContractError) else dict(code='continuous_estimation',detail=str(exc))],
            causal_curve=None,standardized_association=None,inference=None,comparators=None)
        return result
