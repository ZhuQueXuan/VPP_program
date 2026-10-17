"""Prepare one test event and history-only voltage-span proxies, never score models."""
from pathlib import Path
import argparse, json, hashlib, sys, platform, io, zipfile
from datetime import datetime
import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--run-id',required=True)
args=parser.parse_args()
if not args.run_id.isidentifier(): raise ValueError('simple unique run ID required')
OUT=ROOT/'home_capacity_sample_runs'/args.run_id
if OUT.exists(): raise FileExistsError(OUT)
protocol_path=ROOT/'home_capacity_crossperiod_protocol_v4.json'
protocol=json.loads(protocol_path.read_text('utf-8'))
def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1048576),b''): digest.update(chunk)
    return digest.hexdigest()
admission_file=ROOT/protocol['source']['relative_directory']/protocol['source']['admission_receipt']
admission=json.loads(admission_file.read_text('utf-8'))
if admission['status'] not in ('admitted_frozen_history_proxy_only','raw_history_not_admitted') or admission['protocol_sha256']!=sha(protocol_path): raise ValueError('no matching admission')
history_admitted=admission['status']=='admitted_frozen_history_proxy_only'
sources=admission['source_members']
for source in sources:
    if sha(ROOT/source['path'])!=source['sha256']: raise ValueError('source fingerprint mismatch')
start=pd.Timestamp(protocol['information']['history_start_inclusive'])
cutoff=pd.Timestamp(protocol['information']['history_end_exclusive'])
expected=int((cutoff-start).total_seconds())
parts=[]
for source in sources if history_admitted else []:
    for chunk in pd.read_csv(ROOT/source['path'],chunksize=250000):
        ct=pd.to_datetime(chunk['Time'],format='%d-%b-%Y %H:%M:%S',errors='raise')
        selected_chunk=chunk.loc[(ct>=start)&(ct<cutoff)]
        if len(selected_chunk): parts.append(selected_chunk)
frame=pd.concat(parts,ignore_index=True) if parts else pd.DataFrame(columns=['Time','P_in_W','V_in_V','I_in_A','T_Bat_in_C','T_Room_in_C','Interpolated'])
times=pd.to_datetime(frame['Time'],format='%d-%b-%Y %H:%M:%S',errors='raise')
if history_admitted and (len(frame)!=expected or not np.array_equal(times.to_numpy(),pd.date_range(start,periods=expected,freq='s').to_numpy())):
    raise ValueError('raw native prefix differs from frozen continuous history; do not repair')
if len(frame) and not times.iloc[-1]<cutoff: raise ValueError('future history contamination')
columns=['P_in_W','V_in_V','I_in_A','T_Bat_in_C','T_Room_in_C']
finite=np.isfinite(frame[columns].to_numpy(dtype=float)).all(axis=1)
measured=frame['Interpolated'].to_numpy()==0
current=frame['I_in_A'].to_numpy(dtype=float)
voltage=frame['V_in_V'].to_numpy(dtype=float)
power=frame['P_in_W'].to_numpy(dtype=float)
rp=protocol['rest_proxy']
rest=finite&measured&(np.abs(current)<=rp['absolute_current_max_a'])
changes=np.diff(np.r_[False,rest,False].astype(np.int8))
starts=np.flatnonzero(changes==1)
ends=np.flatnonzero(changes==-1)
rest_records=[]; anchors=[]
for index,(begin,end) in enumerate(zip(starts,ends)):
    duration=int(end-begin)
    row={'rest_id':f'rest_{index:05}','start':str(times.iloc[begin]),'end_exclusive':str(start+pd.Timedelta(seconds=int(end))),
         'observed_duration_seconds':duration,'status':'too_short','anchor_time':None,'voltage_proxy_per_cell_v':None}
    if duration>=rp['minimum_consecutive_seconds']:
        anchor=int(begin+rp['minimum_consecutive_seconds']-1)
        tail=int(rp['voltage_tail_seconds'])
        vc=float(np.median(voltage[anchor-tail+1:anchor+1])/protocol['source']['series_cells'])
        kind='high' if vc>=rp['high_voltage_min_v_per_series_cell'] else 'low' if vc<=rp['low_voltage_max_v_per_series_cell'] else 'middle'
        row.update(status=kind,anchor_time=str(times.iloc[anchor]),voltage_proxy_per_cell_v=vc)
        anchors.append({'rest_id':row['rest_id'],'kind':kind,'index':anchor,'time':str(times.iloc[anchor]),'voltage_proxy_per_cell_v':vc})
    rest_records.append(row)
quality_bad=(~(finite&measured)).astype(np.int64)
bad_prefix=np.r_[0,np.cumsum(quality_bad)]
clean_i=np.where(np.isfinite(current),current,0.0)
clean_ui=np.where(np.isfinite(current*voltage),current*voltage,0.0)
clean_p=np.where(np.isfinite(power),power,0.0)
ci=np.r_[0.0,np.cumsum(clean_i)]
cui=np.r_[0.0,np.cumsum(clean_ui)]
cp=np.r_[0.0,np.cumsum(clean_p)]
cc=np.r_[0.0,np.cumsum(np.maximum(clean_i,0))]
cd=np.r_[0.0,np.cumsum(np.maximum(-clean_i,0))]
pending=None; candidates=[]; orphans=[]; replaced=[]
for anchor in anchors:
    if anchor['kind']=='high':
        if pending is not None: replaced.append({'previous_high':pending['time'],'replacement_high':anchor['time']})
        pending=anchor
    elif anchor['kind']=='low':
        if pending is None:
            orphans.append({'low_anchor':anchor['time'],'reason':'no_known_high'})
            continue
        a,b=pending['index'],anchor['index']
        bad=int(bad_prefix[b+1]-bad_prefix[a])
        capacity=-(ci[b]-ci[a])/3600
        energy=-(cui[b]-cui[a])/3600000
        status='quality_failure' if bad else 'nonpositive_net' if capacity<=0 or energy<=0 else 'eligible_proxy'
        candidates.append({'pair_id':f'pair_{len(candidates):04}','high_anchor':pending['time'],'low_anchor':anchor['time'],
                           'available_at_native':anchor['time'],'high_voltage_proxy_cell_v':pending['voltage_proxy_per_cell_v'],
                           'low_voltage_proxy_cell_v':anchor['voltage_proxy_per_cell_v'],'duration_seconds':b-a,'quality_bad_rows_inclusive':bad,
                           'status':status,'net_capacity_ah':None if bad else float(capacity),
                           'net_UI_energy_kwh':None if bad else float(energy),'P_column_energy_kwh_diagnostic':None if bad else float(-(cp[b]-cp[a])/3600000),
                           'gross_charge_ah_diagnostic':None if bad else float((cc[b]-cc[a])/3600),'gross_discharge_ah_diagnostic':None if bad else float((cd[b]-cd[a])/3600)})
        pending=None
