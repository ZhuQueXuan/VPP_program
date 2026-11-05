from methods import *
from data import generate,population_curve
import time
def metric(result,truth,scenario):
    if result['status']!='ok':return dict(status='unsupported',penalized_rmse_seconds=T,contrast_rmse_seconds=None,level_mae_seconds=None,zero_effect_false_claim=None)
    target=truth-truth[0];pred=np.asarray(result['contrast_seconds']);mean=np.asarray(result['mean_seconds']);band=result['inference'];false=bool(np.any(np.asarray(band['lower'])>0)|np.any(np.asarray(band['upper'])<0)) if scenario=='zero_effect' else None
    return dict(status='ok',penalized_rmse_seconds=float(np.sqrt(np.mean((pred-target)**2))),contrast_rmse_seconds=float(np.sqrt(np.mean((pred-target)**2))),level_mae_seconds=float(np.mean(abs(mean-truth))),zero_effect_false_claim=false,min_estimated_seconds=float(mean.min()),max_estimated_seconds=float(mean.max()))
def aggregate(entries):
    out={}
    for method in sorted({m for r in entries for m in r['metrics']}):
        rr=[r['metrics'][method] for r in entries if method in r['metrics']];ok=[r for r in rr if r['status']=='ok']
        out[method]=dict(planned=len(rr),successful=len(ok),coverage=len(ok)/len(rr),primary_seconds=float(np.mean([r['penalized_rmse_seconds'] for r in rr])),zero_effect_false_claims=sum(r['zero_effect_false_claim'] is True for r in rr),zero_effect_evaluated=sum(r['zero_effect_false_claim'] is not None for r in rr),mean_level_mae_seconds=float(np.mean([r['level_mae_seconds'] for r in ok])) if ok else None)
    return out
def run_development():
    spec=read(HERE/'protocol.json')['development'];truth={k:population_curve(k) for k in spec['mechanisms']};entries=[]
    # Snapshot before the first fit, including all formal files and past stage.
    paths=list(HERE.glob('*.py'))+[HERE/'protocol.json']+[ROOT/p for p in read(ROOT/'work/b1_residual_false_20261102/protected_before.json')]
    save('protocol_freeze.json',dict(created_utc=now(),before_development_fit=True,files={p.relative_to(ROOT).as_posix():sha(p) for p in paths}))
    for seed in spec['seeds']:
      for scenario in spec['mechanisms']:
        data=generate(seed,scenario,spec['users'],spec['events']);name=f'{seed}_{scenario}';save('development/facts/'+name+'.json',data)
        a=public_DR(data,seed);b,bundle=estimate(data,'DML','single',seed,True)
        if a['status']=='ok' and b['status']=='ok':
            assert np.allclose(bundle['mu']*T,a['public_result']['audit']['outcome_prediction'],rtol=1e-9,atol=1e-7)
            assert np.allclose(bundle['pdf'],a['public_result']['audit']['observed_dose_density'],rtol=1e-9,atol=1e-10)
            assert bundle['folds'].tolist()==a['public_result']['audit']['fold_by_event']
            shared=estimate(data,'DR','single',seed)
            assert shared['status']=='ok' and np.allclose(shared['contrast_seconds'],a['contrast_seconds'],rtol=1e-9,atol=1e-6)
        result=dict(existing_DR=a,continuous_DML=b);entry=dict(seed=seed,scenario=scenario,metrics={m:metric(r,truth[scenario],scenario) for m,r in result.items()});entries.append(entry);save('development/baseline/'+name+'.json',dict(results=result,metrics=entry['metrics'],truth_seconds=truth[scenario]));print('baseline dev',seed,scenario,{m:round(r['penalized_rmse_seconds'],3) for m,r in entry['metrics'].items()},flush=True)
    summary=aggregate(entries);selected=min(summary,key=lambda m:(summary[m]['primary_seconds'],-summary[m]['coverage'],m));engine='DR' if selected=='existing_DR' else 'DML';save('baseline_selection.json',dict(created_utc=now(),summary=summary,selected=selected,estimator=engine,selection_used_development_only=True,final_not_generated=True))
    improvements=[]
    for entry in entries:
        seed=entry['seed'];scenario=entry['scenario'];name=f'{seed}_{scenario}';data=read(HERE/'development/facts'/f'{name}.json');result={};mm={}
        result['selected_base']=read(HERE/'development/baseline'/f'{name}.json')['results'][selected]
        for key,kind in [('bounded_control','bounded'),('capacity_control','capacity'),('soft_two_part','hurdle')]:result[key]=estimate(data,engine,kind,seed)
        mm={m:metric(r,truth[scenario],scenario) for m,r in result.items()};improvements.append(dict(seed=seed,scenario=scenario,metrics=mm));save('development/improvement/'+name+'.json',dict(results=result,metrics=mm,truth_seconds=truth[scenario]));print('improvement dev',seed,scenario,{m:round(r['penalized_rmse_seconds'],3) for m,r in mm.items()},flush=True)
    save('development/summary.json',dict(baseline=summary,improvement=aggregate(improvements),baseline_entries=entries,improvement_entries=improvements))
    paths=list(HERE.glob('*.py'))+[HERE/'protocol.json',HERE/'baseline_selection.json',HERE/'development/summary.json']+[ROOT/p for p in read(ROOT/'work/b1_residual_false_20261102/protected_before.json')]
    save('freeze.json',dict(created_utc=now(),before_any_final_generation=True,files={p.relative_to(ROOT).as_posix():sha(p) for p in paths},selected_baseline=selected,improvement_budget=1,no_test_tuning=True))
    print('Development frozen:',selected,json.dumps(native(aggregate(improvements))),flush=True)
def run_final():
    verify_freeze();spec=read(HERE/'protocol.json')['final'];selection=read(HERE/'baseline_selection.json');engine=selection['estimator'];truth={k:population_curve(k) for k in spec['mechanisms']};entries=[];weak=[]
    for seed in spec['seeds']:
      for scenario in spec['mechanisms']+['weak_support']:
        data=generate(seed,scenario,spec['users'],spec['events'],stage='final');name=f'{seed}_{scenario}';save('final/facts/'+name+'.json',data)
        result=dict(existing_DR=public_DR(data,seed),continuous_DML=estimate(data,'DML','single',seed))
        for key,kind in [('bounded_control','bounded'),('capacity_control','capacity'),('soft_two_part','hurdle')]:result[key]=estimate(data,engine,kind,seed)
        result['selected_base']=result[selection['selected']]
        if scenario=='weak_support':
            weak.append(dict(seed=seed,statuses={m:r['status'] for m,r in result.items()}));save('final/results/'+name+'.json',dict(results=result,expected='unsupported_deterministic_assignment'));print('final weak-support',seed,{m:r['status'] for m,r in result.items()},flush=True);continue
        mm={m:metric(r,truth[scenario],scenario) for m,r in result.items()};entries.append(dict(seed=seed,scenario=scenario,metrics=mm));save('final/results/'+name+'.json',dict(results=result,metrics=mm,truth_seconds=truth[scenario]));print('final',seed,scenario,{m:round(r['penalized_rmse_seconds'],3) for m,r in mm.items()},flush=True)
    save('final/summary.json',dict(summary=aggregate(entries),entries=entries,heldout_whole_mechanisms=aggregate([r for r in entries if r['scenario'] in ['nonmonotone','assignment_mixture']]),weak_support=weak))
    print('Final summary:',json.dumps(native(aggregate(entries))),flush=True)
if __name__=='__main__':run_development() if sys.argv[1]=='development' else run_final()
