"""Three-hour site, EV deadline120; remaining-time B2 queries and causal dispatch.

No B2 extrapolation to180min. B3 owns explicitly authorized early recovery;
B2 postpower is retained as a forecast/witness, not a fixed actuator command.
"""
import copy,json,hashlib
from datetime import timedelta
import numpy as np
from contracts import number,integer,boolean,identity,stamp,failed,VERSION
from b2_adapter import predict_remaining
H=180;D=120;DT=1/60;ETA=.95;LOW=np.array([.65,.65,.75,.65])

def validate_public(c):
    if c.get('evidence')!='hypothetical_ac' or c.get('units')!='AC_kW_kWh_min':raise ValueError('explicit AC hypothetical evidence/units required')
    identity(c['site_id'],'site_id');a=stamp(c['start']);cut=stamp(c['information_cutoff'])
    if cut>a:raise ValueError('future information cutoff')
    if c['ev_deadline_min']!=D or type(c['ev_deadline_min']) is not int or c['horizon_min']!=H or type(c['horizon_min']) is not int:raise ValueError('site180/EV120 family required')
    if not isinstance(c['evs'],list) or len(c['evs'])!=2:raise ValueError('two EVs required')
    ids=[]
    for ev in c['evs']:
        ids.append(identity(ev['resource_id'],'resource_id'));number(ev['declaration']['b'],'b',.6,7);boolean(ev['declaration']['permission'],'permission')
        if ev['recovery_control_authorized'] is not True:raise ValueError('explicit task-bound early charging recovery authority required')
    for actor in ['pv','battery']:
        ids.append(identity(c[actor]['resource_id'],'resource_id'))
        for field in ['permission','accepted']:
            if type(c[actor][field]) is not bool:raise ValueError('actual ancillary permission/acceptance booleans required')
    if len(set(ids))!=4:raise ValueError('resource IDs must be unique')
    for field in ['grid_headroom_kw','ev_headroom_kw','fixed_kw']:number(c[field],field,0)
    number(c['initial_kwh'],'initial_kwh',.8,7.2)
    if not isinstance(c['pv_forecast_kw'],list) or len(c['pv_forecast_kw'])!=H:raise ValueError('180 PV minutes required')
    for p in c['pv_forecast_kw']:number(p,'PV',0)

def signature(c):return hashlib.sha256(json.dumps(c,sort_keys=True,allow_nan=False).encode()).hexdigest()
def initial(c):return dict(t=0,backlog=[0.,0.],energy=c['initial_kwh'],bounds_valid=True,last_factors=[1.,1.,1.,1.],site_id=c['site_id'],resource_ids=[v['resource_id'] for v in c['evs']],declaration_sha=signature(c))

def validate_state(c,s):
    validate_public(c);integer(s['t'],'clock',0,H-1)
    if s['site_id']!=c['site_id'] or s['resource_ids']!=[v['resource_id'] for v in c['evs']] or s['declaration_sha']!=signature(c):raise ValueError('state/site/resource/declaration binding mismatch')
    if not isinstance(s['backlog'],list) or len(s['backlog'])!=2:raise ValueError('two measured debts required')
    for b in s['backlog']:number(b,'backlog',0)
    number(s['energy'],'energy',.8-1e-8,c['initial_kwh']+1e-8)
    if type(s['bounds_valid']) is not bool:raise ValueError('explicit envelope validity required')
    if not isinstance(s['last_factors'],list) or len(s['last_factors'])!=4:raise ValueError('four prior factors required')
    for x in s['last_factors']:number(x,'last factor',0,1)

