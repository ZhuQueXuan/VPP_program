"""Separate window admission/run decomposition and aggregate calculations.

Parquet decoding still uses DuckDB. This is independent arithmetic, not a
second physical measurement or an independent Parquet implementation.
"""
from kit_common import *
from collections import defaultdict
from bisect import bisect_left
import math,statistics
run=BASE/'runs/CHAR_KIT_STEPS_01';replay=BASE/'runs/CHAR_KIT_STEPS_02';prep=BASE/'runs/PREP_KIT_STEPS_01'
dest=run/'verification.json';assert not dest.exists()
pp=BASE/'kit_step_protocol_v1.json';p=load(pp);assert sha(pp)==load(BASE/'kit_step_freeze_v1.json')['protocol_sha256']
for s in p['sources'].values():assert sha(ROOT/s['path'])==s['sha256']
ad=load(prep/'admission.json');assert all(sha(prep/n)==h for n,h in ad['outputs'].items())
saved={r['event_id']:r for r in read(prep/'all_phase_candidates.csv')};reported={r['event_id']:r for r in read(run/'phase_step_features.csv')}
calc=[];con=connection();valuechecks=0;maxdiff=0.;statuses=0
def checkvalue(a,b):
    global valuechecks,maxdiff
    valuechecks+=1
    if a is None:assert b in ('',None);return
    if isinstance(a,bool):assert a==(b=='True' if isinstance(b,str) else b);return
    diff=abs(float(a)-float(b));maxdiff=max(maxdiff,diff);assert diff<1e-10,(a,b)
def crossing(t,y,initial,delta,level):
    progress=(y-initial)*(1 if delta>0 else -1)/abs(delta)
    mask=(progress>=level)&(t<=10100000)
    padded=np.r_[False,mask,False];changes=np.flatnonzero(padded[1:]!=padded[:-1]);intervals=list(zip(changes[::2],changes[1::2]-1))
    for a,b in intervals:
        if t[a]>10000000:break
        if t[b]-t[a]>=100000:
            confirm=bisect_left(t,int(t[a])+100000)
            return {'sample_s':float(t[a])/1e6,'interval_lower_s':float(t[a-1])/1e6 if a else 0.,
                    'interval_upper_s':float(t[a])/1e6,'confirmed_s':float(t[confirm])/1e6}
    return None
for meta in read(SOURCE/'charging.csv'):
    d=trace(con,meta['charging_uuid']);t=d['t_us'];u=d['u'];assert np.all(np.diff(t)>0)
    for i in np.nonzero(u[1:]-u[:-1])[0]+1:
        old=int(u[i-1]);new=int(u[i]);delta=new-old;t0=int(t[i]);left=bisect_left(t,t0-5000000);right=bisect_left(t,t0+15000000)
        common=[]
        if old<6 or new<6:common.append('outside_study_operating_commands')
        if abs(delta)<2:common.append('command_step_lt2A')
        if left>=i or t[left]>t0-4950000 or t[i-1]<t0-50000:common.append('pre_window_incomplete')
        if any(int(v)!=old for v in u[left:i]):common.append('pre_command_not_constant')
        if right<=i or t[right-1]<t0+14950000:common.append('post_window_incomplete')
        if any(int(v)!=new for v in u[i:right]):common.append('post_command_not_constant')
        if right-left>1 and np.max(np.diff(t[left:right]))>50000:common.append('window_gap_over50ms')
        for phase in (1,2,3):
            key=meta['charging_uuid']+':'+str(i)+':L'+str(phase);orig=saved[key];flags=list(common)
            y=d['i'+str(phase)];initial=statistics.median(y[left:i]) if left<i else None
            if not np.isfinite(y[left:right]).all():flags.append('phase_nonfinite')
            if initial is None or initial<1:flags.append('pre_phase_median_lt1A')
            assert set(filter(None,orig['flags'].split('|')))==set(flags)
            assert orig['status']==('excluded' if flags else 'admitted');statuses+=1
            assert int(orig['edge_index'])==i and int(orig['source_file_row'])==int(d['file_row_number'][i])
            checkvalue(initial,orig['pre_observed_current_A'])
            if flags:continue
            actual=reported[key];tt=t[i:right]-t0;yy=y[i:right];c10=crossing(tt,yy,initial,delta,.1);c90=crossing(tt,yy,initial,delta,.9)
            steady=float(np.median(yy[(tt>=10000000)&(tt<15000000)]));sgn=1 if delta>0 else -1
            values={'t10_observed':c10 is not None,'t90_observed':c90 is not None,
                    'transition_10_to90_s':c90['sample_s']-c10['sample_s'] if c90 and c10 else None,
                    'steady_current_A':steady,'steady_error_from_new_command_A':steady-new,'steady_abs_error_A':abs(steady-new),
                    'post_current_min_A':float(np.min(yy)),'post_current_max_A':float(np.max(yy)),
                    'directional_overshoot_A':float(max(0.,np.max(sgn*(yy-(initial+delta)))))}
            for name,c in (('t10',c10),('t90',c90)):
                for field in ('sample_s','interval_lower_s','interval_upper_s','confirmed_s'):values[name+'_'+field]=c[field] if c else None
            for k,v in values.items():checkvalue(v,actual[k])
            assert actual['crossing_status']==('observed90pct_command_step' if c90 else 'not_observed90pct_within10s')
            calc.append({**orig,**values})
    print(json.dumps({'date':meta['date'],'phase_candidates_checked':statuses}),flush=True)
