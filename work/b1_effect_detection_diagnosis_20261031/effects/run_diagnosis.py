"""Read-only diagnosis on the already-seen final panel; oracle is evaluator only.

No data generation, process refit, hyperparameter search, deployment artifact,
or runtime edit. Original continuous.py is imported without modification.
"""
from pathlib import Path
import os
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import sys, json, hashlib, time
from collections import Counter
import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.preprocessing import PolynomialFeatures, StandardScaler, SplineTransformer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = ROOT / 'work/b1_finish_ev_20261030/final_chain'
sys.path.insert(0, str(ROOT / 'B1算法'))
from b1_algorithm.effects.continuous import fit_continuous_effects, local_linear_weights, _design
from b1_algorithm.effects.validation import user_ids
from b1_algorithm.effects.core import group_folds

PROTOCOL = json.loads((HERE.parent / 'protocol.json').read_text(encoding='utf-8'))
SEEDS = PROTOCOL['factor_diagnosis']['blocks']
GRID = np.array(PROTOCOL['factor_diagnosis']['grid'])
REF = PROTOCOL['factor_diagnosis']['reference']
COV = ('deadline_slack', 'demand_urgency', *(f'history_{j}' for j in range(6)))
LABELS = ('ride_revised_duration', 'cpop_duration', 'raw_duration', 'raw_eta', 'true_duration', 'true_eta')
ESTIMATORS = ('Kennedy_DR_local_linear', 'plugin_shared_outcome', 'unadjusted_local_linear', 'straight_line_same_pseudo_outcome')

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, ensure_ascii=False, allow_nan=False, indent=2,
        default=lambda z: z.tolist() if isinstance(z, np.ndarray) else z.item() if isinstance(z, np.generic) else str(z)), encoding='utf-8')
def rmse(a): return float(np.sqrt(np.mean(np.asarray(a)**2)))
def corr(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return float(np.corrcoef(a,b)[0,1]) if min(a.std(),b.std()) > 1e-12 else None
def stats(v):
    v=np.asarray(v)
    return dict(mean=float(v.mean()), sd=float(v.std()), min=float(v.min()),
                q50=float(np.quantile(v,.5)), q95=float(np.quantile(v,.95)), max=float(v.max()))
def curves(r):
    return {ESTIMATORS[0]:r['causal_curve'], **r['comparators']} if r['status']=='causal' else {}
def numeric_leaves(v):
    if isinstance(v,dict): return sum((numeric_leaves(v[k]) for k in sorted(v)), [])
    if isinstance(v,list): return sum((numeric_leaves(z) for z in v), [])
    return [float(v)] if isinstance(v,(int,float)) and not isinstance(v,bool) else []
def mc(v):
    v=np.asarray(v,float);m=float(v.mean());s=float(v.std(ddof=1)/np.sqrt(len(v))) if len(v)>1 else 0.
    return dict(blocks=len(v),mean=m,descriptive_MC95=[m-1.96*s,m+1.96*s],blocks_negative=int((v<0).sum()))

def file_snapshot():
    paths=list((ROOT/'B1算法').rglob('*.py'))
    for sub in ('events','effects','evaluator','factor_inputs','models','blocks'):
        paths.extend((SOURCE/sub).glob('*.json'))
    paths.extend([SOURCE/'assessment.json',SOURCE/'run.py',ROOT/'work/b1_ev_mainline_20261030/simulation.py', HERE.parent/'protocol.json'])
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(paths)}

