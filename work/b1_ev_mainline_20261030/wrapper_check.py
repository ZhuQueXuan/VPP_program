"""One functional replay through the public single EV-study entry point."""
from pathlib import Path
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import sys,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'B1算法'))
from b1_api import (ReferenceWindow,load_reference_model,predict_reference,EVFactorStudy,
    analyze_ev_factor_study,fit_ev_factor_curve)
from b1_algorithm.api import _default_runtime_config
from run import ASSUMPTIONS
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def main():
    target=HERE/'wrapper_check_receipt.json'
    if target.exists():raise RuntimeError('completed receipt cannot be overwritten')
    seed=5312100;facts=read(ROOT/f'data/B1_EV_mainline_v1_20261030/{seed}_positive_facts.json')
    methods=read(HERE/f'reference/{seed}_selection.json');model=load_reference_model(ROOT/'work/b1_formal_v1_20261029/reference/artifact')
    records=[]
    for row,choice in zip(facts,methods):
        ref=predict_reference(model,ReferenceWindow(**row['reference_window']),method=choice['method'])
        records.append(dict(task=row['task'],starts_min=row['starts_min'],ends_min=row['ends_min'],power_kw=row['power_kw'],
            reference=ref,noise_sigma_kw=row['noise_sigma_kw'],ev_config=dict(max_charge_kw=7.2)))
    factors=[r['factor_record'] for r in facts];study=EVFactorStudy('public-mainline-check','元/千瓦时')
    options=dict(dose_domain=[0,2.4],grid=[.6,1.,1.6],reference_dose=.6,assumptions=ASSUMPTIONS,
                 continuous_assignment=True,config=dict(seed=551,n_boot=99))
    runtime=_default_runtime_config();runtime.update(artifact_dir=str(HERE/'wrapper_native'),timeout_seconds=180)
    combined=analyze_ev_factor_study(records,factors,study,process_method='cpop',process_config=runtime,**options)
    original=read(HERE/f'events/{seed}_positive_cpop.json')
    assert len(combined['events'])==len(original)==400
    for a,b in zip(combined['events'],original):
        assert a['input_digest']==b['input_digest']
        assert a['status']==b['status']
        assert a['process']['features']==b['process']['features']
        assert a['process']['reduction_interval_kw']==b['process']['reduction_interval_kw']
        assert a['outcome']==b['outcome']
    direct=fit_ev_factor_curve(original,factors,study,**options)
    assert combined['factor_analysis']==direct
    receipt=dict(passed=True,events=400,full_public_entry_equal_to_two_stage_chain=True,
        same_inputs_and_outputs_as_saved_CPOP_events=True,main_results_overwritten=False,
        purpose='functional replay only; no new independent performance evidence')
    with target.open('x',encoding='utf-8') as stream:json.dump(receipt,stream,ensure_ascii=False,indent=2)
    print(json.dumps(receipt))
if __name__=='__main__':main()
