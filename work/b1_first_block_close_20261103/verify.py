"""Independent closing checks: retained files, actual input/output, scalar scores and handoff."""
from common import *
import collections,math,csv
import pandas as pd
checks=collections.Counter()
for p,h in read(ROOT/'work/b1_residual_false_20261102/protected_before.json').items():assert sha(ROOT/p)==h,p;checks['production_files_unchanged']+=1
for p,h in read(PREVIOUS/'completion_receipt.json')['artifact_sha256'].items():assert sha(ROOT/p)==h,p;checks['prior_real_adaptation_artifacts_unchanged']+=1
for p,h in read(HERE/'model_freeze.json')['files'].items():assert sha(ROOT/p)==h,p;checks['frozen_model_sources_unchanged']+=1
for name,h in read(HERE/'real_test/label_freeze.json')['files'].items():assert sha(HERE/'real_test'/name)==h,name;checks['frozen_final_labels_unchanged']+=1
amend03=read(HERE/'execution_amendment_03.json');amend04=read(HERE/'execution_amendment_04.json');allowed=dict(amend03['corrected_files']);allowed['work/b1_first_block_close_20261103/evaluate_real.py']=amend04['corrected_evaluate_real_sha256']
for name,h in read(HERE/'evaluation_freeze.json')['files'].items():assert sha(ROOT/name)==allowed.get(name,h),name;checks['evaluation_source_freeze_with_logged_operational_amendments']+=1
assert sha(HERE/'known_test/assessment.json')==amend03['known_assessment_preserved_sha256']
assert sha(HERE/'real_test/predictions.json')==amend04['predictions_preserved_sha256'] and sha(HERE/'real_test/scores.json')==amend04['scores_preserved_sha256']
roles=collections.defaultdict(set)
for r in read(DATA/'download_manifest.json'):
    assert sha(ROOT/r['local'])==r['sha256'];roles[r['user_group']].add(r['split']);checks['original_raw_file_hashes']+=1
assert all(len(r)==1 for r in roles.values())
samples=read(HERE/'real_test/samples.json');rows=read(HERE/'real_test/inputs.json');annotations=read(HERE/'real_test/annotations.json');pred=read(HERE/'real_test/predictions.json');curves=read(HERE/'real_test/native_curves.json');parent,oldmodel=parent_models();newmodel=read(HERE/'candidate_model.json');C=load(HERE/'candidate.py','closing_verify_candidate')
assert len(samples)==len(rows)==len(annotations)==48 and len({r['source_path'] for r in samples})==48
assert collections.Counter(r['stratum'] for r in samples)==dict.fromkeys(['quiet_limit','small_step','ordinary_step','short_limit'],12)
for s,row,ann,old,new in zip(samples,rows,annotations,pred['retained'],pred['candidate']):
    assert s['event_id']==row['event_id']==ann['event_id']==old['event_id']==new['event_id'];assert roles[s['user_group']]=={'test'}
    df=pd.read_csv(ROOT/s['local'],compression='gzip');st=pd.to_datetime(df.iloc[:,0],format='mixed',utc=True);t=(st-pd.Timestamp(s['anchor_timestamp'])).dt.total_seconds().to_numpy();ix=np.flatnonzero((t>=-60)&(t<=180));assert ix.tolist()==s['raw_row_indices'];assert t[ix].tolist()==s['relative_seconds']
    for key,col in [('current_a','Charging Current (A)'),('pilot_a','Actual Pilot (A)'),('power_kw','Power (kW)'),('voltage_v','Voltage (V)'),('energy_kwh','Energy Delivered (kWh)')]:
        actual=pd.to_numeric(df.iloc[ix][col],errors='coerce').to_numpy();stored=np.array([np.nan if v is None else v for v in s[key]]);assert np.allclose(actual,stored,equal_nan=True,rtol=1e-12,atol=1e-12);checks['selected_raw_numeric_values']+=len(ix)
    for key in ['onset_bracket','recovery_completion_bracket']:
        b=ann[key]
        if b is not None:
            indexes=[s['relative_seconds'].index(v) for v in b['relative_seconds']];assert indexes[1]==indexes[0]+1;assert [s['raw_row_indices'][i] for i in indexes]==b['raw_row_indices'];checks['native_annotation_brackets']+=1
    stripped=dict(event_id=row['event_id'],model_input=row['model_input']);cp=curves[row['event_id']]['cpop']['prediction']
    assert native(A.infer(stripped,cp,parent,oldmodel))==old['methods']['candidate'];assert native(C.infer(stripped,cp,parent,newmodel))==new['methods']['candidate'];checks['label_free_frozen_inference_replays']+=2
    assert old['methods']['candidate']['detected']==new['methods']['candidate']['detected'];assert old['methods']['candidate']['onset_seconds']==new['methods']['candidate']['onset_seconds'];checks['event_and_onset_preserved']+=1
