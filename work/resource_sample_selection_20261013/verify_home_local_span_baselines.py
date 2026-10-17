"""Independent streaming state machine verifies all local samples and 32 baseline rows."""
from pathlib import Path
from datetime import datetime,timedelta
from collections import deque
from statistics import median
import argparse,csv,hashlib,json,math,zipfile,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parent
pa=argparse.ArgumentParser()
for key in ('first-sample','repeat-sample','first-run','repeat-run','verification-id'):pa.add_argument('--'+key,required=True)
args=pa.parse_args()
if not all(v.isidentifier() for v in vars(args).values()):raise ValueError('simple IDs required')
BASE=ROOT/'downloads/rwth_home_local_span_20261014';OUT=BASE/f'{args.verification_id}.json'
if OUT.exists():raise FileExistsError(OUT)
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
def rows(path):
    with path.open(encoding='utf-8',newline='') as h:return list(csv.DictReader(h))
pf=ROOT/'home_capacity_local_span_protocol_v1.json';p=json.loads(pf.read_text('utf-8'));rp=p['rest_proxy']
sample=BASE/'samples'/args.first_sample;repeat_sample=BASE/'samples'/args.repeat_sample
first=BASE/'baselines'/args.first_run;repeat=BASE/'baselines'/args.repeat_run
sr=json.loads((sample/'receipt.json').read_text('utf-8'));br=json.loads((first/'receipt.json').read_text('utf-8'))
for r,folder,other in [(sr,sample,repeat_sample),(br,first,repeat)]:
    if r['protocol_sha256']!=sha(pf):raise ValueError('protocol binding differs')
    for name,h in r['artifacts'].items():
        if sha(folder/name)!=h or sha(other/name)!=h:raise ValueError(f'artifact or repeat differs: {name}')
