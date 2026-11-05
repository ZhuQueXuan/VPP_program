"""Independent numeric/state/authorization checks; no production core calls."""
import numpy as np
from core_io import BASE,ROOT,RAW,read,write,sha,integrity

def check_main():
    cases=read(RAW/'cases.json');runs=read(BASE/'runs.json');priv=np.load(RAW/'executor_private.npz');rows=read(BASE/'results.json')['records'];checks=0;maximum=0.;accepted=offered=debt_blocked=valid_second_ev=0
    for ci,(case,run,row) in enumerate(zip(cases,runs,rows)):
        c=case['public'];p=np.array(run['paths_kw']);cmd=np.array(run['commands_kw']);states=run['states'];g=priv['factors'][ci];b=np.array([v['declaration']['b'] for v in c['evs']]);baseline=b[None]*(np.arange(180)[:,None]<120);pv=np.array(c['pv_forecast_kw']);net=c['fixed_kw']+p.sum(axis=1);ref=c['fixed_kw']+baseline.sum(axis=1)-.6*pv;delivery=ref-net
        assert p.shape==(180,4) and len(states)==181 and (p[:,:2]>=-1e-8).all() and (p[:,:2]<=7.2+1e-8).all();assert np.max(-p[:,2]-pv*g[:,2])<1e-8;assert np.max(abs(p[:,3])-3*g[:,3])<1e-8
        assert min(v['energy'] for v in states)>=.8-1e-8 and max(v['energy'] for v in states)<=c['initial_kwh']+1e-8
        violation=max(0,float((net-ref-c['grid_headroom_kw']).max()),float((-net).max()),float((p[:,:2].sum(axis=1)-baseline.sum(axis=1)-c['ev_headroom_kw']).max()));maximum=max(maximum,violation);assert violation<1e-7;checks+=180*7
        sticky=True
        for t in range(180):
            s=states[t];new=states[t+1];assert s['t']==t and new['t']==t+1;debt=np.maximum(0,np.array(s['backlog'])+(baseline[t]-p[t,:2])/60);energy=s['energy']+(p[t,3]/.95 if p[t,3]<0 else p[t,3]*.95)/60;assert np.allclose(new['backlog'],debt,atol=1e-11,rtol=0) and abs(new['energy']-energy)<1e-11
            sticky=bool(sticky and np.all(g[t]>=np.array([.65,.65,.75,.65])-1e-9));assert new['bounds_valid']==sticky;assert new['site_id']==c['site_id'] and new['resource_ids']==[v['resource_id'] for v in c['evs']];checks+=7
            active=next((v for v in run['calls'] if v['initially_admitted'] and v['task']['start_min']<=t<v['task']['start_min']+30),None)
            if active is None:
                assert np.all(p[t,:2]>=baseline[t]-1e-9);assert np.all((p[t,:2]-baseline[t])/60<=np.array(s['backlog'])+1e-9);assert p[t,3]>=-1e-9
            else:assert np.all(p[t,:2]<=baseline[t]+1e-9) and p[t,3]<=1e-9
            if t>=120:assert abs(p[t,:2]).max()<1e-12
            checks+=5
        for j,call in enumerate(run['calls']):
            task=call['task'];a=task['start_min'];assessment=call['assessment'];ss=states[a];assert assessment['state_used']==ss;eligible=assessment['eligible_ev_offers'];assert len(assessment['forecast_packets'])==2
            for i,packet in enumerate(assessment['forecast_packets']):
                d=packet['input_used'];assert d['T']==120-a and abs(d['E']-(b[i]*(120-a)/60+ss['backlog'][i]))<1e-12;assert packet['resource_id']==c['evs'][i]['resource_id'] and packet['task_id']==task['task_id'];assert packet['actual_backlog_kwh']==ss['backlog'][i]
                if ss['backlog'][i]>1e-8:assert packet['status']=='unavailable';debt_blocked+=1
                if a==90:assert packet['status']!='ok'
                if packet['status']=='ok':
                    if j==1:valid_second_ev+=1
                    paths=np.array([v['event_charging_kw'] for v in packet['dynamic_scenarios']]);prob=np.array([v['conditional_probability'] for v in packet['dynamic_scenarios']]);pa=packet['acceptance_probability'];assert abs(prob.sum()-1)<1e-9;assert np.allclose(assessment['native_forecast_max_reduction_kw'][i],np.max(b[i]-paths,axis=0));assert np.allclose(assessment['native_forecast_expected_reduction_kw'][i],pa*(prob@(b[i]-paths)));assert packet['model_version']=='b2_ev_d118_dynamic_r0p1'
                label=call['outcomes'][i]
                if not call['initially_admitted'] or not eligible[i]:assert label==-1
                else:assert label>=0;offered+=1;accepted+=int(label>0)
                if label>0:assert packet['existing_permission'] is True
                checks+=12
            if call['initially_admitted']:
                # Independently replay each componentwise worst-case reservation witness.
                debt=np.array(ss['backlog'],float);energy=ss['energy'];witness=assessment['gate']['witness'];assert len(witness)==180-a
                maxima=np.array(assessment['native_forecast_max_reduction_kw']);needed=np.zeros(30)
                for w in witness:
                    t=w['t'];power=w['battery_kw']
                    if w['event']:
                        assert np.allclose(w['ev_debt_increase_kw'],maxima[:,t-a]);debt+=np.array(w['ev_debt_increase_kw'])/60;pvextra=(.75-.6)*pv[t] if c['pv']['permission'] and c['pv']['accepted'] else 0.;needed[t-a]=max(0,task['q_kw']-pvextra);assert abs(power+needed[t-a])<1e-10;energy+=power/(.95*60);assert -power<=3*.65+1e-9
                    else:
                        extra=np.array(w['ev_recovery_extra_kw']);assert extra.min()>-1e-9 and (extra<=((7.2-b)*.65)+1e-9).all();assert extra.sum()<=c['ev_headroom_kw']+1e-9 and extra.sum()+power<=c['grid_headroom_kw']+1e-9;assert (extra/60<=debt+1e-9).all();debt=np.maximum(0,debt-extra/60);energy+=power*.95/60;assert 0<=power<=3*.65+1e-9
                    assert .8-1e-8<=energy<=c['initial_kwh']+1e-8
                    if t+1==120:assert max(debt)<1e-7
                    checks+=9
                assert max(debt)<1e-7 and abs(energy-c['initial_kwh'])<1e-7
            observed=delivery[a:a+30];ad=call['initially_admitted'];strict=bool(ad and observed.min()>=task['q_kw']-1e-7);assert row['calls'][j]['strict_success']==strict
            if case['regime']!='stress' and ad:assert strict
            if j==1 and not ss['bounds_valid']:assert not ad
            checks+=4
        evok=max(states[120]['backlog'])<1e-7;terminal=max(states[-1]['backlog'])<1e-7 and abs(states[-1]['energy']-c['initial_kwh'])<1e-7;assert row['ev_deadline_ok']==evok and row['terminal_ok']==terminal
        if case['regime']!='stress':assert evok and terminal
        checks+=3
    # B1 event observations compared directly to event integrals and 90% runs.
    lookup={c['id']:(c,r) for c,r in zip(cases,runs)}
    for record in read(BASE/'observed_B1_features.json'):
        case,run=lookup[record['case_id']];c=case['public'];i=next(i for i,v in enumerate(c['evs']) if v['resource_id']==record['resource_id']);task=next(v['task'] for v in run['calls'] if v['task']['task_id']==record['task_id']);t=task['start_min'];b=c['evs'][i]['declaration']['b'];q=c['evs'][i]['declaration']['q'];red=b-np.array(run['paths_kw'])[t:t+30,i];f=record['features'];assert abs(f['features']['Y']-red.mean()/q)<1e-12;assert f['features']['energy_recovery_time_s'] is None;mask=red>=.9*q;longest=count=0
        for x in mask:count=count+1 if x else 0;longest=max(longest,count)
        assert f['cumulative90_s']==int(mask.sum())*60 and f['continuous90_s']==longest*60;checks+=4
    # Independent result aggregation, no event counts treated as formal accuracy.
    for group in read(BASE/'results.json')['groups']:
        rr=[v for v in rows if v['regime']==group['regime']];calls=[a for v in rr for a in v['calls']]
        assert group['admitted']==sum(a['admitted'] for a in calls) and group['rejected']==sum(not a['admitted'] for a in calls) and group['strict_service_success']==sum(a['strict_success'] for a in calls) and group['terminal_ok']==sum(a['terminal_ok'] for a in rr);checks+=4
    return dict(checks=checks,max_shared_violation_kw=maximum,actual_EV_offers=offered,actual_EV_acceptances=accepted,positive_debt_queries_blocked=debt_blocked,supported_second_EV_queries=valid_second_ev)

