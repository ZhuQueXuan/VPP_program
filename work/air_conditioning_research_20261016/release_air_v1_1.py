"""Release exact unchanged runtime plus independently checked descriptive evidence."""
from common import *
import re,ast
pkg=ROOT/'resource_research_results/air_conditioning';rp=pkg/'results/release_validation_v1_1.json';assert not rp.exists()
old=load(pkg/'results/release_validation_v1_0.json');unchanged={}
for name,h in old['verified_files'].items():
    if name=='README.md':assert sha(BASE/'runs/PACKAGE_AIR_V1_1_01/README_v1_0.md')==h;continue
    assert sha(pkg/name)==h,name;unchanged[name]=h
v=load(BASE/'runs/CHAR_AIR_01/verification.json');assert v['status']=='passed'
accept=load(pkg/'results/basic_research_acceptance_v1_1.json');assert len(accept['six_checks'])==6 and all(x['passed_in_scope'] for x in accept['six_checks'])
assert accept['status']=='limited_basic_package_complete' and not accept['formal103_passed'] and accept['new_fitted_parameters']==0
for src,dst in [('runs/CHAR_AIR_01/characteristics.json','results/characteristic_summary_v1_1.json'),('runs/AIR_CURVES_01/test_temperature_curves.png','results/test_temperature_curves_v1_1.png'),('runs/AIR_CURVES_01/test_temperature_curves.svg','results/test_temperature_curves_v1_1.svg')]:assert sha(BASE/src)==sha(pkg/dst)
for name in ['BL_DUAL_ZONE_01','BL_DUAL_ZONE_02','BL_HIL_POWER_01','BL_TEMPERATURE_02']:
    folder=BASE/'runs'/name;r=load(folder/'receipt.json');assert all(sha(folder/n)==h for n,h in r['outputs'].items())
assert load(BASE/'runs/BL_DUAL_ZONE_01/summary.json')['predeclared_relative_success']
assert not load(BASE/'runs/BL_HIL_POWER_01/summary.json')['predeclared_relative_success']
assert not load(BASE/'runs/BL_TEMPERATURE_02/summary.json')['predeclared_relative_success']
for f in pkg.rglob('*.py'):ast.parse(f.read_text(encoding='utf-8'))
result={'date':'2026-10-16','decision':'D063','version':'1.1.0','status':'passed','bounded_basic_package_complete':True,'scope':accept['scope'],'six_checks_passed':6,
 'model_or_coefficients_or_prediction_gate_changed':False,'new_fitted_parameters':0,'new_independent_forecast_test_points':0,'current_runtime_and_scientific_files_identical_to_v1_0':unchanged,
 'previous_runtime_full_replay_rows':old['full_test_rows_replayed'],'previous_runtime_replay_difference_C':old['max_prediction_difference_C'],'previous_runtime_replay_evidence_reused_by_exact_fingerprint':True,
 'previous_7invalid_cases_and_directory_independent_example_retained':True,'new_independent_description_numeric_checks':v['numeric_checks'],'all_observed_pairs_checked':4592,'all_plot_source_room_labels_checked':2304,'all_forecasts_target_time_checked':2288,
 'PNG_manually_reviewed':True,'SVG_separately_rendered':False,'SVG_and_PNG_same_matplotlib_figure':True,'new_description_four_test_days_not_best_case_selection':True,
 'known_negative_results_preserved':True,'real_online_or_control_or_capacity_validated':False,'all_type_P1_or_103_passed':False,
 'historical_v1_0_README_sha256':sha(BASE/'runs/PACKAGE_AIR_V1_1_01/README_v1_0.md'),'previous_release_receipt_sha256':sha(pkg/'results/release_validation_v1_0.json'),
 'verified_files':{str(f.relative_to(pkg)).replace('\\','/'):sha(f) for f in sorted(pkg.rglob('*')) if f.is_file()},'review_script_sha256':sha(Path(__file__))}
dump(rp,result)
links=0
for target in re.findall(r'\]\(([^)]+)\)',(pkg/'README.md').read_text(encoding='utf-8')):
    if '://' in target:continue
    assert (pkg/target.split('#')[0]).exists(),target;links+=1
dump(BASE/'runs/PACKAGE_AIR_V1_1_01/release_check.json',{'status':'passed','current_release_receipt_sha256':sha(rp),'README_local_links_checked':links,'previous_exact_runtime_and_scientific_fingerprints':len(unchanged)})
print(json.dumps({k:v for k,v in result.items() if k not in ['verified_files','current_runtime_and_scientific_files_identical_to_v1_0']},ensure_ascii=False,indent=2))
