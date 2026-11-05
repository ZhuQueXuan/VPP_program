from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,collections,gzip
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DEST=ROOT/'data/ACN_real_user_benchmark_v1_20261102';selected=json.loads((DEST/'session_manifest.json').read_text(encoding='utf-8'));manifest=json.loads((DEST/'download_manifest.json').read_text(encoding='utf-8'));by={r['path']:r for r in manifest};rows=[];events=[]
for item in selected:
    if item['split'] not in ['training','validation']:continue
    r=by[item['path']]
    if r['status']!='downloaded':rows.append(dict(path=r['path'],split=r['split'],eligible=False,reason='not_downloaded'));continue
    p=ROOT/r['local']
    try:df=pd.read_csv(p,compression='gzip')
    except (gzip.BadGzipFile,EOFError,pd.errors.ParserError,pd.errors.EmptyDataError,UnicodeError,OSError) as ex:
        rows.append(dict(path=r['path'],local=r['local'],split=r['split'],user_group=r['user_group'],station_group=r['station_group'],basic_observation_eligible=False,response_annotation_candidate=False,reason='published_source_parse_error',error=str(ex),raw_sha256=r['sha256']));print('Source parse issue preserved',Path(r['path']).name,type(ex).__name__,flush=True);continue
    if not len(df):
        rows.append(dict(path=r['path'],local=r['local'],split=r['split'],user_group=r['user_group'],station_group=r['station_group'],rows=0,basic_observation_eligible=False,response_annotation_candidate=False,reason='empty_source_table',raw_sha256=r['sha256']));continue
    times=pd.to_datetime(df.iloc[:,0],utc=True,format='mixed',errors='coerce');dt=times.diff().dt.total_seconds().to_numpy();num={k:pd.to_numeric(df[k],errors='coerce').to_numpy() for k in ['Charging Current (A)','Actual Pilot (A)','Power (kW)']};finite=np.isfinite(np.column_stack(list(num.values()))).all(axis=1);n=int(finite.sum());duration=float((times.max()-times.min()).total_seconds()) if times.notna().any() else 0.;core_fraction=n/max(1,len(df));change=np.r_[False,np.abs(np.diff(num['Actual Pilot (A)']))>=2.]&np.isfinite(dt)&(dt>0)&(dt<=15.);indices=np.flatnonzero(change)
    enough=duration>=3600. and n>=300 and core_fraction>=.95 and not times.isna().any() and not (dt<0).any()
    row=dict(path=r['path'],local=r['local'],split=r['split'],station_group=r['station_group'],user_group=r['user_group'],rows=len(df),duration_seconds=duration,core_finite_rows=n,core_finite_fraction=core_fraction,
        current_finite=int(np.isfinite(num['Charging Current (A)']).sum()),pilot_finite=int(np.isfinite(num['Actual Pilot (A)']).sum()),power_finite=int(np.isfinite(num['Power (kW)']).sum()),
        sample_median_seconds=float(np.nanmedian(dt)) if len(df)>1 else None,max_gap_seconds=float(np.nanmax(dt)) if len(df)>1 else None,timestamp_parse_fail=int(times.isna().sum()),backward_timestamps=int((dt<0).sum()),duplicate_timestamps=int(times.duplicated().sum()),
        command_change_candidates=int(len(indices)),basic_observation_eligible=bool(enough),response_annotation_candidate=bool(enough and len(indices)>0),
        response_truth_label_available=False,clean_power_target_available=False,untreated_power_reference_available=False,raw_sha256=r['sha256'])
    rows.append(row)
    if enough:
        for i in indices:
            events.append(dict(event_id=hashlib.sha256((r['path']+'|'+str(i)).encode()).hexdigest()[:24],source_path=r['path'],local=r['local'],split=r['split'],station_group=r['station_group'],user_group=r['user_group'],raw_row_index=int(i),command_timestamp=times.iloc[i].isoformat(),previous_pilot_a=float(num['Actual Pilot (A)'][i-1]),pilot_a=float(num['Actual Pilot (A)'][i]),measurement_gap_seconds=float(dt[i]),
                actual_onset_seconds=None,actual_end_seconds=None,actual_response_present=None,label_status='unreviewed_command_candidate_not_response_truth'))
summary={}
for role in ['training','validation']:
    rr=[r for r in rows if r['split']==role];ss=[r for r in rr if r.get('response_annotation_candidate')];summary[role]=dict(downloaded_records=len(rr),rows=sum(r.get('rows',0) for r in rr),station_groups=len({r['station_group'] for r in rr if 'station_group' in r}),
        basic_observation_eligible=sum(r.get('basic_observation_eligible',False) for r in rr),response_annotation_candidate_sessions=len(ss),command_change_candidates=sum(r.get('command_change_candidates',0) for r in ss),
        no_pilot_records=sum(r.get('pilot_finite',0)==0 for r in rr if 'pilot_finite' in r),source_parse_issues=sum(r.get('reason')=='published_source_parse_error' for r in rr),users=len({r['user_group'] for r in rr if 'user_group' in r}),response_labels=0,clean_power_labels=0)
payload=dict(summary=summary,blind_files_not_opened=True,raw_values_not_changed=True,all_source_files_retained=True,labels_not_inferred_from_command=True)
(DEST/'development_profile.json').write_text(json.dumps(dict(**payload,records=rows),ensure_ascii=False,allow_nan=False),encoding='utf-8')
(DEST/'response_annotation_candidates.json').write_text(json.dumps(events,ensure_ascii=False,allow_nan=False),encoding='utf-8')
print(json.dumps(payload),flush=True)
