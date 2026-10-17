"""Actual index/two-roof/day/month audit; keeps raw files unchanged, no model."""
from pathlib import Path
import argparse
from collections import Counter
import csv
import datetime as dt
import hashlib
import json
import math
import re
import sys
import traceback

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
sys.path.insert(0,str(ROOT/'work/python_packages/pv_metadata_20261015'))
import duckdb

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def read_csv(path):
    with path.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))

def finite(value):
    try:return math.isfinite(float(value))
    except (ValueError,TypeError):return False

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-id',required=True)
    args=parser.parse_args()
    out=BASE/'runs'/args.run_id;out.mkdir(parents=True,exist_ok=False)
    source=BASE/'downloads'
    index=read_csv(source/'PVDAQ_INDEX_02/systems.csv')
    assert len(index)==1862
    index_counts=Counter(r['system_id'] for r in index)
    duplicate_index_ids={key:count for key,count in index_counts.items() if count>1}
    assert all(index_counts[str(sid)]==1 for sid in [1239,1277]), 'Candidate metadata must remain unambiguous'
    roofs=[]
    for row in index:
        if finite(row['dc_capacity_kW']) and finite(row['available_sensor_channels']):
            if 1<=float(row['dc_capacity_kW'])<=50 and row['type']=='roof' and row['tracking']=='fixed' and int(row['available_sensor_channels'])>=7:
                roofs.append(row)
    roofs.sort(key=lambda r:(r['qa_status']!='pass',-int(r['available_sensor_channels']),int(r['system_id'])))
    assert [x['system_id'] for x in roofs[:2]]==['1277','1239']
    manifest={};etag_verified=0
    # Each retained source file must still match its acquisition receipt.
    for directory in source.iterdir():
        receipt=directory/'receipt.json'
        if not receipt.exists():continue
        for record in json.loads(receipt.read_text(encoding='utf-8'))['files']:
            if record['status']!='downloaded':continue
            name=record.get('name',record.get('file'));path=directory/name
            assert sha(path)==record['sha256']
            manifest[str(path.relative_to(ROOT))]={'sha256':sha(path),'url':record['url']}
            etag=(record.get('etag') or '').strip('"')
            if re.fullmatch('[0-9a-f]{32}',etag):
                assert hashlib.md5(path.read_bytes()).hexdigest()==etag
                etag_verified+=1
    stats=[];fieldstats=[];dictionaries={}
    for sid in [1277,1239]:
        p=source/f'PVDAQ_METRICS_FILES_01/metrics_{sid}.parquet'
        con=duckdb.connect()
        cursor=con.execute('select * from read_parquet(?)',[str(p)])
        names=[x[0] for x in cursor.description]
        dictionary=[dict(zip(names,x)) for x in cursor.fetchall()]
        dictionaries[str(sid)]=dictionary
        if sid==1277:
            paths=[source/'PVDAQ_CANDIDATE_FILES_01/system_1277_2019_06_15.csv']
        else:
            paths=sorted((source/'PVDAQ_JUNE_FILES_01').glob('*.csv'))+[source/'PVDAQ_CANDIDATE_FILES_01/system_1239_2019_06_15.csv']
            assert len(paths)==30
        dictionary_by_name={x['standard_name']:x for x in dictionary}
        fieldmap={'power':'ac_power_hw__3055','poa':'poa_irradiance__3041','module_temperature':'module_temp_f__3044'} if sid==1277 else {'power':'ac_power_metered_kw__3015','poa':'poa_irradiance__3018','module_temperature':'module_temp_f__3019'}
        for p in paths:
            rows=read_csv(p);timestamps=[dt.datetime.fromisoformat(r['measured_on']) for r in rows]
            assert all(int(r['system_id'])==sid for r in rows)
            assert len(set(timestamps))==len(timestamps) and timestamps==sorted(timestamps)
            dates={x.date() for x in timestamps};assert len(dates)==1
            exact=[x.minute%15==0 and x.second==0 and x.microsecond==0 for x in timestamps]
            all_joint=[all(finite(row[k]) for k in fieldmap.values()) for row in rows]
            quarter=[r for r,ok in zip(rows,exact) if ok]
            stat={'system_id':sid,'date':str(next(iter(dates))),'raw_rows':len(rows),
                  'exact_quarter_rows':sum(exact),'off_grid_rows':len(rows)-sum(exact),
                  'joint_core_finite_rows':sum(all_joint),
                  'exact_quarter_joint_core_finite':sum(a and b for a,b in zip(exact,all_joint)),
                  'nominal_quarters':96,'negative_power_rows':sum(finite(r[fieldmap['power']]) and float(r[fieldmap['power']])<0 for r in rows),
                  'source_path':str(p.relative_to(ROOT))}
            stats.append(stat)
            for name in rows[0]:
                if name in ('measured_on','system_id'):continue
                assert name in dictionary_by_name
                values=[float(r[name]) for r in rows if finite(r[name])]
                fieldstats.append({'system_id':sid,'date':stat['date'],'column':name,
                                   'units':dictionary_by_name[name]['units'],'finite':len(values),
                                   'empty':sum(r[name]=='' for r in rows),'nonfinite_nonempty':sum(r[name]!='' and not finite(r[name]) for r in rows),
                                   'min':min(values) if values else None,'max':max(values) if values else None})
            # Independent SQL parser cross-checks all row/time counts, no model functions involved.
            count,distinct=con.execute('select count(*),count(distinct measured_on) from read_csv_auto(?)',[str(p)]).fetchone()
            assert count==distinct==len(rows)
    # Verify CSV values are already in the published calibrated value space.
    parquet=next((source/'PVDAQ_JUNE_FILES_01').glob('*.parquet'))
    con=duckdb.connect();cur=con.execute('select * from read_parquet(?)',[str(parquet)])
    names=[x[0] for x in cur.description];longrows=[dict(zip(names,r)) for r in cur.fetchall()]
    wide={r['measured_on']:r for r in read_csv(source/'PVDAQ_CANDIDATE_FILES_01/system_1239_2019_06_15.csv')}
    name_by_id={r['metric_id']:r['standard_name'] for r in dictionaries['1239']}
    maximum_difference=0.;utc_offsets=Counter();paired=0
    for row in longrows:
        timestamp=row['measured_on'].strftime('%Y-%m-%d %H:%M:%S')
        expected=wide[timestamp][name_by_id[row['metric_id']]]
        assert finite(expected) and math.isfinite(row['value'])
        maximum_difference=max(maximum_difference,abs(float(expected)-row['value']))
        utc_offsets[str((row['utc_measured_on']-row['measured_on']).total_seconds())]+=1
        paired+=1
    assert maximum_difference<1e-8
    # No raw-to-calibrated scale is applied again to CSV values.
    summary={'status':'completed_source_quality_audit_only','index_rows':len(index),
             'index_unique_ids':len(index_counts),'index_duplicate_ids':duplicate_index_ids,
             'small_fixed_roofs_with_at_least_7_channels':len(roofs),
             'candidate_ids':[1277,1239],'preferred_candidate':1239,
             'preferred_reason':'known manufacturer/model, sufficient core channels, fewer off-grid observations; not model score selection',
             'sensor_dictionary':{'power_units':'W','poa_units':'W/m^2','temperature_units':'C',
                                  'csv_values':'same calibrated values as published Parquet; do not reapply calc_scale/calc_offset',
                                  'raw_units_caution':'temperature raw_units labels are also C despite nonidentity legacy F conversion metadata'},
             'csv_parquet_comparison':{'metric_values':paired,'max_difference':maximum_difference,'utc_minus_local_seconds':dict(utc_offsets)},
             'preferred_month':{'dates':sum(x['system_id']==1239 for x in stats),
                                **{k:sum(x[k] for x in stats if x['system_id']==1239) for k in ['raw_rows','exact_quarter_rows','off_grid_rows','joint_core_finite_rows','exact_quarter_joint_core_finite','negative_power_rows']},
                                'expected_quarters':30*96},
             'single_development_day_other_candidate':[s for s in stats if s['system_id']==1277],
             'source_files_checked':len(manifest),'source_etags_md5_verified':etag_verified,
             'scope':'source/field/quality use only; baseline sample rules, interval alignment, module-to-cell temperature and parameter protocol not yet frozen',
             'no_claims':['new forecast accuracy','verified maximum available output','curtailment/command response','VPP capacity','cross-site transfer']}
    for name,value in [('summary.json',summary),('source_manifest.json',manifest),('sensor_dictionary.json',dictionaries),('roof_candidates.json',roofs)]:
        (out/name).write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
    for name,rows in [('daily_quality.csv',stats),('field_quality.csv',fieldstats)]:
        with (out/name).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    receipt={'run_id':args.run_id,'code_sha256':sha(Path(__file__)), 'output_sha256':{p.name:sha(p) for p in out.iterdir() if p.is_file()},'status':'completed','model_executed':False}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
