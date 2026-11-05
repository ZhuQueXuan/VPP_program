"""Four-path contract smoke test using independent tiny pseudo-user blocks."""
from pathlib import Path
import sys
import json
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import run
from generator import generate_reliability


def main():
    cal,_,_=generate_reliability(7599910,4,variants=('non_event',),clock_shift_min=2016000)['non_event']
    queries=generate_reliability(7599911,2,variants=('strong','weak','null'),clock_shift_min=4032000)
    checks=[];api=run.evidence_api()
    for label,kind,method in run.PATHS:
        refs,_=run.bind_references(cal,kind)
        events,timing=run.process_path(cal,refs,'micro_cal_'+label,method)
        run.dump_new(HERE/f'integration_cal_events_{label}.json',events)
        records=run.bound_records(cal,refs)
        model=api.fit_ev_event_calibration(events,records,
            calibration_cutoff_min=max(f['availability']['power_records_available_at_min'] for f in cal),
            reference_policy_id=run.reference_policy(kind))
        api.save_ev_event_calibration(model,HERE/f'integration_cal_model_{label}.json')
        for variant,(facts,_,_) in queries.items():
            reference,_=run.bind_references(facts,kind)
            output,_=run.process_path(facts,reference,'micro_query_'+variant+'_'+label,method)
            decisions=[api.assess_ev_event_evidence(event,model,reference_policy_id=run.reference_policy(kind)) for event in output]
            run.dump_new(HERE/f'integration_{variant}_{label}.json',dict(events=output,decisions=decisions))
            assert all(d['status']=='insufficient_calibration' and d['decision']=='inconclusive' for d in decisions)
            assert all(d['measured_cumulative_seconds']==e['process']['features']['selected_curve']['cumulative_response_seconds'] for d,e in zip(decisions,output))
            checks.append(dict(path=label,variant=variant,n_events=len(output),status='passed'))
    result=dict(passed=True,checks=checks,n_paths=4,n_query_outputs=sum(c['n_events'] for c in checks),
        scope='tiny independent API contract and explicit insufficient-calibration status; not performance or main validation',truth_used=False)
    run.dump_new(HERE/'integration_receipt.json',result)
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
