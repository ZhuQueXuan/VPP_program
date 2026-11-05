from common import *

def main():
    verification=read('verification.json');assert verification['passed'];summary=read('summary.json');rows=read('results.json');command=read('command_context_audit.json')
    confirmed={r['case_id'] for r in command if r['all_logged_command_fields_constant']};subset=[r for r in rows if r['case_id'] in confirmed]
    assessment=dict(status='real_background_transfer_not_passed',simulation30percent_reproduced_on_real_data=False,
        current_algorithm_retrained_or_tuned=False,old_simulation_result_retained=True,
        real_sources=dict(dortmund='https://zenodo.org/records/14065331',KIT='https://zenodo.org/records/17866847',EPFL='https://github.com/DESL-EPFL/Level-3-EV-charging-dataset'),
        evaluated_source='Dortmund actual ordinary AC charging external grid-PQA observations;12files screened,11pseudo-task windows from6recordings;5EV model names',
        all_background_windows=len(rows),old_positive_windows=summary['background_outputs']['retained']['positive_windows'],new_positive_windows=summary['background_outputs']['current']['positive_windows'],
        logged_constant_command_subset=dict(n=len(subset),old_positive=sum(r['methods']['retained']['positive'] for r in subset),new_positive=sum(r['methods']['current']['positive'] for r in subset)),
        original_observed_power_RMSE_kw=summary['prior_RMSE_kw'],new_conditional_observed_power_RMSE_kw=summary['conditional_RMSE_kw'],
        original_observed_power_MAE_kw=summary['prior_MAE_kw'],new_conditional_observed_power_MAE_kw=summary['conditional_MAE_kw'],
        RMSE_improved_windows=summary['RMSE_improved_windows'],
        cause_supported='Three added task-positive flags already present in original CPOP on corrected reference. The new background correction introduces them before duration calibration. At least Hyundai/Tesla extras have logged setpoint and enable status constant throughout.',
        real_response_duration_accuracy_proven=False,real_short_response_recall_proven=False,
        scope='No newly dispatched DR action: background prediction and false-positive-output challenge. Do not present11windows as labelled genuine demand-response events or as a population false-positive rate.',
        decision='Keep simulation artifacts/algorithms for research, but do not claim unknown-reference correction is real-data validated or suitable for field default. No new production selection or code modification.')
    write('real_assessment.json',assessment)
    for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
    write('completion_receipt.json',dict(status='complete',real_data_test_completed=True,real_transfer_passed=False,
        algorithm_code_models_and_data_unchanged=True,synthetic_responses_added=0,injected_noise_samples=0,
        real_AC_files_screened=12,real_windows=11,recordings=6,power_model_names=5,public_events=22,method_curve_outputs=66,
        independent_raw_minute_checks=verification['raw_minute_means_recomputed'],
        no_report_second_block_changes=True,no_installs_deletes_or_external_submission=True,
        files_sha256={name:sha(HERE/name) for name in ['protocol.json','selection.json','freeze.json','input_ledger.json','results.json','summary.json','verification.json','diagnosis.json','real_assessment.json','real_background_examples.png']}))
    print(json.dumps(native(assessment)),flush=True)
if __name__=='__main__':main()
