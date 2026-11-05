"""Native KIT observations ->1min sample means, no inserted or repaired points."""
from pathlib import Path
import sys,json,csv,hashlib
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'work/python_packages/pv_metadata_20261015'))
import duckdb

def main():
    source=ROOT/'work/ev_charging_research_20261016/downloads/KIT_LF_SOURCE_01/ev-charging_lf.parquet'
    con=duckdb.connect();con.execute("SET memory_limit='768MB'");con.execute('SET threads=2');con.execute('SET temp_directory=?',[str(HERE/'duckdb_tmp')])
    q="""WITH origin AS (SELECT charging_uuid,min(epoch_us(timestamp_ns)) AS origin_us FROM read_parquet(?) GROUP BY charging_uuid),
    raw AS (SELECT p.charging_uuid::VARCHAR AS recording,epoch_us(p.timestamp_ns) AS t,o.origin_us,
      cast(floor((epoch_us(p.timestamp_ns)-o.origin_us)/60000000) AS BIGINT) AS minute,
      cast(p_l1_w AS DOUBLE)+cast(p_l2_w AS DOUBLE)+cast(p_l3_w AS DOUBLE) AS power_w,setpoint_a
      FROM read_parquet(?) p JOIN origin o USING(charging_uuid))
    SELECT recording,origin_us,minute,count(*) AS raw_n,min(t) AS first_us,max(t) AS last_us,
      avg(power_w)/1000 AS power_kw,count(power_w) AS finite_power_n,min(setpoint_a) AS command_min,max(setpoint_a) AS command_max
      FROM raw GROUP BY recording,origin_us,minute ORDER BY recording,minute"""
    cursor=con.execute(q,[str(source),str(source)]);names=[v[0] for v in cursor.description];rows=[dict(zip(names,r)) for r in cursor.fetchall()]
    with (HERE/'kit_minutes.csv').open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=names);w.writeheader();w.writerows(rows)
    records={}
    for r in rows:records.setdefault(r['recording'],[]).append(r)
    summary=[]
    for uid,rr in records.items():
        runs=[];start=None;previous=None;command=None
        for r in rr+[None]:
            valid=r is not None and r['command_min']==r['command_max'] and r['command_min']>=6 and r['finite_power_n']==r['raw_n'] and r['raw_n']>=1000 and r['last_us']-r['first_us']>=59000000
            if start is not None and (not valid or r['minute']!=previous+1 or r['command_min']!=command):
                runs.append(dict(start_minute=start,end_minute=previous+1,duration_minutes=previous+1-start,command_a=command));start=None
            if valid:
                if start is None:start=r['minute'];command=r['command_min']
                previous=r['minute']
        summary.append(dict(recording=uid,minutes=len(rr),eligible_constant_command_runs=runs,max_run=max((x['duration_minutes'] for x in runs),default=0)))
    (HERE/'kit_coverage.json').write_text(json.dumps(summary),encoding='utf-8')
    print(json.dumps(dict(records=len(records),minute_rows=len(rows),runs_over120=sum(x['duration_minutes']>=120 for r in summary for x in r['eligible_constant_command_runs']),records_with120=sum(r['max_run']>=120 for r in summary),max_hold=max(r['max_run'] for r in summary))),flush=True)
if __name__=='__main__':main()
