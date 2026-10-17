"""Actual source-specific QA before selecting any prediction model/scores."""
from common import *
import collections,datetime,math,openpyxl,xml.etree.ElementTree as ET,argparse
ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args()
out=BASE/'runs'/a.run_id;out.mkdir(parents=True,exist_ok=False)
manifest=load(BASE/'downloads/SOURCE_01/dataset.json');metadata={f['filename']:f for f in manifest['files']}
dictionary=BASE/'downloads/DICTIONARY_01/Dataset descriptions.xlsx'
wb=openpyxl.load_workbook(dictionary,read_only=True,data_only=True)
dump(out/'dictionary.json',{ws.title:list(ws.values) for ws in wb})
paper=ET.parse(BASE/'downloads/DICTIONARY_01/data_paper.xml').getroot()
(out/'data_paper.txt').write_text('\n\n'.join(''.join(e.itertext()) for e in paper.findall('.//body//p')+paper.findall('.//table-wrap')),encoding='utf-8')
def dt(s):
    for fmt in ['%Y-%m-%dT%H:%M:%S','%d/%m/%Y %H:%M','%Y/%m/%d %H:%M','%I:%M:%S %p','%H:%M:%S']:
        try:return datetime.datetime.strptime(s,fmt)
        except ValueError:pass
    return None
files=[];selected=[];ranges=[]
for folder in ['NATIVE_CLOCK_01','REGULATION_01','CLOCK_CANDIDATES_01']:
    rec=load(BASE/'downloads'/folder/'receipt.json')
    for item in rec['files']:
        if item['status']!='downloaded':continue
        f=BASE/'downloads'/folder/item['name'];assert sha(f)==metadata[f.name]['content_details']['sha256_hash']
        if f.suffix.lower()!='.json':continue
        d=load(f);tr=d.get('Trace',d.get('TraceCollection'));timekey='TimeStamp' if 'TimeStamp' in tr else 'Timestamp'
        n=len(tr[timekey]);assert len(tr)==101 and all(len(v)==n for v in tr.values())
        parsed=[dt(s) for s in tr[timekey]];tt=[t for t in parsed if t is not None]
        delta=collections.Counter((b-a).total_seconds() for a,b in zip(parsed,parsed[1:]) if a is not None and b is not None)
        keys=['GeyserWaterThermostatTemp','ChamberTempMean','PowerConsumed','WaterConsumed','GeyserHeatingFlag','B0-T0','B0-T8']
        fields={}
        for k in keys:
            values=tr[k];finite=[v for v in values if isinstance(v,(int,float)) and math.isfinite(v) and v!=-127]
            fields[k]={'valid':len(finite),'sentinel_minus127':values.count(-127),'min':min(finite) if finite else None,'max':max(finite) if finite else None,'zero':values.count(0)}
        energy=tr['PowerConsumed'];heat=tr['GeyserHeatingFlag']
        item={'name':f.name,'path':str(f.relative_to(ROOT)).replace('\\','/'),'sha256':sha(f),'n':n,'start':tr[timekey][0],'end':tr[timekey][-1],
          'first_datetime':tt[0].isoformat(),'last_datetime':tt[-1].isoformat(),'sample_period_metadata_s':d['SamplePeriod'],
          'source_time_delta_counts_s':dict(sorted(delta.items())),'unparseable_time_rows':sum(t is None for t in parsed),'duplicate_parseable_time_rows':len(tt)-len(set(tt)),'backward_steps':sum(v for k,v in delta.items() if k<0),
          'fields':fields,'source_header_metadata':{k:v for k,v in d.items() if k not in ['Trace','TraceNames']},
          'energy_Wh_per_sample_from_dictionary':True,'nominal_3000W_Wh_per_sample':3000*d['SamplePeriod']/3600,
          'heating_flag1_energy0_rows':sum(a==1 and b==0 for a,b in zip(heat,energy)),
          'timekey':timekey,'container_key':'Trace' if 'Trace' in d else 'TraceCollection',
          'source_format': 'minute_truncated' if all(len(s)==16 for s in tr[timekey]) else ('time_only_seconds' if tt[0].year==1900 else 'date_seconds')}
        files.append(item)
        if 'heatingreg' in f.name.lower():
            selected.append(item)
            if tt[0].year!=1900:ranges.append((tt[0],tt[-1],f.name))
ranges.sort();overlaps=[]
for i,(s,e,name) in enumerate(ranges):
    for s2,e2,n2 in ranges[i+1:]:
        if s2<=e:overlaps.append([name,n2])
# Original oldCSV has a different header: inspected independently as a source candidate only.
old=BASE/'downloads/CLOCK_CANDIDATES_01/2022_1_18T16_38_36_HeatingAndCoolingData.csv'
rr=read(old);tt=[dt(r['TimeStamp']) for r in rr]
oldsummary={'name':old.name,'rows':len(rr),'fields':len(rr[0]),'first':rr[0]['TimeStamp'],'last':rr[-1]['TimeStamp'],'delta_counts':dict(collections.Counter((b-a).total_seconds() for a,b in zip(tt,tt[1:])))}
summary={'selected_regulation_files':selected,'all_native_json_inspected':files,'regulation_original_rows':sum(r['n'] for r in selected),'regulation_chronological_order':[n for s,e,n in ranges],'regulation_overlapping_experiment_ranges':overlaps,'old_csv_candidate':oldsummary,
 'scope':'Raw field/time/measurement admission only, no fit or prediction error. Different native labels retained; do not invent seconds for truncated records. No assuming single sensor is tank mean or industrial boiler.'}
dump(out/'summary.json',summary)
dump(out/'receipt.json',{'status':'source_QA_completed_no_fit','script_sha256':sha(Path(__file__)),'metadata_sha256':sha(BASE/'downloads/SOURCE_01/dataset.json'),'outputs':{f.name:sha(f) for f in out.iterdir() if f.is_file()}})
print(json.dumps({'regulation_rows':summary['regulation_original_rows'],'overlap':overlaps,'files':[{k:r[k] for k in ['name','n','start','end','source_time_delta_counts_s','source_format']} for r in selected],'oldCSV':oldsummary},indent=2))
