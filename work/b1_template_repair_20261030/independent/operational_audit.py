"""Audit final statuses, solver warnings, denominators and batch timings."""
from pathlib import Path
import json,collections
import pandas as pd
HERE=Path(__file__).resolve().parent;TEST=HERE.parent/'test'
def main():
    target=HERE/'operational_review.json'
    if target.exists():raise RuntimeError('preserve existing operational review')
    metrics=pd.read_csv(TEST/'metrics.csv');timing=pd.read_csv(TEST/'timing.csv')
    final_status=metrics.groupby(['panel','method','status']).size()
    assert set(metrics.status)=={'ok'} and len(metrics)==6912
    solver=collections.Counter();failed_by_panel=collections.Counter();selected_failures=0;failed_nfev=collections.Counter()
    for file in (TEST/'events').glob('*_ride_revised.json'):
        for event in json.loads(file.read_text(encoding='utf-8')):
            evidence=event['process']['selection_evidence'];records=evidence['solver_records']
            selected=records[evidence['selected_solver']]
            selected_failures+=int(not(selected['accepted'] and selected['success'] and selected['termination_status']>0))
            for record in records:
                solver[('accepted' if record['accepted'] else 'rejected',record.get('termination_status'))]+=1
                if not record['accepted']:
                    failed_by_panel['main' if ('_positive_' in file.name or '_zero_' in file.name) else 'stress']+=1
                    failed_nfev[record.get('nfev')]+=1
    assert selected_failures==0 and sum(solver.values())==21056 and failed_nfev=={250:344}
    assert solver[('rejected',0)]==344 and sum(v for (accepted,status),v in solver.items() if accepted=='rejected')==344
    counts=metrics[metrics.panel=='main'].groupby('method')[['no_action','false_detection','response','miss','fallback']].sum()
    assert counts.no_action.nunique()==counts.response.nunique()==1 and counts.no_action.iloc[0]==866 and counts.response.iloc[0]==1182
    main_time=timing[timing.panel=='main'].groupby('method').seconds.sum().to_dict()
    assessment=json.loads((TEST/'assessment.json').read_text(encoding='utf-8'))
    assert all(abs(v-assessment['summed_method_seconds'][m])<1e-9 for m,v in main_time.items())
    log=(TEST.parent/'test.log').read_text(encoding='utf-8')
    warnings=[line for line in log.splitlines() if 'RuntimeWarning:' in line]
    assert len(warnings)==2
    result=dict(passed=True,final_statuses=[dict(panel=p,method=m,status=s,count=int(n)) for (p,m,s),n in final_status.items()],
      denominator_counts=counts.to_dict('index'),solver_records=sum(solver.values()),
      solver_termination_counts=[dict(acceptance=a,status=s,count=n) for (a,s),n in solver.items()],
      rejected_starts_by_panel=dict(failed_by_panel),rejected_nfev_counts={str(k):v for k,v in failed_nfev.items()},selected_failed_starts=selected_failures,
      warnings=warnings,warning_scope='SciPy warnings are not tagged by event/start in the shared process log. They cannot be attributed exactly to the344 rejected starts. All recorded rejected starts had status0 and nfev250; no unsuccessful curve was selected and all6912 final event outputs are ok and finite.',
      main_summed_batch_seconds=main_time,all_panels_summed_batch_seconds=timing.groupby('method').seconds.sum().to_dict(),
      revised_to_cpop_main_batch_time_ratio=main_time['ride_revised']/main_time['cpop'],
      test_stage_wall_seconds=json.loads((TEST/'receipt.json').read_text(encoding='utf-8'))['elapsed_seconds'],
      timing_scope='Observed batch elapsed times while up to4seed workers ran concurrently; original CPOP batches include Rlaunch. Sums are not the stagewall time or an exclusiveCPU latency benchmark.',
      retained_counterexamples=[dict(scope='positive main',metric='curveRMSE',revised=.16098391878909873,cpop=.15171298262875457),
       dict(scope='positive interrupted main',metric='durationMAEseconds',revised=127.33031674208145,cpop=105.3393665158371),
       dict(scope='37minute highnoise stress',metric='durationMAEseconds',revised=155.625,cpop=120.)],
      universal_advantage_claim_supported=False,realEV_validation=False)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('passed','solver_records','rejected_starts_by_panel','selected_failed_starts','revised_to_cpop_main_batch_time_ratio')},indent=2))
if __name__=='__main__':main()
