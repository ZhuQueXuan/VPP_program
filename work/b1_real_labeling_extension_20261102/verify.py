"""Source and split verification; not an independent annotation reviewer."""
from pathlib import Path
import json,hashlib,collections,xml.etree.ElementTree as ET
import pandas as pd,numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DATA=ROOT/'data/ACN_real_user_benchmark_v1_20261102';OUT=DATA/'annotations/batch_20261102_b'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
old=read(ROOT/'work/b1_real_labeling_20261102/samples.json');samples=read(HERE/'samples.json');ann=read(OUT/'first_pass_annotations.json');tasks=read(OUT/'second_review_unlabelled_tasks.json')
checks=collections.Counter()
for name,value in read(DATA/'dataset_receipt.json')['artifact_sha256'].items():
    assert sha(DATA/name)==value,name
    checks['intake_artifact_hashes']+=1
for filename in [DATA/'annotations/batch_20261102/annotation_freeze.json']:
    for name,value in read(filename)['file_sha256'].items():
        assert sha(filename.parent/name)==value,name
        checks['first_batch_annotation_files_unchanged']+=1
for name,value in read(ROOT/'work/b1_real_labeling_20261102/completion_receipt.json')['artifact_sha256'].items():
    # The separately dated annotation status is a living progress index; its
    # initial state remains in the old receipt. Other old artifacts are frozen.
    if name.endswith('/ANNOTATION_STATUS.md'):continue
    assert sha(ROOT/name)==value,name
    checks['first_batch_work_and_data_files_unchanged']+=1
for name,value in read(HERE/'selection_freeze.json')['files'].items():
    assert sha(HERE/name)==value,name
    checks['extension_selection_files']+=1
for name,value in read(ROOT/'work/b1_residual_false_20261102/protected_before.json').items():
    assert sha(ROOT/name)==value,name
    checks['production_files_unchanged']+=1
download=read(DATA/'download_manifest.json');manifest={r['path']:r for r in download};roles=collections.defaultdict(set)
for r in download:
    roles[r['user_group']].add(r['split'])
    assert sha(ROOT/r['local'])==r['sha256']
    checks['raw_files_byte_checked']+=1
assert all(len(v)==1 for v in roles.values())
assert len(samples)==len(ann)==len(tasks)==64
all_samples=old+samples
for i,s in enumerate(all_samples):
    assert s['split'] in ['training','validation']
    for other in all_samples[:i]:
        if s['source_path']==other['source_path']:
            assert abs(s['anchor_seconds_from_start']-other['anchor_seconds_from_start'])>=240
            checks['same_source_nonoverlap_pairs']+=1
cache={};bracket_widths=[];parsed=[];context=[]
for s,a,task in zip(samples,ann,tasks):
    assert s['split'] in ['training','validation']
    assert s['event_id']==a['event_id'] and s['case']==a['case']==task['id']
    m=manifest[s['source_path']]
    assert all(s[k]==m[k] for k in ['local','split','user_group','station_group'])
    if s['local'] not in cache:
        assert m['split'] in ['training','validation']
        cache[s['local']]=pd.read_csv(ROOT/s['local'],compression='gzip');parsed.append(s['local'])
    df=cache[s['local']];stamp=pd.to_datetime(df.iloc[:,0],format='mixed',utc=True)
    t=(stamp-pd.Timestamp(s['anchor_timestamp'])).dt.total_seconds().to_numpy();use=np.flatnonzero((t>=-60)&(t<=180))
    assert use.tolist()==s['raw_row_indices'] and t[use].tolist()==s['relative_seconds']
    assert t[s['raw_row_index']]==0
    for key,col in [('current_a','Charging Current (A)'),('pilot_a','Actual Pilot (A)'),('power_kw','Power (kW)'),('voltage_v','Voltage (V)'),('cumulative_energy_kwh','Energy Delivered (kWh)')]:
        original=pd.to_numeric(df.iloc[use][col],errors='coerce').to_numpy();window=np.array([np.nan if v is None else v for v in s[key]],float)
        assert np.allclose(original,window,equal_nan=True,rtol=1e-13,atol=1e-13)
        checks['original_numeric_channel_values']+=len(window)
        assert task['data']['ts'][key]==s[key]
    states=[str(v) if pd.notna(v) else None for v in df.iloc[use]['Charging State']]
    assert states==s['charging_state']
    checks['original_state_values']+=len(states)
    assert set(task)=={'id','data'} and set(task['data'])=={'case_id','source_context','ts'}
    assert task['data']['ts']['time']==s['relative_seconds']
    assert not a['gold_physical_truth'] and not a['approved_for_production_training']
    assert a['independent_review_status']=='pending'
    assert all(a[k] is None for k in ['effective_duration_seconds','clean_power_kw','fault_label','causal_response_success'])
    if a['onset_bracket']:assert a['anchor_following_label']=='observed_change'
    for key in ['onset_bracket','recovery_completion_bracket']:
        b=a[key]
        if not b:continue
        lo,hi=b['relative_seconds'];ix=[s['relative_seconds'].index(v) for v in [lo,hi]]
        assert ix[1]==ix[0]+1 and hi>lo
        assert b['raw_row_indices']==[s['raw_row_indices'][j] for j in ix]
        for k in ['current_a','power_kw','pilot_a']:assert b['endpoint_'+k]==[s[k][j] for j in ix]
        checks['native_transition_brackets']+=1;bracket_widths.append(hi-lo)
    for key in ['before','after']:
        d=a.get('recorded_level_descriptors',{}).get(key)
        if not d:continue
        ix=[s['raw_row_indices'].index(v) for v in d['raw_row_indices']]
        assert len(ix)==d['n']
        assert float(np.median([s['power_kw'][j] for j in ix]))==d['recorded_power_median_kw']
        checks['reviewed_recorded_level_ranges']+=1
    context.append(dict(case=s['case'],source_path=s['source_path'],flags=a['quality_flags'],context=a['source_context']))
    checks['complete_case_lineages']+=1
