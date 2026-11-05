"""Check retained lineage, split isolation, raw-source equality and scalar scores."""
from pathlib import Path
import json,hashlib,collections,math,importlib.util,datetime,csv
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DATA=ROOT/'data/ACN_real_user_benchmark_v1_20261102';CONF=HERE/'confirmation'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
checks=collections.Counter()
spec=importlib.util.spec_from_file_location('frozen_adapter_for_verification',HERE/'state_v2/adapter.py');A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A);P=A.P;B=A.B
parent=read(HERE/'model.json');state=read(HERE/'state_v2/model.json')
from b1_algorithm.process import _local_response as LR
for file in [ROOT/'work/b1_real_localization_pilot_20261102/completion_receipt.json',ROOT/'work/b1_real_labeling_extension_20261102/completion_receipt.json']:
    for name,value in read(file)['artifact_sha256'].items():
        assert sha(ROOT/name)==value,name
        checks['prior_pilot_and_data_artifacts_unchanged']+=1
for name,value in read(ROOT/'work/b1_residual_false_20261102/protected_before.json').items():
    assert sha(ROOT/name)==value,name
    checks['production_files_unchanged']+=1
manifest=read(DATA/'download_manifest.json');roles=collections.defaultdict(set)
for r in manifest:
    roles[r['user_group']].add(r['split']);assert sha(ROOT/r['local'])==r['sha256'];checks['raw_source_file_byte_hashes']+=1
assert all(len(v)==1 for v in roles.values())
for freeze_file,key in [(HERE/'selection_freeze.json','sources'),(HERE/'state_v2/selection_freeze.json','sources'),(CONF/'selection_freeze.json','files'),(CONF/'label_freeze.json','files')]:
    for name,value in read(freeze_file)[key].items():assert sha(freeze_file.parent/name)==value,name
for name,value in read(CONF/'before_selection_freeze.json')['files'].items():assert sha(ROOT/name)==value,name
assert sha(HERE/'model.json')==read(HERE/'selection_freeze.json')['model_sha256']
assert sha(HERE/'state_v2/model.json')==read(HERE/'state_v2/selection_freeze.json')['model_sha256']
train=B.load('training');val=B.load('validation');fresh=read(CONF/'inputs.json');all_rows=train+val+fresh
registry={r['event_id']:r for r in read(B.VIEW/'registry.json')};new_samples=read(CONF/'samples.json');registry.update({r['event_id']:r for r in new_samples})
train_users={registry[r['event_id']]['user_group'] for r in train};val_users={registry[r['event_id']]['user_group'] for r in val+fresh};assert not train_users&val_users
train_ids={r['event_id'] for r in train};assert set(read(HERE/'selection_freeze.json')['training_event_ids'])==train_ids
oof=read(HERE/'training/oof.json');assert {r['event_id'] for r in oof['rows']}<=train_ids and len(oof['rows'])==62
covered=[]
for fold in oof['folds']:
    assert not set(fold['fit_event_ids'])&set(fold['oof_event_ids']);assert set(fold['fit_event_ids']+fold['oof_event_ids'])<=train_ids;covered+=fold['oof_event_ids'];checks['event_user_group_folds']+=1
assert sorted(covered)==sorted(r['event_id'] for r in oof['rows'])
point=read(HERE/'state_v2/training/point_labels.json');selection=read(HERE/'state_v2/training/selection.json')
assert len(point)==235 and sum(r['label'] for r in point)==21
tr_lookup={r['event_id']:r for r in train}
for row in point:
    assert row['event_id'] in train_ids
    target=tr_lookup[row['event_id']]['provisional_targets'];end=target['recovery_completion_bracket_seconds']
    if row['label']==1:assert end is not None and row['time']==end[1]
    else:assert end is None and target['recovery_status'] in A.CENSORED or end is not None and row['time']<end[0]
    checks['source_defined_state_training_labels']+=1
for fold in selection['folds']:
    assert not set(fold['fit_users'])&set(fold['held_users']);assert set(fold['fit_users']+fold['held_users'])<=train_users;checks['recovery_user_group_folds']+=1
