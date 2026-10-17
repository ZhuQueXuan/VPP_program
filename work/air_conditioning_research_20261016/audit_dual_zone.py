"""Audit all original8 CSV; no regression, future errors or data editing."""
from common import *
import argparse,datetime,math,statistics,collections
ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();assert Path(a.run_id).name==a.run_id
out=BASE/'runs'/a.run_id;out.mkdir(exist_ok=False)
metadata=load(BASE/'downloads/DUAL_ZONE_METADATA_01/dataset.json');src=BASE/'downloads/DUAL_ZONE_DATA_01';receipt=load(src/'receipt.json')
assert len(metadata['files'])==len(receipt['files'])==8
expected={r['filename']:r for r in metadata['files']}
files=[];total=0
for entry in receipt['files']:
    fp=src/entry['name'];e=expected[fp.name];assert entry['status']=='downloaded' and fp.stat().st_size==e['size'] and sha(fp)==e['content_details']['sha256_hash']
    rows=read(fp);header=list(rows[0]);assert len(header)==7
    times=[datetime.datetime.strptime(r['Timestamp'],'%Y-%m-%d %H:%M') for r in rows];interval=[(b-a).total_seconds() for a,b in zip(times,times[1:])]
    nums={}
    for field in header[1:]:
        vals=[];invalid=0
        for r in rows:
            try:x=float(r[field]);assert math.isfinite(x);vals.append(x)
            except Exception:invalid+=1
        nums[field]={'finite':len(vals),'invalid':invalid,'distinct':len(set(vals)),'min':min(vals) if vals else None,'max':max(vals) if vals else None,'negative':sum(v<0 for v in vals),'zero':sum(v==0 for v in vals)}
    files.append({'file':fp.name,'sha256':sha(fp),'rows':len(rows),'columns':header,'first_timestamp':times[0].isoformat(),'last_timestamp':times[-1].isoformat(),'timestamp_timezone_explicit':all(t.tzinfo is not None for t in times),'adjacent_duplicate':sum(x==0 for x in interval),'backward':sum(x<0 for x in interval),'non300s_intervals':sum(x!=300 for x in interval),'min_interval_s':min(interval),'max_interval_s':max(interval),'numeric':nums})
    total+=len(rows)
obj={'metadata_sha256':sha(BASE/'downloads/DUAL_ZONE_METADATA_01/dataset.json'),'total_rows':total,'file_count':len(files),'files':files,
 'license':metadata['data_licence']['short_name'],'publisher_reference_sha256_all_match':True,
 'field_limits':'CSV unit labels C/W and solar MJ/m2 retained. Solar accumulation interval not supplied, not converted to W/m2 or used as instantaneous irradiance. Timestamp naive; no assumed timezone or second-level sync. No explicit setpoint/delivered command/stage in7columns. Power averaging/availability timing and device meter boundary are not fully documented in released files; only conditional record-level prediction considered, not causal capacity/control response.',
 'paper':'Crossref registers Choi etal Energy and Buildings10.1016/j.enbuild.2026.118112, volume issue Nov2026, registration Aug22. SSRN10.2139/ssrn.6828065 abstract describesRCnetwork measured-data model; preprint fetch403, full method/parameters not locally obtained at audit. No transfer of reported peak/cost savings to our experiment.',
 'no_fitting_or_scores':True}
dump(out/'summary.json',obj);dump(out/'receipt.json',{'status':'completed','script_sha256':sha(Path(__file__)),'outputs':{'summary.json':sha(out/'summary.json')}})
print(json.dumps({'total_rows':total,'file_count':len(files),'files':[{k:v for k,v in f.items() if k not in ['numeric','columns','sha256']} for f in files],'ranges':{k:[min(f['numeric'][k]['min'] for f in files),max(f['numeric'][k]['max'] for f in files)] for k in files[0]['numeric']},'invalid':sum(v['invalid'] for f in files for v in f['numeric'].values())},ensure_ascii=False,indent=2))
