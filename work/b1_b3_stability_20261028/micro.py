import copy,itertools
import numpy as np
from core_io import BASE,ROOT,write,read,sha
from generate import build,probabilities
from b1_adapter import extract_event,fit_factor,predict_factor,learn_graph
from b2_adapter import predict_single,predict_remaining
from controller import initial,assess_arrival,admission_witness,validate_state
from legacy_guard import query_previous
from loaders import unique,isolated

def main():
    checks=0;cs,a=build(3,2810200000);case=next(v for v in cs if v['headroom']=='loose' and v['second_start']==60);c=case['public'];tasks=case['arrival_stream'];s=initial(c)
    # Legal output parity and raw0.5 rejection for all three B1 binary operations.
    x=np.array(list(itertools.product([0,1],repeat=4))*25);out=np.c_[x[:,3]*600,x[:,3]*.8];fields=[x[:,i] for i in range(4)];fit=fit_factor(*fields,out,['X','W'],20);assert fit['status']=='ok'
    old=unique('_stable_b1_est','work/b1_ev_factor_chain_20261026/estimators.py');assert fit['model']==old.fit(*fields,out,['X','W'],20);checks+=1
    pred=predict_factor(fit['model'],fields[0],fields[1]);assert np.array_equal(pred['means'],old.predict(fit['model'],fields[0],fields[1]));checks+=1
    graphdata=np.c_[x,x[:,3]];assert learn_graph(graphdata,5)['edges']==unique('_stable_b1_graph','work/b1_ev_factor_chain_20261026/graph.py').learn(graphdata,5)['edges'];checks+=1
    for bad in [.5,2,-1,float('nan'),'0',None]:
        bx=fields[0].astype(object);bx[0]=bad;assert fit_factor(bx,*fields[1:],out,['X','W'])['status']=='unavailable';assert predict_factor(fit['model'],bx,fields[1])['status']=='unavailable';bg=graphdata.astype(object);bg[0,0]=bad;assert learn_graph(bg)['status']=='unavailable';checks+=3
    ref=[3.]*120;power=[1.5]*30+[3.5]*90;v=extract_event(list(range(0,7260,60)),ref,power,0,1800,1.5)
    native=unique('_stable_b1_f0','work/b1_research_20261021/features.py').extract(list(range(0,7260,60)),ref,power,0,1800,1.5,dwell_samples=1);assert v['features']==native and v['cumulative90_s']==1800 and v['continuous90_s']==1800;checks+=1
    multi=extract_event(list(range(0,7260,60)),ref,power,0,1800,1.5,recovery_context='shared_state_multiple_events');assert multi['features']['energy_recovery_time_s'] is None;checks+=1
    p=copy.deepcopy(power);p[0]=None;assert extract_event(list(range(0,7260,60)),ref,p,0,1800,1.5)['features']['Y'] is None;checks+=1
    for badq in [True,'1.5',0,float('nan')]:assert extract_event(list(range(0,7260,60)),ref,power,0,1800,badq)['status']=='unavailable';checks+=1
    r=predict_single(c['evs'][0]['declaration']);assert r['status']=='ok';checks+=1
    assert predict_single(c['evs'][0]['declaration'],'unknown')['status']=='unavailable';checks+=1
    for perm in ['0','1',None,.5]:
        d=copy.deepcopy(c['evs'][0]['declaration']);d['permission']=perm;assert predict_single(d)['status']=='unavailable';checks+=1
    d=copy.deepcopy(c['evs'][0]['declaration']);d['permission']=False;assert predict_single(d)['status']=='blocked';checks+=1
    q=predict_remaining(c['evs'][0]['declaration'],dict(remaining_min=60,backlog_kwh=.2),'ev','t','o',tasks[0]['known_at']);assert q['status']=='unavailable' and abs(q['remaining_required_ac_kwh']-(c['evs'][0]['declaration']['b']+.2))<1e-12;checks+=1
    trial=assess_arrival(c,s,[],tasks[0]);assert trial['status']=='admitted_under_declared_envelope',trial;checks+=1
    for kind in ['state_id','state_clock','state_nan','permission','future','offer','taskid','deadline','overlap','mode_type']:
        cc=copy.deepcopy(c);ss=copy.deepcopy(s);task=copy.deepcopy(tasks[0]);previous=[]
        if kind=='state_id':ss['site_id']='other'
        if kind=='state_clock':ss['t']=.5
        if kind=='state_nan':ss['backlog'][0]=float('nan')
        if kind=='permission':task['permission_records'][0]['granted']='0'
        if kind=='future':task['known_at']='2026-10-28T01:00:00+08:00'
        if kind=='offer':task['permission_records'][0]['resource_id']='other'
        if kind=='taskid':task['task_id']=''
        if kind=='deadline':cc['ev_deadline_min']=180
        if kind=='overlap':previous=[dict(task,task_id='other')]
        if kind=='mode_type':ss['bounds_valid']='True'
        assert assess_arrival(cc,ss,previous,task)['status']=='unavailable',kind;checks+=1
    ss=copy.deepcopy(s);ss['bounds_valid']=False;assert assess_arrival(c,ss,[],tasks[0])['status']=='rejected_domain';checks+=1
    # D120 legal-query parity and unavailable malformed states, with no old receipt writes.
    oldcase=read(ROOT/'data/B3_feedback_v1_20261028/cases.json')[0]['public'];oldstate=dict(t=0,backlog=[0.,0.],energy=oldcase['initial_kwh']);good=query_previous(oldcase,oldstate)
    with isolated('bridge') as old:assert good==old.query_b3(oldcase,oldstate)
    checks+=1
    for v in [.5,True,'0',-1,36]:
        st=dict(oldstate,t=v);assert query_previous(oldcase,st)['status']=='unavailable';checks+=1
    overlap=[dict(start=0,end=6,q_kw=2.,admitted=True),dict(start=0,end=6,q_kw=2.,admitted=True)];assert query_previous(oldcase,oldstate,overlap)['status']=='unavailable';checks+=1
    st=dict(oldstate,envelope_breached=True);assert query_previous(oldcase,st,[],dict(start=0,end=6,q_kw=1.))['status']=='outside_declared_envelope_new_admission_blocked';checks+=1
    write(BASE/'micro_checks_after_contract.json',dict(status='passed',checks=checks,development_seed=2810200003,main_panel_not_generated=True));print('micro passed',checks,flush=True)

if __name__=='__main__':main()