# Scalar independent recomputation; do not call the experiment scoring function.
scores=read(HERE/'real_test/scores.json')
for branch in ['retained','candidate']:
  for method in ['cpop','labs','candidate','raw_only','command_only']:
    binary=[];times=collections.defaultdict(list);ends=collections.defaultdict(list);missing=collections.Counter();span=[];spanend=[]
    for row,p in zip(rows,pred[branch]):
        t=row['provisional_targets'];e=p['methods'][method];truth=t['anchor_visible_following']
        if truth is not None:binary.append((truth,e['status']=='ok' and e['detected']))
        for name,key,field in [('onset','onset_bracket_seconds','onset_seconds'),('recovery','recovery_completion_bracket_seconds','recovery_seconds')]:
            target=t[key]
            if target is None:continue
            val=e[field];lo,hi=target;err=180 if val is None else min(180,max(lo-val,val-hi,0));ep=180 if val is None else min(180,abs(val-hi));times[name].append(err);ends[name].append(ep);missing[name]+=val is None
        on=t['onset_bracket_seconds'];rec=t['recovery_completion_bracket_seconds']
        if on is not None and rec is not None:
            value=None if e['onset_seconds'] is None or e['recovery_seconds'] is None else e['recovery_seconds']-e['onset_seconds'];lo=max(0,rec[0]-on[1]);hi=max(0,rec[1]-on[0]);span.append(180 if value is None else min(180,max(lo-value,value-hi,0)));spanend.append(180 if value is None else min(180,abs(value-(rec[1]-on[1]))))
    s=scores[branch][method];assert s['binary_n']==len(binary);assert s['false_positive']==sum(a==0 and b for a,b in binary);assert s['false_negative']==sum(a==1 and not b for a,b in binary)
    for f in times:
        assert s[f]['missing']==missing[f] and s[f]['n']==len(times[f]);assert math.isclose(s[f]['capped_interval_mae_seconds'],np.mean(times[f]),abs_tol=1e-12);assert math.isclose(s[f]['capped_first_observed_mae_seconds'],np.mean(ends[f]),abs_tol=1e-12)
    assert math.isclose(s['observed_span']['interval_mae_seconds'],np.mean(span),abs_tol=1e-12);assert math.isclose(s['observed_span']['endpoint_mae_seconds'],np.mean(spanend),abs_tol=1e-12);checks['real_method_branch_scores_recomputed']+=1
# Check actual native input lists for both independent baselines in each panel.
def groups(path):
    out=collections.defaultdict(list)
    with path.open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):out[int(r['case_id'])].append(r)
    return out
known=read(HERE/'known_test/minute/facts.json')+read(HERE/'known_test/10s/facts.json')
for kind,native_dir,cases in [('real',HERE/'real_test/native_attempt02',samples),('known',HERE/'known_test/native',known)]:
    for method,pattern in [('cpop','cpop/chunk*/*/input.csv'),('labs','labs/chunk*/input.csv')]:
        seen=set()
        for path in native_dir.glob(pattern):
            for case,points in groups(path).items():
                assert case not in seen;seen.add(case);c=cases[case]
                y=np.asarray(c['power_kw']) if kind=='real' else np.asarray(c['reference_kw'])-np.asarray(c['power_kw'])
                assert np.array_equal(np.array([float(r['y']) for r in points]),y);checks['original_native_common_input_cases']+=1
        assert seen==set(range(len(cases)))
