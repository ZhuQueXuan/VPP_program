"""Local KIT schema/SoC audit; power columns are documented derived values."""
import sys,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'work/python_packages/pv_metadata_20261015'))
sys.path.insert(0,str(ROOT/'work/python_packages/pyreadr'))
import duckdb
source=ROOT/'work/ev_charging_research_20261016/downloads/KIT_LF_SOURCE_01/ev-charging_lf.parquet'
c=duckdb.connect();c.execute("SET threads=1");c.execute("SET memory_limit='512MB'")
schema=c.execute('DESCRIBE SELECT * FROM read_parquet(?)',[str(source)]).fetchall()
rows=c.execute('SELECT cast(charging_uuid as varchar), count(*), count(soc_percent), count(distinct soc_percent), min(soc_percent),max(soc_percent) FROM read_parquet(?) GROUP BY charging_uuid ORDER BY charging_uuid',[str(source)]).fetchall()
result=dict(columns=[dict(name=r[0],type=r[1]) for r in schema],recordings=len(rows),total_rows=sum(r[1] for r in rows),soc_nonnull_rows=sum(r[2] for r in rows),
    soc_by_recording=[dict(recording=r[0],rows=r[1],soc_rows=r[2],soc_distinct=r[3],soc_min=float(r[4]) if r[4] is not None else None,soc_max=float(r[5]) if r[5] is not None else None) for r in rows],
    acknowledgement_or_fault_columns=[r[0] for r in schema if any(x in r[0].lower() for x in ['fault','error','acknow','execution','status','state','accepted'])],
    external_execution_log_in_published_file_list=False,
    evidence_roles=dict(setpoint='Recorded current setpoint, not command acknowledgement or proof of vehicle execution',soc='State context only, not fast fault labels',
        voltage_current='Same measurement system channels',active_reactive_apparent_power='Publisher explicitly describes calculated, not independent meter ground truth'),
    field_source='https://zenodo.org/records/17866847',hf_in_local_data=False,hf_published_bytes=22382024820,
    hf_scope='Higher-rate voltage/current and same setpoint; not a labelled fault or controller acknowledgement log. No22GB download.')
with (HERE/'kit_schema_evidence.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps({k:v for k,v in result.items() if k not in ['columns','soc_by_recording']}))
