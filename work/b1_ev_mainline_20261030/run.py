"""Actual EV power->historical reference->process->structural continuous effects."""
from pathlib import Path
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,hashlib,dataclasses,time,copy
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'B1算法'))
from b1_api import (ReferenceWindow,load_reference_model,predict_reference,select_ev_reference,analyze_events,
    EVFactorStudy,describe_ev_study,fit_ev_factor_curve,screen_incentive_parents,fit_continuous_effects)
from b1_algorithm.api import _default_runtime_config
from simulation import generate,potential_outcome

ASSUMPTIONS=dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,same_outcome_definition=True,
                 conditional_exchangeability=True,randomized_assignment=False)
GRID=np.linspace(.4,2.,9)

def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)

def bind_references(factual,model):
    records=[];selection=[];candidates=[]
    for row in factual:
        window=ReferenceWindow(**row['reference_window']);chosen=select_ev_reference(model,window,row['historical_non_event'])
        if chosen['reference'].reference_status!='available':raise RuntimeError(str(chosen['reference'].reasons))
        records.append(dict(task=row['task'],starts_min=row['starts_min'],ends_min=row['ends_min'],power_kw=row['power_kw'],
            noise_sigma_kw=row['noise_sigma_kw'],reference=chosen['reference'],ev_config={'max_charge_kw':7.2}))
        selection.append(chosen['selection'])
        candidates.append({name:predict_reference(model,window,method=name).reference_kw.tolist() for name in ('gbdt','prev10')})
    return records,selection,candidates

def process_metrics(events,truth,records,scenario,method,seed,panel):
    rows=[]
    for event,t,rec in zip(events,truth,records):
        row=dict(seed=seed,panel=panel,scenario=scenario,method=method,task_id=t['task_id'],user_id=t['user_id'],
            status=event['status'],true_duration=t['cumulative_response_seconds'],true_eta=t['eta'])
        if event['status'] in ('ok','degraded'):
            p=event['process'];curve=np.asarray(p['reduction_interval_kw']);target=np.asarray(t['true_reduction_kw'])
            true_s=np.asarray(t['relative_starts_min']);use=(true_s>=0)&(true_s<t['W_min'])
            selected=p['features']['selected_curve'];raw=p['features']['raw_observed']
            value=selected['cumulative_response_seconds'];zero=t['cumulative_response_seconds']==0
            row.update(curve_rmse=float(np.sqrt(np.mean((curve[use]-target[use])**2))),duration=value,
                duration_absolute_error=abs(value-t['cumulative_response_seconds']),raw_duration=raw['cumulative_response_seconds'],
                eta=event['outcome']['value'],eta_absolute_error=abs(event['outcome']['value']-t['eta']),
                no_action=int(zero),false_detection=int(zero and value>0),response=int(not zero),miss=int(not zero and value==0),
                fallback=int(event['status']=='degraded'))
        rows.append(row)
    return rows