ET.parse(OUT/'label_studio_config.xml')
by_case={r['case']:r for r in ann}
assert by_case[80]['anchor_following_label']=='observed_change' and by_case[80]['onset_bracket'] is None
assert by_case[125]['recovery_completion_bracket']['relative_seconds'][1]>by_case[125]['limit_hold_seconds']
assert by_case[123]['anchor_following_label']=='unresolved'
assert by_case[74]['window_observation_label']=='observed_change' and by_case[74]['stratum']=='quiet_limit'
assert by_case[75]['anchor_following_label']=='no_observable_change'
view=DATA/'prepared/observed_localization_pilot_v1_20261102'
all_by_id={s['event_id']:s for s in all_samples}
all_annotations={a['event_id']:a for a in read(DATA/'annotations/batch_20261102/first_pass_annotations.json')+ann}
prepared_registry=read(view/'registry.json');prepared_roles=collections.defaultdict(set)
assert len(prepared_registry)==128
for r in prepared_registry:
    prepared_roles[r['user_group']].add(r['split'])
    s=all_by_id[r['event_id']]
    assert all(r[k]==s[k] for k in r)
assert all(len(v)==1 for v in prepared_roles.values())
for role,expected in [('training',96),('validation',32)]:
    rows=read(view/(role+'.json'));assert len(rows)==expected
    for r in rows:
        s=all_by_id[r['event_id']];a=all_annotations[r['event_id']]
        assert r['split']==s['split']==role
        assert r['model_input']=={k:s[k] for k in ['relative_seconds','current_a','pilot_a','power_kw']}
        assert set(r['model_input'])=={'relative_seconds','current_a','pilot_a','power_kw'}
        target=r['provisional_targets'];binary={'observed_change':1,'no_observable_change':0}
        assert target['window_visible_change']==binary.get(a['window_observation_label'])
        assert target['anchor_visible_following']==binary.get(a['anchor_following_label'])
        assert target['onset_bracket_seconds']==(a['onset_bracket']['relative_seconds'] if a['onset_bracket'] else None)
        assert target['recovery_completion_bracket_seconds']==(a['recovery_completion_bracket']['relative_seconds'] if a['recovery_completion_bracket'] else None)
        assert all(target[k] is None for k in ['effective_duration_seconds','fault_label','causal_response_success'])
        assert r['physical_gold'] is False and r['independent_review_status']=='pending'
        checks['prepared_development_rows_preserve_inputs_labels_and_roles']+=1
for name,value in read(view/'view_freeze.json')['file_sha256'].items():
    assert sha(view/name)==value,name
    checks['prepared_view_files_frozen']+=1
result=dict(status='passed',checks=dict(checks),combined_windows=128,combined_unique_users=len({s['user_group'] for s in all_samples}),new_unique_users=len({s['user_group'] for s in samples}-{s['user_group'] for s in old}),roles_parsed=sorted({s['split'] for s in samples}),extension_csv_files_parsed=len(parsed),parsed_source_paths=parsed,bracket_width_seconds=dict(min=min(bracket_widths),median=float(np.median(bracket_widths)),max=max(bracket_widths)),zero_limit_positive_output_cases=[r['case'] for r in ann if 'zero_reported_limit_with_positive_output' in r['quality_flags']],high_pilot_context_cases=[r['case'] for r in ann if 'reported_limit_above_80A' in r['quality_flags']],hardware_types_certified=False,test_observation_values_read=False,new_models_fit=0,production_changed=False,independent_semantic_review=False,label_studio_server_import_tested=False)
(HERE/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'source_context.json').write_text(json.dumps(context,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='parsed_source_paths'},ensure_ascii=False),flush=True)