assert statuses==28641 and len(calc)==4928 and len(reported)==4928
def distribution(vals):
    if not vals:return {'n':0,'median':None,'p95':None,'max':None}
    v=np.sort(vals);return {'n':len(v),'median':float(np.median(v)),'p95':float(v[int(np.ceil(.95*len(v)))-1]),'max':float(v[-1])}
def aggregate(rr):
    seen=[r for r in rr if r['t90_observed']]
    return {'phase_events':len(rr),'unique_command_edges':len({(r['charging_uuid'],r['edge_index']) for r in rr}),
        'recording_sets':len({r['charging_uuid'] for r in rr}),'t10_observed':sum(r['t10_observed'] for r in rr),
        't90_observed':len(seen),'t90_not_observed_within10s':len(rr)-len(seen),
        'observed_t10_seconds':distribution([r['t10_sample_s'] for r in rr if r['t10_observed']]),
        'observed_t90_seconds':distribution([r['t90_sample_s'] for r in seen]),
        'observed_transition10_to90_seconds':distribution([r['transition_10_to90_s'] for r in seen]),
        'steady_absolute_error_A':distribution([r['steady_abs_error_A'] for r in rr]),
        'steady_signed_mean_error_A':float(np.mean([r['steady_error_from_new_command_A'] for r in rr])) if rr else None,
        'largest_steady_error_event':max(rr,key=lambda r:r['steady_abs_error_A'])['event_id'] if rr else None}
def compare(a,b):
    if isinstance(a,dict):
        assert set(a)==set(b)
        for k in a:compare(a[k],b[k])
    elif isinstance(a,str):assert a==b
    else:checkvalue(a,b)
groups=load(run/'groups.json')
for key,s in groups.items():
    rr=calc if key=='all' else [r for r in calc if (r['direction'] if key in ('up','down') else r['phase'])==key]
    compare(aggregate(rr),s)
for r in load(run/'recording_metrics.json'):
    rr=[x for x in calc if x['charging_uuid']==r['charging_uuid'] and (r['direction']=='all' or x['direction']==r['direction'])]
    compare(aggregate(rr),{k:v for k,v in r.items() if k not in ('charging_uuid','date','car_brand','car_model','car_battery_size','direction')})
summary=load(run/'summary.json')
for key in ('all','up','down'):compare(groups[key],summary[key])
art=load(run/'receipt.json')['outputs'];same={n:sha(run/n)==sha(replay/n)==h for n,h in art.items()};assert all(same.values())
result={'date':'2026-10-16','status':'passed','protocol_sha256':sha(pp),'admission_sha256':sha(prep/'admission.json'),
 'all_phase_candidates_checked':statuses,'eligible_phase_features_checked':len(calc),'numeric_or_null_checks':valuechecks,'maximum_difference':maxdiff,
 'independent_computation':'bisect original windows, scalar admission/median, vector boolean-run crossings, numpy aggregation; no runner or kernel import',
 'shared_decoder_limit':'Raw Parquet decoding uses the same DuckDB implementation, not a second file parser or physical clock validation.',
 'replay_artifacts_equal':same,'verifier_sha256':sha(Path(__file__))}
dump(dest,result);print(json.dumps(result,ensure_ascii=False,indent=2))