# Independently check duration runs, raw accounting and spatial short hits.
outputs=read(HERE/'known_test/outputs.json');metrics=read(HERE/'known_test/metrics.json');lookup={(r['task_id'],r['method']):r for r in metrics};truth={}
for panel in ['minute','10s']:truth.update({r['task_id']:r for r in read(HERE/'known_test'/panel/'truth.json')})
location=[]
for c,o in zip(known,outputs):
    assert c['task_id']==o['task_id'];s=np.asarray(c['starts_s']);e=np.asarray(c['ends_s']);dt=e[0]-s[0];clean=np.asarray(truth[c['task_id']]['true_reduction_kw']);inside=(s>=0)&(s<1800);mask=clean[inside]>=.15;edges=np.diff(np.r_[False,mask,False].astype(int));runs=np.flatnonzero(edges==-1)-np.flatnonzero(edges==1);cum=float(mask.sum()*dt);longest=float(max(runs,default=0)*dt);longest=longest if longest>=30-1e-8 else 0.
    assert math.isclose(o['truth']['cumulative_response_seconds'],cum,abs_tol=1e-8);assert math.isclose(o['truth']['longest_continuous_response_seconds'],longest,abs_tol=1e-8)
    raw=(np.asarray(c['reference_kw'])-np.asarray(c['power_kw']));energy=float(np.sum(raw[inside]*(e-s)[inside])/3600);cleanenergy=float(np.sum(clean[inside]*(e-s)[inside])/3600)
    for method,r in o['methods'].items():
        f=r['features']['selected_curve'];m=lookup[c['task_id'],method];assert math.isclose(m['cumulative_error'],abs(f['cumulative_response_seconds']-cum),abs_tol=1e-8);assert math.isclose(m['longest_error'],abs(f['longest_continuous_response_seconds']-longest),abs_tol=1e-8);assert math.isclose(r['features']['accounting']['request_net_kwh'],energy,abs_tol=1e-10);assert math.isclose(r['eta_raw'],energy/.75,abs_tol=1e-10);assert math.isclose(m['energy_error'],abs(energy-cleanenergy),abs_tol=1e-10);checks['known_duration_and_raw_accounting_cases']+=1
        support=np.asarray(r['localized_threshold_state'],bool) if method=='retained' else np.asarray(r['reduction_interval_kw'])>=.15
        assert support.shape==s.shape
        hit=f['cumulative_response_seconds']>0 and np.any(support[inside]&mask)
        location.append(dict(task_id=c['task_id'],method=method,positive=cum>0,localized_miss=bool(cum>0 and not hit),short_truth=bool(0<cum<=60+1e-8),short_location_miss=bool(0<cum<=60+1e-8 and not hit)))
    cp=o['methods']['cpop']['features']['selected_curve'];ret=o['methods']['retained']['features']['selected_curve']
    assert all(ret[k]==v for k,v in cp.items() if k not in ['cumulative_response_seconds','longest_continuous_response_seconds']);checks['other_known_features_preserved']+=1
loc={method:{k:sum(r[k] for r in location if r['method']==method) for k in ['localized_miss','short_truth','short_location_miss']} for method in ['cpop','labs','retained']}
assert loc['retained']['short_location_miss']<=loc['cpop']['short_location_miss']
decision=read(HERE/'acceptance_decision.json');assert decision['adopt_closing_candidate'] is False and decision['selected_real_branch']=='retained_state_v2';assert scores['retained']['candidate']['recovery']==scores['candidate']['candidate']['recovery']
kh=read(HERE/'handoff/known_features.json');rh=read(HERE/'handoff/real_features.json');assert len(kh)==112 and len(rh)==48;assert all(r['not_filtered_by_positive'] for r in kh+rh);assert any(not r['effective_response_present'] for r in kh);assert all(r['effective_cumulative_seconds'] is None and r['net_response_energy_kwh'] is None for r in rh);assert all(r['offered_incentive'] is None for r in kh+rh)
assert read(HERE/'model_freeze.json')['created_utc']<read(HERE/'evaluation_freeze.json')['created_utc']<read(HERE/'real_test/selection_freeze.json')['created_utc']<read(HERE/'real_test/label_freeze.json')['created_utc']
assert read(HERE/'public_checks.json')['status']=='passed'
audit=dict(summary=loc,rows=location)
report=dict(status='passed',checks=dict(checks),real_test_windows=48,real_test_users=len({r['user_group'] for r in samples}),new_users_disjoint_from_train_validation=True,known_paired_variants=112,known_independent_base_tasks=len({r['base_task_id'] for r in known}),known_seeds=2,public_native_replays=8,short_location=loc,labels_independent_human_gold=False,external_test_values_unread=True,canonical_primary_test_stage_consumed=True,closing_candidate_adopted=False,no_post_test_fit_or_threshold_tuning=True,production_method_unchanged=True,feature_handoff_rows=160,stage_closed_scope='known-reference30minEV; real observed boundaries provisional',remaining_real_false_positives=2,remaining_censored_false_returns=1)
for name,result in [('location_audit.json',audit),('verification.json',report)]:
    if (HERE/name).exists():assert read(HERE/name)==native(result),name
    else:save(name,result)
print(json.dumps(dict(status='passed',checks=dict(checks),short_location=loc)),flush=True)
