"""One final-test sample; select using time/pilot only, then expose selected raw windows."""
from common import *
import pandas as pd,collections
for p,h in read(HERE/'model_freeze.json')['files'].items():assert sha(ROOT/p)==h,p
evaluation=[p for p in HERE.glob('*.py')]+[HERE/'protocol.json',HERE/'model_freeze.json']
save('evaluation_freeze.json',dict(created_utc=now(),before_test_observations=True,files={p.relative_to(ROOT).as_posix():sha(p) for p in evaluation}))
sessions=read(DATA/'test_sessions.json');manifest={r['path']:r for r in read(DATA/'download_manifest.json')};pool=[];issues=[]
for r in sessions:
    assert r['split']=='test'
    try:
        df=pd.read_csv(ROOT/r['local'],compression='gzip',usecols=['Unnamed: 0','Actual Pilot (A)'])
        stamp=pd.to_datetime(df['Unnamed: 0'],format='mixed',utc=True);t=(stamp-stamp.iloc[0]).dt.total_seconds().to_numpy();pilot=pd.to_numeric(df['Actual Pilot (A)'],errors='coerce').to_numpy()
        if len(t)<300 or t[-1]<3600:issues.append(dict(source=r['path'],reason='short_timestamp_record'));continue
    except Exception as ex:issues.append(dict(source=r['path'],reason=str(ex)));continue
    delta=np.r_[0.,np.diff(pilot)];dt=np.r_[np.nan,np.diff(t)];edges=np.flatnonzero((abs(delta)>=.5)&np.isfinite(pilot)&np.r_[False,np.isfinite(pilot[:-1])]&(dt>0)&(dt<=15));candidates=[]
    for i in edges:
        if t[i]<60 or t[-1]-t[i]<180:continue
        later=np.flatnonzero((np.arange(len(t))>i)&np.isfinite(pilot)&(abs(pilot-pilot[i])>=.25));hold=t[later[0]]-t[i] if len(later) else t[-1]-t[i]
        category='short_limit' if hold<=60 else 'small_step' if abs(delta[i])<2 else 'ordinary_step';candidates.append((i,category,float(hold)))
    for target in np.arange(120,t[-1]-180,300):
        i=int(np.searchsorted(t,target));inside=(t>=t[i]-60)&(t<=t[i]+180)
        if np.isfinite(pilot[inside]).all() and np.ptp(pilot[inside])<.25:candidates.append((i,'quiet_limit',240.))
    for i,category,hold in candidates:
        event=hashlib.sha256(('first-block-close-final-v1|'+r['path']+'|'+str(i)).encode()).hexdigest()
        pool.append(dict(event_id=event,source_path=r['path'],local=r['local'],split='test',user_group=r['user_group'],station_group=r['station_group'],raw_row_index=int(i),stratum=category,pilot_delta_a=float(delta[i]) if category!='quiet_limit' else 0.,limit_hold_seconds=hold,anchor_timestamp=stamp.iloc[i].isoformat(),anchor_seconds_from_start=float(t[i]),source_sha256=manifest[r['path']]['sha256']))
selected=[];used=collections.Counter();sources=set()
for category in ['short_limit','small_step','ordinary_step','quiet_limit']:
    count=0
    while count<12:
        candidates=sorted((r for r in pool if r['stratum']==category and r['source_path'] not in sources),key=lambda r:(used[r['user_group']],r['event_id']))
        if not candidates:break
        r=candidates[0];selected.append(r);sources.add(r['source_path']);used[r['user_group']]+=1;count+=1
save('real_test/selection.json',dict(created_utc=now(),selected=selected,candidate_counts=dict(collections.Counter(r['stratum'] for r in pool)),issues=issues,selection_channels=['timestamps','actual_pilot'],not_power_or_current_selected=True))
samples=[]
for case,r in enumerate(sorted(selected,key=lambda r:r['event_id']),201):
    df=pd.read_csv(ROOT/r['local'],compression='gzip');stamp=pd.to_datetime(df.iloc[:,0],format='mixed',utc=True);t=(stamp-pd.Timestamp(r['anchor_timestamp'])).dt.total_seconds().to_numpy();use=np.flatnonzero((t>=-60)&(t<=180));sub=df.iloc[use];s=dict(r,case=case,relative_seconds=t[use].tolist(),raw_row_indices=use.tolist())
    for key,col in [('current_a','Charging Current (A)'),('pilot_a','Actual Pilot (A)'),('power_kw','Power (kW)'),('voltage_v','Voltage (V)'),('energy_kwh','Energy Delivered (kWh)')]:
        v=pd.to_numeric(sub[col],errors='coerce').to_numpy();s[key]=[float(z) if np.isfinite(z) else None for z in v]
    s['charging_state']=[str(v) if pd.notna(v) else None for v in sub['Charging State']];samples.append(s)
save('real_test/samples.json',samples);save('real_test/selection_freeze.json',dict(created_utc=now(),before_labels_and_inference=True,files={n:sha(HERE/'real_test'/n) for n in ['selection.json','samples.json']},evaluation_freeze_sha256=sha(HERE/'evaluation_freeze.json')))
print(json.dumps(dict(windows=len(samples),users=len(used),strata=dict(collections.Counter(r['stratum'] for r in samples)),issue_count=len(issues))),flush=True)
