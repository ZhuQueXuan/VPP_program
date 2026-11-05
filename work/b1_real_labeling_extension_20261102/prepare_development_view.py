"""Prepare explicitly weak-labelled development inputs; no learner is fitted."""
from pathlib import Path
import json,collections,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DATA=ROOT/'data/ACN_real_user_benchmark_v1_20261102'
OUT=DATA/'prepared/observed_localization_pilot_v1_20261102';OUT.mkdir(parents=True,exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
samples=read(ROOT/'work/b1_real_labeling_20261102/samples.json')+read(HERE/'samples.json')
labels=read(DATA/'annotations/batch_20261102/first_pass_annotations.json')+read(DATA/'annotations/batch_20261102_b/first_pass_annotations.json')
lookup={r['event_id']:r for r in labels};binary={'observed_change':1,'no_observable_change':0}
data=[];registry=[]
for s in samples:
    assert s['split'] in ['training','validation']
    a=lookup[s['event_id']]
    assert a['split']==s['split'] and a['user_group']==s['user_group']
    targets=dict(window_visible_change=binary.get(a['window_observation_label']),window_label_status=a['window_observation_label'],anchor_visible_following=binary.get(a['anchor_following_label']),anchor_label_status=a['anchor_following_label'],onset_bracket_seconds=a['onset_bracket']['relative_seconds'] if a['onset_bracket'] else None,recovery_completion_bracket_seconds=a['recovery_completion_bracket']['relative_seconds'] if a['recovery_completion_bracket'] else None,recovery_status=a['end_status'],effective_duration_seconds=None,fault_label=None,causal_response_success=None)
    data.append(dict(event_id=s['event_id'],split=s['split'],model_input={k:s[k] for k in ['relative_seconds','current_a','pilot_a','power_kw']},provisional_targets=targets,label_source='single_assistant_first_pass',independent_review_status='pending',physical_gold=False))
    registry.append({k:s[k] for k in ['event_id','case','source_path','local','source_sha256','user_group','station_group','split','raw_row_index','raw_row_indices','anchor_timestamp','stratum']})
assert len(data)==128
roles=collections.defaultdict(set)
for r in registry:roles[r['user_group']].add(r['split'])
assert all(len(v)==1 for v in roles.values())
for r in data:
    assert set(r['model_input'])=={'relative_seconds','current_a','pilot_a','power_kw'}
    n=len(r['model_input']['relative_seconds']);assert all(len(v)==n for v in r['model_input'].values())
    # Ambiguous/NA targets remain null, never false negatives.
    for target,status in [('window_visible_change','window_label_status'),('anchor_visible_following','anchor_label_status')]:
        if r['provisional_targets'][status] not in binary:assert r['provisional_targets'][target] is None
    assert all(r['provisional_targets'][k] is None for k in ['effective_duration_seconds','fault_label','causal_response_success'])
write=lambda n,o:(OUT/n).write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
for role in ['training','validation']:write(role+'.json',[r for r in data if r['split']==role])
write('registry.json',registry)
summary={role:dict(windows=sum(r['split']==role for r in data),users=len({r['user_group'] for r in registry if r['split']==role}),window_visible_change_targets=dict(collections.Counter(str(r['provisional_targets']['window_visible_change']) for r in data if r['split']==role)),anchor_visible_following_targets=dict(collections.Counter(str(r['provisional_targets']['anchor_visible_following']) for r in data if r['split']==role)),onset_brackets=sum(r['split']==role and r['provisional_targets']['onset_bracket_seconds'] is not None for r in data),recovery_brackets=sum(r['split']==role and r['provisional_targets']['recovery_completion_bracket_seconds'] is not None for r in data)) for role in ['training','validation']}
write('readiness.json',dict(status='prepared_for_provisional_observational_development_pilot;not_gold_or_production_training',summary=summary,independent_gold=0,unknown_targets_preserved=True,model_inputs_exclude_user_site_identity_and_labels=True,all_users_preserve_original_roles=True,no_test_inputs_in_view=True,native_points_unchanged=True,learners_fit=0,target_caveats='Visible-change supervision is provisional single-assistant interpretation of recorded observations. Onset/recovery brackets are sampling-scale observations, not calibrated physical intervals. Recoveries are not threshold-defined effective durations. No fault, clean-power or causal success target exists. Exploratory development fits may diagnose feasibility, but do not certify real accuracy or justify production adoption without stronger review and a prospectively locked evaluation.'))
write('view_freeze.json',dict(file_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='view_freeze.json'},source_annotation_files=[str((DATA/'annotations/batch_20261102/first_pass_annotations.json').relative_to(ROOT)).replace('\\','/'),str((DATA/'annotations/batch_20261102_b/first_pass_annotations.json').relative_to(ROOT)).replace('\\','/')],provisional_not_gold=True))
print(json.dumps(dict(prepared_windows=len(data),users=len(roles),summary=summary,learners_fit=0,test_inputs=0)),flush=True)
