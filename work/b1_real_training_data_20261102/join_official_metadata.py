from pathlib import Path
import json,hashlib,collections
HERE=Path(__file__).resolve().parent
inventory=json.loads((HERE/'acn_complete_inventory.json').read_text(encoding='utf-8'));sources=json.loads((HERE/'official_metadata_retry_manifest.json').read_text(encoding='utf-8'));metadata={};lookup={}
for source in sources:
    if source['status']!='downloaded':continue
    value=json.loads((HERE/source['path']).read_text(encoding='utf-8'));rows=value.get('_items',[]) if isinstance(value,dict) else value
    for r in rows:
        tid=r['sessionID'];file=tid.replace('_','-').replace(' ','T').replace(':','-').replace('.','-')+'.csv.gz'
        if file in metadata:assert metadata[file]['sessionID']==tid
        metadata[file]=dict(r,metadata_source=source['path'])
joined=[]
for r in inventory['files']:
    m=metadata.get(Path(r['path']).name)
    if m:
        uid=m.get('userID');user='acn_user_'+hashlib.sha256(('acn-user-v1|'+str(uid)).encode()).hexdigest()[:20] if uid else None
        row=dict(r,user_group=user,session_id=m['sessionID'],metadata_source=m['metadata_source'],metadata_sha256=hashlib.sha256(json.dumps(m,sort_keys=True).encode()).hexdigest(),has_vehicle_identity=False)
        joined.append(row);lookup[r['path']]=row
v1=json.loads((HERE/'acn_download_selection.json').read_text(encoding='utf-8'));roles=collections.defaultdict(set)
for r in v1:
    linked=lookup.get(r['path'])
    if linked and linked['user_group']:roles[linked['user_group']].add(r['split'])
overlap=[dict(user_group=k,roles=sorted(v)) for k,v in roles.items() if len(v)>1]
out=dict(complete_official_sessions=len(metadata),matched_raw_sessions=len(joined),matched_with_user=sum(bool(r['user_group']) for r in joined),unique_matched_users=len({r['user_group'] for r in joined if r['user_group']}),
    matched_locations=dict(collections.Counter(r['location'] for r in joined)),v1_downloads_matched=sum(r['path'] in lookup for r in v1),v1_user_cross_split=overlap,
    all_user_metadata_from_official_public_download=True,vehicle_id_not_provided=True,malformed_2018_2019_responses_excluded=True)
(HERE/'official_raw_join.json').write_text(json.dumps(joined,ensure_ascii=False),encoding='utf-8');(HERE/'official_join_receipt.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out),flush=True)
