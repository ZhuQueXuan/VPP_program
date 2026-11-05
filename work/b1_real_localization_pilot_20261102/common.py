import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
from pathlib import Path
import json,hashlib,importlib.util,sys,datetime
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DATA=ROOT/'data/ACN_real_user_benchmark_v1_20261102';VIEW=DATA/'prepared/observed_localization_pilot_v1_20261102'
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.process._cpop import fit_cases
from b1_algorithm.api import _default_runtime_config
def native(v):
    if isinstance(v,np.ndarray):return v.tolist()
    if isinstance(v,np.generic):return v.item()
    if isinstance(v,dict):return {k:native(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [native(x) for x in v]
    return v
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(name,value):
    p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(native(value),f,ensure_ascii=False,allow_nan=False,indent=2)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def load(role):
    assert role in ['training','validation']
    rows=read(VIEW/(role+'.json'));assert all(r['split']==role for r in rows)
    return rows
def arrays(r):
    d=r['model_input'];t=np.array(d['relative_seconds'],float);p=np.array(d['power_kw'],float);i=np.array(d['current_a'],float);pilot=np.array(d['pilot_a'],float)
    if not all(np.isfinite(v).all() for v in [t,p,i,pilot]) or len(t)<3 or np.any(np.diff(t)<=0):return None
    zeros=np.flatnonzero(t==0)
    if len(zeros)!=1 or zeros[0]<1:return None
    return dict(t=t,p=p,i=i,pilot=pilot,j0=int(zeros[0]))
def scale(t,y,floor):
    use=(t>=-60)&(t<=-12);dt=np.diff(t);z=np.diff(y);mask=use[:-1]&use[1:]&(dt>0)&(dt<=15)
    vals=z[mask]
    return float(max(floor,1.4826*np.median(abs(vals-np.median(vals)))/np.sqrt(2))) if len(vals) else float(floor)
def context(a):
    t=a['t'];j=a['j0'];pilot=a['pilot'];old=pilot[j-1];direction=float(np.sign(pilot[j]-old))
    start=j-1
    while start>0 and t[start-1]>=-24 and abs(pilot[start-1]-old)<.25:start-=1
    return dict(direction=direction,pre=np.arange(start,j),sigma_p=scale(t,a['p'],.005),sigma_i=scale(t,a['i'],.05),search=np.flatnonzero((np.arange(len(t))>=j-1)&(t<=24)),prior_pilot=float(old))
def estimate(a,curve,k=3,current=False):
    if a is None:return dict(status='unavailable',detected=False,onset_seconds=None,recovery_seconds=None,reason='nonfinite_or_nonincreasing_native_observations')
    c=context(a);t=a['t'];direction=c['direction']
    if direction==0:return dict(status='not_applicable',detected=False,onset_seconds=None,recovery_seconds=None,reason='no_limit_edge')
    curve=np.asarray(curve,float)
    if curve.shape!=t.shape or not np.isfinite(curve).all():return dict(status='unavailable',detected=False,onset_seconds=None,recovery_seconds=None,reason='native_fit_unavailable')
    base=float(np.median(curve[c['pre']]));base_i=float(np.median(a['i'][c['pre']]))
    threshold=max(.03,k*c['sigma_p']);departure=direction*(curve-base)
    condition=departure>=threshold
    if current:condition &= direction*(a['i']-base_i)>=max(.15,k*c['sigma_i'])
    hits=[j for j in c['search'] if condition[j]]
    if not hits:return dict(status='ok',detected=False,onset_seconds=None,recovery_seconds=None,reference_recorded_power_kw=base,threshold_kw=threshold,reason='no_resolved_local_departure')
    first=hits[0];back=abs(curve-base)<=max(.03,2*c['sigma_p'])
    if current:back &= abs(a['i']-base_i)<=max(.2,2*c['sigma_i'])
    returns=np.flatnonzero(back&(np.arange(len(t))>first))
    return dict(status='ok',detected=True,onset_seconds=float(t[first]),recovery_seconds=float(t[returns[0]]) if len(returns) else None,reference_recorded_power_kw=base,threshold_kw=threshold,reason='native_point_evidence',onset_raw_row_position=int(first))
def candidate(a,cp,k):
    original=estimate(a,cp)
    if a is None:return original
    raw=estimate(a,a['p'],k=k,current=True)
    if raw['detected']:
        return dict(raw,reason='raw_current_power_localization_with_cpop_fallback',cpop_detected=original['detected'],raw_rescued=not original['detected'])
    return dict(original,reason='unchanged_cpop_fallback',cpop_detected=original['detected'],raw_rescued=False)
def command(a):
    if a is None:return dict(status='unavailable',detected=False,onset_seconds=None,recovery_seconds=None)
    c=context(a)
    if c['direction']==0:return dict(status='not_applicable',detected=False,onset_seconds=None,recovery_seconds=None)
    js=np.flatnonzero((a['t']>0)&(abs(a['pilot']-c['prior_pilot'])<.25))
    return dict(status='ok',detected=True,onset_seconds=0.,recovery_seconds=float(a['t'][js[0]]) if len(js) else None)
def fit_native(rows,role):
    spec=importlib.util.spec_from_file_location('existing_baseline_helpers',ROOT/'work/b1_cpop_fine_v3_20261031/common.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h);h.HERE=HERE
    directory=f'native/{role}'
    if (HERE/directory).exists():
        attempt=2
        while (HERE/f'native/{role}_attempt{attempt:02d}').exists():attempt+=1
        directory=f'native/{role}_attempt{attempt:02d}'
    # Create the shared parent once; old helper creates distinct chunk children
    # concurrently and Windows may reject concurrent creation of their parents.
    (HERE/directory/'labs').mkdir(parents=True,exist_ok=False)
    cases=[];vectors=[];ids=[];metadata=[]
    for r in rows:
        a=arrays(r)
        if a is None:continue
        n=len(a['p']);j=len(ids);ids.append(r['event_id']);x=np.arange(1,n+1,dtype=float)
        cases.append(dict(case_id=j,starts=x-.5,ends=x+.5,y=a['p'],sigma=context(a)['sigma_p'],train=np.ones(n,bool)));vectors.append(a['p'])
    cp,cp_meta=h.cp_batch(cases,f'{directory}/cpop')
    labs,labs_meta=h.labs_batch(vectors,f'{directory}/labs')
    outputs={}
    for j,event_id in enumerate(ids):
        outputs[event_id]={}
        for name,result in [('cpop',cp[j]),('labs',labs[j])]:
            outputs[event_id][name]=dict(result)
            if result['status']=='ok':assert len(result['prediction'])==len(vectors[j])
    save(f'{role}/native_curves.json',outputs);save(f'{role}/native_receipt.json',dict(cpop=cp_meta,labs=labs_meta,index_based_common_input=True,role=role))
    return outputs
def predictions(rows,curves,k):
    result=[]
    for r in rows:
        a=arrays(r);entry=curves.get(r['event_id'],{})
        cp=entry.get('cpop',{});lb=entry.get('labs',{})
        cp_curve=cp.get('prediction',np.full(len(a['p']),np.nan) if a is not None else [])
        lb_curve=lb.get('prediction',np.full(len(a['p']),np.nan) if a is not None else [])
        out=dict(cpop=estimate(a,cp_curve),labs=estimate(a,lb_curve),candidate=candidate(a,cp_curve,k),raw_only=estimate(a,a['p'],k=k,current=True) if a is not None else estimate(None,[]),command_only=command(a))
        result.append(dict(event_id=r['event_id'],split=r['split'],methods=out))
    return result
def timing(value,target):
    if value is None:return dict(capped_interval_error_seconds=180.,capped_first_observed_error_seconds=180.,missing=True)
    lo,hi=target;distance=max(lo-value,value-hi,0.)
    return dict(capped_interval_error_seconds=float(min(180.,distance)),capped_first_observed_error_seconds=float(min(180.,abs(value-hi))),missing=False)
def score(rows,pred):
    scored={};no_recovery={'right_censored_by_window','interrupted_by_new_limit','taper_without_return_to_old_level','taper_without_return_to_pre_anchor_level','right_censored_with_later_power_shift','later_stop_without_return_to_old_level','later_unrelated_drop_no_unique_recovery','later_stop_without_return_to_old_level'}
    for method in ['cpop','labs','candidate','raw_only','command_only']:
        binary=[];on=[];rec=[];censored=[];unavailable=[]
        for r,p in zip(rows,pred):
            assert r['event_id']==p['event_id'];target=r['provisional_targets'];estimate=p['methods'][method]
            if estimate['status']=='unavailable':unavailable.append(r['event_id'])
            truth=target['anchor_visible_following']
            if truth is not None:binary.append((int(truth),int(estimate['detected'] and estimate['status']=='ok'),estimate['status']))
            for field,key,bucket in [('onset_bracket_seconds','onset_seconds',on),('recovery_completion_bracket_seconds','recovery_seconds',rec)]:
                if target[field] is not None:bucket.append(timing(estimate[key],target[field]))
            if target['anchor_visible_following']==1 and target['recovery_completion_bracket_seconds'] is None and target['recovery_status'] in no_recovery:censored.append(estimate['recovery_seconds'] is not None)
        stats=dict(binary_n=len(binary),correct=sum(a==b and status=='ok' for a,b,status in binary),false_positive=sum(a==0 and b==1 for a,b,_ in binary),false_negative=sum(a==1 and b==0 for a,b,_ in binary),unavailable_binary=sum(status=='unavailable' for _,_,status in binary),unavailable_all=len(unavailable),no_recovery_references=len(censored),spurious_recovery=sum(censored))
        stats['provisional_label_agreement']=stats['correct']/max(1,len(binary))
        for name,values in [('onset',on),('recovery',rec)]:
            stats[name]=dict(n=len(values),missing=sum(v['missing'] for v in values),capped_interval_mae_seconds=float(np.mean([v['capped_interval_error_seconds'] for v in values])) if values else None,capped_first_observed_mae_seconds=float(np.mean([v['capped_first_observed_error_seconds'] for v in values])) if values else None,detected_only_interval_mae_seconds=float(np.mean([v['capped_interval_error_seconds'] for v in values if not v['missing']])) if any(not v['missing'] for v in values) else None)
        stats['joint_capped_interval_mae_seconds']=float(np.mean([stats['onset']['capped_interval_mae_seconds'],stats['recovery']['capped_interval_mae_seconds']]))
        scored[method]=stats
    return scored
