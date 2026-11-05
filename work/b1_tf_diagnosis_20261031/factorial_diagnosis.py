"""Fixed 4 covariance x 2 lambda diagnostic on 192 already-seen variants.

No reference retraining, facts generation, tuning, oracle inputs or adoption.
Truth is used only after each fit for evaluation of the saved curve.
"""
import os,sys,json,hashlib
from pathlib import Path
from collections import defaultdict,Counter
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
sys.dont_write_bytecode=True
import numpy as np
from scipy.linalg import cho_factor,cho_solve
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
PILOT=ROOT/'work/b1_unknown_reference_pilot_20261031'
sys.path.insert(0,str(PILOT))
from trend_filter import fit_curve,second_difference
inputs={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    inputs[Path(p).relative_to(ROOT).as_posix()]=sha(p)
    return json.loads(Path(p).read_text(encoding='utf8'))
def dump_new(p,x):
    with Path(p).open('x',encoding='utf8') as h:json.dump(x,h,ensure_ascii=False,indent=2,allow_nan=False)

freeze=read(PILOT/'freeze.json');err=read(PILOT/'development_error_model.json')
for name,h in freeze['source_identity'].items():
    assert sha(ROOT/name)==h, name
S=np.asarray(err['covariance']);v=err['scalar_variance'];n=60
factor=v/(float(np.trace(S))/n)
covariances=dict(scalar_rms=v*np.eye(n),diagonal_full=np.diag(np.diag(S)),full=S,trace_normalized_full=factor*S)
penalties=(2.,4.);seeds=(7610500,7610501,7610502,7610503);variants=('strong','weak','null')
design=dict(scope='Already-seen fixed pilot test diagnostic, not new independent test or setting selection.',
    seeds=list(seeds),facts_indices='0:16 in original order per block and variant; exactly first8users x2events',
    variants=list(variants),penalties=list(penalties),covariances={k:a.tolist() for k,a in covariances.items()},
    scalar_rms_variance=v,mean_full_variance=float(np.trace(S))/n,trace_normalization_factor=factor,
    original_source_sha256=freeze['source_identity'],operator='H=I native one-minute interval means',
    no_oracle_inputs=True,no_reference_fit=True,no_adoption_or_deployment=True,
    metrics_definition=dict(duration='60 times number of task bins >=.15kW, same evaluator target',
      false_positive_bins='task fitted>=.15 and true<.15; false-negative vice versa',
      post_exit_positive_bins='fitted>=.15 after final truly threshold-positive task bin, task only; zero when no true positive bins',
      pretask_max_absolute_kw='max abs fitted in[-15,0), includes reference error; not a ringing-only statistic',
      edge_extra_turns='positive excess of discrete slope sign reversals (zero slopes ignored at1e-9) vs truth in fixed[25,35)min neighborhood',
      edge_range_overshoot_kw='max fitted excursion beyond truth min/max in same fixed[25,35)min neighborhood; includes bias, not proof of ringing'))
dump_new(HERE/'factorial_design.json',design)
D=second_difference(n);Z=np.column_stack([np.ones(n)/np.sqrt(n),(np.arange(n)-(n-1)/2)/np.linalg.norm(np.arange(n)-(n-1)/2)])
chols={k:cho_factor(c,lower=True) for k,c in covariances.items()}
controls=[]
for name,cov in covariances.items():
    for lam in penalties:
        for kind,y in [('constant',np.full(n,.17)),('line',-.04+.004*np.arange(n))]:
            result=fit_curve(y,cov,lam);assert result['status']=='ok'
            delta=float(np.max(np.abs(np.asarray(result['prediction'])-y)))
            assert delta<1e-9
            controls.append(dict(covariance=name,penalty=lam,signal=kind,max_prediction_difference=delta,
                gap=result['raw_gap'],solver_success=result['success']))

def turns(x):
    diff=np.diff(x);sign=np.sign(diff[np.abs(diff)>1e-9])
    return int(np.sum(sign[1:]!=sign[:-1])) if len(sign)>1 else 0
rows=[];saved=[];statuses=Counter();maxmoment=0.;maxgap=0.;max_decomposition_error=0.
for seed in seeds:
    ref=read(PILOT/'references'/f'test_{seed}.json')
    for variant in variants:
        facts=read(ROOT/'data/B1_unknown_reference_pilot_v1_20261031/test'/f'{seed}_{variant}_facts.json')[:16]
        truth=read(PILOT/'evaluator/test'/f'{seed}_{variant}_truth.json')[:16]
        assert len(facts)==16 and len({f['task']['user_id'] for f in facts})==8
        assert all(sum(g['task']['user_id']==f['task']['user_id'] for g in facts)==2 for f in facts)
        for index,(f,t) in enumerate(zip(facts,truth)):
            assert f['task']['task_id']==t['task_id']==ref['task_ids'][index]
            y=np.asarray(ref['prediction'][index])-np.asarray(f['power_kw'])
            true=np.asarray(t['true_reduction_kw']);starts=np.asarray(t['relative_starts_min']);req=(starts>=0)&(starts<30)
            realmask=true[req]>=.15;realduration=float(realmask.sum()*60)
            assert realduration==t['cumulative_response_seconds']
            for name,cov in covariances.items():
                for lam in penalties:
                    fitted=fit_curve(y,cov,lam);statuses[fitted['status']]+=1
                    identity=dict(seed=seed,variant=variant,index=index,task_id=f['task']['task_id'],user_id=f['task']['user_id'],covariance=name,penalty=lam)
                    saved.append(dict(**identity,fit=fitted))
                    row=dict(**identity,status=fitted['status'],physical_action=t['physical_action'],threshold_positive=t['threshold_positive'],
                        true_duration=realduration,weak_subtype=t.get('weak_subtype'),weak_amplitude_fraction=t.get('weak_amplitude_fraction'))
                    if fitted['prediction'] is not None:
                        x=np.asarray(fitted['prediction']);mask=x[req]>=.15;duration=float(mask.sum()*60)
                        fp=int(np.sum(mask&~realmask));fn=int(np.sum(~mask&realmask));bias=duration-realduration
                        decomposition_error=abs(bias-60*(fp-fn));assert decomposition_error<1e-9
                        max_decomposition_error=max(max_decomposition_error,decomposition_error)
                        edge=(starts>=25)&(starts<35);localtrue=true[edge];localfit=x[edge]
                        overshoot=max(0.,float(np.max(localfit)-np.max(localtrue)),float(np.min(localtrue)-np.min(localfit)))
                        pos=np.flatnonzero(realmask);tail=int(np.sum(mask[pos[-1]+1:])) if len(pos) else 0
                        moments=Z.T@cho_solve(chols[name],x-y)
                        maxmoment=max(maxmoment,float(np.max(np.abs(moments))));assert np.max(np.abs(moments))<1e-7
                        maxgap=max(maxgap,abs(fitted['raw_gap']))
                        row.update(duration=duration,duration_bias=bias,duration_mae=abs(bias),
                            false_positive_duration=bool(not t['physical_action'] and duration>0),
                            missed_positive_duration=bool(t['threshold_positive'] and duration==0),
                            false_positive_bins=fp,false_negative_bins=fn,fitted_positive_bins=int(mask.sum()),true_positive_bins=int(realmask.sum()),
                            post_exit_positive_bins=tail,task_curve_mse=float(np.mean((x[req]-true[req])**2)),
                            whole_curve_mse=float(np.mean((x-true)**2)),pretask_max_absolute_kw=float(np.max(np.abs(x[starts<0]))),
                            edge_extra_turns=max(0,turns(localfit)-turns(localtrue)),edge_fit_turns=turns(localfit),edge_true_turns=turns(localtrue),
                            edge_range_overshoot_kw=overshoot,weighted_moment_max=float(np.max(np.abs(moments))),
                            raw_gap=fitted['raw_gap'])
                    rows.append(row)

def aggregate(group):
    valid=[r for r in group if r['status']=='ok']
    out=dict(events=len(group),available=len(valid),unavailable=len(group)-len(valid),
        no_action=sum(not r['physical_action'] for r in group),threshold_positive=sum(r['threshold_positive'] for r in group),
        unavailable_positive=sum(r['threshold_positive'] and r['status']!='ok' for r in group))
    for key in ('false_positive_duration','missed_positive_duration','false_positive_bins','false_negative_bins','fitted_positive_bins','true_positive_bins','post_exit_positive_bins','edge_extra_turns'):
        out[key]=sum(r[key] for r in valid)
    for key in ('duration_mae','duration_bias','pretask_max_absolute_kw','edge_range_overshoot_kw'):
        out[key+'_mean']=float(np.mean([r[key] for r in valid])) if valid else None
    for key in ('task_curve_mse','whole_curve_mse'):
        out[key.replace('_mse','_pooled_rmse_kw')]=float(np.sqrt(np.mean([r[key] for r in valid]))) if valid else None
    out['fp_fn_balance_identity_seconds']=60*(out['false_positive_bins']-out['false_negative_bins'])
    out['summed_duration_bias_seconds']=sum(r['duration_bias'] for r in valid)
    assert abs(out['fp_fn_balance_identity_seconds']-out['summed_duration_bias_seconds'])<1e-9
    return out

summary=[];by_seed=[]
for variant in variants:
    for name in covariances:
        for lam in penalties:
            group=[r for r in rows if r['variant']==variant and r['covariance']==name and r['penalty']==lam]
            summary.append(dict(variant=variant,covariance=name,penalty=lam,**aggregate(group)))
            for seed in seeds:by_seed.append(dict(seed=seed,variant=variant,covariance=name,penalty=lam,**aggregate([r for r in group if r['seed']==seed])))
contrasts=[]
for variant in variants:
    for lam in penalties:
        group={(r['covariance'],r['penalty']):r for r in summary if r['variant']==variant}
        for a,b,label in [('full','diagonal_full','correlation_conditional_on_diagonal_and_lambda'),
                          ('trace_normalized_full','full','common_scalar_covariance_scale'),
                          ('diagonal_full','scalar_rms','variance_diagonal_and_average_scale_compound')]:
            first,second=group[(a,lam)],group[(b,lam)]
            keys=['false_positive_duration','missed_positive_duration','duration_mae_mean','duration_bias_mean','false_positive_bins','false_negative_bins','edge_extra_turns','edge_range_overshoot_kw_mean','task_curve_pooled_rmse_kw']
            contrasts.append(dict(variant=variant,penalty=lam,comparison=f'{a} minus {b}',meaning=label,
                difference={k:first[k]-second[k] for k in keys}))
    for name in covariances:
        a=next(r for r in summary if r['variant']==variant and r['covariance']==name and r['penalty']==4)
        b=next(r for r in summary if r['variant']==variant and r['covariance']==name and r['penalty']==2)
        contrasts.append(dict(variant=variant,covariance=name,comparison='lambda4 minus lambda2',meaning='regularization_strength_same_covariance',
            difference={k:a[k]-b[k] for k in ['false_positive_duration','missed_positive_duration','duration_mae_mean','duration_bias_mean','false_positive_bins','false_negative_bins','edge_extra_turns','task_curve_pooled_rmse_kw']}))
for p,h in inputs.items():assert sha(ROOT/p)==h
for p,h in freeze['source_identity'].items():assert sha(ROOT/p)==h
result=dict(scope=design['scope'],independent_test=False,new_configuration_selected=False,original_selection_changed=False,
    n_factual_variants=192,n_base_tasks=64,settings=8,fits=len(rows),status_counts=dict(statuses),summary=summary,
    seed_summary=by_seed,paired_contrasts=contrasts,controls=controls,max_weighted_moment=maxmoment,
    max_absolute_gap=maxgap,max_duration_bin_decomposition_error=max_decomposition_error,input_sha256=inputs,
    original_source_sha256=freeze['source_identity'],all_original_source_and_read_inputs_unchanged=True,
    scale_diagnostics=dict(scalar_variance=v,mean_full_variance=float(np.trace(S))/n,normalization_factor=factor,
       full_condition_number=float(np.linalg.cond(S)),full_min_eigenvalue=float(np.linalg.eigvalsh(S)[0]),
       normalized_full_equivalence='Multiplying covariance by c is algebraically equivalent to multiplying lambda by c at fixed original covariance; this is a diagnostic contrast, not an extra free mechanism.'))
dump_new(HERE/'factorial_curves_solver.json',saved)
dump_new(HERE/'factorial_event_metrics.json',rows)
dump_new(HERE/'factorial_diagnosis.json',result)
print(json.dumps(dict(fits=len(rows),status_counts=dict(statuses),max_weighted_moment=maxmoment,max_absolute_gap=maxgap,summary=summary),ensure_ascii=False))
