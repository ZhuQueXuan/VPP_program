"""Full LF file quality, not a controller response evaluation."""
from kit_common import *
from collections import Counter
out=BASE/'runs/KIT_SOURCE_QA_01';out.mkdir(parents=True,exist_ok=False)
receipt=load(SOURCE/'receipt.json');assert all(s['status']=='downloaded_and_checksum_verified' for s in receipt['files'])
for s in receipt['files']:assert sha(SOURCE/s['name'])==s['sha256']
record=load(BASE/'downloads/EV_NEXT_SOURCE_01/kit_zenodo_record.json');assert record['metadata']['license']['id']=='cc-by-4.0'
meta=read(SOURCE/'charging.csv');assert len(meta)==18 and len({r['charging_uuid'] for r in meta})==18
con=connection()
schema=con.execute('DESCRIBE SELECT * FROM read_parquet(?)',[str(SOURCE/'ev-charging_lf.parquet')]).fetchall()
dump(out/'schema.json',schema)
dump(out/'parquet_time_schema.json',con.execute("SELECT name,type,converted_type,logical_type FROM parquet_schema(?) WHERE name='timestamp_ns'",[str(SOURCE/'ev-charging_lf.parquet')]).fetchall())
source_counts={str(uid):n for uid,n in con.execute('SELECT charging_uuid,count(*) FROM read_parquet(?) GROUP BY charging_uuid',[str(SOURCE/'ev-charging_lf.parquet')]).fetchall()}
assert set(source_counts)=={r['charging_uuid'] for r in meta}
rows=[]
for r in meta:
    d=trace(con,r['charging_uuid']);t=d['t_us'];dt=np.diff(t);u=d['u'];currents=np.column_stack([d[k] for k in ('i1','i2','i3')])
    nulls={k:int(np.ma.getmaskarray(v).sum()) for k,v in d.items()};assert len(t)==source_counts[r['charging_uuid']]
    v={**r,'rows':len(t),'null_counts':nulls,'first_time_us':int(t[0]),'last_time_us':int(t[-1]),
       'duplicate_time_steps':int(sum(dt==0)),'backward_time_steps':int(sum(dt<0)),
       'minimum_step_us':int(dt.min()),'maximum_step_us':int(dt.max()),'median_step_us':float(np.median(dt)),
       'steps_over50000us':int(sum(dt>50000)),'command_min_A':int(u.min()),'command_max_A':int(u.max()),
       'command_values':sorted(int(x) for x in np.unique(u)),'command_changes':int(sum(u[1:]!=u[:-1])),
       'finite_phase_values':int(np.isfinite(currents).sum()),'negative_phase_values':int(sum((currents<0).ravel())),
       'phase_max_A':[float(currents[:,i].max()) for i in range(3)],'phase_min_A':[float(currents[:,i].min()) for i in range(3)]}
    rows.append(v);print(json.dumps({k:v[k] for k in ('date','car_brand','car_model','rows','backward_time_steps','duplicate_time_steps','command_changes')}),flush=True)
dump(out/'trace_quality.json',rows)
summary={'date':'2026-10-16','source_record':17866847,'version':'1.0.0','license':'CC-BY-4.0 per official metadata and KIT catalog',
 'LF_bytes':422470722,'LF_sha256':sha(SOURCE/'ev-charging_lf.parquet'),'LF_MD5':'0327dae2664c79ecde0bd07166bf6b1d',
 'recorded_sets':len(meta),'vehicle_brand_model_combinations':len({(r['car_brand'],r['car_model']) for r in meta}),'brands':len({r['car_brand'] for r in meta}),
 'raw_rows':sum(r['rows'] for r in rows),'command_changes':sum(r['command_changes'] for r in rows),
 'duplicate_steps':sum(r['duplicate_time_steps'] for r in rows),'backward_steps':sum(r['backward_time_steps'] for r in rows),
 'steps_over50ms':sum(r['steps_over50000us'] for r in rows),'null_values':sum(sum(r['null_counts'].values()) for r in rows),
 'time_semantics':'Column named timestamp_ns actually decoded as Parquet TIMESTAMP in microseconds; see physical/logical schema. Do not interpret it as integer ns or claim microsecond instrument accuracy. Use relative elapsed time, timezone unconfirmed.',
 'scope':'Observed commandA and each phase RMS currentA within original LF trace; one recorded set is not one individual step experiment. No new model/error evaluated.',
 'limits':['Paper abstract/preprint only; attempted public SSRN PDF403, not bypassed.','No22GB HF download.','No physical timestamp/network-arrival or endpoint dispatch-latency proof.','No firm capacity/authorization/departure demand.','Do not transfer Dortmund fitted breakpoints or treat KIT as same vehicle instance.']}
dump(out/'summary.json',summary);dump(out/'receipt.json',{'date':'2026-10-16','status':'source_quality_completed',
 'script_sha256':sha(Path(__file__)),'duckdb_version':duckdb.__version__,'outputs':{f.name:sha(f) for f in sorted(out.iterdir())}})
print(json.dumps(summary,ensure_ascii=False,indent=2))