def run_seed(seed,protocol):
    model=load_reference_model(ROOT/protocol['reference']['frozen_model'])
    runtime=_default_runtime_config();runtime.update(artifact_dir=str(HERE/'native'/str(seed)),timeout_seconds=180)
    process_rows=[];effect_rows=[];ref_rows=[];screens=[]
    rawdir=ROOT/'data/B1_EV_mainline_v1_20261030';rawdir.mkdir(exist_ok=True)
    positive,positive_truth,meta=generate(seed)
    records,selection,candidates=bind_references(positive,model)
    dump(rawdir/f'{seed}_positive_facts.json',positive);dump(HERE/f'evaluator/{seed}_positive_truth.json',positive_truth)
    dump(HERE/f'reference/{seed}_selection.json',selection)
    for rec,t,c in zip(records,positive_truth,candidates):
        actual=np.asarray(t['true_reference_kw']);s=np.asarray(t['relative_starts_min']);use=(s>=0)&(s<30)
        for method,curve in dict(c,selected=np.asarray(rec['reference'].reference_kw)).items():
            error=np.asarray(curve)[use]-actual[use]
            ref_rows.append(dict(seed=seed,task_id=t['task_id'],method=method,mae=float(np.mean(abs(error))),bias=float(np.mean(error))))
    for scenario in ('positive','zero'):
        facts,truth,metadata=(positive,positive_truth,meta) if scenario=='positive' else generate(seed,scenario='zero')
        if scenario=='zero':
            dump(rawdir/f'{seed}_zero_facts.json',facts);dump(HERE/f'evaluator/{seed}_zero_truth.json',truth)
        current=[dict(rec,power_kw=row['power_kw']) for rec,row in zip(records,facts)]
        factor_records=[r['factor_record'] for r in facts]
        outputs={}
        for method in ('ride_template','cpop'):
            values=analyze_events(current,process_method=method,process_config=runtime);outputs[method]=values
            dump(HERE/f'events/{seed}_{scenario}_{method}.json',values)
            process_rows.extend(process_metrics(values,truth,current,scenario,method,seed,'main'))
        # Structure screen sees only the first60% training users and never
        # changes the declared L/U adjustment used by subsequent fits.
        study=EVFactorStudy('ev-mainline-duration','元/千瓦时')
        training=sorted({t['task']['user_id'] for t in facts})[:120]
        screen=screen_incentive_parents(outputs['ride_template'],factor_records,study,training,dose_domain=[0,2.4])
        screens.append(dict(seed=seed,scenario=scenario,**screen))
        # Potential truth is evaluated after all event predictions are saved.
        true_curves={name:[] for name in ('cumulative_response_seconds','eta')}
        for a in GRID:
            potentials=[potential_outcome(float(a),t) for t in truth]
            for name in true_curves:true_curves[name].append(np.array([p[name] for p in potentials]))
        group_masks={'all':np.ones(len(facts),bool),'slack_negative':np.array([r['deadline_slack']<0 for r in facts]),
                     'slack_nonnegative':np.array([r['deadline_slack']>=0 for r in facts])}
        for group,mask in group_masks.items():
            group_factors=[r for r,use in zip(factor_records,mask) if use]
            for label,method,name,source in [('RIDE_duration','ride_template','cumulative_response_seconds','selected_curve'),
                ('CPOP_duration','cpop','cumulative_response_seconds','selected_curve'),
                ('raw_duration','ride_template','cumulative_response_seconds','raw_observed'),
                ('eta_raw','ride_template','eta_raw','raw_observed')]:
                events=[r for r,use in zip(outputs[method],mask) if use]
                design=dataclasses.replace(study,outcome_name=name,outcome_source=source,target_population='supplied_'+group)
                result=fit_ev_factor_curve(events,group_factors,design,dose_domain=[0,2.4],grid=GRID,reference_dose=.4,
                    assumptions=ASSUMPTIONS,config=dict(seed=seed,n_boot=199),continuous_assignment=True)
                target_name='eta' if name=='eta_raw' else name
                target=np.array([values[mask].mean() for values in true_curves[target_name]]);target-=target[0]
                row=dict(seed=seed,scenario=scenario,group=group,method=label,status=result['status'],events=int(mask.sum()),
                    outcome_name=name,true_max_contrast=float(max(abs(target))))
                if result['status']=='causal':
                    predicted=np.asarray(result['causal_curve']['contrasts']);row.update(curve_rmse=float(np.sqrt(np.mean((predicted-target)**2))),
                        max_absolute_contrast=float(np.max(abs(predicted))),mean_absolute_contrast=float(np.mean(abs(predicted))))
                else:row['reason']=str(result.get('reasons'))
                effect_rows.append(row)
                dump(HERE/f'effects/{seed}_{scenario}_{group}_{label}.json',result)
    # Higher-noise, noncanonical task lengths; separate from causal panel.
    for W in (20,37):
        facts,truth,metadata=generate(seed+10000,n_users=8,W=W,noise_sigma_kw=.15)
        stress,_,_=bind_references(facts,model)
        dump(rawdir/f'{seed}_stress_{W}_facts.json',facts);dump(HERE/f'evaluator/{seed}_stress_{W}_truth.json',truth)
        for method in ('ride_template','cpop'):
            values=analyze_events(stress,process_method=method,process_config=runtime)
            dump(HERE/f'stress/{seed}_{W}_{method}.json',values)
            process_rows.extend(process_metrics(values,truth,stress,'positive',method,seed,'stress_'+str(W)))
    print('completed seed',seed,flush=True)
    result=dict(seed=seed,process=process_rows,effects=effect_rows,references=ref_rows,screens=screens)
    dump(HERE/f'blocks/{seed}.json',result)
    return result


def main():
    if (HERE/'research_receipt.json').exists():raise RuntimeError('completed study cannot be overwritten')
    start=time.perf_counter();protocol=json.loads((HERE/'protocol.json').read_text(encoding='utf-8'))
    freeze={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'B1算法').rglob('*') if p.is_file()}
    freeze.update({p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (HERE/'protocol.json',HERE/'simulation.py',HERE/'run.py')})
    dump(HERE/'scientific_source_freeze.json',freeze)
    process_rows=[];effect_rows=[];ref_rows=[];screens=[]
    workers=min(4,os.cpu_count() or 1)
    with ProcessPoolExecutor(max_workers=workers) as executor:
        pending={executor.submit(run_seed,seed,protocol):seed for seed in protocol['main_seeds']}
        for future in as_completed(pending):
            result=future.result()
            process_rows.extend(result['process']);effect_rows.extend(result['effects'])
            ref_rows.extend(result['references']);screens.extend(result['screens'])
            print('block saved',result['seed'],flush=True)
    pd.DataFrame(process_rows).to_csv(HERE/'process_metrics.csv',index=False)
    pd.DataFrame(effect_rows).to_csv(HERE/'effect_metrics.csv',index=False)
    pd.DataFrame(ref_rows).to_csv(HERE/'reference_metrics.csv',index=False);dump(HERE/'structure_screening.json',screens)
    receipt=dict(completed=True,seeds=8,main_factual_variants=6400,stress_factual_variants=256,mainline_steps=[1,2,3],
        effect_queries_are_continuous=True,truth_used_only_by_evaluator=True,source_frozen_before_main=True,
        reference_default_changed=False,process_default_changed=False,full_chain_confidence_coverage_claim=False,
        real_EV_validation=False,elapsed_seconds=time.perf_counter()-start)
    dump(HERE/'research_receipt.json',receipt);print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