# Exact numerical feature lineage on actual negative-direction histories whose
# first observed gap equals the declared feature-step median. No test data or
# fabricated response is needed for this identity check.
curves_by_block=[read(B.HERE/'training/native_curves.json'),read(B.HERE/'validation/native_curves.json'),read(CONF/'native_curves.json')]
blocks=[train,val,fresh]
saved_predictions=[None,read(HERE/'state_v2/validation/predictions.json'),read(CONF/'predictions.json')]
for rows,curves,saved in zip(blocks,curves_by_block,saved_predictions):
    saved_map={r['event_id']:r['methods']['candidate'] for r in saved} if saved is not None else {}
    for row in rows:
        a=B.arrays(row);cp=curves.get(row['event_id'],{}).get('cpop',{}).get('prediction',[])
        expected=A.infer(row,cp,parent,state)
        stripped=dict(event_id=row['event_id'],model_input=row['model_input'])
        assert B.native(A.infer(stripped,cp,parent,state))==B.native(expected)
        checks['public_inference_label_independence_and_replays']+=1
        if saved is not None:
            assert B.native(expected)==saved_map[row['event_id']]
            checks['saved_validation_inference_replayed']+=1
        for name in ['effective_qualification','cumulative_effective_response_seconds','longest_continuous_effective_response_seconds']:assert expected[name] is None
        old=B.estimate(a,cp)
        if old['detected']:assert expected['detected'],row['event_id']
        checks['old_positive_preservation_checks']+=1
        if a is None or len(a['p'])<4:continue
        c=B.context(a);step=float(np.median(np.diff(a['t'])))
        if c['direction']==-1 and np.isclose(a['t'][1]-a['t'][0],step):
            original_case=dict(starts_s=a['t'],ends_s=np.r_[a['t'][1:],a['t'][-1]+step],reference_kw=np.full(len(a['t']),np.median(a['p'][c['pre']])),power_kw=a['p'],sigma=c['sigma_p'])
            original=LR.raw_features(original_case);adapted,_=P.raw50(a)
            assert np.array_equal(original,adapted)
            checks['exact_retained50_feature_matrix_reuse']+=1
# Check what the original native programs actually received, not only the
# prepared JSON. Source observations and both baselines must use the same y.
def csv_groups(path):
    groups=collections.defaultdict(list)
    with path.open(encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream):groups[int(row['case_id'])].append(row)
    return groups
native_seen={'cpop':set(),'labs':set()}
for method,pattern in [('cpop','cpop/chunk*/*/input.csv'),('labs','labs/chunk*/input.csv')]:
    for path in (CONF/'native').glob(pattern):
        inputs=csv_groups(path);outputs=csv_groups(path.with_name('segments.csv' if method=='cpop' else 'output.csv'))
        for case,points in inputs.items():
            assert case not in native_seen[method];native_seen[method].add(case)
            row=fresh[case];y=np.array(row['model_input']['power_kw']);x=np.arange(1,len(y)+1,dtype=float)
            assert np.array_equal(np.array([float(r['y']) for r in points]),y)
            assert np.array_equal(np.array([float(r['x' if method=='cpop' else 'index']) for r in points]),x)
            fitted=curves_by_block[2][row['event_id']][method]['prediction']
            if method=='labs':assert np.array_equal(np.array([float(r['fitted']) for r in outputs[case]]),fitted)
            else:
                segments=[r for r in outputs[case] if float(r['x1'])>float(r['x0'])]
                result=np.full(len(y),np.nan)
                for j,r in enumerate(segments):
                    lo,hi=float(r['x0']),float(r['x1']);mask=(x>=lo-1e-9)&(x<=hi+1e-9)
                    if j==0:mask|=x<lo
                    if j==len(segments)-1:mask|=x>hi
                    result[mask]=float(r['gradient'])*x[mask]+float(r['intercept'])
                assert np.array_equal(result,fitted)
            checks['confirmation_original_native_input_and_output_cases']+=1
assert native_seen['cpop']==native_seen['labs']==set(range(32))
# Read only new validation-role originals and check every selected point/row.
old_samples=read(ROOT/'work/b1_real_labeling_20261102/samples.json')+read(ROOT/'work/b1_real_labeling_extension_20261102/samples.json');occupied=collections.defaultdict(list)
for r in old_samples:occupied[r['source_path']].append(r['anchor_seconds_from_start'])
annotations={r['event_id']:r for r in read(CONF/'annotations.json')}
for s in new_samples:
    assert s['split']=='validation' and roles[s['user_group']]=={'validation'}
    assert all(abs(s['anchor_seconds_from_start']-v)>=240 for v in occupied[s['source_path']]);occupied[s['source_path']].append(s['anchor_seconds_from_start'])
    assert sha(ROOT/s['local'])==s['source_sha256'];df=pd.read_csv(ROOT/s['local'],compression='gzip');stamp=pd.to_datetime(df.iloc[:,0],format='mixed',utc=True);t=(stamp-pd.Timestamp(s['anchor_timestamp'])).dt.total_seconds().to_numpy();use=np.flatnonzero((t>=-60)&(t<=180))
    assert use.tolist()==s['raw_row_indices'] and t[use].tolist()==s['relative_seconds']
    for key,col in [('current_a','Charging Current (A)'),('pilot_a','Actual Pilot (A)'),('power_kw','Power (kW)'),('voltage_v','Voltage (V)'),('energy_kwh','Energy Delivered (kWh)')]:
        actual=pd.to_numeric(df.iloc[use][col],errors='coerce').to_numpy();expected=np.array([np.nan if v is None else v for v in s[key]],float);assert np.allclose(actual,expected,equal_nan=True,rtol=1e-12,atol=1e-12);checks['confirmation_original_numeric_values']+=len(actual)
    for key in ['onset_bracket','recovery_completion_bracket']:
        b=annotations[s['event_id']][key]
        if b is None:continue
        ix=[s['relative_seconds'].index(v) for v in b['relative_seconds']];assert ix[1]==ix[0]+1;assert b['raw_row_indices']==[s['raw_row_indices'][j] for j in ix];checks['confirmation_native_label_brackets']+=1
    checks['confirmation_source_lineages']+=1
