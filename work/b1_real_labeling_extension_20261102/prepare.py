from pathlib import Path
import json,hashlib,collections,datetime
import pandas as pd,numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DATA=ROOT/'data/ACN_real_user_benchmark_v1_20261102'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
protocol=read(HERE/'protocol.json');old=read(ROOT/'work/b1_real_labeling_20261102/samples.json')
records=[r for r in read(DATA/'development_profile.json')['records'] if r.get('basic_observation_eligible')]
manifest={r['path']:r for r in read(DATA/'download_manifest.json')}
occupied=collections.defaultdict(list)
for r in old:occupied[r['source_path']].append(r['anchor_seconds_from_start'])
used_old=collections.Counter(r['user_group'] for r in old)
pool=[];stats=collections.Counter();skipped=collections.Counter()
for r in records:
    assert r['split'] in ['training','validation']
    df=pd.read_csv(ROOT/r['local'],compression='gzip');stamp=pd.to_datetime(df.iloc[:,0],utc=True,format='mixed');t=(stamp-stamp.iloc[0]).dt.total_seconds().to_numpy()
    pilot=pd.to_numeric(df['Actual Pilot (A)'],errors='coerce').to_numpy()
    delta=np.r_[0.,np.diff(pilot)];dt=np.r_[np.nan,np.diff(t)]
    edge=np.flatnonzero((abs(delta)>=.5)&np.isfinite(pilot)&np.r_[False,np.isfinite(pilot[:-1])]&(dt>0)&(dt<=15))
    candidates=[]
    for i in edge:
        if t[i]<60 or t[-1]-t[i]<180:continue
        changes_after=np.flatnonzero((np.arange(len(t))>i)&np.isfinite(pilot)&(abs(pilot-pilot[i])>=.25))
        hold=t[changes_after[0]]-t[i] if len(changes_after) else t[-1]-t[i]
        category='short_limit' if hold<=60 else 'small_step' if abs(delta[i])<2 else 'ordinary_step'
        candidates.append((i,category,float(hold)))
    for target in np.arange(120,t[-1]-180,300):
        i=int(np.searchsorted(t,target));inside=(t>=t[i]-60)&(t<=t[i]+180)
        if np.isfinite(pilot[inside]).all() and np.ptp(pilot[inside])<.25:candidates.append((i,'quiet_limit',240.))
    for i,category,hold in candidates:
        if any(abs(t[i]-v)<240 for v in occupied[r['path']]):
            skipped[r['split']+'|'+category]+=1;continue
        event=hashlib.sha256(('acn-label-expansion-v1|'+r['path']+'|'+str(i)).encode()).hexdigest()
        pool.append(dict(event_id=event,source_path=r['path'],local=r['local'],split=r['split'],user_group=r['user_group'],station_group=r['station_group'],raw_row_index=int(i),stratum=category,pilot_delta_a=float(delta[i]) if category!='quiet_limit' else 0.,limit_hold_seconds=hold,anchor_timestamp=stamp.iloc[i].isoformat(),anchor_seconds_from_start=float(t[i]),source_sha256=manifest[r['path']]['sha256']))
        stats[r['split']+'|'+category]+=1
selected=[];used=used_old.copy()
for role,n in protocol['counts_per_stratum'].items():
    for category in protocol['strata']:
        block=sorted((r for r in pool if r['split']==role and r['stratum']==category),key=lambda r:(used[r['user_group']],r['event_id']))
        users=set();chosen=[]
        for r in block:
            if r['user_group'] in users:continue
            # Also prevent overlap among newly chosen windows in a source file.
            if any(v['source_path']==r['source_path'] and abs(v['anchor_seconds_from_start']-r['anchor_seconds_from_start'])<240 for v in selected+chosen):continue
            users.add(r['user_group']);chosen.append(r)
            if len(chosen)==n:break
        assert len(chosen)==n,(role,category,len(chosen))
        for r in chosen:used[r['user_group']]+=1
        selected+=chosen
selected.sort(key=lambda r:r['event_id']);samples=[];cache={}
for number,r in enumerate(selected,65):
    if r['local'] not in cache:cache[r['local']]=pd.read_csv(ROOT/r['local'],compression='gzip')
    df=cache[r['local']];stamp=pd.to_datetime(df.iloc[:,0],utc=True,format='mixed');ts=(stamp-pd.Timestamp(r['anchor_timestamp'])).dt.total_seconds().to_numpy();use=np.flatnonzero((ts>=-60)&(ts<=180));sub=df.iloc[use]
    sample=dict(r,case=number,relative_seconds=ts[use].tolist(),raw_row_indices=use.tolist())
    for key,col in [('current_a','Charging Current (A)'),('pilot_a','Actual Pilot (A)'),('power_kw','Power (kW)'),('voltage_v','Voltage (V)'),('cumulative_energy_kwh','Energy Delivered (kWh)')]:
        vals=pd.to_numeric(sub[col],errors='coerce').to_numpy();sample[key]=[float(v) if np.isfinite(v) else None for v in vals]
    sample['charging_state']=[str(v) if pd.notna(v) else None for v in sub['Charging State']]
    samples.append(sample)
assert len(samples)==64
write=lambda name,obj:(HERE/name).write_text(json.dumps(obj,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
write('selection.json',dict(pool_counts=dict(stats),excluded_overlaps=dict(skipped),selected=selected,based_on_pilot_not_actual_response=True))
write('samples.json',samples)
write('selection_freeze.json',dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),before_visual_labels=True,files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE/'protocol.json',HERE/'prepare.py',HERE/'selection.json',HERE/'samples.json']},test_values_read=False))
print(json.dumps(dict(windows=len(samples),users=len({r['user_group'] for r in samples}),new_users=len({r['user_group'] for r in samples}-set(used_old)),combined_users=len({r['user_group'] for r in old+samples}),strata=dict(collections.Counter(r['stratum'] for r in samples)),roles=dict(collections.Counter(r['split'] for r in samples)))),flush=True)
