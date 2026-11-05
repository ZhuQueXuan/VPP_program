"""Same raw rows, explicit nested bins, command and observed-shape evidence.

This audit never edits points, imputes values, fits a curve or assigns real fault
labels. Threshold descriptions are inherited10/90 command-progress measures.
"""
import json,hashlib
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'work/b1_command_feature_selection_20261031'
RESULT=HERE/'analysis_run2'

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(name,v):
    def native(x):
        if isinstance(x,np.generic):return x.item()
        if isinstance(x,np.ndarray):return x.tolist()
        if isinstance(x,dict):return {k:native(y) for k,y in x.items()}
        if isinstance(x,(tuple,list)):return [native(y) for y in x]
        return x
    with (RESULT/name).open('x',encoding='utf-8') as f:json.dump(native(v),f,ensure_ascii=False,allow_nan=False,indent=2)
def runs(mask):
    d=np.diff(np.r_[False,mask,False].astype(int));return list(zip(np.flatnonzero(d==1),np.flatnonzero(d==-1)))
def crossing(t,y,level):
    mask=(t>=0)&(t<=10100000)&(y>=level)
    for a,b in runs(mask):
        if t[a]<=10000000 and t[b-1]-t[a]>=100000:return float(t[a]/1e6)
    return None

def aggregate(t,y,u,width):
    lo=np.arange((-5000000//width)*width,((15000000+width-1)//width)*width,width,dtype=np.int64)
    hi=lo+width;count=[];means=[];umin=[];umax=[];u_changes=[]
    for a,b in zip(lo,hi):
        ix=np.flatnonzero((t>=a)&(t<b));count.append(len(ix))
        means.append(float(np.mean(y[ix])) if len(ix) else np.nan)
        umin.append(float(np.min(u[ix])) if len(ix) else np.nan);umax.append(float(np.max(u[ix])) if len(ix) else np.nan)
        u_changes.append(int(np.sum(np.diff(u[ix])!=0)) if len(ix)>1 else 0)
    assert sum(count)==len(t)
    return dict(lo=lo,hi=hi,count=np.array(count),mean=np.array(means),u_min=np.array(umin),u_max=np.array(umax),
        command_changes=np.array(u_changes),complete=(lo>=-5000000)&(hi<=15000000))

def describe(case,panel,phase,t,y,u,pre_us,baseline_old=None):
    assert np.all(np.diff(t)>0) and len(t)==len(y)==len(u) and np.isfinite(y).all() and np.isfinite(u).all()
    base=float(np.median(y[(t>=-pre_us)&(t<0)]));du=case['new_command_A']-case['previous_command_A'];direction=np.sign(du)
    z=direction*(y-base)/abs(du)
    grids={width:aggregate(t,y,u,width) for width in [100000,1000000,5000000,10000000]}
    g=grids[100000];fine=direction*(g['mean']-base)/abs(du);maxdiff=0.;checks=0
    for width,d in grids.items():
        for a,b,n,mean in zip(d['lo'],d['hi'],d['count'],d['mean']):
            ix=(g['lo']>=a)&(g['hi']<=b);n2=int(g['count'][ix].sum());assert n==n2
            if n:
                weighted=float(np.sum(g['mean'][ix]*g['count'][ix])/n);maxdiff=max(maxdiff,abs(weighted-mean));assert abs(weighted-mean)<1e-10
            checks+=1
    if baseline_old is not None:
        assert abs(base-baseline_old['pre_current_A'])<1e-12
        assert np.array_equal(g['count'],baseline_old['bin_counts'])
        assert np.max(abs(g['mean']-np.array(baseline_old['current_mean_A'])))<1e-12
        assert np.max(abs(fine-np.array(baseline_old['progress'])))<1e-12
        checks+=4
    payload={}
    for w,d in grids.items():
        for key,value in d.items():payload[f'{key}_{w}us']=value
    name=f'{panel}_{len(ALL_ROWS):04d}_phase{phase}.npz'
    with (RESULT/'aligned'/name).open('xb') as f:np.savez_compressed(f,**payload)
    m=(g['lo']>=0)&(g['hi']<=10000000);ym=fine[m]
    targetruns=runs((g['lo']>=0)&(fine>=.9));lengths=[(b-a)*.1 for a,b in targetruns]
    a10=crossing(t,z,.1);a90=crossing(t,z,.9)
    rawmask=(t>=0)&(t<10000000)
    native_spans=[float((t[b-1]-t[a])/1e6) for a,b in runs(rawmask&(z>=.9))]
    c10=grids[10000000];j=int(np.flatnonzero(c10['lo']==0)[0]);coarse_progress=direction*(c10['mean'][j]-base)/abs(du)
    transitions=[dict(time_s=float(t[i]/1e6),before=float(u[i-1]),after=float(u[i])) for i in np.flatnonzero(np.diff(u)!=0)+1]
    d=dict(panel=panel,event_id=case['event_id'],recording=case['recording'],phase=phase,raw_samples=len(t),max_gap_us=int(max(np.diff(t))),
        raw_source=case.get('raw_trace_npz',case.get('raw_path')),aligned_file='analysis_run2/aligned/'+name,pre_median_A=base,step_A=du,
        direct_vs_weighted_max_difference_A=maxdiff,alignment_checks=checks,
        all_raw_samples_counted_each_scale=True,coarse10s_progress=float(coarse_progress),
        fine100ms_first10s_fraction_above10=float(np.mean(ym>=.1)),fine100ms_first10s_fraction_above90=float(np.mean(ym>=.9)),
        fine100ms_target_runs_seconds=lengths,fine100ms_longest_target_seconds=float(max(lengths,default=0)),
        fine100ms_short_target_run_count=sum(x<=.20000001 for x in lengths),
        native_first10s_longest_target_span_seconds=max(native_spans,default=0.),
        confirmed_native_t10_s=a10,confirmed_native_t90_s=a90,
        confirmed_native_transition_10to90_s=a90-a10 if a10 is not None and a90 is not None else None,
        last5s_median_progress=float(np.median(fine[g['lo']>=10000000])),command_changes=transitions,
        mode=case.get('mode','held_command_panel'),labels='Observed shapes only, not true fault/response classes')
    if panel=='pulse':
        dur=case['duration_us'];during=(t>=0)&(t<dur);pre=(t>=-2000000)&(t<0);post=(t>=dur)&(t<dur+2000000)
        assert np.any(during) and np.any(pre) and np.any(post)
        native_run=[float((t[b-1]-t[a])/1e6) for a,b in runs(during&(z>=.1))]
        d.update(command_duration_s=dur/1e6,pre2s_command_constant=bool(np.all(u[pre]==case['previous_command_A'])),
            post2s_command_constant=bool(np.all(u[post]==case['previous_command_A'])),
            during_native_samples=int(during.sum()),during_median_progress=float(np.median(z[during])),
            during_fraction_above10=float(np.mean(z[during]>=.1)),during_max_above10_span_s=max(native_run,default=0.),
            post2s_median_progress=float(np.median(z[post])))
    return d

ALL_ROWS=[]
def main():
    RESULT.mkdir(exist_ok=False);(RESULT/'aligned').mkdir(exist_ok=False)
    original=read(OLD/'real_cases.json')
    for c in original:
        with np.load(ROOT/c['raw_trace_npz'],allow_pickle=False) as f:
            ALL_ROWS.append(describe(c,'held',c['phase'],f['relative_time_us'],f['phase_current_A'],f['command_A'],5000000,c))
    pulses=read(HERE/'pulse_extraction_all_modes.json');multi=[]
    for c in pulses:
        with np.load(ROOT/c['raw_path'],allow_pickle=False) as f:
            t=f['relative_us'];u=f['command']
            for phase in [1,2,3]:
                d=describe(c,'pulse',phase,t,f[f'i{phase}'],u,2000000)
                before=(t>=-2000000)&(t<0);during=(t>=0)&(t<c['duration_us'])
                d['pre_voltage_median_V']=float(np.median(f[f'u{phase}'][before]));d['pre_power_median_W']=float(np.median(f[f'p{phase}'][before]));d['during_power_median_W']=float(np.median(f[f'p{phase}'][during]))
                d['during_power_directional_change_W']=float(np.sign(d['step_A'])*(d['during_power_median_W']-d['pre_power_median_W']))
                ALL_ROWS.append(d)
    held=[r for r in ALL_ROWS if r['panel']=='held'];pulse=[r for r in ALL_ROWS if r['panel']=='pulse']
    fast=[r for r in held if r['confirmed_native_transition_10to90_s'] is not None and r['confirmed_native_transition_10to90_s']<=.10000001 and r['fine100ms_longest_target_seconds']>=5.]
    brief=[r for r in held if r['fine100ms_short_target_run_count']>0]
    below=[r for r in held if r['last5s_median_progress']<.9]
    pulse_l1=[r for r in pulse if r['phase']==1]
    isolated_active=[r for r in pulse_l1 if r['pre2s_command_constant'] and r['post2s_command_constant'] and r['pre_median_A']>=1]
    supported=[r for r in isolated_active if r['during_max_above10_span_s']>=.1 and r['during_median_progress']>=.1]
    example_categories={'fast_transition_then_long_support':fast,'observed_brief_threshold_excursion_not_fault_label':brief,
        'persistent_below90_not_fault_label':below,'first_short_command_return':pulse_l1,
        'isolated_active_short_command_with_observed_current_change':supported}
    examples={k:sorted(v,key=lambda r:(r['recording'],r['event_id']))[0] if v else None for k,v in example_categories.items()}
    summary=dict(held_events=len(held),held_recordings=len({r['recording'] for r in held}),pulse_events=len(pulses),pulse_recordings=len({r['recording'] for r in pulse}),
        pulse_phase_rows=len(pulse),same_event_phase_rows=len(ALL_ROWS),alignment_checks=sum(r['alignment_checks'] for r in ALL_ROWS),
        max_direct_weighted_difference_A=max(r['direct_vs_weighted_max_difference_A'] for r in ALL_ROWS),
        held_fast_native_transition_le100ms_then_target_support_ge5s=len(fast),held_events_with_brief_target_excursion_le200ms=len(brief),
        held_last5s_median_progress_below90=len(below),held_coarse10s_mean_above90_but_fine_above90_less_than_half=sum(r['coarse10s_progress']>=.9 and r['fine100ms_first10s_fraction_above90']<.5 for r in held),
        pulse_durations_s_min_median_max=[float(min(c['duration_us'] for c in pulses)/1e6),float(np.median([c['duration_us'] for c in pulses])/1e6),float(max(c['duration_us'] for c in pulses)/1e6)],
        isolated_active_pulse_l1_events=len(isolated_active),isolated_active_with_observed_directional_change=len(supported),
        observed_change_definition='L1 pre median>=1A, constant old command pre2s/post2s, during directional median>=10% and native above10 run spans>=.1s; descriptive support, not causal/fault truth.',
        all_phase_rows_retained=True,real_fault_truth_labels=False,real_clean_response_truth_labels=False,
        decision='Time detail and command context add observable evidence; no validated3class classifier, no accuracy/adoption claim.')
    write('observed_shapes.json',ALL_ROWS);write('summary.json',summary);write('examples.json',examples)
    print((RESULT/'summary.json').read_text(encoding='utf-8'));print((RESULT/'examples.json').read_text(encoding='utf-8')[:2000])
if __name__=='__main__':main()
