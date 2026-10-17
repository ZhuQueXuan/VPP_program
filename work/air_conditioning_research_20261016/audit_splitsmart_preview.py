"""Full QA of ONE small CSV; eight byte prefixes only check source schema."""
from common import *
import argparse,datetime,math,collections,io
ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();assert Path(a.run_id).name==a.run_id
out=BASE/'runs'/a.run_id;out.mkdir(exist_ok=False)
src=BASE/'downloads/SPLITSMART_PREVIEW_01';prefix=BASE/'downloads/SPLITSMART_HEADERS_01'
rec=load(src/'receipt.json');assert all(r['status']=='downloaded' and sha(src/r['name'])==r['sha256'] for r in rec['files'])
pr=load(prefix/'receipt.json');assert len(pr['files'])==8
full=src/'dataC108AC01.csv';rows=read(full);header=list(rows[0]);assert all(header==r['header'].split(',') and sha(prefix/(r['name']+'.prefix'))==r['prefix_sha256'] for r in pr['files'])
times=[datetime.datetime.fromisoformat(r['Time_Stamp']) for r in rows];deltas=[(b-a).total_seconds() for a,b in zip(times,times[1:])]
numeric={}
for k in ['Current','voltage','Power_Factor','Real_Power','room_temp','External_temp','Humidity','unit_consumption']:
    vals=[];bad=0
    for r in rows:
        if not r[k].strip():continue
        try:
            x=float(r[k]);assert math.isfinite(x);vals.append(x)
        except Exception:bad+=1
    numeric[k]={'nonempty':sum(bool(r[k].strip()) for r in rows),'finite_numeric':len(vals),'invalid_nonempty':bad,'distinct_finite':len(set(vals)),'min':min(vals) if vals else None,'max':max(vals) if vals else None}
lag=[(datetime.datetime.fromisoformat(r['_created'].replace('Z','+00:00'))-t).total_seconds() for r,t in zip(rows,times)]
ordered=sorted(deltas)
obj={'full_file':full.name,'full_file_sha256':sha(full),'rows':len(rows),'device_ids':dict(collections.Counter(r['Device_ID'] for r in rows)), 'header':header,
 'timestamp_first':times[0].isoformat(),'timestamp_last':times[-1].isoformat(),'unique_timestamps':len(set(times)),'adjacent_duplicate':sum(x==0 for x in deltas),'backward':sum(x<0 for x in deltas),'interval_min_s':min(deltas),'interval_median_s':__import__('statistics').median(deltas),'interval_max_s':max(deltas),'interval_gt120s':sum(x>120 for x in deltas),
 'created_minus_measurement_timestamp_s':{'min':min(lag),'max':max(lag),'negative':sum(x<0 for x in lag),'note':'Database creation metadata, not proven network latency or delivered control time.'},
 'numeric_fields':numeric,'contexts':{p.name:read(p) for p in sorted(src.glob('*_context.csv'))},
 'eight_other_files':'Only 16KiB prefixes/headers obtained, never full-row QA. Matching 14-column headers; no command/setpoint/on-off/stage column in released schema.',
 'source_license':'Official catalog exact link CC-BY-4.0; attribution Kaushik and Naik, BITS Pilani Goa. Local hashes identify downloaded bytes, no publisher reference checksum supplied.',
 'admission':{'source_metadata_and_one_file_quality':'checked','command_stage_response_validation':False,'independent_real_active_power_validation':False,'room_control_temperature_validation':False},
 'reason':'No explicit delivered command/stage/setpoint/time columns; full checked CSV Real_Power is empty; room_temp has only '+str(numeric['room_temp']['distinct_finite'])+' distinct finite values in '+str(numeric['room_temp']['min'])+' to '+str(numeric['room_temp']['max'])+'. Sensor units/calibration/sampling/updated-time semantics not documented in retrieved source. No synthetic P from I*V*PF, no missing power fill, no propagation of one file quality to other files. Multiple room ACs prevent isolated unit-to-room causal attribution.',
 'correction':'QA_01 summary reason mistakenly said constant room_temp, while its numeric table correctly had 3 distinct values,24.8--25.0. This run corrects prose only, keeping raw data and numerical calculations unchanged; QA_01 remains historical.',
 'scope':'Candidate deferred for present control/dynamic and independent electric-power validation; not claiming all nine files unusable or other Real_Power columns empty; no model fit/errors.'}
dump(out/'summary.json',obj)
dump(out/'receipt.json',{'status':'completed','script_sha256':sha(Path(__file__)),'full_file_sha256':sha(full),'metadata_receipt_sha256':sha(src/'receipt.json'),'prefix_receipt_sha256':sha(prefix/'receipt.json'),'outputs':{'summary.json':sha(out/'summary.json')}})
print(json.dumps({k:v for k,v in obj.items() if k not in ('contexts','header')},ensure_ascii=False,indent=2))