def validate_task(c,s,previous,task):
    validate_state(c,s)
    if not isinstance(previous,list) or len(previous)>=2:raise ValueError('two-call family only')
    for call in previous+[task]:
        identity(call['task_id'],'task_id');integer(call['start_min'],'task start',0,H-30);number(call['q_kw'],'q',1e-12)
        if call['duration_min']!=30 or type(call['duration_min']) is not int:raise ValueError('30min tasks required')
    if task['start_min']!=s['t']:raise ValueError('new task must arrive now')
    if any(v['start_min']>s['t'] for v in previous):raise ValueError('future task must not be in released task history')
    if len(set(v['task_id'] for v in previous+[task]))!=len(previous)+1:raise ValueError('duplicate task ID')
    allcalls=previous+[task]
    for i,a in enumerate(allcalls):
        for b in allcalls[i+1:]:
            if a['start_min']<b['start_min']+30 and b['start_min']<a['start_min']+30:raise ValueError('overlapping tasks unsupported')
    now=stamp(c['start'])+timedelta(minutes=s['t'])
    if stamp(task['known_at'])!=now:raise ValueError('task known_at must bind current arrival')
    records=task['permission_records']
    if not isinstance(records,list) or len(records)!=2:raise ValueError('two offer-bound permission records required')
    ids=[]
    for ev,record in zip(c['evs'],records):
        ids.append(identity(record['offer_id'],'offer_id'))
        if record['resource_id']!=ev['resource_id'] or record['task_id']!=task['task_id'] or stamp(record['known_at'])>now:raise ValueError('permission record binding/time mismatch')
        if boolean(record['granted'],'granted')!=boolean(ev['declaration']['permission'],'permission'):raise ValueError('permission record/declaration mismatch')
    if len(set(ids))!=2:raise ValueError('distinct offer IDs required')

def allocate(debt,b,g,grid,evhead):
    cap=np.minimum(np.maximum(debt,0)/DT,(7.2-b)*g[:2]);total=min(grid,evhead,float(cap.sum()))
    if total<=0:return np.zeros(2)
    # Same-deadline, debt-weighted water filling; no claim of optimal effort.
    out=np.zeros(2);active=np.ones(2,bool)
    for _ in range(3):
        left=total-out.sum()
        if left<=1e-12 or not active.any():break
        weight=np.where(active,debt,0.);weight=weight/weight.sum() if weight.sum()>0 else active/active.sum()
        add=np.minimum(cap-out,left*weight);out+=add;active=(cap-out)>1e-12
    return out

def recovery_command(c,s,g,grid=None):
    b=np.array([e['declaration']['b'] for e in c['evs']]);grid=c['grid_headroom_kw'] if grid is None else grid
    extra=allocate(np.array(s['backlog']),b,g,max(0,grid),c['ev_headroom_kw']) if s['t']<D else np.zeros(2)
    charge=min(3*g[3],max(0,c['initial_kwh']-s['energy'])/(DT*ETA),max(0,grid-extra.sum())) if c['battery']['permission'] and c['battery']['accepted'] else 0.
    return extra,charge

def forecast_components(c,packets):
    maximum=[];expected=[]
    for ev,p in zip(c['evs'],packets):
        if p['status']!='ok':maximum.append(np.zeros(30));expected.append(np.zeros(30));continue
        scenes=p['dynamic_scenarios'];b=ev['declaration']['b'];pa=p['acceptance_probability']
        paths=np.array([v['event_charging_kw'] for v in scenes]);probs=np.array([v['conditional_probability'] for v in scenes])
        if p['default_execution']!='dynamic' or paths.shape!=(5,30) or not np.isfinite(paths).all() or paths.min()<-1e-8 or paths.max()>7.2+1e-8 or np.any(paths>b+1e-8):raise ValueError('native B2 dynamic trajectory family invalid')
        if not np.isfinite(probs).all() or probs.min()<0 or abs(probs.sum()-1)>1e-9 or not 0<=pa<=1:raise ValueError('native B2 probability invalid')
        reduction=b-paths;mean=pa*(probs@reduction)
        if not np.allclose(b-mean,p['expected_event_charging_kw'],atol=1e-9,rtol=0):raise ValueError('B2 mean/scenario mismatch')
        maximum.append(reduction.max(axis=0));expected.append(mean)
    return np.array(maximum),np.array(expected)

