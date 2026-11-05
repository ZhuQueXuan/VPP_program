from pathlib import Path
import json,hashlib,collections
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DEST=ROOT/'data/ACN_real_user_benchmark_v1_20261102';DEST.mkdir(exist_ok=False)
def read(name):return json.loads((HERE/name).read_text(encoding='utf-8'))
joined=[r for r in read('official_raw_join.json') if r['user_group']]
seen=set(r['path'] for r in read('acn_development_profile.json')['records'])
for fn in ['acn_early_screening_manifest.json','acn_screening_manifest.json']:seen.update(r['path'] for r in read(fn))
seen_users={r['user_group'] for r in joined if r['path'] in seen}
office_users={r['user_group'] for r in joined if r['site']=='office_01'};external=office_users-seen_users
primary={r['user_group'] for r in joined if r['site']=='caltech'}-office_users
digest=lambda u:hashlib.sha256(('b1-user-split-v2-20261102|'+u).encode()).hexdigest()
fresh=sorted(primary-seen_users,key=digest);n=max(1,round(.15*len(primary)));assert len(fresh)>=2*n
test=set(fresh[:n]);val=set(fresh[n:2*n]);train=primary-test-val
role={u:'training' for u in train};role.update({u:'validation' for u in val});role.update({u:'test' for u in test});role.update({u:'external_test' for u in external})
out=[]
for r in joined:
    if r['user_group'] not in role:continue
    row=dict(r,split=role[r['user_group']],station_group='/'.join([r['site'],r['location'],'-'.join(Path(r['path']).name.split('-')[:4])]))
    row['local']=(DEST/'raw'/r['site']/r['location']/Path(r['path']).name).relative_to(ROOT).as_posix();out.append(row)
assert not any(r['path'] in seen for r in out if r['split'] in ['test','external_test'])
spec=dict(schema='acn.real-user-benchmark.v1',selection='Complete successfully parsed official metadata linked exactly to pinned raw sessionID; exclude unknown user IDs and all previously viewed users from blind roles.',
    source_snapshot_commit=read('acn_split_plan.json')['commit'],official_complete_metadata='Caltech2020,Office2019and2020; failed/truncated earlier exports excluded, not repaired.',
    grouping='all sessions from one official anonymous user stay in one role across all sites; user identity never input feature',
    vehicle_identity_available=False,user_disjoint_not_physical_vehicle_certification=True,
    training_users=len(train),validation_users=len(val),test_users=len(test),external_users=len(external),seen_users_forced_training_or_excluded=len(seen_users),
    session_counts=dict(collections.Counter(r['split'] for r in out)),total_sessions=len(out),raw_bytes=sum(r['bytes'] for r in out),
    labels=dict(response_presence=0,onset_offset=0,clean_power=0,fault=0),
    data_quality='Before modeling:>=60min,>=300 finite current+pilot+power samples,>=.95 finite core fraction; command changes>=2A with gap<=15s create review candidates, never truth. Keep all original files and values.',
    blind_policy='No response-value inspection of test/external until model, labels, metrics, sample sizes and stop rules fixed. Routine iteration uses validation only; one final evaluation per frozen stage.',
    retired_station_split='work/b1_real_training_data_20261102/acn_split_plan.json was acquisition screening, not the final supervised benchmark. Never mix its partitions with this user-group registry.',
    no_current_model_fit=True,no_raw_points_deleted_or_filled=True,research_citation_required=True,mirror_standalone_license_absent_no_redistribution=True)
(DEST/'split_protocol.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf-8');(DEST/'session_manifest.json').write_text(json.dumps(out,ensure_ascii=False),encoding='utf-8')
for name in ['training','validation','test','external_test']:(DEST/(name+'_sessions.json')).write_text(json.dumps([r for r in out if r['split']==name],ensure_ascii=False),encoding='utf-8')
paths=[p for p in DEST.glob('*.json')];(DEST/'split_freeze.json').write_text(json.dumps(dict(before_canonical_download=True,files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}),indent=2),encoding='utf-8')
(HERE/'canonical_dataset_pointer.json').write_text(json.dumps(dict(path=DEST.relative_to(ROOT).as_posix(),protocol='split_protocol.json',manifest='session_manifest.json')),encoding='utf-8')
print(json.dumps(spec),flush=True)