def design_audit(x,d,users,folds,configuration):
    out=[]
    for k in np.unique(folds):
        tr=folds!=k
        poly=PolynomialFeatures(2,include_bias=False)
        z=poly.fit_transform(x[tr]);z=StandardScaler().fit_transform(z)
        spline=SplineTransformer(knots=np.linspace(0,2.4,configuration['spline_knots'])[:,None],degree=3,include_bias=False,extrapolation='error').fit(np.array([[0.],[2.4]]))
        b=spline.transform(d[tr,None]);a=_design(z,b)
        centered=a-a.mean(0);sv=np.linalg.svd(centered,compute_uv=False)
        out.append(dict(fold=int(k),training_events=int(tr.sum()),training_users=len(set(users[tr])),
            nominal_X_columns=x.shape[1],nonconstant_raw_X_columns=int((x[tr].std(0)>1e-12).sum()),
            polynomial_X_columns=z.shape[1],nonconstant_polynomial_columns=int((z.std(0)>1e-12).sum()),
            spline_columns=b.shape[1],outcome_design_columns=a.shape[1],
            nonconstant_outcome_columns=int((a.std(0)>1e-12).sum()),
            centered_design_rank=int(np.linalg.matrix_rank(centered)),
            ridge_effective_df_plus_intercept=float(1+np.sum(sv**2/(sv**2+configuration['ridge_alpha']))),
            density_design_nonconstant_columns=int((z.std(0)>1e-12).sum()),
            user_overlap=len(set(users[tr])&set(users[~tr]))))
    return out

