"""Score frozen transparent baselines for one retrospective controlled test."""
from pathlib import Path
import argparse,csv,json,hashlib,time,sys,platform,math
ROOT=Path(__file__).resolve().parent
pa=argparse.ArgumentParser(); pa.add_argument('--run-id',required=True); pa.add_argument('--sample-run',required=True)
args=pa.parse_args()
if not args.run_id.isidentifier() or not args.sample_run.isidentifier(): raise ValueError('simple unique IDs required')
OUT=ROOT/'home_capacity_baseline_runs'/args.run_id
if OUT.exists(): raise FileExistsError(OUT)
begin=time.perf_counter()
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read_rows(path): return list(csv.DictReader(path.open(encoding='utf-8',newline='')))
protocol_file=ROOT/'home_capacity_crossperiod_protocol_v4.json'
protocol=json.loads(protocol_file.read_text('utf-8'))['baseline']
sample=ROOT/'home_capacity_sample_runs'/args.sample_run
receipt=json.loads((sample/'validation_receipt.json').read_text('utf-8'))
sample_protocol=json.loads((sample/'protocol_snapshot.json').read_text('utf-8'))
if sample_protocol!=json.loads((ROOT/protocol['sample_protocol']).read_text('utf-8')): raise ValueError('sample protocol changed')
for name,value in receipt['artifacts'].items():
    if sha(sample/name)!=value: raise ValueError(f'sample artifact changed {name}')
admission=json.loads((ROOT/sample_protocol['source']['relative_directory']/sample_protocol['source']['admission_receipt']).read_text('utf-8'))
for item in admission['source_members']:
    if sha(ROOT/item['path'])!=item['sha256']: raise ValueError('source changed')
if sha(ROOT/sample_protocol['reference']['relative_path'])!=sample_protocol['reference']['sha256']: raise ValueError('reference changed')
features=read_rows(sample/'features.csv'); refs=read_rows(sample/'references.csv')
if len(features)!=1 or len(refs)!=1 or features[0]['sample_id']!=refs[0]['sample_id']: raise ValueError('single event mismatch')
f,r=features[0],refs[0]
available=f['history_proxy_available']=='True'
prediction_records=[]; metric_records=[]; failure_records=[]
for model in ('B_NOM','B_DS','B_HIST_SPAN'):
    for quantity,unit in (('capacity','Ah'),('energy','kWh')):
        reference=float(r['author_test_capacity_ah' if quantity=='capacity' else 'author_test_energy_kwh'])
        if not math.isfinite(reference) or reference<=0: raise ValueError('invalid positive reference')
        if model=='B_NOM':
            value=float(f['nominal_capacity_ah' if quantity=='capacity' else 'nominal_energy_kwh']); status='ok'
        elif model=='B_DS':
            value=None if quantity=='capacity' else float(f['datasheet_usable_energy_kwh'])
            status='unsupported_quantity' if quantity=='capacity' else 'ok'
        else:
            value=float(f['history_net_capacity_ah' if quantity=='capacity' else 'history_net_UI_energy_kwh']) if available else None
            status='ok' if available else f.get('history_unavailability_reason') or 'history_proxy_unavailable'
        if value is not None and (not math.isfinite(value) or value<=0): raise ValueError('invalid baseline prediction')
        prediction_records.append({'sample_id':f['sample_id'],'model':model,'quantity':quantity,'unit':unit,'status':status,'prediction':value,'reference':reference})
        error=None if value is None else value-reference
        metric_records.append({'sample_id':f['sample_id'],'model':model,'quantity':quantity,'unit':unit,'status':status,
                               'n_target_events':1,'n_predictions':int(value is not None),'signed_error':error,
                               'absolute_error':None if error is None else abs(error),
                               'absolute_error_percent_of_reference':None if error is None else abs(error)/reference*100})
        if status!='ok': failure_records.append({'sample_id':f['sample_id'],'model':model,'quantity':quantity,'status':status,'runtime_failure':False})
OUT.mkdir(parents=True)
def write(name,records,columns=None):
    with (OUT/name).open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=columns or list(records[0])); writer.writeheader(); writer.writerows(records)
write('predictions.csv',prediction_records)
write('metrics.csv',metric_records)
write('failures.csv',failure_records,columns=['sample_id','model','quantity','status','runtime_failure'])
(OUT/'protocol_snapshot.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'input_snapshot.json').write_text(json.dumps({'features':f,'reference':r,'sample_protocol':sample_protocol},ensure_ascii=False,indent=2),encoding='utf-8')
artifact_hashes={p.name:sha(p) for p in OUT.iterdir() if p.is_file()}
runtime={'run_id':args.run_id,'sample_run':args.sample_run,'input_data_card':receipt['data_card_version'],
         'baseline_protocol_sha256':sha(protocol_file),'sample_protocol_sha256':sha(ROOT/protocol['sample_protocol']),
         'sample_artifacts':receipt['artifacts'],'source_members':admission['source_members'],'reference_sha256':sample_protocol['reference']['sha256'],
         'code_sha256':sha(Path(__file__)),'python':sys.version,'platform':platform.platform(),'n_controlled_test_events':1,
         'n_entities':1,'fit':'none','runtime_failures':0,'unavailable_outputs':len(failure_records),'elapsed_seconds':time.perf_counter()-begin,'artifacts':artifact_hashes,
         'claim_scope':'one retrospective test, recorded-voltage-span proxy, not proven full cycle or VPP capacity'}
(OUT/'run_receipt.json').write_text(json.dumps(runtime,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'run_id':args.run_id,'metrics':metric_records,'runtime_failures':0,'unavailable_outputs':len(failure_records),'elapsed_seconds':runtime['elapsed_seconds']},ensure_ascii=False))
