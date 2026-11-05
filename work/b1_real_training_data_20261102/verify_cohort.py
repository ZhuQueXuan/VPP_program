from pathlib import Path
import json,hashlib,gzip,collections
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(name):return json.loads((HERE/name).read_text(encoding='utf-8'))
freeze=read('acn_split_freeze.json')
for name,h in freeze['files'].items():assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==h,name
all_rows=read('acn_split_all.json');selected=read('acn_download_selection.json');downloaded=read('acn_download_manifest.json');assert len(selected)==len(downloaded)==1230
locations=collections.defaultdict(set);roles=collections.defaultdict(set)
for r in all_rows:
    station='-'.join(Path(r['path']).name.split('-')[:4]);locations[station].add((r['site'],r['location']))
    if r['split']!='screening_only':roles[station].add(r['split'])
cross=[dict(station=k,locations=sorted(locations[k]),roles=sorted(roles[k])) for k in roles if len(roles[k])>1]
assert not cross,cross
groups={role:{r['station_group'] for r in selected if r['split']==role} for role in sorted({r['split'] for r in selected})}
for a in groups:
    for b in groups:
        if a!=b:assert not groups[a]&groups[b]
assert len({r['path'] for r in selected})==len(selected)
content=collections.defaultdict(list);size=0
for r in downloaded:
    assert r['status']=='downloaded';p=HERE/r['local'];raw=p.read_bytes();assert len(raw)==r['bytes']
    assert hashlib.sha256(raw).hexdigest()==r['sha256']
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==r['git_blob_sha']
    # Inspect byte integrity only; do not decompress held-out observation values.
    assert raw[:2]==b'\x1f\x8b';content[r['sha256']].append(r['path']);size+=len(raw)
duplicates=[paths for paths in content.values() if len(paths)>1];assert not duplicates
prior=ROOT/'work/b1_residual_false_20261102';protected=json.loads((prior/'protected_before.json').read_text(encoding='utf-8'))
for name,h in protected.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
profile=read('acn_development_profile.json');events=read('response_annotation_candidates.json');index={r['path']:r for r in downloaded}
for e in events:
    assert e['split'] in ['training','validation'] and index[e['source_path']]['split']==e['split']
    assert e['actual_response_present'] is None and e['actual_onset_seconds'] is None and e['actual_end_seconds'] is None
assert len({e['event_id'] for e in events})==len(events)
out=dict(downloaded_files=len(downloaded),verified_compressed_bytes=size,complete_remote_inventory=len(all_rows),all_git_blob_and_sha256_match=True,
    station_groups={k:len(v) for k,v in groups.items()},same_station_cross_split_count=len(cross),same_raw_file_duplicate_count=len(duplicates),vehicle_ids_unavailable_vehicle_disjoint_not_claimed=True,
    heldout_observation_values_not_opened=True,raw_source_values_preserved=True,unreviewed_command_candidates=len(events),candidate_labels_all_unset=True,
    production_files_unchanged=len(protected),trained_models_in_this_task=0)
(HERE/'verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out),flush=True)
