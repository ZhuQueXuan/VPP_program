"""Finite causal-prefix, native forecast-consumption and import-isolation checks."""
import copy
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from core_io import BASE,RAW,read,write,integrity
from controller import simulate,forecast_components,assess_arrival,initial
from b2_adapter import predict_single
from b1_adapter import extract_event

def main():
    integrity();cases=read(RAW/'cases.json');a=np.load(RAW/'executor_private.npz');checks=0
    for rep in range(20):
        i=next(i for i,c in enumerate(cases) if c['replicate']==rep and c['headroom']=='loose' and c['second_start']==60 and c['regime']=='bounded');case=cases[i];c=case['public'];stream=case['arrival_stream'];args=[a[k][i].copy() for k in ['factors','ua','us','pa','ps']]
        r=simulate(c,stream,*args)
        changed=[v.copy() for v in args];changed[0][15:]=[.12,.12,.62,.12];r2=simulate(c,stream,*changed)
        assert r['commands_kw'][:15]==r2['commands_kw'][:15] and r['states'][:16]==r2['states'][:16];checks+=2
        future=copy.deepcopy(stream);future[1]['q_kw']+=.2;r3=simulate(c,future,*args);assert r['commands_kw'][:60]==r3['commands_kw'][:60] and r['states'][:61]==r3['states'][:61];checks+=2
        # State0 and state3 share the first15min response; controller must not see later exit.
        changed=[v.copy() for v in args];changed[1][0,0]=0.;changed[2][0,0]=changed[4][0,0,0]/2;r4=simulate(c,stream,*changed)
        changed[2][0,0]=changed[4][0,0,:3].sum()+changed[4][0,0,3]/2;r5=simulate(c,stream,*changed)
        assert r4['commands_kw'][:15]==r5['commands_kw'][:15] and r4['states'][:16]==r5['states'][:16];checks+=2
    c=cases[13]['public'];stream=cases[13]['arrival_stream'];ss=initial(c);r=assess_arrival(c,ss,[],stream[0]);pack=r['forecast_packets'];native=copy.deepcopy(pack)
    # Alter valid probabilities coherently: forecast expectation must change, physical envelope must not.
    idx=next((i for i,p in enumerate(native) if p['status']=='ok'),None)
    if idx is not None:
        p=native[idx];weights=np.array([.6,.1,.1,.1,.1]);paths=np.array([v['event_charging_kw'] for v in p['dynamic_scenarios']]);b=c['evs'][idx]['declaration']['b']
        for scene,w in zip(p['dynamic_scenarios'],weights):scene['conditional_probability']=float(w)
        p['expected_event_charging_kw']=(b-p['acceptance_probability']*(weights@(b-paths))).tolist();maximum,mean=forecast_components(c,native);oldmax,oldmean=forecast_components(c,pack);assert np.allclose(maximum,oldmax) and not np.allclose(mean,oldmean);checks+=2
    decl=copy.deepcopy(c['evs'][0]['declaration']);one=predict_single(decl);original=copy.deepcopy(one);one['dynamic_scenarios'].clear();assert predict_single(decl)==original;checks+=1
    def query(i):
        if i%2:return predict_single(decl)['model_version']
        return extract_event(list(range(0,7260,60)),[3.]*120,[3.]*120,0,1800,1.5)['features']['Y']
    with ThreadPoolExecutor(max_workers=4) as pool:out=list(pool.map(query,range(24)))
    assert out==[0. if i%2==0 else 'b2_ev_d118_dynamic_r0p1' for i in range(24)];checks+=24
    write(BASE/'prefix_checks.json',dict(status='passed',checks=checks,seed_blocks=20,prefix_scenarios=60,parallel_queries=24,future_factors_tasks_and_exit_not_used=True,native_probability_consumption_checked=idx is not None));print('prefix/import passed',checks,flush=True);integrity()
if __name__=='__main__':main()
