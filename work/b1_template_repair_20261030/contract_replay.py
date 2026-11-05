"""Explicit bound-contract checks and equivalence to frozen test predictions."""
from pathlib import Path
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,ast,hashlib
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'B1算法'))
from b1_api import ReferenceWindow,predict_reference,select_ev_reference,load_reference_model,analyze_event,provided_reference
from b1_algorithm.process import _ride_revised as revised
from b1_algorithm.process.api import prepare
from b1_algorithm.resources.ev import EVAnalysisConfig,ev_config
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)
def functions(path):
    return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef)}
def main():
    if (HERE/'contract_replay_receipt.json').exists():raise RuntimeError('preserve completed replay')
    old=HERE/'test/source/B1算法/b1_algorithm/process/_ride_revised.py';current=ROOT/'B1算法/b1_algorithm/process/_ride_revised.py'
    old_funcs=functions(old);new_funcs=functions(current)
    for name in ('interval_components','bounded_amplitudes','observed_starts','_runs'):assert old_funcs[name]==new_funcs[name]
    # The only fitting-body difference formats nonfinite diagnostic fields;
    # no objective, start, bounds, solver options, BIC or detection are changed.
    previous=old.read_text(encoding='utf-8');updated=current.read_text(encoding='utf-8')
    formatted="termination_status=int(result.status),nfev=int(result.nfev),\n                    optimality=float(result.optimality) if np.isfinite(result.optimality) else None,\n                    rss=rss if np.isfinite(rss) else None,accepted=accepted)"
    restored=updated.replace(formatted,'termination_status=int(result.status),nfev=int(result.nfev),optimality=float(result.optimality),rss=rss,accepted=accepted)')
    body=functions_from_text(restored)
    assert body['fit_revised_ride']==old_funcs['fit_revised_ride']
    configs=[];bound_checks=0;event_files={};raw_files={};replays=0
    model=load_reference_model(ROOT/'work/b1_formal_v1_20261029/reference/artifact')
    for seed in read(HERE/'protocol.json')['test']['seeds']:
        choices=read(HERE/f'test/reference/{seed}.json')
        for suffix in ('positive','zero','stress20','stress37'):
            prefix=f'{seed}_{suffix}'
            raw=ROOT/f'data/B1_template_repair_v1_20261030/test/{prefix}_facts.json'
            facts=read(raw);raw_files[raw.relative_to(ROOT).as_posix()]=sha(raw)
            repaired_path=HERE/f'test/events/{prefix}_ride_revised.json';events=read(repaired_path)
            event_files[repaired_path.relative_to(ROOT).as_posix()]=sha(repaired_path)
            cpop=read(HERE/f'test/events/{prefix}_cpop.json')
            signal=pd.read_csv(Path(cpop[0]['process']['backend']['artifact_dir'])/'input.csv')
            for i,(fact,event) in enumerate(zip(facts,events)):
                y=signal[signal.case_id==i*10].y.to_numpy();reference=np.asarray(fact['power_kw'])+y
                old_bound=event['process']['selection_evidence']['rebound_max_ratio']
                new_bound=max(0.,7.2-float(reference.max()))/fact['task']['request_kw']
                assert abs(new_bound-old_bound)<1e-12
                bound_checks+=1
                if i>=(2 if suffix in ('positive','zero') else 1):continue
                if suffix in ('positive','zero'):
                    ref=predict_reference(model,ReferenceWindow(**fact['reference_window']),method=choices[i]['method'])
                else:ref=select_ev_reference(model,ReferenceWindow(**fact['reference_window']),fact['historical_non_event'])['reference']
                output=analyze_event(fact['task'],fact['starts_min'],fact['ends_min'],fact['power_kw'],ref,fact['noise_sigma_kw'],
                    process_method='ride_revised',ev_config=dict(max_charge_kw=7.2,revised_rebound_bound_policy='declared_headroom'))
                assert output['status']==event['status']=='ok'
                assert output['input_digest']==event['input_digest']
                assert output['outcome']==event['outcome']
                assert output['process']['features']==event['process']['features']
                assert np.array_equal(output['process']['reduction_interval_kw'],event['process']['reduction_interval_kw'])
                replays+=1
        print('contract replay',seed,flush=True)
    s=np.arange(-15.,45.);e=s+1.;ref=np.full(60,3.5);power=ref.copy()
    task=dict(task_id='contract',user_id='u',meter_id='m',start_min=0.,end_min=30.,notice_min=-15.,request_kw=1.5,task_pre_treatment=True)
    def prepared(config):return prepare(s,e,power,ref,task,.05,config)
    configured=prepared(dict(max_charge_kw=7.2,template_rebound_max_ratio=.02))
    assert revised.rebound_bound(configured)==(.02,'configured_ratio')
    physical=prepared(dict(max_charge_kw=7.2,template_rebound_max_ratio=.02,revised_rebound_bound_policy='declared_headroom'))
    assert abs(revised.rebound_bound(physical)[0]-(7.2-3.5)/1.5)<1e-12
    zero=prepared(dict(max_charge_kw=3.5,revised_rebound_bound_policy='declared_headroom'))
    assert revised.rebound_bound(zero)[0]==0.
    fallback=prepared(dict(template_rebound_max_ratio=.4,revised_rebound_bound_policy='declared_headroom'))
    assert revised.rebound_bound(fallback)==(.4,'configured_ratio_no_declared_max')
    for bad in (True,'silent-auto',None):
        try:ev_config(dict(revised_rebound_bound_policy=bad))
        except ValueError:pass
        else:raise AssertionError('invalid bound policy accepted')
    from types import SimpleNamespace
    saved=revised.least_squares
    revised.least_squares=lambda fun,x0,**kw:SimpleNamespace(x=x0,success=False,status=0,nfev=250,optimality=np.nan)
    supplied=provided_reference(task,s,e,ref,available_at_min=-15.)
    failed=analyze_event(task,s,e,power,supplied,.05,process_method='ride_revised',ev_config=dict(max_charge_kw=7.2))
    revised.least_squares=saved
    assert failed['status']=='degraded' and failed['process']['method']=='raw_F0'
    records=failed['process']['selection_evidence']['solver_records']
    assert records and all(not row['accepted'] and row['optimality'] is None for row in records)
    for name,value in raw_files.items():assert sha(ROOT/name)==value
    for name,value in event_files.items():assert sha(ROOT/name)==value
    final={p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'B1算法').rglob('*') if p.is_file()}
    frozen=read(HERE/'final_candidate_freeze.json')['source']
    changed={name:dict(frozen=value,current=sha(ROOT/name)) for name,value in frozen.items() if sha(ROOT/name)!=value}
    write(HERE/'contract_replay_receipt.json',dict(passed=True,bound_equivalence_events=bound_checks,actual_public_prediction_replays=replays,
        prediction_arrays_features_and_eta_exact=True,initialization_and_interval_math_AST_unchanged=True,
        objective_and_solver_BIC_detection_body_unchanged_except_finite_diagnostic_format=True,
        explicit_configured_ratio_respected=True,physical_mode_explicit=True,zero_headroom_exact_zero=True,
        failed_local_diagnostics_preserved_and_JSON_finite=True,raw_file_hashes=raw_files,event_file_hashes=event_files,
        changed_source_identity=changed,current_runtime=final,original_scores_modified=False,
        interpretation='Frozen test uses headroom policy; current equivalent call must explicitly set declared_headroom. configured_ratio is a separate contract behavior, not scored as the frozen candidate.'))
    print('contract checks and replay passed',bound_checks,replays)
def functions_from_text(value):
    return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(value).body if isinstance(n,ast.FunctionDef)}
if __name__=='__main__':main()
