"""Bind all original records and clock exclusions before computing any errors."""
from crossseason_common import *
from collections import Counter,defaultdict
from datetime import datetime,timedelta
import math
import pandas as pd
import duckdb
P=frozen()
OUT=BASE/'runs/PREP_CROSSSEASON_02';OUT.mkdir(exist_ok=False,parents=True)
FMT='%Y-%m-%d %H:%M:%S'
raw=[];manifest=[];groups=defaultdict(list)
source_dir=BASE/'downloads/PV_CROSSSEASON_FILES_01'
receipt=json.loads((source_dir/'receipt.json').read_text())
assert len(receipt['files'])==251
sources=[(source_dir,e) for e in receipt['files']]
bd=BASE/'downloads/PVDAQ_SMART_AUGUST_01'
br=json.loads((bd/'receipt.json').read_text())
sources += [(bd,e) for e in br['files'] if e['name']=='system_1239__date_2019_08_31.csv']
assert len(sources)==252
for folder,e in sources:
    assert e['status']=='downloaded',e
    path=folder/e['name'];assert sha(path)==e['sha256']
    assert hashlib.md5(path.read_bytes()).hexdigest()==e['etag'].strip('"')
    manifest.append({**e,'path':path.relative_to(ROOT).as_posix()})
    for i,r in enumerate(read(path),2):
        assert int(float(r['system_id']))==1239
        t=datetime.strptime(r['measured_on'],FMT)
        try:v=float(r['ac_power_metered_kw__3015'])
        except ValueError:v=float('nan')
        row={'time':t.strftime(FMT),'power_W':v if math.isfinite(v) else '',
             'finite':math.isfinite(v),'exact_grid':t.minute%15==0 and t.second==0,
             'source':path.relative_to(ROOT).as_posix(),'source_row':i}
        raw.append(row);groups[t].append(row)
table(OUT/'raw_power_rows.csv',raw);dump(OUT/'source_manifest.json',manifest)
start=datetime(2019,9,1);end=datetime(2020,6,1)
labels=pd.date_range(start-timedelta(minutes=30),end-timedelta(minutes=15),freq='15min')
tz=labels.tz_localize('America/New_York',ambiguous='NaT',nonexistent='NaT')
probe=labels.tz_localize('America/New_York',ambiguous=True,nonexistent='NaT')
clock={t.to_pydatetime():('nonexistent' if pd.isna(probe[i]) else 'ambiguous' if pd.isna(tz[i]) else 'ok',
                        '' if pd.isna(tz[i]) else tz[i].tz_convert('UTC').strftime(FMT)) for i,t in enumerate(labels)}
samples=[]
for target in labels[2:]:
    target=target.to_pydatetime();flags=[];pairflags=[]
    row={'target_time':target.strftime(FMT),'month':target.strftime('%Y-%m')}
    row['season']=next(s for s,months in P['period']['seasons'].items() if row['month'] in months)
    for key,delta in (('target',0),('origin',15),('lag',30)):
        t=target-timedelta(minutes=delta);rr=groups.get(t,[]);cc,utc=clock[t]
        f=[]
        if not rr:f.append(key+'_missing')
        elif len(rr)!=1:f.append(key+'_duplicate')
        elif not rr[0]['finite']:f.append(key+'_nonfinite')
        if cc!='ok':f.append(key+'_'+cc)
        flags+=f
        if key!='lag':pairflags+=f
        row[key+'_time']=t.strftime(FMT);row[key+'_utc']=utc
        row[key+'_clock']=cc;row[key+'_count']=len(rr)
        row[key+'_W']=rr[0]['power_W'] if len(rr)==1 else ''
    for a,b in (('target','origin'),('origin','lag')):
        if row[a+'_utc'] and row[b+'_utc'] and (datetime.strptime(row[a+'_utc'],FMT)-datetime.strptime(row[b+'_utc'],FMT)).total_seconds()!=900:
            flags.append(a+'_'+b+'_utc_step')
            if b!='lag':pairflags.append(a+'_'+b+'_utc_step')
    row['status']='admitted' if not flags else 'excluded'
    row['flags']='|'.join(flags);row['pair_available']=not pairflags
    samples.append(row)
