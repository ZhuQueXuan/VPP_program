"""All6raw timeseries and event members; core use-specific quality, no model."""
from common import *
import io,zipfile,datetime,math,collections,argparse,re
ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();assert Path(a.run_id).name==a.run_id
out=BASE/'runs'/a.run_id;out.mkdir(exist_ok=False)
archive=BASE/'downloads/KELMARSH_2018_01/Kelmarsh_SCADA_2018_3084.zip';expected=load(BASE/'runs/ARCHIVE_QA_01/receipt.json');assert sha(archive)==expected['archive_sha256']
selected=['Wind speed (m/s)','Wind speed, Standard deviation (m/s)','Power (kW)','Turbine Power setpoint (kW)','Potential power default PC (kW)','Potential power learned PC (kW)']
summary=[];events=[]
with zipfile.ZipFile(archive) as z:
    for name in sorted(z.namelist()):
        with io.TextIOWrapper(z.open(name),encoding='utf-8-sig',newline='') as f:
            comments=[next(f).rstrip('\r\n') for _ in range(9)];assert '# Time zone: UTC' in comments
            reader=csv.reader(f);h=next(reader);unit=int(re.search(r'Kelmarsh_(\d)_',name).group(1));count=0;last=None;seen=set();clock=collections.Counter();first=None
            if name.startswith('Turbine_'):
                assert h[0]=='# Date and time';assert len(h)==len(set(h));positions={k:h.index(k) for k in selected};ranges={k:[] for k in selected};missing=collections.Counter();negative=collections.Counter();overrated=0;core=0
                for values in reader:
                    assert len(values)==len(h);count+=1;t=datetime.datetime.strptime(values[0],'%Y-%m-%d %H:%M:%S');first=first or t
                    clock['duplicate']+=t in seen;seen.add(t)
                    if last is not None:
                        dt=(t-last).total_seconds();clock['backward']+=dt<0;clock['non600s']+=dt!=600
                    last=t;parsed={}
                    for k,j in positions.items():
                        x=float(values[j]);parsed[k]=x
                        if math.isfinite(x):ranges[k].append(x);negative[k]+=x<0
                        else:missing[k]+=1
                    core+=math.isfinite(parsed[selected[0]]) and parsed[selected[0]]>=0 and math.isfinite(parsed[selected[2]])
                    overrated+=math.isfinite(parsed[selected[2]]) and parsed[selected[2]]>2050
                summary.append({'member':name,'unit':unit,'fields':len(h),'rows':count,'first_UTC':first.isoformat()+'Z','last_UTC':last.isoformat()+'Z','clock':dict(clock),'core_wind_nonnegative_and_power_finite':int(core),'core_excluded':count-int(core),'power_above_static_rated_retained':int(overrated),'selected':{k:{'finite':len(ranges[k]),'nonfinite':missing[k],'negative':negative[k],'min':min(ranges[k]) if ranges[k] else None,'max':max(ranges[k]) if ranges[k] else None} for k in selected},'header':h,'comments':comments})
                print(json.dumps({'unit':unit,'rows':count,'core':int(core),'clock':dict(clock)},ensure_ascii=False),flush=True)
            else:
                fields={k:h.index(k) for k in ['Timestamp start','Timestamp end','Status','Code','IEC category']};statuses=collections.Counter();categories=collections.Counter();codes=collections.Counter();openend=0;end_before_start=0;before2018=0;after2018=0
                for values in reader:
                    assert len(values)==len(h);count+=1;t=datetime.datetime.strptime(values[fields['Timestamp start']],'%Y-%m-%d %H:%M:%S');first=first or t
                    if last:clock['backward_start']+=t<last
                    last=t;before2018+=t<datetime.datetime(2018,1,1);after2018+=t>=datetime.datetime(2019,1,1)
                    statuses[values[fields['Status']]]+=1;categories[values[fields['IEC category']]]+=1;codes[values[fields['Code']]]+=1
                    end=values[fields['Timestamp end']]
                    if end=='-':openend+=1
                    else:end_before_start+=datetime.datetime.strptime(end,'%Y-%m-%d %H:%M:%S')<t
                events.append({'member':name,'unit':unit,'rows':count,'start_first_UTC':first.isoformat()+'Z','start_last_UTC':last.isoformat()+'Z','clock':dict(clock),'statuses':dict(statuses),'IEC_categories':dict(categories),'codes_distinct':len(codes),'missing_end':openend,'end_before_start':end_before_start,'starts_before2018':before2018,'starts_at_or_after2019':after2018,'header':h,'interpretation':'Event records,not sampled state trajectory. Missingend marker cannot be assumed ongoing/instantaneous or forward-filled into true unit state. No future forced-outage-week deletion.'})
dump(out/'summary.json',{'archive_sha256':sha(archive),'timeseries':summary,'events':events,'total_rows':sum(r['rows'] for r in summary),'core_rows':sum(r['core_wind_nonnegative_and_power_finite'] for r in summary),'total_event_rows':sum(r['rows'] for r in events),'scope':'Core physical fields and clock checked,source original missing/error markerNaN preserved. No normal-state/curtailment/forecast/model accuracy admission from this QA. Vendor potential-power fields are computed estimates,not independent available-capacity truth.'})
dump(out/'receipt.json',{'status':'source_use_specific_QA_completed_no_fit','script_sha256':sha(Path(__file__)),'outputs':{'summary.json':sha(out/'summary.json')}})
print(json.dumps({'total_rows':sum(r['rows'] for r in summary),'core_rows':sum(r['core_wind_nonnegative_and_power_finite'] for r in summary),'events':events},ensure_ascii=False,indent=2))