eligible=[r for r in candidates if r['status']=='eligible_proxy']
selected=max(eligible,key=lambda r:(r['low_anchor'],r['high_anchor'])) if eligible else None
feature={'sample_id':protocol['sample']['sample_id'],'system_id':protocol['source']['system_id'],
         'history_unavailability_reason':'raw_history_not_admitted' if not history_admitted else 'no_eligible_span' if selected is None else '',
         'nominal_capacity_ah':protocol['source']['nominal_capacity_ah'],'nominal_energy_kwh':protocol['source']['nominal_energy_kwh'],
         'datasheet_usable_energy_kwh':protocol['source']['datasheet_usable_energy_kwh'],'history_cutoff':str(cutoff),
         'history_proxy_available':selected is not None,'selected_pair_id':None if selected is None else selected['pair_id'],
         'history_net_capacity_ah':None if selected is None else selected['net_capacity_ah'],
         'history_net_UI_energy_kwh':None if selected is None else selected['net_UI_energy_kwh'],
         'history_anchor_age_seconds':None if selected is None else float((cutoff-pd.Timestamp(selected['low_anchor'])).total_seconds())}
OUT.mkdir(parents=True)
def table(name,records,columns=None):
    pd.DataFrame(records,columns=columns).to_csv(OUT/name,index=False)
table('historical_rest_candidates.csv',rest_records)
table('historical_span_candidates.csv',candidates,columns=list(candidates[0]) if candidates else ['pair_id','high_anchor','low_anchor','status'])
table('missing_high_anchors.csv',orphans,columns=['low_anchor','reason'])
table('replaced_high_anchors.csv',replaced,columns=['previous_high','replacement_high'])
table('features.csv',[feature])
table('split_manifest.csv',[{'sample_id':feature['sample_id'],'split':'retrospective_evaluation','history_cutoff_exclusive':str(cutoff),'target_test_start_native':protocol['reference']['test_start_native'],'n_independent_entities':1,'n_controlled_tests':1}])
(OUT/'protocol_snapshot.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf-8')
# Numeric labels are only opened after all history selection and feature outputs exist.
ref=ROOT/protocol['reference']['relative_path']
if sha(ref)!=protocol['reference']['sha256']: raise ValueError('reference changed')
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(ref) as archive:
    strings=[''.join(n.itertext()) for n in ET.fromstring(archive.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in archive.namelist() else []
    rows=[]
    for row in ET.fromstring(archive.read(protocol['reference']['worksheet'])).findall('.//s:row',ns):
        d={}
        for cell in row.findall('s:c',ns):
            value=cell.find('s:v',ns); v=None if value is None else value.text
            if cell.attrib.get('t')=='s' and v is not None: v=strings[int(v)]
            d[''.join(ch for ch in cell.attrib['r'] if ch.isalpha())]=v
        rows.append(d)
    selected_labels=[r for r in rows[1:] if r.get('B')==protocol['reference']['system_id_value'] and r.get('A')==protocol['reference']['excel_time_value']]
    if len(selected_labels)!=1: raise ValueError('reference key is not unique')
    lab=selected_labels[0]
    table('references.csv',[{'sample_id':feature['sample_id'],'author_test_capacity_ah':float(lab['D']),'author_test_energy_kwh':float(lab['E']),'reference_status':'author_reported_controlled_DC_test'}])
artifacts={p.name:sha(p) for p in OUT.iterdir() if p.is_file()}
receipt={'run_id':args.run_id,'data_card_version':protocol['data_card_version'],'protocol_sha256':sha(protocol_path),
         'code_sha256':sha(Path(__file__)),'source_members':sources,'admission_sha256':sha(admission_file),'reference_sha256':sha(ref),
         'python':sys.version,'pandas':pd.__version__,'numpy':np.__version__,'platform':platform.platform(),
         'history_rows_used':len(frame),'history_native_rows_observed':admission['history_rows'],'history_admitted':history_admitted,
         'latest_history_time':str(times.iloc[-1]) if len(frame) else None,'rest_runs':len(rest_records),
         'confirmed_rest_anchors':len(anchors),'anchor_counts':dict(pd.Series([a['kind'] for a in anchors]).value_counts().astype(int).items()),
         'span_candidates':len(candidates),'eligible_proxy_spans':len(eligible),'selected_pair':selected,'orphan_low_anchors':len(orphans),
         'replaced_high_anchors':len(replaced),'target_events':1,'no_fit_or_baseline_scoring':True,'artifacts':artifacts}
(OUT/'validation_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k not in ('artifacts','python','platform')},ensure_ascii=False))