assert len(samples)==26304
table(OUT/'samples.csv',samples)
coverage=[]
for typ,keys in (('month',P['period']['months']),('season',list(P['period']['seasons']))):
    for key in keys:
        rr=[r for r in samples if r[typ]==key];n=sum(r['status']=='admitted' for r in rr)
        coverage.append({'group_type':typ,'group':key,'expected_targets':len(rr),'main_samples':n,'main_fraction':n/len(rr),
                         'pair_samples':sum(r['pair_available'] for r in rr),
                         'excluded_flags':dict(Counter(f for r in rr for f in r['flags'].split('|') if f))})
dump(OUT/'coverage.json',coverage)
clock_results=[];layout=BASE/'downloads/PV_CROSSSEASON_LAYOUT_01'
lr=json.loads((layout/'receipt.json').read_text())
for e in lr['files']:
    if not e['name'].endswith('.parquet'):continue
    if e['status']!='downloaded':clock_results.append(e);continue
    file=layout/e['name'];assert sha(file)==e['sha256']
    pp=duckdb.connect().execute('select measured_on,utc_measured_on,value from read_parquet(?) where metric_id=3015 order by measured_on,utc_measured_on',[str(file)]).fetchall()
    errors=[];excluded_value_mismatches=[];offsets=Counter();ambiguous=0
    for local,utc,value in pp:
        offsets[str((utc-local).total_seconds()/3600)]+=1
        rr=groups.get(local,[])
        cc,cu=clock.get(local,('outside',''))
        if not any(r['power_W']!='' and abs(r['power_W']-value)<1e-9 for r in rr):
            (excluded_value_mismatches if cc=='ambiguous' else errors).append(local.strftime(FMT)+' value')
        if cc=='ok' and cu!=utc.strftime(FMT):errors.append(local.strftime(FMT)+' clock')
        if cc=='ambiguous':ambiguous+=1
        # UTC must round-trip to the published local time even where fold is unknown.
        if pd.Timestamp(utc,tz='UTC').tz_convert('America/New_York').tz_localize(None).to_pydatetime()!=local:errors.append(local.strftime(FMT)+' roundtrip')
    clock_results.append({'file':e['name'],'sha256':e['sha256'],'power_records':len(pp),'utc_minus_local_hours':dict(offsets),'ambiguous_labels':ambiguous,'errors':errors,
                          'excluded_ambiguous_value_mismatches':excluded_value_mismatches})
dump(OUT/'clock_checks.json',clock_results)
qa={'raw_rows_with_boundary':len(raw),'period_raw_rows':sum(start<=datetime.strptime(r['time'],FMT)<end for r in raw),
    'offgrid_rows':sum(not r['exact_grid'] for r in raw),'negative_rows':sum(r['power_W']!='' and r['power_W']<0 for r in raw),
    'nonfinite_rows':sum(not r['finite'] for r in raw),'duplicate_labels':sum(len(v)>1 for v in groups.values()),
    'expected_targets':len(samples),'admitted':sum(r['status']=='admitted' for r in samples),'pair_samples':sum(r['pair_available'] for r in samples),
    'calendar_missing_days':[d.strftime('%Y-%m-%d') for d in pd.date_range(start,end-timedelta(days=1),freq='D') if not any(t.date()==d.date() for t in groups)],
    'clock_diagnostic_errors':sum(len(r.get('errors',[])) for r in clock_results),
    'excluded_ambiguous_clock_value_mismatches':sum(len(r.get('excluded_ambiguous_value_mismatches',[])) for r in clock_results),
    'clock_unavailable_dates':[r['name'] for r in clock_results if r.get('status')!='downloaded' and 'errors' not in r]}
assert qa['clock_diagnostic_errors']==0,qa
dump(OUT/'qa.json',qa)
frozen()
dump(OUT/'admission.json',{'date':'2026-10-16','status':'admitted_for_preregistered_conditional_offline_test','protocol_sha256':sha(BASE/'crossseason_protocol_v1.json'),
    'before_new_prediction_errors':True,'files':{f.name:sha(f) for f in sorted(OUT.iterdir())},'script_sha256':sha(Path(__file__)),'qa':qa})
print(json.dumps(qa,ensure_ascii=False,indent=2))
