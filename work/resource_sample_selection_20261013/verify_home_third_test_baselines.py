"""Verify all predictions/metrics against native historical interval and original XLSX."""
from pathlib import Path
from datetime import datetime
import argparse,csv,json,hashlib,zipfile,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parent
pa=argparse.ArgumentParser()
for name in ('first-run','repeat-run','sample-run','sample-verification','verification-id'): pa.add_argument('--'+name,required=True)
args=pa.parse_args()
if not all(v.isidentifier() for v in vars(args).values()): raise ValueError('simple IDs required')
base=ROOT/'home_capacity_baseline_runs'; first=base/args.first_run; repeat=base/args.repeat_run
out=base/f'{args.verification_id}.json'
if out.exists(): raise FileExistsError(out)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path): return list(csv.DictReader(path.open(encoding='utf-8',newline='')))
run=json.loads((first/'run_receipt.json').read_text('utf-8'))
for name,value in run['artifacts'].items():
    if sha(first/name)!=value or sha(repeat/name)!=value: raise ValueError(f'changed repeat artifact {name}')
sample=ROOT/'home_capacity_sample_runs'/args.sample_run
sp=json.loads((sample/'protocol_snapshot.json').read_text('utf-8'))
proof=json.loads((ROOT/'home_capacity_sample_runs'/f'{args.sample_verification}.json').read_text('utf-8'))
if proof['status']!='passed' or proof['protocol_sha256']!=sha(sample/'protocol_snapshot.json'): raise ValueError('sample proof does not match input')
admission=json.loads((ROOT/sp['source']['relative_directory']/sp['source']['admission_receipt']).read_text('utf-8'))
for item in admission['source_members']:
    if sha(ROOT/item['path'])!=item['sha256']: raise ValueError('original source changed')
if sha(ROOT/sp['reference']['relative_path'])!=sp['reference']['sha256']: raise ValueError('reference changed')
def native_rows():
    for item in admission['source_members']:
        with (ROOT/item['path']).open(encoding='utf-8',newline='') as handle:
            yield from csv.DictReader(handle)
sample_receipt=json.loads((sample/'validation_receipt.json').read_text('utf-8'))
for name,expected in sample_receipt['artifacts'].items():
    if sha(sample/name)!=expected: raise ValueError(f'changed sample artifact {name}')
f=rows(sample/'features.csv')[0]
selected=next((r for r in rows(sample/'historical_span_candidates.csv') if r['pair_id']==f['selected_pair_id']),None)
if proof['source_members']!=admission['source_members']: raise ValueError('sample source binding differs')
cap=energy=None
if selected:
    begin=datetime.fromisoformat(selected['high_anchor']); end=datetime.fromisoformat(selected['low_anchor'])
    integral_i=integral_ui=0.0; count=0
    if True:
        for raw in native_rows():
            t=datetime.strptime(raw['Time'],'%d-%b-%Y %H:%M:%S')
            if t>=end: break
            if t>=begin:
                current=float(raw['I_in_A']); voltage=float(raw['V_in_V'])
                if raw['Interpolated']!='0': raise ValueError('selected interval is interpolated')
                integral_i+=current; integral_ui+=current*voltage; count+=1
    if count!=int((end-begin).total_seconds()): raise ValueError('native integral duration differs')
    cap=-integral_i/3600; energy=-integral_ui/3600000
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(ROOT/sp['reference']['relative_path']) as archive:
    shared=[''.join(n.itertext()) for n in ET.fromstring(archive.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in archive.namelist() else []
    matrix=[]
    for row in ET.fromstring(archive.read(sp['reference']['worksheet'])).findall('.//s:row',ns):
        cells={}
        for cell in row.findall('s:c',ns):
            value=cell.find('s:v',ns); text=None if value is None else value.text
            if cell.attrib.get('t')=='s' and text is not None: text=shared[int(text)]
            column=''.join(ch for ch in cell.attrib['r'] if ch.isalpha()); cells[column]=text
        matrix.append(cells)
    headers=matrix[0]
    records=[{headers[k]:v for k,v in row.items()} for row in matrix[1:]]
    match=[r for r in records if r['ID']==sp['reference']['system_id_value'] and r['Time']==sp['reference']['excel_time_value']]
    if len(match)!=1: raise ValueError('controlled reference key differs')
    reference={'capacity':float(match[0]['Capacity_Ah']),'energy':float(match[0]['Energy_kWh'])}
expected={('B_NOM','capacity'):sp['source']['nominal_capacity_ah'],('B_NOM','energy'):sp['source']['nominal_energy_kwh'],
          ('B_DS','capacity'):None,('B_DS','energy'):sp['source']['datasheet_usable_energy_kwh'],
          ('B_HIST_SPAN','capacity'):cap,('B_HIST_SPAN','energy'):energy}
pred=rows(first/'predictions.csv'); metric=rows(first/'metrics.csv')
if len(pred)!=6 or len(metric)!=6: raise ValueError('prediction/metric rows differ')
if len({(r['model'],r['quantity']) for r in pred})!=6: raise ValueError('prediction keys not unique')
max_prediction=max_metric=0.0
for row in pred:
    key=row['model'],row['quantity']; value=expected[key]; ref=reference[key[1]]
    if abs(float(row['reference'])-ref)>1e-12: raise ValueError('reference differs from source XLSX')
    if value is None:
        wanted='unsupported_quantity' if key==('B_DS','capacity') else f.get('history_unavailability_reason') or 'history_proxy_unavailable'
        if row['prediction']!='' or row['status']!=wanted: raise ValueError('unavailable prediction filled/dropped')
    else:
        error=abs(float(row['prediction'])-value); max_prediction=max(max_prediction,error)
        if error>1e-9 or row['status']!='ok': raise ValueError('baseline prediction differs')
for row in metric:
    key=row['model'],row['quantity']; value=expected[key]; ref=reference[key[1]]
    if row['n_target_events']!='1' or row['n_predictions']!=str(int(value is not None)): raise ValueError('denominator differs')
    if value is None:
        if any(row[k]!='' for k in ('signed_error','absolute_error','absolute_error_percent_of_reference')): raise ValueError('missing metric filled')
    else:
        wanted={'signed_error':value-ref,'absolute_error':abs(value-ref),'absolute_error_percent_of_reference':abs(value-ref)/ref*100}
        for k,v in wanted.items():
            diff=abs(float(row[k])-v); max_metric=max(max_metric,diff)
            if diff>1e-9: raise ValueError(f'metric mismatch {key} {k}')
failures=rows(first/'failures.csv')
expected_missing={(m,q) for (m,q),value in expected.items() if value is None}
if {(r['model'],r['quantity']) for r in failures}!=expected_missing or any(r['runtime_failure']!='False' for r in failures): raise ValueError('failure/unavailable output record differs')
result={'verification_id':args.verification_id,'status':'passed','scope':'all six prediction/metric rows, availability, original selected native I/UI integral and original published XLSX reference; history selection independently checked by referenced sample proof',
        'sample_verification':args.sample_verification,'events':1,'repeat_equal_artifacts':len(run['artifacts']),
        'max_prediction_absolute_difference':max_prediction,'max_metric_absolute_difference':max_metric,'tolerance':1e-9,
        'original_interval_capacity_ah':cap,'original_interval_UI_energy_kwh':energy,'unavailable_outputs':len(expected_missing),
        'code_sha256':sha(Path(__file__)),'source_members':admission['source_members'],'reference_sha256':sp['reference']['sha256']}
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
