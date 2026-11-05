from pathlib import Path
import json,hashlib,collections,datetime
HERE=Path(__file__).resolve().parent
inv=json.loads((HERE/'acn_complete_inventory.json').read_text(encoding='utf-8'));screen=set()
for fn in ['acn_early_screening_manifest.json','acn_screening_manifest.json']:
    screen.update(r['path'] for r in json.loads((HERE/fn).read_text(encoding='utf-8')))
def digest(v):return hashlib.sha256(('b1-real-foundation-v1|'+v).encode()).hexdigest()
def station(r):return '/'.join([r['site'],r['location'],'-'.join(Path(r['path']).name.split('-')[:4])])
groups=collections.defaultdict(list)
for r in inv['files']:groups[(r['site'],r['location'])].append(r)
assignment={}
for (site,loc),block in groups.items():
    ids=sorted({station(r) for r in block},key=digest)
    for i,g in enumerate(ids):
        if site=='office_01':role='external_test'
        elif site=='jpl':role='current_only_reserve'
        else:
            # Group station, never time rows; each location contributes unseen
            # stations when it has enough station groups.
            val=max(1,round(len(ids)*.15)) if len(ids)>=3 else 0;test=val
            role='test' if i<test else 'validation' if i<test+val else 'training'
        assignment[g]=role
pool=[]
for r in inv['files']:
    row=dict(r,station_group=station(r),split='screening_only' if r['path'] in screen else assignment[station(r)])
    row['metadata_candidate']=5000<=row['bytes']<=250000
    pool.append(row)
chosen=[];targets=dict(training=700,validation=150,test=150,external_test=200,current_only_reserve=30)
for role,target in targets.items():
    candidates=[r for r in pool if r['split']==role and r['metadata_candidate']]
    # Round-robin station groups, deterministic hash order within each group.
    blocks=collections.defaultdict(list)
    for r in sorted(candidates,key=lambda r:digest(r['path'])):blocks[r['station_group']].append(r)
    keys=sorted(blocks,key=digest);got=[];depth=0
    while len(got)<min(target,len(candidates)):
        for k in keys:
            if depth<len(blocks[k]):got.append(blocks[k][depth])
            if len(got)>=target:break
        depth+=1
    chosen+=got
spec=dict(version='b1-real-foundation-v1',commit=inv['commit'],selection_before_bulk_download=True,selection_uses_only_path_size_station_not_algorithm_or_response=True,
    primary_split_unit='recorded EVSE station group; all sessions and future windows of station stay together',vehicle_id_present=False,
    vehicle_disjointness_not_established=True,screening_files_excluded=len(screen),
    raw_fields='time,current,pilot,voltage,state,energy,power; per-file completeness still pending',
    data_quality='No replacement/deletion of raw points. Development admission:>=60min,>=300 jointly finite current+pilot+power records,>=.95 finite core fraction,>=1 command change of2A with adjacent gap<=15s; does not mean action success or establish onset/fault truth.',
    blind_rule='Do not inspect test/external response curves or algorithm outcomes during development. Manifest checksum and byte integrity only until separately frozen benchmark/labels. Holdout labels not yet built.',
    labels='No exact clean power/onset/offset/fault labels supplied. Pilot is a current limit, not actual response truth or untreated reference. No current synthetic model fitted here.',
    research_use_only_no_redistribution=True,official_source='https://ev.caltech.edu/dataset.html',mirror='https://github.com/tongxin-li/ACN-Data-Static',mirror_standalone_license_absent=True,
    selected_counts=dict(collections.Counter(r['split'] for r in chosen)),all_inventory_split_counts=dict(collections.Counter(r['split'] for r in pool)))
for name,obj in [('acn_split_plan.json',spec),('acn_split_all.json',pool),('acn_download_selection.json',chosen)]:
    p=HERE/name;assert not p.exists();p.write_text(json.dumps(obj,ensure_ascii=False,indent=2 if name.endswith('plan.json') else None),encoding='utf-8')
freeze=dict(files={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ['acn_split_plan.json','acn_split_all.json','acn_download_selection.json']},before_bulk_download=True)
(HERE/'acn_split_freeze.json').write_text(json.dumps(freeze,indent=2),encoding='utf-8')
print(json.dumps(spec),flush=True)
