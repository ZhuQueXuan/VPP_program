"""Inspect all reported state/error codes; corroboration in native AC only."""
from common import *
import zipfile,io
from collections import Counter

def main():
    with (EV/'runs/EV_SOURCE_QA_02/archive_inventory.csv').open(encoding='utf-8-sig',newline='') as f:inventory={r['member']:r for r in csv.DictReader(f)}
    files=[];fault_runs=[];candidates=[];selected=[]
    with zipfile.ZipFile(ARCHIVE) as z:
      for file_index,name in enumerate(sorted(n for n in z.namelist() if n.endswith('_e.csv'))):
        meta=inventory[name];is_ac=meta['type']=='ts_unidir_arbitrary_1' and meta['station']=='EVTEC' and meta['mode']=='AC'
        with z.open(name) as stream:
            reader=csv.reader(io.TextIOWrapper(stream,encoding='utf-8-sig',newline=''),delimiter=';');h=next(reader);units=next(reader);idx={k:i for i,k in enumerate(h)}
            states=[k for k in h if k.startswith(('STATE_ID','ChargeState_ID'))];counts={k:Counter() for k in states};openruns={};local_runs=[];n=bad=0
            keep=[k for k in ['epoch','P_kocos_200','Output_Power_ID4','AC_Power_set_ID4','STATE_ID4','ChargeState_ID4','Output_Voltage_ID4','Output_Current_ID4'] if k in idx];arrays={k:[] for k in keep}
            for row in reader:
                if not row:continue
                if len(row)!=len(h):bad+=1;continue
                t=num(row[idx['epoch']]) if 'epoch' in idx else np.nan
                for k in states:
                    v=num(row[idx[k]]);value=str(int(v)) if np.isfinite(v) and v==int(v) else str(v);counts[k][value]+=1
                    flag=(v==9 if k.startswith('STATE_') else v==7)
                    if flag:
                        if k not in openruns:openruns[k]=dict(member=name,column=k,code=int(v),start_data_index=n,start_epoch_ms=float(t) if np.isfinite(t) else None)
                        openruns[k]['end_data_index']=n;openruns[k]['end_epoch_ms']=float(t) if np.isfinite(t) else None
                    elif k in openruns:local_runs.append(openruns.pop(k))
                if is_ac:
                    for k in keep:arrays[k].append(num(row[idx[k]]))
                n+=1
        local_runs.extend(openruns.values());fault_runs.extend(local_runs)
        f=dict(member=name,rows=n,row_width_errors=bad,type=meta['type'],mode=meta['mode'],station=meta['station'],plug_type=meta['plug_type'],
            state_counts={k:dict(c) for k,c in counts.items()},fault_or_error_runs=len(local_runs),
            direct_fault_ack_columns=[k for k in h if any(w in k.lower() for w in ['fault','error','acknow','execution','accepted'])],ac_cross_audited=is_ac)
        if is_ac:
            a={k:np.array(v,float) for k,v in arrays.items()};t=a['epoch'];u=a['AC_Power_set_ID4'];grid=a['P_kocos_200'];charger=a['Output_Power_ID4']
            positive=np.diff(t)[np.diff(t)>0];good=np.isfinite(grid)&np.isfinite(charger)
            f.update(ac_rows=len(t),native_positive_step_ms_median=float(np.median(positive)) if len(positive) else None,
                backward_steps=int(np.sum(np.diff(t)<0)),gaps_over2s=int(np.sum(np.diff(t)>2000)),
                charger_output_finite_rows=int(np.sum(np.isfinite(charger))),charger_output_nonzero_rows=int(np.sum(abs(charger)>.1)),
                grid_charger_correlation=float(np.corrcoef(grid[good],charger[good])[0,1]) if good.sum()>2 and np.std(grid[good])>1e-9 and np.std(charger[good])>1e-9 else None)
            edges=np.flatnonzero(np.isfinite(u[1:])&np.isfinite(u[:-1])&(abs(np.diff(u))>1e-6))+1
            for i,j in zip(edges,edges[1:]):
                du=u[i]-u[i-1];duration=(t[j]-t[i])/1000
                if not(0<duration<=10 and abs(du)>=.5 and abs(u[j]-u[i-1])<=1e-6):continue
                pre=(t>=t[i]-3000)&(t<t[i]);during=(t>=t[i])&(t<t[j]);post=(t>=t[j])&(t<t[j]+3000);use=pre|during|post;ids=np.flatnonzero(use)
                c=dict(candidate_id=f'ac-{file_index:03d}-{int(i)}',member=name,metadata_key=meta['metadata_key'],
                    start_data_index=int(i),return_data_index=int(j),start_epoch_ms=float(t[i]),return_epoch_ms=float(t[j]),command_duration_s=float(duration),
                    previous_command_kw=float(u[i-1]),new_command_kw=float(u[i]),step_kw=float(du),
                    pre_rows=int(pre.sum()),during_rows=int(during.sum()),post_rows=int(post.sum()),
                    timestamp_contiguous=bool(len(ids)>1 and np.all(np.diff(ids)==1) and np.all(np.diff(t[ids])>0) and np.all(np.diff(t[ids])<=2000)),
                    command_isolated=bool(pre.any() and post.any() and np.all(abs(u[pre]-u[i-1])<=1e-6) and np.all(abs(u[post]-u[i-1])<=1e-6)),
                    type2_charging_state_seen=bool(np.any(a['STATE_ID4'][during]==4)),channel_evidence={},cross_supported=False)
                eligible=c['timestamp_contiguous'] and c['command_isolated'] and min(c['pre_rows'],c['during_rows'],c['post_rows'])>=3
                for channel,y in [('grid',grid),('charger',charger)]:
                    if not(pre.any() and during.any() and post.any()) or not np.isfinite(y[use]).all():
                        c['channel_evidence'][channel]=dict(complete_finite=False,supported=False);continue
                    b=float(np.median(y[pre]));mid=float(np.median(y[during]));end=float(np.median(y[post]));shift=float(np.sign(du)*(mid-b));return_error=abs(end-b)
                    support=shift>=max(.3,.2*abs(du)) and return_error<=max(.3,.3*shift)
                    c['channel_evidence'][channel]=dict(complete_finite=True,pre_median_kw=b,during_median_kw=mid,post_median_kw=end,directional_shift_kw=shift,return_error_kw=return_error,supported=bool(support))
                c['cross_supported']=bool(eligible and c['type2_charging_state_seen'] and all(c['channel_evidence'][k]['supported'] for k in ['grid','charger']))
                candidates.append(c)
                if c['cross_supported']:
                    p=HERE/'corroborated_windows';p.mkdir(exist_ok=True);rawpath=p/(c['candidate_id']+'.npz')
                    with rawpath.open('xb') as out:np.savez_compressed(out,original_data_indices=ids,**{k:v[ids] for k,v in a.items()})
                    selected.append(dict(**c,raw_window_path=rawpath.relative_to(ROOT).as_posix(),label_tier='B_cross_instrument_observed_AC_change_not_exact100ms_truth_or_sensor_fault'))
        files.append(f)
        if (file_index+1)%16==0:print('Dortmund members',file_index+1,'/128',flush=True)
    result=dict(members=len(files),total_rows=sum(f['rows'] for f in files),
        reported_fault_or_error_runs=len(fault_runs),members_with_reported_fault_or_error=sum(f['fault_or_error_runs']>0 for f in files),
        fault_state9_runs=sum(r['column'].startswith('STATE_') for r in fault_runs),error_ended7_runs=sum(r['column'].startswith('ChargeState_') for r in fault_runs),
        ac_dynamic_members=sum(f['ac_cross_audited'] for f in files),ac_dynamic_rows=sum(f.get('ac_rows',0) for f in files),
        ac_nonzero_charger_output_members=sum(f.get('charger_output_nonzero_rows',0)>0 for f in files),
        ac_short_command_return_candidates=len(candidates),ac_cross_supported_short_change_windows=len(selected),
        exact100ms_fault_labels_established=False,execution_acknowledgement_ids_found=False,
        limitation='Device status is not per-sample sensor-fault ground truth. Native merged AC corroboration is not independently resynchronised100ms truth; pre/during/post median criteria are descriptive, not trained/calibrated labels.')
    write('dortmund_files.json',files);write('device_reported_fault_runs.json',fault_runs);write('ac_short_candidates.json',candidates);write('corroborated_short_changes.json',selected);write('dortmund_summary.json',result)
    print(json.dumps(result),flush=True)
if __name__=='__main__':main()
