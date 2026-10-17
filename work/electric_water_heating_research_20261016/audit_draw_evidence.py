"""Source audit only. Never fits models or changes original/D067 files."""
from pathlib import Path
import argparse, collections, csv, datetime as dt, hashlib, json, math, statistics
import urllib.request, xml.etree.ElementTree as ET
from openpyxl import load_workbook

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent.parent
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p, x): p.write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
def valid(x): return isinstance(x, (int,float)) and not isinstance(x,bool) and math.isfinite(x) and x != -127
def stats(v):
    z=[float(x) for x in v if valid(x)]
    return {'n':len(v),'valid':len(z),'null':sum(x is None for x in v),
            'nonfinite':sum(isinstance(x,(int,float)) and not math.isfinite(x) for x in v),
            'sentinel_minus127':sum(x == -127 for x in v),'nonnumeric':sum(not isinstance(x,(int,float)) for x in v),
            'zero':sum(x==0 for x in z),'negative_valid':sum(x<0 for x in z),
            'min':min(z) if z else None,'max':max(z) if z else None,
            'sum_valid':math.fsum(z) if z else None,'mean_valid':statistics.fmean(z) if z else None}

ap=argparse.ArgumentParser(); ap.add_argument('--run-id',required=True); ap.add_argument('--fetch-metadata',action='store_true'); args=ap.parse_args()
out=BASE/'runs'/args.run_id; out.mkdir(parents=True,exist_ok=False)
protocol=BASE/'draw_evidence_protocol_v1.json'; cfg=read(protocol)
receipt={'run_id':args.run_id,'started_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
         'script_sha256':sha(Path(__file__)),'protocol_sha256':sha(protocol),'model_experiment':False}
