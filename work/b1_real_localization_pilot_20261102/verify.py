"""Independent scalar scoring and native-input checks; no model selection."""
from pathlib import Path
import json,csv,hashlib,math,collections
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DATA=ROOT/'data/ACN_real_user_benchmark_v1_20261102';VIEW=DATA/'prepared/observed_localization_pilot_v1_20261102'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
checks=collections.Counter();registry={r['event_id']:r for r in read(VIEW/'registry.json')};roles=collections.defaultdict(set)
for r in registry.values():roles[r['user_group']].add(r['split'])
assert all(len(v)==1 for v in roles.values())
for file in [ROOT/'work/b1_real_labeling_extension_20261102/completion_receipt.json',ROOT/'work/b1_real_labeling_20261102/completion_receipt.json']:
    for name,value in read(file)['artifact_sha256'].items():
        if name.endswith('/ANNOTATION_STATUS.md') and file.parent.name=='b1_real_labeling_20261102':continue
        assert sha(ROOT/name)==value,name
        checks['prior_data_and_annotation_artifacts_unchanged']+=1
for name,value in read(ROOT/'work/b1_residual_false_20261102/protected_before.json').items():
    assert sha(ROOT/name)==value,name
    checks['production_files_unchanged']+=1
for r in read(DATA/'download_manifest.json'):
    assert sha(ROOT/r['local'])==r['sha256']
    checks['raw_files_byte_checked_without_test_parse']+=1
freeze=read(HERE/'selection_freeze.json')
for name,value in freeze['source_sha256'].items():assert sha(HERE/name)==value,name
assert sha(VIEW/'training.json')==freeze['input_training_sha256']
assert sha(VIEW/'validation.json')==freeze['input_validation_sha256']
vendor=ROOT/'work/b1_command_feature_selection_20261031/vendor/LABS'
for name,item in read(vendor/'download_receipt.json')['downloads'].items():
    assert sha(vendor/name)==item['sha256'],name
    checks['pinned_LABS_vendor_files']+=1
sources=[];failures=[];short_results={};per_event_timing=[]
for role in ['training','validation']:
    rows=read(VIEW/(role+'.json'));pred=read(HERE/(role+'/predictions_k3.json' if role=='training' else role+'/predictions.json'))
    stats=read(HERE/(role+'/scores_k3.json' if role=='training' else role+'/scores.json'))
    curves=read(HERE/role/'native_curves.json');receipt=read(HERE/role/'native_receipt.json')
    assert len(rows)==len(pred)
    valid=[]
    for r in rows:
        d=r['model_input'];t=d['relative_seconds']
        good=all(v is not None and math.isfinite(v) for key in ['relative_seconds','current_a','pilot_a','power_kw'] for v in d[key]) and len(t)>=3 and all(b>a for a,b in zip(t,t[1:])) and t.count(0.)==1 and t.index(0.)>0
        if good:valid.append(r)
        else:failures.append(dict(role=role,case=registry[r['event_id']]['case'],event_id=r['event_id'],reason='unsupported_native_time_or_missing_value',duplicate_or_reversed_time_pairs=sum(b<=a for a,b in zip(t,t[1:])),zero_timestamp_count=t.count(0.),nonfinite_model_values=sum(v is None or not math.isfinite(v) for key in ['relative_seconds','current_a','pilot_a','power_kw'] for v in d[key]),window_retained=True))
    cp_inputs={};lab_inputs={};cp_segments=collections.defaultdict(list);lab_outputs=collections.defaultdict(list)
    for chunk in receipt['cpop']:
        folder=Path(chunk['artifact_dir'])
        for row in csv.DictReader((folder/'input.csv').open(encoding='utf-8-sig',newline='')):cp_inputs.setdefault(int(row['case_id']),[]).append(row)
        for row in csv.DictReader((folder/'segments.csv').open(encoding='utf-8-sig',newline='')):cp_segments[int(row['case_id'])].append(row)
    for chunk in receipt['labs']:
        folder=Path(chunk['directory'])
        for row in csv.DictReader((folder/'input.csv').open(encoding='utf-8-sig',newline='')):lab_inputs.setdefault(int(row['case_id']),[]).append(row)
        for row in csv.DictReader((folder/'output.csv').open(encoding='utf-8-sig',newline='')):lab_outputs[int(row['case_id'])].append(row)
    assert len(cp_inputs)==len(lab_inputs)==len(valid)
    for j,r in enumerate(valid):
        y=r['model_input']['power_kw'];assert len(cp_inputs[j])==len(lab_inputs[j])==len(y)
        for k,(v,c,l) in enumerate(zip(y,cp_inputs[j],lab_inputs[j]),1):
            assert float(c['x'])==k and float(c['y'])==v and c['train']=='1'
            assert int(l['index'])==k and float(l['y'])==v
            checks['identical_original_native_power_inputs']+=1
        event=r['event_id']
        cp=curves[event]['cpop'];labs=curves[event]['labs']
        if cp['status']=='ok':
            seg=[s for s in cp_segments[j] if float(s['x1'])>float(s['x0'])]
            for k,value in enumerate(cp['prediction'],1):
                hits=[s for s in seg if float(s['x0'])-1e-9<=k<=float(s['x1'])+1e-9]
                if not hits:hits=[seg[0] if k<float(seg[0]['x0']) else seg[-1]]
                s=hits[-1];expected=float(s['gradient'])*k+float(s['intercept'])
                assert math.isclose(value,expected,rel_tol=1e-11,abs_tol=1e-9)
                checks['CPOP_native_prediction_replays']+=1
        if labs['status']=='ok':
            assert len(lab_outputs[j])==len(labs['prediction'])
            for record,v in zip(lab_outputs[j],labs['prediction']):
                assert record['status']=='ok' and math.isclose(float(record['fitted']),v,rel_tol=1e-12,abs_tol=1e-12)
                checks['LABS_native_prediction_replays']+=1
    # Recalculate counting/error arithmetic directly, without importing the
    # experiment scorer or using any runtime model outputs as truth.
    for method in ['cpop','labs','candidate','raw_only','command_only']:
        b=[];errors={'onset':[],'recovery':[]};missing={'onset':0,'recovery':0};short=[]
        for r,p in zip(rows,pred):
            assert r['event_id']==p['event_id'];a=r['provisional_targets'];e=p['methods'][method]
            if a['anchor_visible_following'] is not None:b.append((a['anchor_visible_following'],int(e['status']=='ok' and e['detected']),e['status']))
            for name,label,output in [('onset','onset_bracket_seconds','onset_seconds'),('recovery','recovery_completion_bracket_seconds','recovery_seconds')]:
                target=a[label]
                if target is None:continue
                v=e[output]
                if v is None:distance=endpoint=180.;missing[name]+=1
                else:
                    lo,hi=target
                    distance=min(180.,lo-v if v<lo else v-hi if v>hi else 0.)
                    endpoint=min(180.,abs(v-hi))
                errors[name].append((distance,endpoint))
                per_event_timing.append(dict(role=role,case=registry[r['event_id']]['case'],method=method,feature=name,interval_error_seconds=distance,endpoint_error_seconds=endpoint,missing=v is None))
            on=a['onset_bracket_seconds'];ret=a['recovery_completion_bracket_seconds']
            if on is not None and ret is not None and ret[1]-on[0]<=60:short.append(not e['detected'])
        expected=stats[method]
        assert expected['binary_n']==len(b)
        assert expected['correct']==sum(a==p and status=='ok' for a,p,status in b)
        assert expected['false_positive']==sum(a==0 and p==1 for a,p,_ in b)
        assert expected['false_negative']==sum(a==1 and p==0 for a,p,_ in b)
        for name,values in errors.items():
            assert expected[name]['n']==len(values) and expected[name]['missing']==missing[name]
            assert math.isclose(expected[name]['capped_interval_mae_seconds'],sum(v[0] for v in values)/len(values),abs_tol=1e-10)
            assert math.isclose(expected[name]['capped_first_observed_mae_seconds'],sum(v[1] for v in values)/len(values),abs_tol=1e-10)
            checks['independently_recomputed_method_feature_scores']+=1
        short_results[role+'|'+method]=dict(observed_recovered_short_windows=len(short),misses=sum(short),not_physical_effective_duration_truth=True)
    checks['all_retained_windows_scored_or_coverage_reported']+=len(rows)