def admission_witness(c,s,task,eligible,forecast_maximum=None):
    if not s['bounds_valid'] or np.any(np.array(s['last_factors'])<LOW-1e-9):return dict(status='rejected_domain',reason='observed lower-envelope breach; new admission blocked')
    sim=copy.deepcopy(s);paths=[];b=np.array([v['declaration']['b'] for v in c['evs']]);qs=np.array([v['declaration']['q'] for v in c['evs']])*eligible
    pv_on=c['pv']['permission'] and c['pv']['accepted'];bat_on=c['battery']['permission'] and c['battery']['accepted']
    for t in range(s['t'],H):
        sim['t']=t;pv=c['pv_forecast_kw'][t];refpv=.6*pv;event=t<task['start_min']+30
        if event:
            worst_ev=(forecast_maximum[:,t-task['start_min']] if forecast_maximum is not None else qs) if t<D else np.zeros(2);pvextra=max(0,(LOW[2]-.6)*pv) if pv_on else 0.;need=max(0,task['q_kw']-pvextra)
            if need>3*LOW[3]+1e-9 or (need>1e-9 and not bat_on):return dict(status='rejected_under_fixed_policy',reason='no-EV-response service reserve exceeds declared source/storage limits')
            sim['backlog']=(np.array(sim['backlog'])+worst_ev*DT).tolist();sim['energy']-=need*DT/ETA
            # Two separate worst cases: full EV creates maximal debt; zero EV needs maximal storage.
            paths.append(dict(t=t,event=True,ev_debt_increase_kw=worst_ev.tolist(),battery_kw=-need,pv_kw=-refpv-pvextra))
        else:
            extra,charge=recovery_command(c,sim,LOW);sim['backlog']=np.maximum(0,np.array(sim['backlog'])-extra*DT).tolist();sim['energy']+=charge*ETA*DT
            paths.append(dict(t=t,event=False,ev_recovery_extra_kw=extra.tolist(),battery_kw=charge,pv_kw=-refpv))
        if sim['energy']<.8-1e-8:return dict(status='rejected_under_fixed_policy',reason='worst-case source/storage energy reserve exhausted')
        if t+1==D and max(sim['backlog'])>1e-7:return dict(status='rejected_under_fixed_policy',reason='shared EV recovery cannot meet original120min deadline under fixed policy',remaining_backlog=sim['backlog'])
    if max(sim['backlog'])>1e-7 or abs(sim['energy']-c['initial_kwh'])>1e-7:return dict(status='rejected_under_fixed_policy',reason='site terminal recovery reserve insufficient')
    return dict(status='admitted_under_declared_envelope',witness=paths,witness_type='componentwise dominating debt/storage reserve, not simultaneous optimal trajectory',committed_kw=None)

def assess_arrival(c,s,previous,task):
    try:
        validate_task(c,s,previous,task);packets=[]
        for ev,record in zip(c['evs'],task['permission_records']):
            p=predict_remaining(ev['declaration'],dict(remaining_min=D-s['t'],backlog_kwh=s['backlog'][len(packets)]),ev['resource_id'],task['task_id'],record['offer_id'],task['known_at']);packets.append(p)
        eligible=np.array([p['status']=='ok' for p in packets]);maximum,expected=forecast_components(c,packets);gate=admission_witness(c,s,task,eligible,maximum)
        return dict(status=gate['status'],reason=gate.get('reason'),forecast_packets=packets,eligible_ev_offers=eligible.tolist(),gate=gate,state_used=copy.deepcopy(s),committed_kw=None,
          interface_version=VERSION,result_type='joint_admission_with_native_B2_forecast',site_id=c['site_id'],task_id=task['task_id'],information_cutoff=task['known_at'],units=c['units'],evidence=c['evidence'],
          native_forecast_max_reduction_kw=maximum.tolist(),native_forecast_expected_reduction_kw=expected.tolist(),forecast_sum_expected_delivery_kwh=float(expected.sum()/60),forecast_is_control=False,
          conditional_model_scope='site180min with EV original deadline120 and remaining B2 T120/60 only; debt/T30/180 are not extrapolated')
    except (ValueError,TypeError,KeyError,IndexError,OverflowError) as e:return failed(e)

