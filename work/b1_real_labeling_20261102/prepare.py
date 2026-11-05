from pathlib import Path
import json,hashlib,collections
import pandas as pd,numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DATA=ROOT/'data/ACN_real_user_benchmark_v1_20261102'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
protocol=read(HERE/'protocol.json');profile=read(DATA/'development_profile.json');records=[r for r in profile['records'] if r.get('basic_observation_eligible')];manifest={r['path']:r for r in read(DATA/'download_manifest.json')}
pool=[];stats=collections.Counter()
for r in records:
    assert r['split'] in ['training','validation']
    df=pd.read_csv(ROOT/r['local'],compression='gzip');stamp=pd.to_datetime(df.iloc[:,0],utc=True,format='mixed');t=(stamp-stamp.iloc[0]).dt.total_seconds().to_numpy();pilot=pd.to_numeric(df['Actual Pilot (A)'],errors='coerce').to_numpy();current=pd.to_numeric(df['Charging Current (A)'],errors='coerce').to_numpy();power=pd.to_numeric(df['Power (kW)'],errors='coerce').to_numpy()
    good=np.isfinite(pilot)&np.isfinite(current)&np.isfinite(power);delta=np.r_[0.,np.diff(pilot)];dt=np.r_[np.nan,np.diff(t)];edge=np.flatnonzero((abs(delta)>=.5)&good&np.r_[False,good[:-1]]&(dt>0)&(dt<=15))
    candidates=[]
    for i in edge:
        if t[i]<60 or t[-1]-t[i]<180:continue
        changes_after=np.flatnonzero((np.arange(len(t))>i)&np.isfinite(pilot)&(abs(pilot-pilot[i])>=.25));hold=t[changes_after[0]]-t[i] if len(changes_after) else t[-1]-t[i]
        category='short_limit' if hold<=60 else 'small_step' if abs(delta[i])<2 else 'ordinary_step'
        candidates.append((i,category,float(hold)))
    # Background is selected only from recorded limit history, never from the
    # measured response. It may still contain real physical drift or changes.
    for target in np.arange(120,t[-1]-180,300):
        i=int(np.searchsorted(t,target));inside=(t>=t[i]-60)&(t<=t[i]+180)
        if good[i] and np.isfinite(pilot[inside]).all() and np.ptp(pilot[inside])<.25:candidates.append((i,'quiet_limit',float(240.)))
    for i,category,hold in candidates:
        key=r['path']+'|'+str(i);event=hashlib.sha256(('acn-label-batch-v1|'+key).encode()).hexdigest()
        pool.append(dict(event_id=event,source_path=r['path'],local=r['local'],split=r['split'],user_group=r['user_group'],station_group=r['station_group'],raw_row_index=int(i),stratum=category,pilot_delta_a=float(delta[i]) if category!='quiet_limit' else 0.,limit_hold_seconds=hold,anchor_timestamp=stamp.iloc[i].isoformat(),anchor_seconds_from_start=float(t[i]),source_sha256=manifest[r['path']]['sha256']))
        stats[r['split']+'|'+category]+=1
selected=[]
for role,n in protocol['counts_per_stratum'].items():
    used=collections.Counter()
    for category in ['short_limit','small_step','ordinary_step','quiet_limit']:
        block=sorted([r for r in pool if r['split']==role and r['stratum']==category],key=lambda r:r['event_id']);users=set();chosen=[]
        # At most one case per user in each stratum; prefer users not selected
        # in another stratum, then deterministic hash tie breaking.
        block.sort(key=lambda r:(used[r['user_group']],r['event_id']))
        for r in block:
            if r['user_group'] in users:continue
            users.add(r['user_group']);chosen.append(r)
            if len(chosen)==n:break
        for r in chosen:used[r['user_group']]+=1
        selected+=chosen
assert len(selected)==64,(len(selected),dict(stats))
selected.sort(key=lambda r:r['event_id'])
cache={};samples=[]
for number,r in enumerate(selected,1):
    if r['local'] not in cache:cache[r['local']]=pd.read_csv(ROOT/r['local'],compression='gzip')
    df=cache[r['local']];stamp=pd.to_datetime(df.iloc[:,0],utc=True,format='mixed');ts=(stamp-pd.Timestamp(r['anchor_timestamp'])).dt.total_seconds().to_numpy();use=np.flatnonzero((ts>=-60)&(ts<=180));sub=df.iloc[use]
    sample=dict(r,case=number,relative_seconds=ts[use].tolist(),raw_row_indices=use.tolist(),current_a=pd.to_numeric(sub['Charging Current (A)'],errors='coerce').where(pd.notna(sub['Charging Current (A)']),None).tolist(),pilot_a=pd.to_numeric(sub['Actual Pilot (A)'],errors='coerce').tolist(),power_kw=pd.to_numeric(sub['Power (kW)'],errors='coerce').tolist())
    for k in ['current_a','pilot_a','power_kw']:sample[k]=[float(v) if np.isfinite(v) else None for v in sample[k]]
    samples.append(sample)
(HERE/'selection.json').write_text(json.dumps(dict(candidates_by_stratum=dict(stats),selected=selected,selection_based_on_limit_not_power=True),ensure_ascii=False),encoding='utf-8');(HERE/'samples.json').write_text(json.dumps(samples,ensure_ascii=False,allow_nan=False),encoding='utf-8')
files=[HERE/'protocol.json',HERE/'prepare.py',HERE/'selection.json',HERE/'samples.json'];(HERE/'selection_freeze.json').write_text(json.dumps(dict(files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},before_visual_labels=True,no_test_values_read=True),indent=2),encoding='utf-8')
print(json.dumps(dict(pool=dict(stats),selected=len(samples),users=len({r['user_group'] for r in samples}),by_stratum=dict(collections.Counter(r['stratum'] for r in samples)))),flush=True)
