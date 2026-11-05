from pathlib import Path
import json,hashlib,collections
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DEST=ROOT/'data/ACN_real_user_benchmark_v1_20261102'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
for name,h in read(DEST/'split_freeze.json')['files'].items():assert hashlib.sha256((DEST/name).read_bytes()).hexdigest()==h,name
records=read(DEST/'session_manifest.json');downloads=read(DEST/'download_manifest.json');assert len(records)==len(downloads)==1878
roles=collections.defaultdict(set);paths=set();hashes=collections.defaultdict(list);bytes_total=0
for r in downloads:
    assert r['status']=='downloaded';assert r['path'] not in paths;paths.add(r['path']);roles[r['user_group']].add(r['split'])
    raw=(ROOT/r['local']).read_bytes();assert len(raw)==r['bytes'] and hashlib.sha256(raw).hexdigest()==r['sha256'];assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==r['git_blob_sha']
    hashes[r['sha256']].append(r['path']);bytes_total+=len(raw)
assert all(len(v)==1 for v in roles.values());assert all(len(v)==1 for v in hashes.values())
seen=set(r['path'] for r in read(HERE/'acn_development_profile.json')['records'])
for fn in ['acn_early_screening_manifest.json','acn_screening_manifest.json']:seen.update(r['path'] for r in read(HERE/fn))
seen_users={r['user_group'] for r in records if r['path'] in seen}
assert not any(r['user_group'] in seen_users for r in records if r['split'] in ['test','external_test'])
dev=read(DEST/'development_profile.json');events=read(DEST/'response_annotation_candidates.json');assert len(dev['records'])==sum(r['split'] in ['training','validation'] for r in records)
for r in dev['records']:assert r['split'] in ['training','validation']
for e in events:assert e['actual_response_present'] is None and e['actual_onset_seconds'] is None
original=read(ROOT/'work/b1_residual_false_20261102/protected_before.json')
for name,h in original.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
result=dict(raw_files=len(records),raw_bytes=bytes_total,users=len(roles),users_by_split={role:sum(next(iter(v))==role for v in roles.values()) for role in sorted({r['split'] for r in records})},
    sessions_by_split=dict(collections.Counter(r['split'] for r in records)),cross_user_split_leaks=0,duplicate_source_files=0,all_file_hashes_and_git_blobs_checked=True,
    all_previously_profiled_users_absent_from_blind_roles=True,test_and_external_observation_values_not_opened=True,user_is_not_vehicle_identity=True,
    development_summary=dev['summary'],command_candidates=len(events),candidate_labels_all_unset=True,trained_models=0,production_files_unchanged=len(original))
(DEST/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
