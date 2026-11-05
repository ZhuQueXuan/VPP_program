"""Harden D120/D122 remaining-capacity entry without changing frozen solvers."""
import copy,sys
import numpy as np
from contracts import number,integer,failed
from loaders import isolated
LOW=np.array([.65,.65,.75,.65])

def query_previous(public,state=None,announced_calls=None,new_call=None,mode='envelope'):
    try:
        if mode not in ['nominal','envelope','persistence']:raise ValueError('unknown mode')
        public=copy.deepcopy(public);state=copy.deepcopy(state) if state is not None else dict(t=0,backlog=[0.,0.],energy=public['initial_kwh'])
        integer(state['t'],'clock',0,35);number(state['energy'],'energy',.8-1e-7,public['initial_kwh']+1e-7)
        for name,v,n,lo,hi in [('b',public['b'],2,0,7.2),('backlog',state['backlog'],2,0,None),('PV',public['pv_forecast_kw'],36,0,None),('last_factors',state.get('last_factors',[1.,1.,1.,1.]),4,0,1)]:
            if not isinstance(v,list) or len(v)!=n:raise ValueError(name+' wrong length')
            for x in v:number(x,name,lo,hi)
        for k in ['grid_headroom_kw','ev_headroom_kw']:number(public[k],k,0)
        number(public['initial_kwh'],'initial_kwh',.8,7.2)
        if len(public['agents'])!=4 or any(type(v.get(k)) is not bool for v in public['agents'] for k in ['permission','accepted']):raise ValueError('explicit actual permission/acceptance required')
        calls=copy.deepcopy(announced_calls if announced_calls is not None else [])
        with isolated('bridge') as old:
            # Original D122 fixes all-list overlap/type checks. Do not bypass them.
            oldmod=sys.modules['guards'];oldmod.validate_calls(calls,new_call)
            if any(v['start']>state['t'] for v in calls):raise ValueError('unreleased future task in announced list')
            if new_call is not None and new_call['start']!=state['t']:raise ValueError('new task must arrive now')
            if 'envelope_breached' in state and type(state['envelope_breached']) is not bool:raise ValueError('envelope_breached requires boolean')
            observed=np.array(state.get('last_factors',[1.,1.,1.,1.]));breach=bool(state.get('envelope_breached',False) or np.any(observed<LOW-1e-9))
            if breach:
                recovery=old.query_b3(public,state,calls,None,mode='persistence')
                return dict(status='outside_declared_envelope_new_admission_blocked',new_task_status='rejected_domain' if new_call is not None else None,capacity_bound_valid=False,existing_service_recovery_assessment=recovery,state_used=state,committed_kw=None)
            return old.query_b3(public,state,calls,new_call,mode)
    except (ValueError,TypeError,KeyError,IndexError,OverflowError) as e:return failed(e)

def replay(public,factors,second_start,offered):
    """Fourth guarded policy replay; never alters the three old frozen policies."""
    with isolated('feedback') as old:
        m=sys.modules['model'];s=m.initial(public);s['envelope_breached']=False;calls=[];states=[copy.deepcopy(s)];paths=[];commands=[];events=[];statuses=[]
        for t in range(36):
            task=None
            if t in [0,second_start]:
                j=0 if t==0 else 1;task=dict(task_id=f'guarded-{j}',start=t,end=t+6,q_kw=float(offered[j]),admitted=True)
            r=query_previous(public,s,calls,task)
            if task is not None:
                task['initially_admitted']=r['status']=='admitted_under_declared_model';task['admitted']=task['initially_admitted'];calls.append(task)
            # On a contradicted envelope, withdraw active service and explicitly recover.
            if r['status'] not in ['admitted_under_declared_model','feasible_under_declared_model']:
                for call in calls:
                    if call['admitted'] and call['end']>t:call['admitted']=False;call['withdrawn_at']=t
                r2=query_previous(public,s,calls,None)
            else:r2=r
            def plan(v):
                if 'plan' in v and v['plan'].get('paths_kw') is not None:return v['plan']
                nested=v.get('existing_service_recovery_assessment')
                return plan(nested) if isinstance(nested,dict) else None
            p=plan(r2)
            if p is None:
                p=m.solve(public,s,[],mode='persistence',soft=True)
                if p.get('paths_kw') is None:raise RuntimeError('no physical best-effort recovery plan')
            cmd=np.array(p['paths_kw'])[:,0];event=any(v['admitted'] and v['start']<=t<v['end'] for v in calls);actual,new=m.execute(public,s,cmd,factors[t],event)
            new['envelope_breached']=bool(s['envelope_breached'] or np.any(factors[t]<LOW-1e-9));s=new;states.append(copy.deepcopy(s));paths.append(actual);commands.append(cmd.tolist());events.append(event);statuses.append(r['status'])
    return dict(calls=calls,states=states,paths_kw=paths,commands_kw=commands,event=events,statuses=statuses,committed_kw=None)