def main():
    started=time.perf_counter();before=file_snapshot();dump(HERE/'input_source_sha256_before.json',before)
    effects=[];decomp=[];points=[];events=[];weights=[];designs=[];replays=[];statuses=[]
    for seed in SEEDS:
        for scenario in ('positive','zero'):
            inputs=read(SOURCE/f'factor_inputs/{seed}_{scenario}.json')
            rec=inputs['records'];idx=inputs['target_indices']
            truth_all=read(SOURCE/f'evaluator/{seed}_{scenario}_truth.json')
            truth=[truth_all[i] for i in idx];del truth_all
            target=read(SOURCE/f'evaluator/{seed}_{scenario}_target_curves.json')
            cpop=read(SOURCE/f'events/{seed}_{scenario}_cpop.json')
            revised=read(SOURCE/f'events/{seed}_{scenario}_ride_revised.json')
            assert len(rec)==len(truth)==len(cpop)==len(revised)==256
            assert inputs['representation']=='C0'
            for r,t,c,n in zip(rec,truth,cpop,revised):
                assert r['task_id']==t['task_id']==c['task']['task_id']==n['task']['task_id']
                assert r['user_id']==t['user_id']==c['task']['user_id']==n['task']['user_id']
            # The original _inputs uses all_X[:, indices], a Fortran-contiguous
            # view. Preserve that layout for bit-exact support-stat summation.
            x=np.asfortranarray([[r[k] for k in COV] for r in rec]);d=np.array([r['offered_incentive'] for r in rec]);u=np.array([r['user_id'] for r in rec])
            assert np.array_equal(x[:,2:],np.zeros((256,6)))
            ys=dict(ride_revised_duration=np.array([e['process']['features']['selected_curve']['cumulative_response_seconds'] for e in revised]),
                cpop_duration=np.array([e['process']['features']['selected_curve']['cumulative_response_seconds'] for e in cpop]),
                raw_duration=np.array([e['process']['features']['raw_observed']['cumulative_response_seconds'] for e in cpop]),
                raw_eta=np.array([e['outcome']['value'] for e in cpop]),
                true_duration=np.array([t['cumulative_response_seconds'] for t in truth]),true_eta=np.array([t['eta'] for t in truth]))
            assert np.array_equal(ys['raw_eta'],[e['outcome']['value'] for e in revised])
            fits={}
            for label in LABELS:
                original_label='cpop_eta' if 'eta' in label else 'cpop_duration' if label=='true_duration' else label
                original=read(SOURCE/f'effects/{seed}_{scenario}_{original_label}.json')
                cfg=dict(original['configuration']);cfg['return_audit']=True
                result=fit_continuous_effects(x,d,ys[label],u,dose_domain=original['dose_domain'],grid=GRID,reference_dose=REF,
                    incentive_unit=original['incentive_unit'],task=original['task'],continuous_assignment=True,
                    assumptions=original['declared_assumptions'],config=cfg)
                fits[label]=result
                dump(HERE/f'fits/{seed}_{scenario}_{label}.json',result)
                statuses.append(dict(seed=seed,scenario=scenario,label=label,status=result['status'],reasons=result.get('reasons')))
                if label not in ('true_duration','true_eta'):
                    fields=('causal_curve','comparators','inference','diagnostics')
                    old=numeric_leaves({k:original[k] for k in fields});new=numeric_leaves({k:result[k] for k in fields})
                    diff=max(abs(np.array(old)-np.array(new)),default=0.) if len(old)==len(new) else None
                    replays.append(dict(seed=seed,scenario=scenario,label=label,original_status=original['status'],
                        current_status=result['status'],numeric_values=len(old),maximum_absolute_difference=diff,
                        identical_numeric=(diff==0. and result['status']==original['status'])))
                    if diff!=0. or result['status']!=original['status']: raise AssertionError(f'original replay changed {seed} {scenario} {label}: {diff}')
                if result['status']!='causal': continue
                truth_key='eta' if 'eta' in label else 'cumulative_response_seconds'
                for estimator,c in curves(result).items():
                    ct=np.array(c['contrasts']);mt=np.array(c['mean_outcomes']);tc=np.array(target[truth_key]['contrasts']);tm=np.array(target[truth_key]['mean'])
                    effects.append(dict(seed=seed,scenario=scenario,label=label,estimator=estimator,
                        contrast_rmse=rmse(ct-tc),mean_curve_rmse=rmse(mt-tm),unit='ratio' if 'eta' in label else 'seconds',
                        max_absolute_contrast_error=float(abs(ct-tc).max())))
                audit=result['audit'];w=np.array(audit['stabilized_weight']);mu=np.array(audit['outcome_prediction']);xi=np.array(audit['pseudo_outcome']);folds=np.array(audit['fold_by_event']);res=ys[label]-mu
                L=local_linear_weights(d,GRID,result['diagnostics']['bandwidth']);Lref=local_linear_weights(d,np.array([REF]),result['diagnostics']['bandwidth']);contrast=L-Lref
                # Both target events stay in one user fold. These residual correlations are descriptive.
                pair=np.array([[res[np.flatnonzero(u==uid)[0]],res[np.flatnonzero(u==uid)[1]]] for uid in dict.fromkeys(u)])
                weights.append(dict(seed=seed,scenario=scenario,label=label,
                    bandwidth=result['diagnostics']['bandwidth'],stabilized_weight=stats(w),
                    observed_density=stats(audit['observed_dose_density']),outcome_oof_residual=stats(res),
                    outcome_oof_rmse=rmse(res),user_pair_residual_correlation=corr(pair[:,0],pair[:,1]),
                    weighted_residual=stats(w*res),pseudo_outcome=stats(xi),
                    pseudo_vs_outcome_sd_ratio=float(xi.std()/ys[label].std()),
                    local_min_ess=min(z['effective_events'] for z in result['diagnostics']['by_dose']),
                    local_min_events=min(z['local_events'] for z in result['diagnostics']['by_dose']),
                    local_min_users=min(z['local_users'] for z in result['diagnostics']['by_dose']),
                    maximum_abs_contrast_equivalent_weight=float(abs(contrast).max()),
                    contrast_sampling_amplification=float(np.max(np.sum(contrast**2,axis=1))),
                    maximum_abs_single_event_residual_contribution=float(abs(contrast*(w*res)[None,:]).max()),
                    diagnostics=result['diagnostics']))
                if label=='true_duration':
                    designs.extend(dict(seed=seed,scenario=scenario,**z) for z in design_audit(x,d,user_ids(u),folds,cfg))
            for label in ('ride_revised_duration','cpop_duration','raw_duration','raw_eta'):
                oracle='true_eta' if 'eta' in label else 'true_duration';truth_key='eta' if 'eta' in label else 'cumulative_response_seconds'
                error=ys[label]-ys[oracle]
                for i,(r,t) in enumerate(zip(rec,truth)):
                    events.append(dict(seed=seed,scenario=scenario,label=label,task_id=r['task_id'],user_id=r['user_id'],
                        dose=float(d[i]),L=float(x[i,0]),U=float(x[i,1]),shape=t['latent']['shape'],truth=float(ys[oracle][i]),
                        measured=float(ys[label][i]),error=float(error[i]),true_no_action=ys['true_duration'][i]==0))
                if fits[label]['status']!='causal' or fits[oracle]['status']!='causal':continue
                for estimator,c in curves(fits[label]).items():
                    oc=curves(fits[oracle])[estimator]
                    measured=np.array(c['contrasts']);true_est=np.array(oc['contrasts']);truth_c=np.array(target[truth_key]['contrasts'])
                    A=measured-true_est;B=true_est-truth_c;T=measured-truth_c
                    Amean=np.array(c['mean_outcomes'])-np.array(oc['mean_outcomes']);aref=float(Amean[np.flatnonzero(GRID==REF)[0]])
                    mseA=float(np.mean(A*A));mseB=float(np.mean(B*B));cross=float(2*np.mean(A*B));total=float(np.mean(T*T))
                    identity=float(abs(T-A-B).max());square_identity=abs(total-mseA-mseB-cross)
                    assert identity<1e-10 and square_identity<1e-7
                    decomp.append(dict(seed=seed,scenario=scenario,label=label,estimator=estimator,unit='ratio' if 'eta' in label else 'seconds',
                        total_curve_rmse=rmse(T),measurement_chain_curve_rmse=rmse(A),oracle_estimator_curve_rmse=rmse(B),
                        mse_total=total,mse_measurement=mseA,mse_oracle_estimation=mseB,squared_error_cross_term=cross,
                        pointwise_identity_max_abs=identity,square_identity_abs=square_identity,
                        absolute_mean_measurement_curve_rms=rmse(Amean),reference_measurement_component=aref,
                        centered_mean_measurement_curve_rms=rmse(Amean-Amean.mean()),
                        mean_measurement_curve_offset=float(Amean.mean()),
                        constant_contrast_cancellation_max_abs=float(abs(A-(Amean-aref)).max())))
                    for j,a in enumerate(GRID):
                        points.append(dict(seed=seed,scenario=scenario,label=label,estimator=estimator,dose=float(a),
                            measured_estimator=float(measured[j]),trueY_estimator=float(true_est[j]),intervention_truth=float(truth_c[j]),
                            total_error=float(T[j]),measurement_chain_component=float(A[j]),oracle_estimator_component=float(B[j]),
                            squared_error_cross_term=float(2*A[j]*B[j]),mean_measurement_component=float(Amean[j]),reference_measurement_component=aref))
            print('completed',seed,scenario,'elapsed',round(time.perf_counter()-started,2),flush=True)
    for name,value in [('effect_scores',effects),('decomposition',decomp),('pointwise_decomposition',points),('event_measurement',events),
                       ('nuisance_diagnostics',weights),('design_audit',designs),('exact_replay',replays),('statuses',statuses)]:
        dump(HERE/(name+'.json'),value);pd.DataFrame(value).to_csv(HERE/(name+'.csv'),index=False,encoding='utf-8-sig')
    ef=pd.DataFrame(effects);dc=pd.DataFrame(decomp);ev=pd.DataFrame(events)
    summary=[]
    for keys,g in ef.groupby(['scenario','label','estimator']):
        summary.append(dict(zip(('scenario','label','estimator'),keys)),)
        summary[-1].update(blocks=len(g),contrast_rmse_mean=float(g.contrast_rmse.mean()),mean_curve_rmse_mean=float(g.mean_curve_rmse.mean()))
    measurement=[];dose_bins=[]
    for keys,g in ev.groupby(['scenario','label']):
        error=g.error.to_numpy();des=np.column_stack([np.ones(len(g)),g.dose,g.L,g.U]);coef=np.linalg.lstsq(des,error,rcond=None)[0]
        residual=error-des@coef;SST=float(np.sum((error-error.mean())**2))
        measurement.append(dict(zip(('scenario','label'),keys)),)
        measurement[-1].update(events=len(g),mae=float(abs(error).mean()),rmse=rmse(error),mean_bias=float(error.mean()),
            centered_error_rmse=rmse(error-error.mean()),corr_error_dose=corr(error,g.dose),corr_error_L=corr(error,g.L),corr_error_U=corr(error,g.U),
            descriptive_linear_projection=dict(intercept=float(coef[0]),dose_slope=float(coef[1]),L_slope=float(coef[2]),U_slope=float(coef[3]),
                R_squared=1-float(np.sum(residual**2))/SST if SST>0 else None,causal_interpretation=False))
        for lo,hi in zip((0.,.6,1.2,1.8),(.6,1.2,1.8,2.4)):
            h=g[(g.dose>=lo)&(g.dose<hi)]
            dose_bins.append(dict(scenario=keys[0],label=keys[1],lo=lo,hi=hi,events=len(h),mean_dose=float(h.dose.mean()),mean_bias=float(h.error.mean()),mae=float(abs(h.error).mean())))
    comparisons=[]
    for scenario in ('positive','zero','pooled_equal_positive_zero'):
        subset=ef if scenario.startswith('pooled') else ef[ef.scenario==scenario]
        for outcome in ('ride_revised_duration','cpop_duration','raw_duration','true_duration','raw_eta','true_eta'):
            g=subset[subset.label==outcome].groupby(['seed','estimator']).contrast_rmse.mean().unstack()
            for alternative in ESTIMATORS[1:]:
                comparisons.append(dict(scenario=scenario,label=outcome,candidate='Kennedy_DR_local_linear',baseline=alternative,
                    **mc(g['Kennedy_DR_local_linear']-g[alternative])))
        for estimator in ESTIMATORS:
            g=subset[subset.estimator==estimator].groupby(['seed','label']).contrast_rmse.mean().unstack()
            comparisons.append(dict(scenario=scenario,label='duration_measurement_comparison',candidate='ride_revised_duration',baseline='cpop_duration',
                estimator=estimator,**mc(g.ride_revised_duration-g.cpop_duration)))
    dec_summary=[]
    for keys,g in dc.groupby(['scenario','label','estimator']):
        row=dict(zip(('scenario','label','estimator'),keys));row['blocks']=len(g)
        for name in ('mse_total','mse_measurement','mse_oracle_estimation','squared_error_cross_term','total_curve_rmse','measurement_chain_curve_rmse',
                     'oracle_estimator_curve_rmse','absolute_mean_measurement_curve_rms','reference_measurement_component',
                     'mean_measurement_curve_offset','centered_mean_measurement_curve_rms'):
            row[name+'_mean']=float(g[name].mean())
        row['cross_term_negative_blocks']=int((g.squared_error_cross_term<0).sum());dec_summary.append(row)
    all_summary=dict(schema='b1.effect-chain-diagnosis.v1',scope='already seen8 simulated blocks; oracle evaluator only; no optimization',
        effect_scores=summary,decomposition=dec_summary,measurement_error=measurement,dose_bin_error=dose_bins,paired_comparisons=comparisons,
        identity_max_abs=float(dc.pointwise_identity_max_abs.max()),square_identity_max_abs=float(dc.square_identity_abs.max()))
    dump(HERE/'results.json',all_summary)
    pd.DataFrame(summary).to_csv(HERE/'effect_summary.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(dec_summary).to_csv(HERE/'decomposition_summary.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(comparisons).to_csv(HERE/'paired_comparisons.csv',index=False,encoding='utf-8-sig')
    after=file_snapshot();dump(HERE/'input_source_sha256_after.json',after)
    receipt=dict(schema='b1.effect-chain-diagnosis-receipt.v1',completed=before==after,input_source_unchanged=before==after,
        protected_files=len(before),existing_factual_target_variants=4096,fit_calls=len(statuses),statuses=dict(Counter(r['status'] for r in statuses)),
        exact_replay_calls=len(replays),exact_replay_all_identical=all(z['identical_numeric'] for z in replays),
        exact_replay_numeric_values=sum(z['numeric_values'] for z in replays),maximum_replay_absolute_difference=max(z['maximum_absolute_difference'] for z in replays),
        decomposition_curves=len(decomp),decomposition_points=len(points),runtime_seconds=time.perf_counter()-started,
        code_sha256=sha(Path(__file__)),new_independent_test=False,new_data_generated=False,new_estimator=False,
        oracle_used_only_in_diagnosis=True,process_refitted=False,runtime_changed=False,default_changed=False,hyperparameters_changed=False,
        failure_or_unsupported_rows_preserved=True,
        initial_audit_harness_failure='First replay used C-contiguous manual X; only support SMD summation differed by8.33e-17, curve/band identical. Retained log and fit; corrected original Fortran-contiguous layout, no scientific parameter changed.')
    dump(HERE/'receipt.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