if br['sample_run']!=args.first_sample or br['sample_artifacts']!=sr['artifacts']:raise ValueError('baseline sample differs')
if json.loads((sample/'protocol_snapshot.json').read_text('utf-8'))!=p:raise ValueError('sample snapshot differs')
max_numeric=0.;expected_features=[];expected_summary=[];all_blocks=[];all_rests=[];all_pairs=[];all_orphans=[];all_resets=[]
def reconstruct(e):
    sid=e['sample_id'];start=datetime.fromisoformat(e['information']['history_start_inclusive']);cutoff=datetime.fromisoformat(e['information']['history_end_exclusive'])
    rests=[];pairs=[];orphans=[];resets=[];blocks=[];pending=None;rest=None;tail=deque(maxlen=rp['voltage_tail_seconds'])
    block_first=None;last=None;bn=badblock=total=0
    def close_rest(end,right):
        nonlocal rest
        if rest is not None:
            rest['end_exclusive']=str(end);rest['right_censored']=right;rests.append(rest);rest=None;tail.clear()
    def close_block():
        nonlocal pending
        after=last+timedelta(seconds=1);bid=f'block_{len(blocks):02}';close_rest(after,True)
        if pending:resets.append({'sample_id':sid,'block_id':bid,'high_anchor':pending['time'],'reason':'block_end_reset','boundary':str(after)})
        pending=None;blocks.append({'sample_id':sid,'block_id':bid,'start':str(block_first),'end_exclusive':str(after),'native_rows':bn,'bad_rows':badblock})
    for src in e['source_members']:
        if sha(ROOT/src['path'])!=src['sha256']:raise ValueError('raw source changed')
        with (ROOT/src['path']).open(encoding='utf-8',newline='') as h:
            for raw in csv.DictReader(h):
                t=datetime.strptime(raw['Time'],'%d-%b-%Y %H:%M:%S')
                if t<start:continue
                if t>=cutoff:break
                if last is not None and t<=last:raise ValueError('nonincreasing time')
                if last is not None and t!=last+timedelta(seconds=1):close_block();block_first=None;bn=badblock=0
                if block_first is None:block_first=t
                bid=f'block_{len(blocks):02}'
                vals=[float(raw[k]) for k in ('P_in_W','V_in_V','I_in_A','T_Bat_in_C','T_Room_in_C')];power,voltage,current=vals[:3]
                if raw['Interpolated'] not in ('0','1'):raise ValueError('invalid interpolation flag')
                finite=all(math.isfinite(v) for v in vals);valid=finite and raw['Interpolated']=='0';is_rest=valid and abs(current)<=rp['absolute_current_max_a']
                if is_rest:
                    if rest is None:rest={'sample_id':sid,'block_id':bid,'rest_id':f'rest_{len(rests):05}','start':str(t),'end_exclusive':None,'observed_seconds':0,
                        'left_censored':bn==0,'right_censored':False,'kind':'too_short','anchor_time':None,'voltage_proxy_cell_v':None,'used_for_pairing':False}
                    rest['observed_seconds']+=1;tail.append(voltage)
                    if rest['observed_seconds']==rp['minimum_consecutive_seconds']:
                        vc=median(tail)/p['source_metadata']['series_cells'];kind='high' if vc>=rp['high_voltage_min_v_per_series_cell'] else 'low' if vc<=rp['low_voltage_max_v_per_series_cell'] else 'middle'
                        rest.update(kind=kind,anchor_time=str(t),voltage_proxy_cell_v=vc,used_for_pairing=not rest['left_censored'])
                        if not rest['left_censored']:
                            if kind=='high':
                                if pending:resets.append({'sample_id':sid,'block_id':bid,'high_anchor':pending['time'],'reason':'replaced_by_high','boundary':str(t)})
                                pending={'time':str(t),'i':0.,'ui':0.,'charge':0.,'discharge':0.,'duration':0,'bad':0}
                            elif kind=='low':
                                if pending is None:orphans.append({'sample_id':sid,'block_id':bid,'low_anchor':str(t),'reason':'no_high_in_same_block'})
                                else:
                                    cap=None if pending['bad'] else -pending['i']/3600;energy=None if pending['bad'] else -pending['ui']/3600000
                                    status='quality_failure' if pending['bad'] else 'nonpositive_net' if cap<=0 or energy<=0 else 'eligible'
                                    pairs.append({'sample_id':sid,'pair_id':f'pair_{len(pairs):04}','block_id':bid,'high_anchor':pending['time'],'low_anchor':str(t),
                                        'duration_seconds':pending['duration'],'bad_rows_inclusive':pending['bad'],'status':status,'net_capacity_ah':cap,'net_UI_energy_kwh':energy,
                                        'gross_charge_ah':None if pending['bad'] else pending['charge']/3600,'gross_discharge_ah':None if pending['bad'] else pending['discharge']/3600})
                                    pending=None
                else:close_rest(t,False)
                if pending:
                    pending['bad']+=int(not valid);pending['duration']+=1
                    if math.isfinite(current) and math.isfinite(voltage):
                        pending['i']+=current;pending['ui']+=current*voltage;pending['charge']+=max(current,0);pending['discharge']+=max(-current,0)
                bn+=1;badblock+=int(not valid);total+=1;last=t
    if last is not None:close_block()
    eligible=[r for r in pairs if r['status']=='eligible'];selected=max(eligible,key=lambda q:(q['low_anchor'],q['high_anchor'])) if eligible else None
    low=None if selected is None else datetime.fromisoformat(selected['low_anchor']);test=datetime.fromisoformat(e['reference']['test_start_native'])
    feature={'sample_id':sid,'test_start_native':str(test),'history_start':str(start),'history_cutoff':str(cutoff),'history_rows_observed':total,
        'history_seconds_expected':int((cutoff-start).total_seconds()),'continuous_blocks':len(blocks),'proxy_available':selected is not None,
        'unavailable_reason':'' if selected else 'no_eligible_complete_local_span','selected_pair_id':None if selected is None else selected['pair_id'],
        'selected_low_anchor':None if low is None else str(low),'capacity_ah':None if selected is None else selected['net_capacity_ah'],'energy_kwh':None if selected is None else selected['net_UI_energy_kwh'],
        'age_at_cutoff_seconds':None if low is None else int((cutoff-low).total_seconds()),'age_at_test_seconds':None if low is None else int((test-low).total_seconds())}
    summary={'sample_id':sid,'rests':len(rests),'anchors':sum(r['kind']!='too_short' for r in rests),'left_censored_anchors':sum(r['kind']!='too_short' and r['left_censored'] for r in rests),
        'pairs':len(pairs),'eligible_pairs':len(eligible),'orphan_lows':len(orphans),'high_resets':len(resets),'selected':selected}
    return feature,summary,blocks,rests,pairs,orphans,resets
for e in p['events']:
    f,s,b,r,q,o,z=reconstruct(e);expected_features.append(f);expected_summary.append(s);all_blocks+=b;all_rests+=r;all_pairs+=q;all_orphans+=o;all_resets+=z
    print(json.dumps({'reconstructed_event':e['sample_id'],'selected_pair':f['selected_pair_id'],'capacity_ah':f['capacity_ah'],'age_at_cutoff_seconds':f['age_at_cutoff_seconds']}),flush=True)
def compare(wanted,actual,key=''):
    global max_numeric
    if isinstance(wanted,dict):
        for k,v in wanted.items():compare(v,actual[k],k)
    elif isinstance(wanted,list):
        if len(wanted)!=len(actual):raise ValueError(f'count differs {key}')
        for a,b in zip(wanted,actual):compare(a,b,key)
    elif isinstance(wanted,float):
        diff=abs(wanted-float(actual));max_numeric=max(max_numeric,diff);tol=1e-12 if 'voltage' in key else 1e-9
        if diff>tol:raise ValueError(f'numeric mismatch {key} {diff}')
    else:
        if ('' if wanted is None else str(wanted))!=('' if actual is None else str(actual)):raise ValueError(f'value mismatch {key}: {wanted} != {actual}')
