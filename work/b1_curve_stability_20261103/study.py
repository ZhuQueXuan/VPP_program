"""One new final-smoother hypothesis, with retained and constant-blend controls."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
from pathlib import Path
import sys,json,hashlib,time
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OLD=HERE.parent/'b1_curve_spline_pilot_20261103'
sys.path.insert(0,str(ROOT/'B1算法'));sys.path.append(str(OLD))
from b1_algorithm.effects.continuous import fit_continuous_effects,ContinuousEffectConfig,local_linear_weights,_local_support
from b1_algorithm.effects.frozen import local_linear_derivative_weights
from data import generate,population,truth
from smoothers import spline_state,spline_query,crossings
from nested import select_nested_alpha
from prepare import save,formal_hashes

P=json.loads((HERE/'protocol.json').read_text(encoding='utf-8'))
GRID=np.asarray(P['grid']);MESH=np.asarray(P['mesh']);REF=P['reference']
TASK=dict(task_id='curve-stability-30min',outcome_name='cumulative_response_seconds',outcome_unit='seconds',
    target_population='new invited simulated population including nonresponders',window_minutes=[0.,30.],q_kw=1.5,
    task_pre_treatment=True,reference_status='provided',reference_uncertainty='not_propagated')

def key(prefix,value):return prefix+'_'+format(float(value),'.8g')

def evaluate(mean,derivative,true,target_truth,root_available):
    contrast=mean-mean[0]
    # Crossing evaluated separately through the actual continuous model by caller.
    return dict(status='ok',mean=mean.tolist(),contrast=contrast.tolist(),derivative=derivative.tolist(),
        curve_rmse_seconds=float(np.sqrt(np.mean((contrast-np.asarray(true['contrasts']))**2))),
        level_mae_seconds=float(np.mean(abs(mean-np.asarray(true['mean'])))),
        reference_error=float(mean[0]-true['mean'][0]),
        derivative_rmse=float(np.sqrt(np.mean((derivative-np.asarray(true['derivative']))**2))),
        target=None,true_target=target_truth,root_support=root_available)

def aggregate(rows):
    names=sorted({n for row in rows for n in row['policies']});out={}
    for n in names:
        valid=[r['policies'][n] for r in rows if r['policies'].get(n,{}).get('status')=='ok']
        targets=[r for r in valid if r['target'] is not None]
        errors=[abs(r['target']['first_crossing']-r['true_target']['first_crossing']) for r in targets if r['target']['reached'] and r['true_target']['reached']]
        out[n]=dict(outputs=len(valid),designed=len(rows),
            mean_curve_rmse=float(np.mean([r['curve_rmse_seconds'] for r in valid])) if valid else None,
            mean_level_mae=float(np.mean([r['level_mae_seconds'] for r in valid])) if valid else None,
            mean_derivative_rmse=float(np.mean([r['derivative_rmse'] for r in valid])) if valid else None,
            target_outputs=len(targets),target_correct=sum(r['target']['reached']==r['true_target']['reached'] for r in targets),
            false_reached=sum(r['target']['reached'] and not r['true_target']['reached'] for r in targets),
            missed_reached=sum(not r['target']['reached'] and r['true_target']['reached'] for r in targets),
            crossing_error=float(np.mean(errors)) if errors else None,jointly_reached=len(errors))
    return out

def cohort(stage,seed,kind,selected):
    started=time.perf_counter();spec=P[stage];folder=HERE/stage/f'{seed}-{kind}'
    folder.mkdir(parents=True,exist_ok=False)
    f=generate(seed,kind,spec['users'],spec['events_per_user']);save(folder/'facts.json',f)
    x=np.asarray(f['X'])[:,:2];d=np.asarray(f['treatment']);y=np.asarray(f['outcome']);u=np.asarray(f['users'])
    cfg=ContinuousEffectConfig(seed=seed,n_boot=99,return_audit=True)
    assumptions=dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,same_outcome_definition=True,
        conditional_exchangeability=True,randomized_assignment=kind=='randomized_saturation')
    b=fit_continuous_effects(x,d,y,u,dose_domain=P['domain'],grid=GRID,reference_dose=REF,incentive_unit='yuan/kWh',
        task=TASK,continuous_assignment=True,assumptions=assumptions,known_density=f['known_density'],config=cfg)
    save(folder/'baseline_api.json',b)
    t=truth(GRID,kind,reference=REF)
    target_truth=crossings(lambda a:population(a,kind),REF,MESH,P['target_seconds'])
    save(folder/'truth.json',dict(**t,target=target_truth))
    row=dict(seed=seed,mechanism=kind,users=spec['users'],events=len(d),policies={},shared_full_fit_status=b['status'])
    if b['status']!='causal':
        row.update(failure=b['reasons'],elapsed_seconds=time.perf_counter()-started)
        save(folder/'score.json',row);print(stage,seed,kind,'unsupported full fit',flush=True);return row
    xi=np.asarray(b['audit']['pseudo_outcome']);w=np.asarray(b['audit']['stabilized_weight'])
    h=b['diagnostics']['bandwidth']
    if GRID.min()<d.min() or GRID.max()>d.max():
        row.update(failure='Spline amount query beyond observed extremes; no replacement data',elapsed_seconds=time.perf_counter()-started)
        save(folder/'score.json',row);return row
    try:
        state=spline_state(d,xi,1e-4)
        smean=spline_query(state,GRID);sder=spline_query(state,GRID,1)
    except (ValueError,np.linalg.LinAlgError) as exc:
        row.update(failure='Retained spline numeric fit/query unavailable: '+str(exc),elapsed_seconds=time.perf_counter()-started)
        save(folder/'score.json',row);return row
    save(folder/'retained_spline_state.json',state)
    common_root=not _local_support(x,d,u,MESH,h,w,cfg)[1]
    spline_root=MESH.min()>=d.min() and MESH.max()<=d.max()
    llmean=local_linear_weights(d,GRID,2*h)@xi;lld=local_linear_derivative_weights(d,GRID,2*h)@xi
    strong_failed=_local_support(x,d,u,GRID,2*h,w,cfg)[1]
    strong_root=not _local_support(x,d,u,MESH,2*h,w,cfg)[1]
    strong_valid=not strong_failed and 2*h<=(P['domain'][1]-P['domain'][0])/2
    cv=select_nested_alpha(x,d,y,u,config=cfg,known_density=f['known_density'])
    save(folder/'nested_selection.json',cv)
    raw=float(cv['alpha']);row.update(raw_alpha_spline=raw,cv_status=cv['status'],
        cv_failure_count=len(cv['failures']),shared_pseudo_outcome_sha256=hashlib.sha256(xi.tobytes()).hexdigest())
    def add(name,alpha):
        if alpha<1 and not strong_valid:
            row['policies'][name]=dict(status='unsupported',reason='strong-smoother support failure');return
        values=alpha*smean+(1-alpha)*llmean;derivative=alpha*sder+(1-alpha)*lld
        valid_root=common_root and (alpha==0 or spline_root) and (alpha==1 or strong_root)
        score=evaluate(values,derivative,t,target_truth,valid_root)
        if valid_root:
            def query(a):
                if alpha==0:return local_linear_weights(d,np.asarray(a),2*h)@xi
                if alpha==1:return spline_query(state,a)
                return alpha*spline_query(state,a)+(1-alpha)*(local_linear_weights(d,np.asarray(a),2*h)@xi)
            score['target']=crossings(query,REF,MESH,P['target_seconds'])
        score['alpha_spline']=alpha;row['policies'][name]=score
    add('retained_S',1.);add('strong_LL2',0.)
    orig=local_linear_weights(d,GRID,h)@xi;origder=local_linear_derivative_weights(d,GRID,h)@xi
    original=evaluate(orig,origder,t,target_truth,common_root)
    if common_root:original['target']=crossings(lambda a:local_linear_weights(d,np.asarray(a),h)@xi,REF,MESH,P['target_seconds'])
    row['policies']['original_LL']=original
    assert np.allclose(original['contrast'],b['causal_curve']['contrasts'],rtol=0,atol=1e-9)
    gammas=P['candidate']['gamma_grid'] if selected is None else [selected['gamma']]
    betas=P['fixed_blend_control']['beta_grid'] if selected is None else [selected['beta']]
    for beta in betas:add(key('constant',beta),float(beta))
    for gamma in gammas:add(key('adaptive',gamma),1-float(gamma)*(1-raw))
    # Exact same xi and final models for every policy, including a fallback.
    save(folder/'final_shared_state.json',dict(X=x.tolist(),dose=d.tolist(),pseudo_outcome=xi.tolist(),
        users=u.tolist(),stabilized_weight=w.tolist(),configuration=b['configuration'],bandwidth=h,
        retained_spline=state,reference=REF,domain=P['domain'],task=TASK,raw_alpha_spline=raw,
        selected_gamma=None if selected is None else selected['gamma'],output_scope='part3 point curve only'))
    row['elapsed_seconds']=time.perf_counter()-started
    save(folder/'score.json',row)
    chosen=['retained_S','constant_'+format(selected['beta'],'.8g'),'adaptive_'+format(selected['gamma'],'.8g')] if selected else ['retained_S','adaptive_1']
    print(stage,seed,kind,round(row['elapsed_seconds'],2),'alpha',round(raw,3),cv['status'],
        {n:round(row['policies'][n]['curve_rmse_seconds'],3) if row['policies'][n]['status']=='ok' else None for n in chosen},flush=True)
    return row

def main(stage):
    selected=None
    if stage=='confirmation':
        frozen=json.loads((HERE/'selection_freeze.json').read_text(encoding='utf-8'))
        for path,h in frozen['files'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h,path
        selected=frozen['selected']
    else:
        assert stage=='development'
        assert formal_hashes()==json.loads((HERE/'formal_before.json').read_text(encoding='utf-8'))
        freeze=json.loads((HERE/'source_freeze.json').read_text(encoding='utf-8'))
        for name,h in freeze.items():assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==h,name
    rows=[cohort(stage,seed,kind,selected) for seed in P[stage]['seeds'] for kind in P[stage]['mechanisms']]
    agg=aggregate(rows);save(HERE/stage/'summary.json',dict(rows=rows,aggregate=agg,independent_seed_blocks=len(P[stage]['seeds'])))
    if stage=='development':
        def choose(prefix,values,prefer_smaller):
            eligible=[v for v in values if agg[key(prefix,v)]['outputs']==len(rows)]
            if not eligible:raise ValueError('No complete candidate; no replacement samples')
            return min(eligible,key=lambda v:(agg[key(prefix,v)]['mean_curve_rmse'],v if prefer_smaller else -v))
        selected=dict(gamma=choose('adaptive',P['candidate']['gamma_grid'],True),
            beta=choose('constant',P['fixed_blend_control']['beta_grid'],False))
        files=formal_hashes()
        for name in ('data.py','nested.py','study.py','protocol.json','prepare.py'):
            f=HERE/name;files[str(f.relative_to(ROOT))]=hashlib.sha256(f.read_bytes()).hexdigest()
        for name in ('smoothers.py',):
            f=OLD/name;files[str(f.relative_to(ROOT))]=hashlib.sha256(f.read_bytes()).hexdigest()
        save(HERE/'selection_freeze.json',dict(selected=selected,files=files,development_aggregate=agg,
            confirmation_data_generated_or_read=False))
        print('SELECTED',selected,flush=True)
    print('AGGREGATE',json.dumps({n:v for n,v in agg.items() if n in ['retained_S','strong_LL2','original_LL',key('constant',selected['beta']),key('adaptive',selected['gamma'])]}),flush=True)

if __name__=='__main__':main(sys.argv[1])
