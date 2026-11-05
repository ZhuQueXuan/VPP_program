"""Micro-only original positive/zero mechanism and phase 2 input contracts."""
from pathlib import Path
import sys
import json
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import run
from generator import BASE,shift_fact


def main():
    by={};checks=[];model_before=run.sha(run.MODEL_PATH)
    for scenario in ('positive','zero'):
        facts,truth,meta=BASE.generate(7599920,n_users=8,events_per_user=2,scenario=scenario)
        facts=[shift_fact(f,8064000) for f in facts]
        for f in facts:f.update(non_event=False,task_dispatched=True)
        refs,_=run.bind_references(facts,'new')
        outputs,timing=run.process_path(facts,refs,'micro_continuous_'+scenario,'cpop')
        assert len(outputs)==16 and all(e['status']=='ok' for e in outputs)
        for f,e in zip(facts,outputs):
            assert f['factor_record']['task_id']==e['task']['task_id']
            assert f['factor_record']['treatment_set_min']==e['task']['notice_min']
            assert all(f['factor_record']['available_at_min'][name]<e['task']['notice_min'] for name in ('deadline_slack','demand_urgency'))
        run.dump_new(HERE/f'continuous_{scenario}.json',dict(events=outputs,factors=[f['factor_record'] for f in facts],timing=timing))
        by[scenario]=(facts,truth)
        checks.append(scenario+' complete16 events, legal factor identities and times')
    positive,pt=by['positive'];zero,zt=by['zero']
    assert all(a['reference_window']==b['reference_window'] and a['X']==b['X'] and a['offered_incentive']==b['offered_incentive'] for a,b in zip(positive,zero))
    assert any(t['cumulative_response_seconds']>0 for t in zt)
    assert all(BASE.potential_outcome(.4,t)==BASE.potential_outcome(2.,t) for t in zt)
    assert run.sha(run.MODEL_PATH)==model_before
    checks.extend(('positive/zero exogenous conditions paired','zero mechanism retains physical responses','zero intervention outcomes equal at .4 and2','frozen reference not refit or changed'))
    receipt=dict(passed=True,n_micro_process_outputs=32,checks=checks,
        scope='Micro original mechanism and CP/factor input contracts only, not main validation/test or estimator performance',main_phase2_data_generated=False)
    run.dump_new(HERE/'continuous_contract_receipt.json',receipt)
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