def check_replay():
    runs=read(BASE/'guarded_replay.json');checks=0;summary=[]
    for run in runs:
        c=run['public'];p=np.array(run['paths_kw']);g=np.array(run['actual_factors']);ss=run['states'];b=np.array(c['b']);ref=5+b.sum()-.6*np.array(c['pv_forecast_kw']);net=5+p.sum(axis=1)
        assert np.max(net-ref-c['grid_headroom_kw'])<1e-7 and np.max(p[:,:2].sum(axis=1)-b.sum()-c['ev_headroom_kw'])<1e-7 and net.min()>-1e-7
        breach=False
        for t in range(36):
            s=ss[t];new=ss[t+1];debt=np.maximum(0,np.array(s['backlog'])+(b-p[t,:2])/12);energy=s['energy']+(p[t,3]/.95 if p[t,3]<0 else p[t,3]*.95)/12;assert np.allclose(new['backlog'],debt,atol=1e-8,rtol=0) and abs(new['energy']-energy)<1e-8
            assert p[t,:2].min()>-1e-8 and p[t,:2].max()<7.2+1e-8 and .8-1e-8<=new['energy']<=c['initial_kwh']+1e-8;assert -p[t,2]<=c['pv_forecast_kw'][t]*g[t,2]+1e-8 and abs(p[t,3])<=3*g[t,3]+1e-8
            if breach:assert run['statuses'][t]=='outside_declared_envelope_new_admission_blocked'
            breach=bool(breach or np.any(g[t]<np.array([.65,.65,.75,.65])-1e-9));assert new['envelope_breached']==breach;checks+=11
        calls=[]
        for call in run['calls']:
            a,z=call['start'],call['end'];got=ref[a:z]-net[a:z];success=bool(call['initially_admitted'] and 'withdrawn_at' not in call and min(got)>=call['q_kw']-1e-7)
            if ss[a]['envelope_breached']:assert not call['initially_admitted']
            calls.append(dict(admitted=call['initially_admitted'],withdrawn='withdrawn_at' in call,strict_success=success));checks+=1
        summary.append(dict(id=run['id'],regime=run['regime'],calls=calls,terminal_ok=bool(max(ss[-1]['backlog'])<1e-7 and abs(ss[-1]['energy']-c['initial_kwh'])<1e-7)))
    return dict(checks=checks,cases=len(runs),summary=summary)

def main():
    integrity();a=check_main();b=check_replay();write(BASE/'independent_checks.json',dict(status='passed',main=a,legacy_guard_replay=b,checks=a['checks']+b['checks'],real_world_validation=False,old_source_receipts_unchanged=True));print('independent passed',a['checks']+b['checks'],flush=True)
if __name__=='__main__':main()