for name,wanted in [('features.csv',expected_features),('blocks.csv',all_blocks),('rests.csv',all_rests),('pairs.csv',all_pairs),('orphan_lows.csv',all_orphans),('high_resets.csv',all_resets)]:compare(wanted,rows(sample/name),name)
compare(expected_summary,json.loads((sample/'summary.json').read_text('utf-8')))
# Independently read original reference XML using column headers, then reconstruct all models.
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'};expected_predictions=[];expected_metrics=[];expected_failures=[]
for e,f in zip(p['events'],expected_features):
    ref=e['reference'];path=ROOT/ref['relative_path']
    if sha(path)!=ref['sha256']:raise ValueError('reference changed')
    with zipfile.ZipFile(path) as z:
        strings=[''.join(n.itertext()) for n in ET.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
        matrix=[]
        for rr in ET.fromstring(z.read(ref['worksheet'])).findall('.//s:row',ns):
            cells={}
            for c in rr.findall('s:c',ns):
                v=c.find('s:v',ns);value=None if v is None else v.text
                if c.attrib.get('t')=='s' and value is not None:value=strings[int(value)]
                cells[''.join(ch for ch in c.attrib['r'] if ch.isalpha())]=value
            matrix.append(cells)
        header=matrix[0];records=[{header[k]:v for k,v in rr.items()} for rr in matrix[1:]]
        hit=[rr for rr in records if rr['ID']==ref['system_id_value'] and rr['Time']==ref['excel_time_value']]
        if len(hit)!=1:raise ValueError('reference key differs')
        label={'capacity':float(hit[0]['Capacity_Ah']),'energy':float(hit[0]['Energy_kWh'])}
    old=ROOT/'home_capacity_baseline_runs'/e['old_baseline_run']
    if sha(old/'predictions.csv')!=e['old_prediction_sha256'] or sha(old/'metrics.csv')!=e['old_metric_sha256']:raise ValueError('old results changed')
    previous=rows(old/'predictions.csv')
    for model in p['comparison']['models']:
        for quantity,unit in [('capacity','Ah'),('energy','kWh')]:
            if model=='B_LOCAL_SPAN':value=f['capacity_ah' if quantity=='capacity' else 'energy_kwh'];status='ok' if value is not None else f['unavailable_reason']
            elif model=='B_NOM':value=p['source_metadata']['nominal_capacity_ah' if quantity=='capacity' else 'nominal_energy_kwh'];status='ok'
            elif model=='B_DS':value=None if quantity=='capacity' else p['source_metadata']['datasheet_usable_energy_kwh'];status='unsupported_quantity' if value is None else 'ok'
            else:
                control=next(r for r in previous if r['model']==model and r['quantity']==quantity);value=None if control['prediction']=='' else float(control['prediction']);status=control['status']
            reference=label[quantity];error=None if value is None else value-reference
            expected_predictions.append({'sample_id':f['sample_id'],'model':model,'quantity':quantity,'unit':unit,'status':status,'prediction':value,'reference':reference})
            expected_metrics.append({'sample_id':f['sample_id'],'model':model,'quantity':quantity,'unit':unit,'status':status,'n_target_events':1,'n_predictions':int(value is not None),
                'signed_error':error,'absolute_error':None if value is None else abs(error),'absolute_error_percent_of_reference':None if value is None else abs(error)/reference*100})
            if value is None:expected_failures.append({'sample_id':f['sample_id'],'model':model,'quantity':quantity,'status':status,'runtime_failure':False})
compare(expected_predictions,rows(first/'predictions.csv'));compare(expected_metrics,rows(first/'metrics.csv'));compare(expected_failures,rows(first/'unavailable.csv'))
result={'status':'passed','verification_id':args.verification_id,'scope':'independent raw streaming reconstruction of all four histories/blocks/rests/pairs/selection/integrals/age plus original XLSX and all 32 prediction/metric rows',
    'events':4,'prediction_rows':len(expected_predictions),'unavailable_rows':len(expected_failures),'sample_equal_artifacts':len(sr['artifacts']),'baseline_equal_artifacts':len(br['artifacts']),
    'maximum_numeric_difference':max_numeric,'integral_prediction_metric_tolerance':1e-9,'voltage_tolerance':1e-12,'code_sha256':sha(Path(__file__)),'protocol_sha256':sha(pf)}
OUT.open('x',encoding='utf-8').write(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
