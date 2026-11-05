"""Read original Parquet rows for preselected short-command returns, all phases."""
import sys,json,os
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'work/python_packages/pv_metadata_20261015'))
sys.path.insert(0,str(ROOT/'work/python_packages/pyreadr'))
import numpy as np
import duckdb

def main():
    suffix='_all_modes' if len(sys.argv)>1 and sys.argv[1]=='all_modes' else ''
    selection_path=HERE/f'pulse_selection{suffix}.json'
    selection=json.loads(selection_path.read_text(encoding='utf-8'));source=ROOT/'work/ev_charging_research_20261016/downloads/KIT_LF_SOURCE_01/ev-charging_lf.parquet'
    out=HERE/f'pulse_raw{suffix}';out.mkdir(exist_ok=False);temp=HERE/f'duckdb_temp{suffix}';temp.mkdir(exist_ok=False)
    c=duckdb.connect();c.execute("SET threads=1");c.execute("SET memory_limit='512MB'");c.execute('SET temp_directory=?',[str(temp)])
    columns=', '.join(f'cast(r.{v}_l{phase}_{unit} as double) AS {v}{phase}' for v,unit in [('i','a'),('p','w'),('u','v')] for phase in [1,2,3])
    query=('SELECT w.event_id, r.file_row_number AS source_row, epoch_us(r.timestamp_ns)-w.edge_time_us AS relative_us, r.setpoint_a AS command, '+columns+
        ' FROM read_parquet(?,file_row_number=true) r JOIN read_json_auto(?) w ON cast(r.charging_uuid as varchar)=w.recording '
        'AND epoch_us(r.timestamp_ns)>=w.edge_time_us-5000000 AND epoch_us(r.timestamp_ns)<w.edge_time_us+15000000 ORDER BY w.event_id,r.file_row_number')
    d=c.execute(query,[str(source),str(selection_path)]).fetchnumpy();rows=[]
    for name,values in d.items():
        assert not np.any(np.ma.getmaskarray(values)), 'Missing raw values must be preserved explicitly, not silently converted: '+name
    for j,item in enumerate(selection):
        use=d['event_id']==item['event_id'];payload={k:np.asarray(v[use]) for k,v in d.items() if k!='event_id'}
        n=len(payload['relative_us']);assert n>0 and np.all(np.diff(payload['source_row'])>0) and np.all(np.diff(payload['relative_us'])>0)
        ix=np.flatnonzero(payload['relative_us']==0);back=np.flatnonzero(payload['relative_us']==item['duration_us'])
        assert len(ix)==len(back)==1
        a,b=int(ix[0]),int(back[0]);assert payload['source_row'][a]==item['source_file_row'] and payload['source_row'][b]==item['return_source_file_row']
        assert payload['command'][a-1]==item['previous_command_A'] and payload['command'][a]==item['new_command_A'] and payload['command'][b]==item['previous_command_A']
        path=out/f'pulse{j:03d}.npz'
        with path.open('xb') as h:np.savez_compressed(h,**payload)
        rows.append(dict(**item,raw_path=path.relative_to(ROOT).as_posix(),samples=n,max_gap_us=int(max(np.diff(payload['relative_us']))),
            phases_preserved=[1,2,3],source_values_unchanged=True))
    with (HERE/f'pulse_extraction{suffix}.json').open('x',encoding='utf-8') as h:json.dump(rows,h,indent=2)
    print(json.dumps(dict(extracted=len(rows),recordings=len({r['recording'] for r in rows}),source_rows=len(d['source_row']),no_interpolation_or_value_changes=True)))
if __name__=='__main__':main()