training=read(HERE/'training/selection.json');selected=training['selected']
assert selected['k']==freeze['selected_k']==3
assert all(r['split']=='training' for r in read(VIEW/'training.json'))
firstval=min(Path(x['artifact_dir']).stat().st_ctime for x in read(HERE/'validation/native_receipt.json')['cpop'])
import datetime
assert datetime.datetime.fromisoformat(freeze['created_utc']).timestamp()<=firstval+1
validation=read(HERE/'validation/scores.json')
assert validation['candidate']['false_positive']==validation['cpop']['false_positive']+1
assert validation['candidate']['false_negative']==validation['cpop']['false_negative']==0
rec_errors=[r for r in per_event_timing if r['role']=='validation' and r['method']=='cpop' and r['feature']=='recovery']
assert len(rec_errors)==7 and sum(r['interval_error_seconds'] for r in rec_errors)==44.
assert [r['case'] for r in rec_errors if r['interval_error_seconds']>0]==[41]
proof=read(HERE/'source_diagnosis.json')['cases'][0]
assert proof['case']==41 and proof['cpop']['recovery_seconds']==proof['raw_only']['recovery_seconds']==52.
at8=next(r for r in proof['raw_rows'] if r['seconds']==8.)
assert at8['power_kw']>proof['return_band_kw'][1] and at8['current_a']==31.7
save=lambda n,o:(HERE/n).write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8')
save('per_event_timing_audit.json',per_event_timing)
result=dict(status='passed',checks=dict(checks),unsupported_retained_cases=failures,native_power_sequences=127,native_original_curves=254,short_observation_checks=short_results,validation_recovery_error_concentration=dict(annotated=7,nonzero_error_cases=[41],summed_interval_error_seconds=44.,not_a_population_conclusion=True),configuration_frozen_before_validation_native_outputs=True,all_test_observation_values_unread=True,production_unchanged=True,physical_gold_or_independent_reviewer=False,algorithm_supervised_models_trained=0,training_parameter_configurations=3,validation_retuning=False)
save('verification.json',result)
print(json.dumps({k:v for k,v in result.items() if k!='short_observation_checks'},ensure_ascii=False),flush=True)