try:
    meta_dir=BASE/'downloads'/'DRAW_METADATA_20261017_01'
    if args.fetch_metadata:
        meta_dir.mkdir(exist_ok=False)
        url='https://data.mendeley.com/public-api/datasets/ddmv4w434g'
        req=urllib.request.Request(url,headers={'User-Agent':'VPP-public-source-research/1.0'})
        with urllib.request.urlopen(req,timeout=40) as response:
            raw=response.read(5_000_001)
            if len(raw)>5_000_000: raise ValueError('metadata exceeds limit')
            (meta_dir/'dataset.json').write_bytes(raw)
            dump(meta_dir/'receipt.json',{'url':url,'status':response.status,'bytes':len(raw),
                 'sha256':hashlib.sha256(raw).hexdigest(),'content_type':response.headers.get('Content-Type')})
    metadata=read(meta_dir/'dataset.json'); published={f['filename']:f for f in metadata['files']}
    receipt['fresh_metadata_sha256']=sha(meta_dir/'dataset.json')
    # Preserve every released artifact and the existing temperature protocol.
    releases={}
    for name,rel in [('lithium_ion_storage','release_validation.json'),('distributed_photovoltaic','release_validation_v1_2.json'),
          ('ev_charging','release_validation_v1_1.json'),('air_conditioning','release_validation_v1_1.json'),
          ('wind_power','release_validation_v1_1.json'),('electric_water_heating','release_validation.json')]:
        p=ROOT/'resource_research_results'/name; m=read(p/'results'/rel)
        for f,h in m.get('verified_files',m.get('artifact_sha256',{})).items():
            q=p/f; assert sha(q)==h,(name,f); releases[str(q.relative_to(ROOT))]=h
    assert len(releases)==104
    receipt['original_release_files']=releases
    receipt['original_temperature_protocol_sha256']=sha(BASE/'temperature_protocol_v1.json')
    wb=load_workbook(BASE/'downloads/DICTIONARY_01/Dataset descriptions.xlsx',read_only=True,data_only=True)
    tab=list(wb.active.values); dictionary=[{'description':tab[1][i],'unit_format':tab[4][i]} for i in range(1,len(tab[1]))]
    wb.close(); dump(out/'dictionary_readonly.json',dictionary)
    tree=ET.parse(BASE/'downloads/DICTIONARY_01/data_paper.xml').getroot()
    tables=[''.join(e.itertext()) for e in tree.findall('.//table-wrap')]
    assert any('Energy usage per sample' in s and 'Water usage per sample' in s for s in tables)
    dump(out/'paper_tables.json',tables)
    summaries=[]; records=[]; allflags=[]
    states=['ChamberAirTempReg','GeyserWaterTempReg','InletWaterTempReg','FlowRateReg','WaterScheduleControl',
          'PowerScheduleControl','ChamberHeatingFans','ChamberVentingFans','CirculationFans','ChamberHeatingElement','WaterValveState','GeyserHeatingFlag']
    selected=['DesiredFlowRate','GeyserWaterSetTemp','PowerConsumed','WaterConsumed','TotalWaterConsumed',
              'WaterValveState','GeyserHeatingFlag','InletWaterTemp','OutletWaterTemp','GeyserWaterThermostatTemp','ChamberTempMean','B0-T0','B0-T8']
    for filename in cfg['files']:
        path=BASE/'downloads/CLOCK_CANDIDATES_01'/filename
        official=published[filename]; assert sha(path)==official['content_details']['sha256_hash']
        assert path.stat().st_size==official['size']
        native=read(path); tr=native.get('Trace',native.get('TraceCollection')); assert len(tr)==101
        n=len(tr['TimeStamp']); assert all(len(v)==n for v in tr.values())
        parsed=[]; unitrows=[]
        for i,s in enumerate(tr['TimeStamp']):
            if s=='YYYY-MM-DDTHH:mm:ss': unitrows.append(i); continue
            parsed.append((i,dt.datetime.strptime(s,'%Y-%m-%dT%H:%M:%S')))
        ids=[i for i,t in parsed]; times=[t for i,t in parsed]
        allflags.extend({'file':filename,'row':i,'kind':'explicit_unit_row',
                         'source_values':{k:tr[k][i] for k in tr}} for i in unitrows)
        period=float(native['SamplePeriod']); assert period>0
        fields={k:stats([tr[k][i] for i in ids]) for k in tr if k!='TimeStamp'}
        deltas=[(b-a).total_seconds() for a,b in zip(times,times[1:])]
        invalid=[{'row':i,'field':k,'value':tr[k][i]} for i in ids for k in tr if k!='TimeStamp' and not valid(tr[k][i])]
        invalid_states=[{'row':i,'field':k,'value':tr[k][i]} for i in ids for k in states if tr[k][i] not in (0,1)]
        allflags.extend({'file':filename,**r} for r in invalid+invalid_states)
        water=[tr['WaterConsumed'][i] for i in ids]; energy=[tr['PowerConsumed'][i] for i in ids]
        cumulative=[tr['TotalWaterConsumed'][i] for i in ids]
        runs=[]; start=None
        for j,i in enumerate(ids):
            active=valid(water[j]) and water[j]>0
            if active and start is None: start=j
            if start is not None and (not active or j==len(ids)-1):
                end=j if active else j-1
                runs.append({'first_source_row':ids[start],'last_source_row':ids[end],
                             'first':times[start].isoformat(),'last':times[end].isoformat(),
                             'n':end-start+1,'span_s':(times[end]-times[start]).total_seconds(),
                             'sum_water_mL':math.fsum(water[start:end+1])})
                start=None
        counter=[]
        for offset in (-1,0,1):
            vals=[]
            for j in range(1,len(ids)):
                k=j+offset
                if 0<=k<len(ids) and valid(cumulative[j]) and valid(cumulative[j-1]) and valid(water[k]):
                    vals.append((cumulative[j]-cumulative[j-1])*1000-water[k])
            counter.append({'water_index_offset':offset,'n':len(vals),
                            'mean_absolute_difference_mL':statistics.fmean(map(abs,vals)) if vals else None,
                            'max_absolute_difference_mL':max(map(abs,vals)) if vals else None})
        per=[]
        for j,(i,t) in enumerate(parsed):
            r={'file':filename,'source_row':i,'timestamp':tr['TimeStamp'][i],
               'elapsed_s':(t-times[0]).total_seconds(),'previous_interval_s':deltas[j-1] if j else None}
            r.update({k:tr[k][i] for k in selected})
            r['energy_nominal_equivalent_W']=tr['PowerConsumed'][i]*3600/period if valid(tr['PowerConsumed'][i]) else None
            r['water_nominal_equivalent_Lmin']=tr['WaterConsumed'][i]*60/(1000*period) if valid(tr['WaterConsumed'][i]) else None
            r['selected_invalid_fields']=';'.join(k for k in selected if not valid(tr[k][i]))
            records.append(r); per.append(r)
        groups=[]
        for key,values in [('GeyserHeatingFlag',[0,1]),('WaterValveState',[0,1]),('water_status',['positive','zero','invalid']),('energy_status',['positive','zero','invalid'])]:
            for value in values:
                def group_value(r):
                    if key in ('GeyserHeatingFlag','WaterValveState'): return r[key]
                    x=r['WaterConsumed' if key=='water_status' else 'PowerConsumed']
                    return 'invalid' if not valid(x) else ('positive' if x>0 else ('zero' if x==0 else 'negative'))
                g=[r for r in per if group_value(r)==value]
                groups.append({'group':key,'value':value,'n':len(g),
                               'energy_Wh_sum':math.fsum(r['PowerConsumed'] for r in g if valid(r['PowerConsumed'])) if g else None,
                               'water_mL_sum':math.fsum(r['WaterConsumed'] for r in g if valid(r['WaterConsumed'])) if g else None})
        lastpos=max((j for j,x in enumerate(water) if valid(x) and x>0),default=None)
        summary={'file':filename,'official_id':official['id'],'bytes':path.stat().st_size,'sha256':sha(path),
          'raw_entries':n,'unit_source_rows':unitrows,'data_rows':len(ids),'trace_fields':len(tr),
          'first':times[0].isoformat(),'last':times[-1].isoformat(),'span_s':(times[-1]-times[0]).total_seconds(),
          'timezone':'not supplied','sample_period_metadata_s':period,'interval_counts_s':dict(collections.Counter(deltas)),
          'duplicate_time_count':len(times)-len(set(times)),'backward_steps':sum(x<0 for x in deltas),
          'non_nominal_intervals':sum(x!=period for x in deltas),'field_quality':fields,
          'all_invalid_numeric_cells':len(invalid),'invalid_state_cells':invalid_states,
          'state_counts':{k:dict(collections.Counter(tr[k][i] for i in ids)) for k in states},
          'first_data_sample':{k:tr[k][ids[0]] for k in selected},'last_data_sample':{k:tr[k][ids[-1]] for k in selected},
          'interval_energy_sum_including_first_Wh':math.fsum(x for x in energy if valid(x)),
          'interval_water_sum_including_first_mL':math.fsum(x for x in water if valid(x)),
          'counter_first_L':cumulative[0],'counter_last_L':cumulative[-1],
          'counter_negative_steps':sum(b<a for a,b in zip(cumulative,cumulative[1:]) if valid(a) and valid(b)),
          'counter_alignment_all_offsets':counter,'positive_water_runs':runs,
          'observed_suffix_after_last_positive_water_s':(times[-1]-times[lastpos]).total_seconds() if lastpos is not None else None,
          'heating1_energy0_rows':[i for i in ids if tr['GeyserHeatingFlag'][i]==1 and tr['PowerConsumed'][i]==0],
          'valve0_positive_water_rows':[i for i in ids if tr['WaterValveState'][i]==0 and valid(tr['WaterConsumed'][i]) and tr['WaterConsumed'][i]>0],
          'valve1_zero_water_rows':[i for i in ids if tr['WaterValveState'][i]==1 and tr['WaterConsumed'][i]==0],
          'selected_invalid_source_rows':[i for i in ids if any(not valid(tr[k][i]) for k in selected)],
          'energy_nominal_equivalent_W':stats([r['energy_nominal_equivalent_W'] for r in per]),
          'water_nominal_equivalent_Lmin':stats([r['water_nominal_equivalent_Lmin'] for r in per]),'groups':groups}
        summaries.append(summary)
    dump(out/'source_summary.json',{'files':summaries,'scope':cfg['purpose'],'admission_boundaries':cfg['admission']})
    dump(out/'raw_quality_flags.json',allflags)
    with (out/'rows.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0])); w.writeheader(); w.writerows(records)
    (out/'protocol_snapshot.json').write_bytes(protocol.read_bytes())
    (out/'audit_code_snapshot.py').write_bytes(Path(__file__).read_bytes())
    receipt['status']='completed_source_audit_no_model'
    receipt['source_files']={s['file']:s['sha256'] for s in summaries}
    receipt['source_dictionary_sha256']=sha(BASE/'downloads/DICTIONARY_01/Dataset descriptions.xlsx')
    receipt['paper_xml_sha256']=sha(BASE/'downloads/DICTIONARY_01/data_paper.xml')
    receipt['outputs']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    for f,h in releases.items(): assert sha(ROOT/f)==h
    dump(out/'receipt.json',receipt)
    print(json.dumps({'status':receipt['status'],'rows':len(records),'original_release_files_unchanged':len(releases),
          'files':[{**{k:s[k] for k in ['file','data_rows','interval_counts_s','interval_energy_sum_including_first_Wh','interval_water_sum_including_first_mL','counter_last_L','all_invalid_numeric_cells']},
                    'valve0_positive_water_count':len(s['valve0_positive_water_rows']),
                    'heating1_energy0_count':len(s['heating1_energy0_rows'])} for s in summaries]},indent=2))
except Exception as e:
    receipt.update(status='failed',error=repr(e)); dump(out/'receipt.json',receipt); raise
