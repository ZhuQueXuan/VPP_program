"""Freeze every command-edge phase status before any step-response scoring."""
from kit_common import *
from collections import Counter
out=BASE/'runs/PREP_KIT_STEPS_01';out.mkdir(parents=True,exist_ok=False)
pp=BASE/'kit_step_protocol_v1.json';p=load(pp);assert sha(pp)==load(BASE/'kit_step_freeze_v1.json')['protocol_sha256']
for s in p['sources'].values():assert sha(ROOT/s['path'])==s['sha256']
con=connection();events=[];counts=[]
for meta in read(SOURCE/'charging.csv'):
    d=trace(con,meta['charging_uuid']);t=d['t_us'];u=d['u'];assert np.all(np.diff(t)>0)
    edges=np.flatnonzero(u[1:]!=u[:-1])+1;trace_rows=[]
    for idx in edges:
        t0=int(t[idx]);old=int(u[idx-1]);new=int(u[idx]);common_flags=[]
        left=int(np.searchsorted(t,t0-5000000,side='left'));right=int(np.searchsorted(t,t0+15000000,side='left'))
        if old<6 or new<6:common_flags.append('outside_study_operating_commands')
        if abs(new-old)<2:common_flags.append('command_step_lt2A')
        if left>=idx or int(t[left])>t0-4950000 or int(t[idx-1])<t0-50000:common_flags.append('pre_window_incomplete')
        if not np.all(u[left:idx]==old):common_flags.append('pre_command_not_constant')
        if right<=idx or int(t[right-1])<t0+14950000:common_flags.append('post_window_incomplete')
        if not np.all(u[idx:right]==new):common_flags.append('post_command_not_constant')
        if right-left>1 and np.any(np.diff(t[left:right])>50000):common_flags.append('window_gap_over50ms')
        for phase in (1,2,3):
            values=d['i'+str(phase)];flags=list(common_flags)
            finite=bool(np.isfinite(values[left:right]).all())
            if not finite:flags.append('phase_nonfinite')
            initial=float(np.median(values[left:idx])) if left<idx and np.isfinite(values[left:idx]).all() else None
            if initial is None or initial<1:flags.append('pre_phase_median_lt1A')
            row={**meta,'event_id':meta['charging_uuid']+':'+str(idx)+':L'+str(phase),
                 'edge_index':int(idx),'source_file_row':int(d['file_row_number'][idx]),'phase':'L'+str(phase),
                 'edge_time_us':t0,'pre_start_index':left,'post_end_index':right,'previous_command_A':old,'new_command_A':new,
                 'step_A':new-old,'direction':'up' if new>old else 'down','pre_observed_current_A':initial if initial is not None else '',
                 'status':'admitted' if not flags else 'excluded','flags':'|'.join(flags)}
            events.append(row);trace_rows.append(row)
    counts.append({**meta,'raw_rows':len(t),'command_edges':len(edges),'phase_candidates':len(trace_rows),
                   'admitted_phase_events':sum(r['status']=='admitted' for r in trace_rows)})
    print(json.dumps({'date':meta['date'],'edges':len(edges),'admitted_phases':counts[-1]['admitted_phase_events']}),flush=True)
table(out/'all_phase_candidates.csv',events);table(out/'recording_coverage.csv',counts)
eligible=[r for r in events if r['status']=='admitted']
summary={'date':'2026-10-16','recording_sets':len(counts),'raw_rows':sum(r['raw_rows'] for r in counts),
 'command_edges':sum(r['command_edges'] for r in counts),'phase_candidates':len(events),'eligible_phase_events':len(eligible),
 'eligible_command_edges':len({(r['charging_uuid'],r['edge_index']) for r in eligible}),
 'eligible_up_down':dict(Counter(r['direction'] for r in eligible)),'eligible_phases':dict(Counter(r['phase'] for r in eligible)),
 'exclusion_flags':dict(Counter(f for r in events for f in r['flags'].split('|') if f)),
 'limit':'Retrospective complete held-command windows and preceding measured-load phases only, not startup/stop/all operating availability.'}
dump(out/'summary.json',summary)
dump(out/'admission.json',{'date':'2026-10-16','status':'limited_recorded_step_characterisation','before_crossing_features':True,
 'protocol_sha256':sha(pp),'script_sha256':sha(Path(__file__)),'outputs':{f.name:sha(f) for f in sorted(out.iterdir())}})
print(json.dumps(summary,ensure_ascii=False,indent=2))
