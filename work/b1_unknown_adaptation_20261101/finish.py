from common import *

def main():
    assessment=read('assessment.json');assert assessment['adopt'];assert read('independent_checks.json')['passed'] and read('public_checks.json')['passed']
    allowed={'B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py','B1算法/README.md'};changed=[]
    for p,h in read('preserved_before.json').items():
        if sha(ROOT/p)!=h:changed.append(p)
    assert set(changed)==allowed,changed
    for p,h in read('freeze.json')['source_sha256'].items():
        if p not in allowed:assert sha(ROOT/p)==h,p
    for p,h in read('production_before.json').items():assert sha(HERE/'production_before'/Path(p).relative_to('B1算法'))==h,p
    assert sha(ROOT/'B1算法/b1_algorithm/process/_reference_tracking.py')==sha(HERE/'staged_reference_tracking.py')
    model=HERE/read('error_tracking/selection.json')['selected']['model'];assert sha(model)==sha(ROOT/'B1算法/b1_algorithm/process/reference_tracking_model.json')
    rows=read('test/metrics.json');assert len(rows)==19712 and all(r['status']=='ok' for r in rows)
    main={r['method']:r for r in assessment['summary']['main']};short={r['method']:r for r in assessment['summary']['short']}
    result=dict(status='complete',adopted=True,entrypoint='process_method="reference_tracked_duration"',old_duration_fusion_retained=True,old_default_unchanged=True,
        scope='First block only, retrospective pre-actuation tracking, native1min EV30min/q1.5/sigma.05/pre/post15min; no report or second-block change',
        main_inputs=2304,extra_short_inputs=512,method_outputs=len(rows),
        main_duration_error_seconds_before=main['old_retained']['primary_seconds'],main_duration_error_seconds_after=main['tracked_retained']['primary_seconds'],
        improvement_percent=100*(1-main['tracked_retained']['primary_seconds']/main['old_retained']['primary_seconds']),
        short_local_miss_before=short['old_retained']['short_local_miss'],short_local_miss_after=short['tracked_retained']['short_local_miss'],short_positive_n=short['tracked_retained']['short_n'],
        same_condition_CPOP=main['tracked_cpop']['primary_seconds'],same_condition_LABS=main['tracked_labs']['primary_seconds'],
        changed_preexisting_files=changed,raw_measurement_deleted=False,original_energy_and_notice_reference_preserved=True,
        conditional_reference_is_not_notice_time_prediction=True,field_accuracy_claim=False,
        production_files={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in [ROOT/'B1算法/b1_algorithm/process/_reference_tracking.py',ROOT/'B1算法/b1_algorithm/process/reference_tracking_model.json']},
        result_sha256={name:sha(HERE/name) for name in ['assessment.json','independent_checks.json','public_checks.json','test/metrics.json','test/curves.json','freeze.json']})
    write('completion_receipt.json',result);print(json.dumps(native(result)),flush=True)
if __name__=='__main__':main()
