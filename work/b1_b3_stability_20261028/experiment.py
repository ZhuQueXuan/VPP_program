import copy,time,sys
import numpy as np
from core_io import BASE,ROOT,RAW,read,write,sha,integrity
from controller import simulate,H,D
from b1_adapter import extract_event
from legacy_guard import replay

def freeze():
    assert read(BASE/'micro_checks.json')['status']=='passed'
    assert read(BASE/'micro_checks_after_contract.json')['status']=='passed'
    old=read(ROOT/'work/b1_b2_history_20261028/source_freeze.json');protected=dict(old['protected'])
    for p in (ROOT/'work/b1_b2_history_20261028').iterdir():
        if p.is_file():protected[str(p.relative_to(ROOT))]=sha(p)
    for p in [ROOT/'work/b1_research_20261021/features.py',ROOT/'data/B3_feedback_v1_20261028/cases.json',ROOT/'data/B3_feedback_v1_20261028/evaluation_actual_factors.npz']:protected[str(p.relative_to(ROOT))]=sha(p)
    for n,h in protected.items():assert sha(ROOT/n)==h,n
    sources={p.name:sha(p) for p in BASE.iterdir() if p.suffix in ['.py','.json'] and p.name!='source_freeze.json'}
    write(BASE/'source_freeze.json',dict(source=sources,protected=protected,main_generation_not_started=True));print('frozen',len(sources),len(protected),flush=True)

def metrics(c,run):
    p=np.array(run['paths_kw']);b=np.array([e['declaration']['b'] for e in c['evs']]);baseline=c['fixed_kw']+b.sum()*(np.arange(H)<D)-.6*np.array(c['pv_forecast_kw']);net=c['fixed_kw']+p.sum(axis=1);delivery=baseline-net;calls=[]
    for call in run['calls']:
        t=call['task'];a=t['start_min'];ad=call['initially_admitted'];got=delivery[a:a+30]
        calls.append(dict(task_id=t['task_id'],admitted=ad,status=call['assessment']['status'],strict_success=bool(ad and got.min()>=t['q_kw']-1e-7),shortfall_kwh=float(np.maximum(t['q_kw']-got,0).sum()/60) if ad else None,
          ev_offer_statuses=[v['status'] for v in call['assessment'].get('forecast_packets',[])],outcomes=call['outcomes'],second_state_debt=call['assessment'].get('state_used',{}).get('backlog'),service_min_kw=float(got.min()) if ad else None))
    return dict(calls=calls,ev_deadline_ok=bool(max(run['states'][120]['backlog'])<1e-7),terminal_ok=bool(max(run['states'][-1]['backlog'])<1e-7 and abs(run['states'][-1]['energy']-c['initial_kwh'])<1e-7),
      terminal_ev_debt_kwh=sum(run['states'][-1]['backlog']),terminal_battery_debt_kwh=c['initial_kwh']-run['states'][-1]['energy'],hard_shared_violation_kw=float(max(0.,(net-baseline-c['grid_headroom_kw']).max(),(-net).max(),(p[:,:2].sum(axis=1)-b.sum()*(np.arange(H)<D)-c['ev_headroom_kw']).max())))

def run_main():
    integrity();cases=read(RAW/'cases.json');private=np.load(RAW/'executor_private.npz');outputs=[];features=[];tic=time.perf_counter()
    for i,case in enumerate(cases):
        c=case['public'];r=simulate(c,case['arrival_stream'],private['factors'][i],private['ua'][i],private['us'][i],private['pa'][i],private['ps'][i]);outputs.append(dict(id=case['id'],**r));p=np.array(r['paths_kw'])
        for call in r['calls']:
            start=call['task']['start_min'];end=120;n=end-start
            for ev_index,ev in enumerate(c['evs']):
                if call['outcomes'][ev_index]<0:continue
                b=ev['declaration']['b'];q=ev['declaration']['q'];f=extract_event(list(range(0,(n+1)*60,60)),[b]*n,p[start:end,ev_index].tolist(),0,1800,q,recovery_context='shared_state_multiple_events')
                if f['status']!='ok':raise RuntimeError(f)
                features.append(dict(case_id=case['id'],task_id=call['task']['task_id'],resource_id=ev['resource_id'],outcome=call['outcomes'][ev_index],features=f))
        if (i+1)%24==0:print('continuous native B2/B3 simulation',i+1,round(time.perf_counter()-tic,2),flush=True)
    write(BASE/'runs.json',outputs);write(BASE/'observed_B1_features.json',features);write(BASE/'run_receipt.json',dict(cases=len(outputs),seconds=time.perf_counter()-tic,run_sha=sha(BASE/'runs.json'),B1_observed_event_queries=len(features)))
    rows=[dict(id=case['id'],replicate=case['replicate'],headroom=case['headroom'],second_start=case['second_start'],regime=case['regime'],**metrics(case['public'],r)) for case,r in zip(cases,outputs)]
    groups=[]
    for regime in ['nominal','bounded','stress']:
        rs=[v for v in rows if v['regime']==regime];calls=[a for r in rs for a in r['calls']];groups.append(dict(regime=regime,runs=len(rs),admitted=sum(v['admitted'] for v in calls),rejected=sum(not v['admitted'] for v in calls),strict_service_success=sum(v['strict_success'] for v in calls),ev_deadline_ok=sum(v['ev_deadline_ok'] for v in rs),terminal_ok=sum(v['terminal_ok'] for v in rs),max_shared_violation=max(v['hard_shared_violation_kw'] for v in rs)))
    write(BASE/'results.json',dict(groups=groups,records=rows,no_predictive_accuracy_or_optimality_claim=True,committed_kw=None));integrity()

def replay_guard():
    integrity();cases=read(ROOT/'data/B3_feedback_v1_20261028/cases.json');factors=np.load(ROOT/'data/B3_feedback_v1_20261028/evaluation_actual_factors.npz')['factors'];oldruns={v['id']:v for v in read(ROOT/'work/b3_feedback_20261028/runs.json')};outputs=[];tic=time.perf_counter()
    for i,case in enumerate(cases):
        if case['replicate']>=2:continue
        offered=oldruns[case['id']]['offered_kw'];r=replay(case['public'],factors[i],case['second_start'],offered);outputs.append(dict(id=case['id'],public=case['public'],regime=case['regime'],offered=offered,actual_factors=factors[i],**r))
    write(BASE/'guarded_replay.json',outputs);write(BASE/'guarded_replay_receipt.json',dict(cases=len(outputs),seconds=time.perf_counter()-tic,old_three_policies_not_changed=True,regression_not_independent_performance_study=True));print('guarded full replay',len(outputs),flush=True);integrity()

if __name__=='__main__':globals()[sys.argv[1]]()