# Independently re-score aggregate counts/timing without B.score.
timing_rows=[];short={}
for label,rows,predfile,scorefile in [('seen_validation',val,HERE/'state_v2/validation/predictions.json',HERE/'state_v2/validation/scores.json'),('additional_development',fresh,CONF/'predictions.json',CONF/'scores.json')]:
    predictions=read(predfile);scores=read(scorefile);assert len(predictions)==len(rows)
    for method in ['cpop','labs','candidate','raw_only','command_only']:
        binary=[];errors={'onset':[],'recovery':[]};end_errors={'onset':[],'recovery':[]};missing={'onset':0,'recovery':0};short_misses=[]
        for row,p in zip(rows,predictions):
            assert p['event_id']==row['event_id'];e=p['methods'][method];a=row['provisional_targets'];truth=a['anchor_visible_following']
            if truth is not None:binary.append((truth,int(e['status']=='ok' and e['detected']),e['status']))
            for feature,key,outkey in [('onset','onset_bracket_seconds','onset_seconds'),('recovery','recovery_completion_bracket_seconds','recovery_seconds')]:
                target=a[key]
                if target is None:continue
                value=e[outkey]
                if value is None:dist=ep=180.;missing[feature]+=1
                else:
                    lo,hi=target;dist=min(180.,lo-value if value<lo else value-hi if value>hi else 0.);ep=min(180.,abs(value-hi))
                errors[feature].append(dist);end_errors[feature].append(ep);timing_rows.append(dict(block=label,case=registry[row['event_id']]['case'],method=method,feature=feature,value=value,target=target,interval_error=dist,endpoint_error=ep))
            on=a['onset_bracket_seconds'];end=a['recovery_completion_bracket_seconds']
            if on is not None and end is not None and end[1]-on[0]<=60:short_misses.append(not e['detected'])
        s=scores[method];assert s['binary_n']==len(binary);assert s['correct']==sum(a==p and status=='ok' for a,p,status in binary);assert s['false_positive']==sum(a==0 and p==1 for a,p,_ in binary);assert s['false_negative']==sum(a==1 and p==0 for a,p,_ in binary)
        for feature in errors:
            assert s[feature]['n']==len(errors[feature]) and s[feature]['missing']==missing[feature]
            assert math.isclose(s[feature]['capped_interval_mae_seconds'],sum(errors[feature])/len(errors[feature]),abs_tol=1e-10);assert math.isclose(s[feature]['capped_first_observed_mae_seconds'],sum(end_errors[feature])/len(end_errors[feature]),abs_tol=1e-10);checks['independently_recomputed_method_feature_scores']+=1
        short[label+'|'+method]=dict(observed_short_count=len(short_misses),misses=sum(short_misses),not_physical_effective_duration_truth=True)
label_time=datetime.datetime.fromisoformat(read(CONF/'label_freeze.json')['created_utc']).timestamp();assert label_time<=(CONF/'native_curves.json').stat().st_mtime
before=datetime.datetime.fromisoformat(read(CONF/'before_selection_freeze.json')['created_utc']).timestamp();assert before<=datetime.datetime.fromisoformat(read(CONF/'selection_freeze.json')['created_utc']).timestamp()
freshscore=read(CONF/'scores.json');seen=read(HERE/'state_v2/validation/scores.json')
assert freshscore['candidate']['false_positive']==freshscore['candidate']['false_negative']==0 and freshscore['candidate']['recovery']['missing']==1
assert freshscore['candidate']['recovery']['capped_interval_mae_seconds']==22.875 and freshscore['cpop']['recovery']['capped_interval_mae_seconds']==31.875
result=dict(status='passed',checks=dict(checks),training_event_rows=62,recovery_point_rows=235,recovery_positive_endpoints=21,total_training_recovery_targets_scored=22,old_production_weights_changed=False,old_physical_heads_claimed_transferred=False,additional_windows=32,additional_users=22,new_validation_users=0,confirmation_labels_before_model_outputs=True,all_test_observation_values_unread=True,production_adopt=False,supervision='provisional_single_assistant_not_independent_physical_gold',short_observed_checks=short,confirmed_interval_recovery_error_reduction=1-22.875/31.875,confirmed_endpoint_recovery_error_reduction=1-23.375/31.875,remaining_confirmation_recovery_missing=1,known_early_confirmation_recovery_case=133)
with (HERE/'verification.json').open('w',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
with (HERE/'timing_audit.json').open('w',encoding='utf-8') as f:json.dump(timing_rows,f,ensure_ascii=False,indent=2)
print(json.dumps({k:v for k,v in result.items() if k!='short_observed_checks'},ensure_ascii=False),flush=True)
