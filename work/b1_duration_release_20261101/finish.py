"""Final change inventory, immutable experiment and production asset receipt."""
from common import *

def main():
    assessment=read('assessment.json');assert assessment['adopt']
    assert read('public_api_checks.json')['all_passed'] and read('independent_checks.json')['all_passed']
    allowed={'B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py','B1算法/README.md'}
    changed=[]
    for path,expected in read('protected_before.json').items():
        assert (ROOT/path).is_file(),path
        if sha(ROOT/path)!=expected:changed.append(path)
    assert set(changed)==allowed,changed
    frozen=read('selection_freeze.json');post_install_source_changes=[]
    for path,expected in frozen['source_sha256'].items():
        if sha(ROOT/path)!=expected:post_install_source_changes.append(path)
    assert set(post_install_source_changes)<=allowed
    for relative,expected in read('staging_receipt.json')['files'].items():
        assert sha(ROOT/'B1算法/b1_algorithm/process'/relative)==expected,relative
    for path,expected in read('production_before.json').items():
        assert sha(HERE/'production_before'/Path(path).relative_to('B1算法'))==expected,path
    rows=read('test/metrics.json');facts=[r for p in ['minute','10s'] for r in read('test/'+p+'/facts.json')]
    assert len(rows)==6048 and len(facts)==2016 and all(r['status']=='ok' for r in rows)
    bases=len({r['base_task_id'] for r in facts});assert bases==792
    by={(r['task_id'],r['method']):r for r in rows}
    assert all(by[c['task_id'],'cpop']['eta_raw']==by[c['task_id'],'duration_fusion']['eta_raw']==by[c['task_id'],'labs']['eta_raw'] for c in facts)
    result=dict(status='complete',adopted=True,entrypoint='analyze_event(s)(...,process_method="duration_fusion")',
        main_scope='B1 first block; explicit bounded duration-refinement route',
        unchanged_global_default=True,original_CPOP_and_LABS_controls_retained=True,
        tested_inputs=len(facts),base_trajectories=bases,method_outputs=len(rows),
        primary_improvement_percent=100*(1-assessment['balanced_metrics']['duration_fusion']['primary_seconds']/assessment['balanced_metrics']['cpop']['primary_seconds']),
        changed_preexisting_protected_files=changed,new_production_files=read('installation_assets.json')['files'],
        raw_energy_identical=True,original_source_snapshots_verified=True,
        no_field_accuracy_claim=True,unknown_reference_validation_completed=False,event_false_alarm_improvement=False,
        no_report_or_second_block_changes=True,no_deletion_or_install_or_external_submission=True,
        observer_print_failure='Frozen assess.py JSON result saved before console numpy-bool serialization error; no scoring/code changes.',
        result_sha256={p.relative_to(HERE).as_posix():sha(p) for p in [HERE/'assessment.json',HERE/'test/metrics.json',HERE/'test/curves.json',HERE/'independent_checks.json',HERE/'public_api_checks.json',HERE/'segment_checks.json']})
    write('completion_receipt.json',result);print(json.dumps(native(result),ensure_ascii=False))
if __name__=='__main__':main()