def dispatch(c,s,task,measured_ev_kw,pv_available_kw):
    """Current EV/PV observations; only last factors for unobserved current battery."""
    b=np.array([v['declaration']['b'] for v in c['evs']])*(s['t']<D);ev=np.array(measured_ev_kw);pv=c['pv_forecast_kw'][s['t']];refpv=.6*pv
    event=task is not None;g=LOW if s['bounds_valid'] else np.array(s['last_factors']);pv_on=c['pv']['permission'] and c['pv']['accepted'];bat_on=c['battery']['permission'] and c['battery']['accepted']
    if event:
        need=task['q_kw']-float((b-ev).sum());generation=min(pv_available_kw,refpv+max(0,need)) if pv_on else min(pv_available_kw,refpv);need=max(0,need-(generation-refpv));battery=-min(need,3*g[3],max(0,s['energy']-.8)*ETA/DT) if bat_on else 0.
        return np.r_[ev,-generation,battery]
    generation=min(pv_available_kw,refpv);grid=max(0,c['grid_headroom_kw']-(refpv-generation));extra,charge=recovery_command(c,s,g,grid);return np.r_[b+extra,-generation,charge]

def execute(c,s,command,g,event):
    p=np.array(command,float);g=np.asarray(g);b=np.array([v['declaration']['b'] for v in c['evs']])*(s['t']<D)
    if not event:
        if s['t']<D:p[:2]=b+np.minimum(np.maximum(0,p[:2]-b),np.minimum((7.2-b)*g[:2],np.array(s['backlog'])/DT))
        else:p[:2]=0.
    if p[3]<0:p[3]=-min(-p[3],3*g[3],max(0,s['energy']-.8)*ETA/DT)
    else:p[3]=min(p[3],3*g[3],max(0,c['initial_kwh']-s['energy'])/(ETA*DT))
    new=dict(t=s['t']+1,backlog=np.maximum(0,np.array(s['backlog'])+(b-p[:2])*DT).tolist(),energy=float(s['energy']+(p[3]/ETA if p[3]<0 else p[3]*ETA)*DT),bounds_valid=bool(s['bounds_valid'] and np.all(g>=LOW-1e-9)),last_factors=g.tolist(),site_id=s['site_id'],resource_ids=list(s['resource_ids']),declaration_sha=s['declaration_sha'])
    return p,new

def templates():
    a=np.zeros((5,30));a[0]=1;a[1,2:]=1;a[2,5:]=1;a[3,:15]=1;a[4]=.7;return a

def simulate(c,arrivals,factors,ua,us,choice_prob,state_prob):
    """Executor probabilities/realizations are private and never reach forecast/admission."""
    validate_public(c);state=initial(c);states=[copy.deepcopy(state)];log=[];calls=[];paths=[];commands=[];b=np.array([e['declaration']['b'] for e in c['evs']]);active=None;outcome=None
    for t in range(H):
        if active is not None and t==active['start_min']+30:active=None;outcome=None
        arrived=next(((j,v) for j,v in enumerate(arrivals) if v['start_min']==t),None)
        if arrived is not None:
            j,task=arrived;assessment=assess_arrival(c,state,[v['task'] for v in calls],task);admitted=assessment['status']=='admitted_under_declared_envelope';labels=np.full(2,-1,int)
            if admitted:
                for i,p in enumerate(assessment['forecast_packets']):
                    if p['status']=='ok':labels[i]=min(4,int(np.searchsorted(np.cumsum(state_prob[j,i]),us[j,i])))+1 if ua[j,i]<choice_prob[j,i] else 0
                active=task;outcome=labels
            calls.append(dict(task=task,assessment=assessment,initially_admitted=admitted,outcomes=labels.tolist()))
        ev=b.copy() if t<D else np.zeros(2)
        if active is not None and t<D:
            for i,label in enumerate(outcome):
                if label>0:ev[i]-=min(c['evs'][i]['declaration']['q']*templates()[label-1,t-active['start_min']],b[i]*factors[t,i])
        available=c['pv_forecast_kw'][t]*factors[t,2];command=dispatch(c,state,active,ev,available);p,new=execute(c,state,command,factors[t],active is not None)
        paths.append(p.tolist());commands.append(command.tolist());log.append(dict(t=t,active_task=active['task_id'] if active else None,announced_tasks=len(calls),observed_ev_kw=ev.tolist(),observed_pv_available_kw=float(available),command_kw=command.tolist(),bounds_valid_before=state['bounds_valid']));state=new;states.append(copy.deepcopy(state))
    return dict(calls=calls,states=states,paths_kw=paths,commands_kw=commands,log=log,committed_kw=None)
