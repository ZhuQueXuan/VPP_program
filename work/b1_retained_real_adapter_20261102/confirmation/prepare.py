from pathlib import Path
import json,hashlib,collections,datetime
import pandas as pd,numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];DATA=ROOT/'data/ACN_real_user_benchmark_v1_20261102';PARENT=HERE.parent
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
freeze_files=[PARENT/'adapter.py',PARENT/'model.json',PARENT/'state_v2/adapter.py',PARENT/'state_v2/model.json',HERE/'protocol.json',HERE/'prepare.py']
(HERE/'before_selection_freeze.json').write_text(json.dumps(dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in freeze_files},before_new_raw_window_review=True),indent=2),encoding='utf-8')
old=read(ROOT/'work/b1_real_labeling_20261102/samples.json')+read(ROOT/'work/b1_real_labeling_extension_20261102/samples.json')
occupied=collections.defaultdict(list)
for r in old:occupied[r['source_path']].append(r['anchor_seconds_from_start'])
used=collections.Counter(r['user_group'] for r in old);manifest={r['path']:r for r in read(DATA/'download_manifest.json')}
profile=[r for r in read(DATA/'development_profile.json')['records'] if r.get('basic_observation_eligible') and r['split']=='validation'];pool=[];counts=collections.Counter()
for r in profile:
    assert r['split']=='validation';df=pd.read_csv(ROOT/r['local'],compression='gzip');stamp=pd.to_datetime(df.iloc[:,0],format='mixed',utc=True);t=(stamp-stamp.iloc[0]).dt.total_seconds().to_numpy();pilot=pd.to_numeric(df['Actual Pilot (A)'],errors='coerce').to_numpy();delta=np.r_[0.,np.diff(pilot)];dt=np.r_[np.nan,np.diff(t)]
    edge=np.flatnonzero((abs(delta)>=.5)&np.isfinite(pilot)&np.r_[False,np.isfinite(pilot[:-1])]&(dt>0)&(dt<=15));candidates=[]
    for i in edge:
        if t[i]<60 or t[-1]-t[i]<180:continue
        later=np.flatnonzero((np.arange(len(t))>i)&np.isfinite(pilot)&(abs(pilot-pilot[i])>=.25));hold=t[later[0]]-t[i] if len(later) else t[-1]-t[i]
        category='short_limit' if hold<=60 else 'small_step' if abs(delta[i])<2 else 'ordinary_step';candidates.append((i,category,float(hold)))
    for target in np.arange(120,t[-1]-180,300):
        i=int(np.searchsorted(t,target));inside=(t>=t[i]-60)&(t<=t[i]+180)
        if np.isfinite(pilot[inside]).all() and np.ptp(pilot[inside])<.25:candidates.append((i,'quiet_limit',240.))
    for i,category,hold in candidates:
        if any(abs(t[i]-v)<240 for v in occupied[r['path']]):continue
        event=hashlib.sha256(('retained-real-confirm-v1|'+r['path']+'|'+str(i)).encode()).hexdigest()
        pool.append(dict(event_id=event,source_path=r['path'],local=r['local'],split='validation',user_group=r['user_group'],station_group=r['station_group'],raw_row_index=int(i),stratum=category,pilot_delta_a=float(delta[i]) if category!='quiet_limit' else 0.,limit_hold_seconds=hold,anchor_timestamp=stamp.iloc[i].isoformat(),anchor_seconds_from_start=float(t[i]),source_sha256=manifest[r['path']]['sha256']));counts[category]+=1
selected=[]
for category in ['short_limit','small_step','ordinary_step','quiet_limit']:
    block=sorted((r for r in pool if r['stratum']==category),key=lambda r:(used[r['user_group']],r['event_id']));chosen=[];users=set()
    for r in block:
        if r['user_group'] in users:continue
        if any(v['source_path']==r['source_path'] and abs(v['anchor_seconds_from_start']-r['anchor_seconds_from_start'])<240 for v in selected+chosen):continue
        users.add(r['user_group']);chosen.append(r)
        if len(chosen)==8:break
    assert len(chosen)==8
    for r in chosen:used[r['user_group']]+=1
    selected+=chosen
selected.sort(key=lambda r:r['event_id']);samples=[]
for number,r in enumerate(selected,129):
    df=pd.read_csv(ROOT/r['local'],compression='gzip');stamp=pd.to_datetime(df.iloc[:,0],format='mixed',utc=True);t=(stamp-pd.Timestamp(r['anchor_timestamp'])).dt.total_seconds().to_numpy();use=np.flatnonzero((t>=-60)&(t<=180));sub=df.iloc[use];s=dict(r,case=number,relative_seconds=t[use].tolist(),raw_row_indices=use.tolist())
    for key,col in [('current_a','Charging Current (A)'),('pilot_a','Actual Pilot (A)'),('power_kw','Power (kW)'),('voltage_v','Voltage (V)'),('energy_kwh','Energy Delivered (kWh)')]:
        v=pd.to_numeric(sub[col],errors='coerce').to_numpy();s[key]=[float(z) if np.isfinite(z) else None for z in v]
    s['charging_state']=[str(v) if pd.notna(v) else None for v in sub['Charging State']];samples.append(s)
write=lambda n,o:(HERE/n).write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
write('selection.json',dict(candidate_counts=dict(counts),selected=selected));write('samples.json',samples)
write('selection_freeze.json',dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),before_labels_and_new_model_outputs=True,files={p.name:sha(p) for p in [HERE/'protocol.json',HERE/'prepare.py',HERE/'selection.json',HERE/'samples.json']},model_freeze_sha256=sha(HERE/'before_selection_freeze.json')))
print(json.dumps(dict(windows=len(samples),users=len({r['user_group'] for r in samples}),new_users=len({r['user_group'] for r in samples}-{r['user_group'] for r in old}),strata=dict(collections.Counter(r['stratum'] for r in samples)),test_read=False)),flush=True)
