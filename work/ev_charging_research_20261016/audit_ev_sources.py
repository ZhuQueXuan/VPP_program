"""Re-admit a published archive by current publisher digest, not old scores.

Only source/quality measurements are calculated here; no model fit/error.
"""
from pathlib import Path
from collections import Counter
import argparse,csv,datetime,hashlib,io,json,math,statistics,zipfile
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
ARCHIVE=ROOT/'data/public_datasets/德国_多特蒙德_电动汽车充电实验/dataset_merged.zip'
META=BASE/'downloads/EV_SOURCE_03/measurements.csv'
ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);args=ap.parse_args();assert Path(args.run_id).name==args.run_id
OUT=BASE/'runs'/args.run_id;OUT.mkdir(parents=True,exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def table(p,rows):
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def num(x):
    try:v=float(x)
    except (ValueError,TypeError):return None
    return v if math.isfinite(v) else None
assert hashlib.md5(ARCHIVE.read_bytes()).hexdigest()=='8459a973f9c196a4f7daa3faf1ee148e'
assert hashlib.md5(META.read_bytes()).hexdigest()=='332378d8e25b2edf808f3f05a610fdc1'
with META.open(encoding='utf-8-sig',newline='') as f:metadata=list(csv.DictReader(f,delimiter=';'))
assert len(metadata)==142
byname={r['meas_name'].casefold():r for r in metadata};assert len(byname)==142
inventory=[];quality=[];matches=set();crc_checks=0;unmapped=[]
with zipfile.ZipFile(ARCHIVE) as z:
    for item in sorted(z.infolist(),key=lambda x:x.filename):
        if not item.filename.endswith('_e.csv'):continue
        key=Path(item.filename).name[:-6].casefold();meta=byname.get(key)
        if meta is None:
            unmapped.append({'member':item.filename,'reason':'No exact metadata meas_name association after casefold only; no fuzzy reassignment.'})
            meta={'car_name':'unmapped','charger':'unmapped','charging_station':'unmapped','plug_type':'unmapped','meas_type':'unmapped',
                  'start_soc_percent':'','end_soc_percent':'','index':'','meas_name':''}
        else:matches.add(key)
        with z.open(item) as stream:
            reader=csv.reader(io.TextIOWrapper(stream,encoding='utf-8-sig',newline=''),delimiter=';')
            header=next(r for r in reader if r);units=next(r for r in reader if r)
            assert len(header)==len(units),(item.filename,'units')
            dd=dict(zip(header,units));cmdcols=[k for k in header if k.startswith('AC_Power_set_ID')]
            inventory.append({'member':item.filename,'bytes_uncompressed':item.file_size,'zip_crc32':format(item.CRC,'08x'),
                'vehicle':meta['car_name'],'mode':meta['charger'],'station':meta['charging_station'],
                'plug_type':meta['plug_type'],'type':meta['meas_type'],'start_soc_metadata':meta['start_soc_percent'],
                'end_soc_metadata':meta['end_soc_percent'],'index':meta['index'],'metadata_key':meta['meas_name'],
                'columns':len(header),'command_columns':'|'.join(cmdcols),
                'power_unit':dd.get('P_kocos_200',''),'command_units':'|'.join(dd[k] for k in cmdcols),
                'epoch_present':'epoch' in header})
            # Consume the complete member to validate its CRC, including static files.
            full=hashlib.sha256();rows=0;length_errors=0
            dynamic='_ts_unidir_arbitrary_1_' in item.filename
            idx={k:i for i,k in enumerate(header)};times=[];pvalues=[];dt=[];missing=Counter();duplicates=0;backwards=0;previous=None
            setvalues={k:[] for k in cmdcols};statevalues={k:set() for k in header if k.startswith(('STATE_ID','ConnectorType_ID','ChargeState_ID'))}
            for r in reader:
                if not r:continue
                rows+=1;full.update((';'.join(r)+'\n').encode('utf-8'))
                if len(r)!=len(header):length_errors+=1;continue
                if not dynamic:continue
                t=num(r[idx['epoch']]) if 'epoch' in idx else None
                v=num(r[idx['P_kocos_200']]) if 'P_kocos_200' in idx else None
                if t is None:missing['epoch']+=1
                else:
                    times.append(t)
                    if previous is not None:
                        gap=t-previous;dt.append(gap);duplicates+=gap==0;backwards+=gap<0
                    previous=t
                if v is None:missing['grid_power']+=1
                else:pvalues.append(v)
                for k in cmdcols:
                    u=num(r[idx[k]])
                    if u is None:missing[k]+=1
                    else:setvalues[k].append(u)
                for k in statevalues:
                    v=num(r[idx[k]])
                    if v is not None:statevalues[k].add(v)
            crc_checks+=1
            if dynamic:
                quality.append({'member':item.filename,'vehicle':meta['car_name'],'mode':meta['charger'],'station':meta['charging_station'],
                    'plug_type':meta['plug_type'],'rows':rows,'row_width_errors':length_errors,'normalized_data_sha256':full.hexdigest(),
                    'epoch_min':min(times) if times else None,'epoch_max':max(times) if times else None,
                    'span_seconds_if_epoch_ms':(max(times)-min(times))/1000 if times else None,
                    'median_positive_step_ms':statistics.median([g for g in dt if g>0]) if any(g>0 for g in dt) else None,
                    'duplicate_epoch_steps':duplicates,'backward_epoch_steps':backwards,
                    'gaps_over_2000ms':sum(g>2000 for g in dt),'missing_core_fields':dict(missing),
                    'grid_power_min_kW':min(pvalues) if pvalues else None,'grid_power_max_kW':max(pvalues) if pvalues else None,
                    'negative_grid_power_rows':sum(v<0 for v in pvalues),
                    'command_ranges':{k:{'min':min(v) if v else None,'max':max(v) if v else None,'distinct_values':len(set(v))} for k,v in setvalues.items()},
                    'observed_state_codes_not_interpreted':{k:sorted(v) for k,v in statevalues.items()}})
        print(json.dumps({'member':item.filename,'rows':rows,'dynamic_v1g':dynamic,'crc':'passed'}),flush=True)
table(OUT/'archive_inventory.csv',inventory);dump(OUT/'dynamic_v1g_quality.json',quality)
table(OUT/'merged_trials_without_exact_metadata.csv',unmapped)
missing_meta=[r for r in metadata if r['meas_name'].casefold() not in matches]
table(OUT/'metadata_trials_absent_from_merged.csv',missing_meta)
cohort=[r for r in inventory if r['type']=='ts_unidir_arbitrary_1' and r['station']=='EVTEC']
summary={'date':'2026-10-16','status':'source_quality_complete_not_response_model_admission',
 'publisher_record':'https://zenodo.org/records/14065331','publisher_version':'2.0.0',
 'archive_path':ARCHIVE.relative_to(ROOT).as_posix(),'archive_bytes':ARCHIVE.stat().st_size,'archive_md5':hashlib.md5(ARCHIVE.read_bytes()).hexdigest(),'archive_sha256':sha(ARCHIVE),
 'current_publisher_md5_matches':True,'metadata_sha256':sha(META),'metadata_md5_matches':True,
 'metadata_trials':len(metadata),'merged_trials':len(inventory),'fully_read_crc_checked_members':crc_checks,
 'metadata_trials_missing_from_merged':len(missing_meta),'merged_trials_without_exact_metadata':len(unmapped),'metadata_counts_by_type':dict(Counter(r['meas_type'] for r in metadata)),
 'merged_counts_by_type':dict(Counter(r['type'] for r in inventory)),
 'dynamic_v1g_files':len(quality),'dynamic_v1g_rows':sum(r['rows'] for r in quality),
 'evtec_dynamic_v1g_files':len(cohort),'evtec_dynamic_v1g_modes':dict(Counter(r['mode'] for r in cohort)),
 'evtec_dynamic_v1g_vehicles':sorted({r['vehicle'] for r in cohort}),
 'all_dynamic_grid_power_units_kW':all(r['power_unit']=='kW' for r in inventory if r['type']=='ts_unidir_arbitrary_1'),
 'all_evtec_command_units_kW':all(all(u=='kW' for u in r['command_units'].split('|')) for r in cohort),
 'dynamic_bad_row_width':sum(r['row_width_errors'] for r in quality),
 'dynamic_duplicate_epoch_steps':sum(r['duplicate_epoch_steps'] for r in quality),'dynamic_backward_steps':sum(r['backward_epoch_steps'] for r in quality),
 'dynamic_gaps_over_2000ms':sum(r['gaps_over_2000ms'] for r in quality),
 'dynamic_missing_grid_power':sum(r['missing_core_fields'].get('grid_power',0) for r in quality),
 'use_allowed':'Field/quality/cohort design only. Model sampling/protocol and connection state dictionary pending. Laboratory known-record response, not operational dispatch.',
 'limits':['Original merged archive previously used in historical work; cannot claim new blind independent data.',
 'Only published merged G/C rows here; no independent raw re-synchronization.',
 'Epoch magnitude/spacing consistent with milliseconds, but per-device update/network arrival/physical timing not independently calibrated.',
 'STATE/ConnectorType numeric codes retained without interpreting missing official dictionary.',
 'No user departure/demand/authorization or station shared-capacity truth; no shiftable capacity/V2G willingness claims.',
 'No model fit/error, source data not redistributed; dataset license unconfirmed separately from article CC-BY4.0.']}
dump(OUT/'summary.json',summary)
dump(OUT/'receipt.json',{'script_sha256':sha(Path(__file__)),'outputs':{f.name:sha(f) for f in sorted(OUT.iterdir())},
 'source_documents':{str(p.relative_to(ROOT)):sha(p) for p in (META,BASE/'downloads/EV_SOURCE_02/esser_2025_paper.pdf')}})
print(json.dumps(summary,ensure_ascii=False,indent=2))
