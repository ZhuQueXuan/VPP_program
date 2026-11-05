"""Verify source lineage and isolation; this is NOT an independent label review."""
from pathlib import Path
import json,hashlib,collections,math,xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
DATA=ROOT/'data/ACN_real_user_benchmark_v1_20261102';OUT=DATA/'annotations/batch_20261102'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
samples=read(HERE/'samples.json');ann=read(OUT/'first_pass_annotations.json');tasks=read(OUT/'second_review_unlabelled_tasks.json')
intake=read(DATA/'dataset_receipt.json');download=read(DATA/'download_manifest.json')
checks=collections.Counter();parsed_sources=[]
for name,value in intake['artifact_sha256'].items():
    assert sha(DATA/name)==value,name
    checks['intake_artifact_hashes']+=1
for name,value in read(HERE/'selection_freeze.json')['files'].items():
    assert sha(HERE/name)==value,name
    checks['frozen_selection_files']+=1
for name,value in read(ROOT/'work/b1_residual_false_20261102/protected_before.json').items():
    assert sha(ROOT/name)==value,name
    checks['unchanged_production_files']+=1
user_roles=collections.defaultdict(set)
for r in download:
    user_roles[r['user_group']].add(r['split'])
    # Byte checks do not parse sealed-test observations.
    assert sha(ROOT/r['local'])==r['sha256'],r['local']
    checks['raw_file_hashes_all_roles']+=1
assert all(len(v)==1 for v in user_roles.values())
checks['users_with_one_role']=len(user_roles)
manifest={r['path']:r for r in download};cache={};native_brackets=[]
assert len(samples)==len(ann)==len(tasks)==64
assert len({s['user_group'] for s in samples})==64
for s,a,task in zip(samples,ann,tasks):
    assert s['split'] in ['training','validation']
    assert a['event_id']==s['event_id'] and a['case']==task['id']==s['case']
    m=manifest[s['source_path']]
    assert all(s[k]==m[k] for k in ['local','split','user_group','station_group'])
    assert s['source_sha256']==m['sha256']
    if s['local'] not in cache:
        assert m['split'] in ['training','validation']
        cache[s['local']]=pd.read_csv(ROOT/s['local'],compression='gzip')
        parsed_sources.append(s['local'])
    df=cache[s['local']];stamp=pd.to_datetime(df.iloc[:,0],utc=True,format='mixed')
    actual=(stamp-pd.Timestamp(s['anchor_timestamp'])).dt.total_seconds().to_numpy()
    use=np.flatnonzero((actual>=-60)&(actual<=180))
    assert use.tolist()==s['raw_row_indices']
    assert actual[use].tolist()==s['relative_seconds']
    assert actual[s['raw_row_index']]==0
    for key,col in [('current_a','Charging Current (A)'),('pilot_a','Actual Pilot (A)'),('power_kw','Power (kW)')]:
        expected=pd.to_numeric(df.iloc[use][col],errors='coerce').to_numpy()
        got=np.array([np.nan if v is None else v for v in s[key]],float)
        assert np.allclose(got,expected,rtol=1e-13,atol=1e-13,equal_nan=True)
        checks['source_channel_values']+=len(got)
        assert task['data']['ts'][key]==s[key]
    assert task['data']['ts']['time']==s['relative_seconds']
    assert set(task)=={'id','data'}
    assert set(task['data'])=={'case_id','ts'}
    assert 'annotations' not in task and 'predictions' not in task
    assert not a['gold_physical_truth'] and not a['approved_for_production_training']
    assert a['independent_review_status']=='pending'
    assert all(a[k] is None for k in ['effective_duration_seconds','clean_power_kw','fault_label','causal_response_success'])
    for key in ['onset_bracket','recovery_completion_bracket']:
        b=a[key]
        if b is None:continue
        lo,hi=b['relative_seconds'];indices=[s['relative_seconds'].index(v) for v in [lo,hi]]
        assert indices[1]==indices[0]+1 and lo<hi
        assert b['raw_row_indices']==[s['raw_row_indices'][i] for i in indices]
        for k in ['current_a','power_kw','pilot_a']:
            assert b['endpoint_'+k]==[s[k][i] for i in indices]
        native_brackets.append(hi-lo)
        checks['native_transition_brackets']+=1
    assert (a['onset_bracket'] is not None)==(a['anchor_following_label']=='observed_change')
    assert (a['recovery_completion_bracket'] is not None)==(a['end_status']=='observed_recovery')
    for key in ['before','after']:
        desc=a.get('recorded_level_descriptors',{}).get(key)
        if not desc:continue
        ix=[s['raw_row_indices'].index(i) for i in desc['raw_row_indices']]
        assert len(ix)==desc['n']>=3
        assert math.isclose(float(np.median([s['power_kw'][i] for i in ix])),desc['recorded_power_median_kw'],abs_tol=1e-13)
        checks['explicit_native_level_ranges']+=1
    checks['complete_case_lineages']+=1
ET.parse(OUT/'label_studio_config.xml')
assert ann[17]['window_observation_label']=='unresolved' # Three-point local gap retained.
assert ann[31]['anchor_following_label']=='observed_change' # Short low point not suppressed.
assert ann[27]['anchor_following_label']=='no_observable_change' # Limit is not success truth.
assert ann[22]['window_observation_label']=='observed_change' # Quiet limit not negative truth.
result=dict(status='passed',checks=dict(checks),source_csv_files_parsed=len(parsed_sources),source_roles_parsed=sorted({manifest[s['source_path']]['split'] for s in samples}),parsed_source_paths=parsed_sources,sealed_test_observation_values_parsed=False,transition_bracket_width_seconds=dict(min=min(native_brackets),median=float(np.median(native_brackets)),max=max(native_brackets)),independent_annotation_review=False,algorithm_evaluation=False,new_models_fit=0,all_original_points_retained=True,label_studio_xml_well_formed=True,label_studio_server_import_executed=False)
(HERE/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='parsed_source_paths'},ensure_ascii=False),flush=True)
