"""User-cluster bootstrap with actual nuisance refitting on a finite grid.

This empirical study propagates nuisance refitting and cohort sampling through
the retained Kennedy curve. It does not implement Takatsu--Westling smoothing
bias correction or resimulate uncertainty in the supplied outcome measurement.
"""
import json
import numpy as np
from . import continuous as CT
from .frozen import FrozenContinuousModel, _payload, query_continuous_model, find_incentive_threshold
from .validation import numeric_array, integer, real_scalar


def refit_curve_uncertainty(model, amounts, *, draws=99, seed=0,
                            target_contrast=120., alpha=None):
    """Resample whole original users and refit each sampled cohort from scratch.

    The input is an integrated research model. Every copy of an original user
    keeps its original identity within a draw, so copies cannot leak across
    cross-fitting folds. A failing draw remains in ``draw_status``; any failure
    yields status ``incomplete`` even if a diagnostic band can be computed.
    """
    if model.get('schema') != 'b1.research-point-one.v1':
        raise ValueError('integrated research model required')
    integer(draws, 'draws', 99, 10000)
    integer(seed, 'seed', 0, 2**32-1)
    target=real_scalar(target_contrast, 'target_contrast', positive=True)
    frozen=FrozenContinuousModel(**model['mean_model'])
    p,x,d,xi,stabilized,residual,users,cfg=_payload(frozen)
    a=numeric_array(amounts, 'amounts', 1)
    original=query_continuous_model(frozen,a)
    level=cfg.alpha if alpha is None else real_scalar(alpha, 'alpha', positive=True)
    if not 0 < level < 1: raise ValueError('alpha must be in (0,1)')
    state=model['derivative_model']
    y=numeric_array(state['outcome'], 'stored outcome', 1)
    if len(y)!=len(d) or not np.allclose(state['dose'],d,rtol=0,atol=1e-12) or not np.allclose(state['X'],x,rtol=0,atol=1e-12):
        raise ValueError('stored outcome cohort must match the retained mean model')
    if list(state['users'])!=list(users):
        raise ValueError('stored original-user identities must match mean model')
    result=dict(schema='b1.user-refit-uncertainty.v1', status='unsupported',
        method='whole_original_user_bootstrap_with_nuisance_refitting',
        interpretation=p['status'], requested_draws=int(draws), success_draws=0,
        failed_draws=0, incentive_values=a.tolist(), reference_incentive=p['reference_dose'],
        nominal_level=1-level, bandwidth=p['bandwidth'], bandwidth_refitted=False,
        outcome_nuisance_refitted_each_draw=True,
        GPS_refitted_each_draw=not p['known_density_used'],
        known_uniform_design_density_fixed=p['known_density_used'],
        target_cohort_distribution_resampled=True,
        original_user_copies_share_fold=True, source_process_outputs_fixed=True,
        smoothing_bias_corrected=False, exact_Takatsu_Westling_reproduction=False,
        empirical_coverage_validated=False, full_measurement_uncertainty_propagated=False,
        finite_grid_only=True, mean_curve_status=original['status'], draw_status=[],
        center_mean_outcomes=None, center_contrasts=None, lower=None, upper=None,
        bootstrap_mean_outcomes=[], bootstrap_contrasts=[], target_candidates=None)
    if original.get('curve') is None:
        result['reason']='original query has insufficient support'
        return result
    reference=float(p['reference_dose']);h=float(p['bandwidth'])
    points=np.r_[reference,a[~np.isclose(a,reference,atol=1e-12,rtol=0)]]
    mapping=np.array([int(np.argmin(abs(points-v))) for v in a])
    original_mean=np.asarray(original['curve']['mean_outcomes'])
    center=np.asarray(original['curve']['contrasts'])
    result.update(center_mean_outcomes=original_mean.tolist(),center_contrasts=center.tolist())
    unique=np.unique(users);indices=[np.flatnonzero(users==user) for user in unique]
    rng=np.random.default_rng(seed)
    for draw in range(draws):
        selected=rng.integers(0,len(unique),len(unique))
        sample=np.concatenate([indices[i] for i in selected])
        bx,bd,by,bu=x[sample],d[sample],y[sample],users[sample]
        item=dict(draw=draw,events=len(sample),unique_original_users=len(set(bu)))
        try:
            if len(set(bu)) < max(cfg.n_folds*2,cfg.min_local_users):
                raise ValueError('insufficient unique resampled users')
            density=np.full(len(sample),1/(p['dose_domain'][1]-p['dose_domain'][0])) if p['known_density_used'] else None
            bxi,bweights,folds,_,_,_=CT._crossfit(bx,bd,by,bu,cfg,p['dose_domain'],density)
            for user in set(bu):
                if len(set(folds[bu==user]))!=1:
                    raise ValueError('original user copies were split across folds')
            diagnostics,failed=CT._local_support(bx,bd,bu,points,h,bweights,cfg)
            if failed:
                item.update(status='unsupported',unsupported_amounts=failed,diagnostics=diagnostics)
            else:
                means=CT.local_linear_weights(bd,points,h)@bxi
                contrasts=(means-means[0])[mapping]
                if not np.isfinite(means).all():raise ValueError('nonfinite refitted curve')
                result['bootstrap_mean_outcomes'].append(means[mapping].tolist())
                result['bootstrap_contrasts'].append(contrasts.tolist())
                item.update(status='ok',nuisance_folds=int(len(set(folds))),fold_integrity=True)
        except (ValueError, TypeError, FloatingPointError, np.linalg.LinAlgError) as exc:
            item.update(status='unsupported',reason=str(exc))
        result['draw_status'].append(item)
    success=len(result['bootstrap_contrasts']);failure=draws-success
    result.update(success_draws=success,failed_draws=failure,
                  status='complete' if failure==0 else 'incomplete')
    if success < 2:
        result['reason']='fewer than two successful refits; no band calculated'
        return result
    boot=np.asarray(result['bootstrap_contrasts'])
    supremum=np.max(abs(boot-center[None,:]),axis=1)
    radius=float(np.quantile(supremum,1-level))
    lower=center-radius;upper=center+radius
    exact_ref=np.isclose(a,reference,atol=1e-12,rtol=0)
    lower[exact_ref]=0.;upper[exact_ref]=0.
    candidate=[];prior_definite=False
    for j,amount in enumerate(a):
        if upper[j]>=target and not prior_definite:
            candidate.append([float(a[max(j-1,0)]),float(amount)])
        if lower[j]>=target:prior_definite=True
    point=(find_incentive_threshold(frozen,target_contrast=target,
        search_domain=[float(a[0]),float(a[-1])],mesh_step=float(np.min(np.diff(a))))
        if len(a)>1 else dict(status='single_query_no_search_interval',point_crossings=[]))
    result.update(band_kind='empirical_absolute_supremum_refitted_user_bootstrap_on_requested_grid',
        band_requires_all_draws_successful=True,band_valid_for_use=failure==0,
        successful_draw_conditional_band=failure>0,absolute_supremum_radius=radius,
        bootstrap_standard_errors=np.std(boot,axis=0,ddof=1).tolist(),
        lower=lower.tolist(),upper=upper.tolist(),
        target_candidates=dict(target_contrast=target,first_hit_candidate_cells=candidate,
            not_reached_possible=bool(np.all(lower<target)),
            definitely_not_reached_on_grid=bool(np.all(upper<target)),
            point_result=point,kind='finite_grid_first_hit_candidates_not_continuous_threshold_CI'))
    json.dumps(result,allow_nan=False)
    return result
