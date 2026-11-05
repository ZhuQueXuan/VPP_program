"""New development and a single held-out confirmation; only final smoothing changes."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
from pathlib import Path
import sys,json,hashlib,time
from dataclasses import replace
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.effects.continuous import (fit_continuous_effects,ContinuousEffectConfig,
    local_linear_weights,_local_support)
from b1_algorithm.effects.frozen import local_linear_derivative_weights
from data import generate,truth,population
from smoothers import spline_state,spline_query,crossings
from prepare import save,hashes

P=json.loads((HERE/'protocol.json').read_text(encoding='utf-8'))
GRID=np.asarray(P['grid']);MESH=np.asarray(P['threshold_mesh']);REF=P['reference']
TASK=dict(task_id='smoother-only-common-30min',outcome_name='cumulative_response_seconds',outcome_unit='seconds',
    target_population='new simulated invited population including nonresponders',window_minutes=[0.,30.],
    q_kw=1.5,task_pre_treatment=True,reference_status='provided',reference_uncertainty='not_propagated')

def support(x,d,u,a,h,w,cfg):
    return _local_support(x,d,u,a,h,w,cfg)[1]

def policy_name(value,kind):return kind+'_'+format(float(value),'.8g')

def assess(query,derivative,true,true_cross,root_available):
    mean=query(GRID);contrast=mean-float(query(np.array([REF]))[0])
    dc=derivative(GRID)
    root=crossings(query,REF,MESH,P['target_seconds']) if root_available else None
    return dict(status='ok',mean_outcomes=mean.tolist(),contrasts=contrast.tolist(),derivative=dc.tolist(),
        curve_rmse_seconds=float(np.sqrt(np.mean((contrast-true['contrasts'])**2))),
        level_mae_seconds=float(np.mean(abs(mean-true['mean']))),
        maximum_contrast_error_seconds=float(np.max(abs(contrast-true['contrasts']))),
        derivative_rmse=float(np.sqrt(np.mean((dc-true['derivative'])**2))),
        target=root,true_target=true_cross,
        target_correct=None if root is None else root['reached']==true_cross['reached'],
        crossing_error=None if root is None or not root['reached'] or not true_cross['reached'] else abs(root['first_crossing']-true_cross['first_crossing']))

def cohort(stage,seed,kind,selected=None):
    started=time.perf_counter();spec=P[stage];folder=HERE/stage/f'{seed}-{kind}'
    folder.mkdir(parents=True,exist_ok=False)
    facts=generate(seed,kind,spec['users'],spec['events_per_user']);save(folder/'facts.json',facts)
    x=np.asarray(facts['X'])[:,:2];d=np.asarray(facts['treatment']);y=np.asarray(facts['outcome'])
    u=np.asarray(facts['users']);cfg=ContinuousEffectConfig(seed=seed,n_boot=99,return_audit=True)
    assumptions=dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,same_outcome_definition=True,
        conditional_exchangeability=True,randomized_assignment=kind=='randomized_saturation')
    result=fit_continuous_effects(x,d,y,u,dose_domain=P['dose_domain'],grid=GRID,reference_dose=REF,
        incentive_unit='yuan/kWh',task=TASK,continuous_assignment=True,assumptions=assumptions,
        known_density=facts['known_density'],config=cfg)
    save(folder/'baseline_api.json',result)
    true=truth(GRID,kind,reference=REF)
    true_cross=crossings(lambda a:population(a,kind),REF,MESH,P['target_seconds'])
    save(folder/'truth.json',dict(**true,target=true_cross))
    row=dict(seed=seed,mechanism=kind,events=len(y),users=spec['users'],nuisance_fits=1,policies={})
    if result['status'] not in ('causal','association'):
        row.update(baseline_status=result['status'],failure=result['reasons'],elapsed_seconds=time.perf_counter()-started)
        save(folder/'score.json',row);print(stage,seed,kind,result['status'],flush=True);return row
    audit=result['audit'];xi=np.asarray(audit['pseudo_outcome']);w=np.asarray(audit['stabilized_weight'])
    h=result['diagnostics']['bandwidth']
    common_root=not support(x,d,u,MESH,h,w,cfg)
    row.update(baseline_status=result['status'],pseudo_outcome_sha256=hashlib.sha256(xi.tobytes()).hexdigest(),
        common_threshold_support=common_root,amount_min=float(d.min()),amount_max=float(d.max()))
    def ll(mult):
        hh=h*mult
        if hh>P['dose_domain'][1]/2 or support(x,d,u,GRID,hh,w,cfg):
            return dict(status='unsupported',bandwidth=hh)
        q=lambda a:local_linear_weights(d,np.asarray(a),hh)@xi
        dq=lambda a:local_linear_derivative_weights(d,np.asarray(a),hh)@xi
        score=assess(q,dq,true,true_cross,common_root and not support(x,d,u,MESH,hh,w,cfg))
        score['bandwidth']=hh
        return score
    row['policies']['fixed_LL']=ll(1.)
    if row['policies']['fixed_LL']['status']=='ok':
        assert np.allclose(row['policies']['fixed_LL']['contrasts'],result['causal_curve']['contrasts'],rtol=0,atol=1e-9)
    multipliers=P['tuning_control']['grid'] if selected is None else [selected['ll_multiplier']]
    lambdas=P['candidate']['lambda_mean_grid'] if selected is None else [selected['lambda_mean']]
    for mult in multipliers:row['policies'][policy_name(mult,'LL')]=ll(mult)
    for lam in lambdas:
        name=policy_name(lam,'spline')
        if GRID.min()<d.min() or GRID.max()>d.max():
            row['policies'][name]=dict(status='unsupported',reason='query beyond observed amount extremes')
            continue
        try:
            state=spline_state(d,xi,lam)
            root_available=common_root and MESH.min()>=d.min() and MESH.max()<=d.max()
            score=assess(lambda a:spline_query(state,a),lambda a:spline_query(state,a,1),true,true_cross,root_available)
            score.update(lambda_mean=lam,same_shared_pseudo_outcome=True)
            row['policies'][name]=score
            save(folder/(name+'_state.json'),state)
        except (ValueError,np.linalg.LinAlgError) as exc:
            row['policies'][name]=dict(status='unsupported',reason=str(exc))
    row['elapsed_seconds']=time.perf_counter()-started
    save(folder/'score.json',row)
    print(stage,seed,kind,round(row['elapsed_seconds'],2),{k:round(v['curve_rmse_seconds'],2) if v['status']=='ok' else None for k,v in row['policies'].items()},flush=True)
    return row

def aggregate(rows):
    names=sorted({k for r in rows for k in r['policies']})
    out={}
    for k in names:
        valid=[r['policies'][k] for r in rows if r['policies'].get(k,{}).get('status')=='ok']
        target=[v for v in valid if v['target'] is not None]
        cross=[v['crossing_error'] for v in target if v['crossing_error'] is not None]
        out[k]=dict(outputs=len(valid),designed_cohorts=len(rows),
            mean_curve_rmse=float(np.mean([v['curve_rmse_seconds'] for v in valid])) if valid else None,
            mean_level_mae=float(np.mean([v['level_mae_seconds'] for v in valid])) if valid else None,
            mean_derivative_rmse=float(np.mean([v['derivative_rmse'] for v in valid])) if valid else None,
            target_outputs=len(target),target_correct=sum(v['target_correct'] for v in target),
            false_reached=sum(v['target']['reached'] and not v['true_target']['reached'] for v in target),
            missed_reached=sum(not v['target']['reached'] and v['true_target']['reached'] for v in target),
            mean_crossing_error=float(np.mean(cross)) if cross else None,jointly_reached=len(cross))
    return out

def main(stage):
    assert stage in ('development','confirmation')
    selected=None
    if stage=='confirmation':
        freeze=json.loads((HERE/'selection_freeze.json').read_text(encoding='utf-8'))
        for path,h in freeze['files'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h,path
        selected=freeze['selected']
    else:
        before=json.loads((HERE/'formal_before.json').read_text(encoding='utf-8'))
        assert hashes()==before
    rows=[]
    for seed in P[stage]['seeds']:
        for kind in P[stage]['mechanisms']:rows.append(cohort(stage,seed,kind,selected))
    summary=dict(rows=rows,aggregate=aggregate(rows),independent_seed_blocks=len(P[stage]['seeds']))
    save(HERE/stage/'summary.json',summary)
    if stage=='development':
        agg=summary['aggregate'];base_outputs=agg['fixed_LL']['outputs']
        def choose(prefix,values):
            eligible=[v for v in values if agg[policy_name(v,prefix)]['outputs']>=base_outputs and agg[policy_name(v,prefix)]['mean_curve_rmse'] is not None]
            if not eligible:raise ValueError('No supported development candidate; cannot silently switch design')
            return min(eligible,key=lambda v:(agg[policy_name(v,prefix)]['mean_curve_rmse'],-v))
        selected=dict(lambda_mean=choose('spline',P['candidate']['lambda_mean_grid']),
            ll_multiplier=choose('LL',P['tuning_control']['grid']))
        files=hashes()
        for name in ('prepare.py','data.py','smoothers.py','study.py','protocol.json'):
            p=HERE/name;files[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
        save(HERE/'selection_freeze.json',dict(selected=selected,files=files,
            selected_on='new development only; no confirmation generated/read',development_aggregate=agg))
        print('SELECTED',json.dumps(selected),flush=True)
    print('AGGREGATE',json.dumps(summary['aggregate']),flush=True)

if __name__=='__main__':main(sys.argv[1])
