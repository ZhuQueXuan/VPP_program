"""Final bounded-stage audit: existing six criteria, exact old science and navigation."""
from common import *
import re,ast
out=BASE/'runs/D063_DELIVERY_01';out.mkdir(exist_ok=False)
pkg=ROOT/'resource_research_results/air_conditioning';r=load(pkg/'results/release_validation_v1_1.json')
assert r['status']=='passed' and r['six_checks_passed']==6 and not r['model_or_coefficients_or_prediction_gate_changed']
assert all(sha(pkg/n)==h for n,h in r['verified_files'].items())
a=load(pkg/'results/basic_research_acceptance_v1_1.json');assert a['status']=='limited_basic_package_complete' and all(x['passed_in_scope'] for x in a['six_checks'])
assert not a['all_type_P1_passed'] and not a['formal103_passed'] and a['new_forecast_validation_points']==0
pp=BASE/'air_characteristic_protocol_v1.json';p=load(pp);assert sha(pp)==load(BASE/'air_characteristic_freeze_v1.json')['protocol_sha256']
for src in p['sources'].values():assert sha(ROOT/src['path'])==src['sha256']
assert sha(BASE/'runs/BL_DUAL_ZONE_01/predictions.csv')==p['old_predictions_sha256']
verified={}
for foldername in ['CHAR_AIR_01','CHAR_AIR_02','AIR_CURVES_01','BL_DUAL_ZONE_01','BL_DUAL_ZONE_02','HIL_DIAGNOSTIC_01','BL_HIL_POWER_01','BL_TEMPERATURE_02']:
    folder=BASE/'runs'/foldername;receipt=load(folder/'receipt.json')
    assert all(sha(folder/n)==h for n,h in receipt['outputs'].items());verified[foldername]=len(receipt['outputs'])
v=load(BASE/'runs/CHAR_AIR_01/verification.json');assert v['status']=='passed' and v['numeric_checks']==11890
assert not load(BASE/'runs/BL_HIL_POWER_01/summary.json')['predeclared_relative_success']
assert not load(BASE/'runs/BL_TEMPERATURE_02/summary.json')['predeclared_relative_success']
old=load(pkg/'results/release_validation_v1_0.json');assert sha(BASE/'runs/PACKAGE_AIR_V1_1_01/README_v1_0.md')==old['verified_files']['README.md']
for n,h in old['verified_files'].items():
    if n!='README.md':assert sha(pkg/n)==h
expected={'README.md','code/room_temperature.py','parameters/dual_zone_temperature_v1.json','examples/constructed_inputs.json','run_example.py','运行示例.cmd','source_manifest.json','results/validation_metrics.json','results/evidence_summary.json','results/release_validation_v1_0.json','results/characteristic_summary_v1_1.json','results/test_temperature_curves_v1_1.png','results/test_temperature_curves_v1_1.svg','results/basic_research_acceptance_v1_1.json','results/release_validation_v1_1.json'}
assert {str(f.relative_to(pkg)).replace('\\','/') for f in pkg.rglob('*') if f.is_file()}==expected
previous={}
for resource,receipt,key in [('lithium_ion_storage','release_validation.json','artifact_sha256'),('ev_charging','release_validation_v1_1.json','verified_files'),('distributed_photovoltaic','release_validation_v1_2.json','verified_files')]:
    folder=ROOT/'resource_research_results'/resource;oldr=load(folder/'results'/receipt);assert all(sha(folder/n)==h for n,h in oldr[key].items());previous[resource]=len(oldr[key])
meta=load(BASE/'downloads/SHIFDR_METADATA_01/michigan_datacite.json')['data']['attributes'];assert meta['rightsList']==[]
assert load(BASE/'downloads/SHIFDR_SUBSET_01/receipt.json')['files'][0]['status']=='failed'
status=load(BASE/'control_candidate_status_v3.json');assert status['SHIFDR']['admitted'] is False and status['SHIFDR']['raw_downloaded'] is False
docs=['AGENTS.md','docs/DECISION_LOG.md','docs/DATA_CARD.md','docs/EXPERIMENT_LOG.md','outputs/ROADMAP_v2.md','outputs/第一阶段两周执行计划_v2_20261013.md','项目文件索引.md','resource_research_results/README.md','work/process_notes/2026-10-16_空调资源研究.md','work/air_conditioning_research_20261016/README.md']
for n in docs:assert 'D063' in (ROOT/n).read_text(encoding='utf-8'),n
assert '卡版本：DC-20261016-09' in (ROOT/'docs/DATA_CARD.md').read_text(encoding='utf-8')
ag=(ROOT/'AGENTS.md').read_text(encoding='utf-8');assert '先读D063' in ag and '2026-10-16现用D063' in ag
for f in list(BASE.glob('*.py'))+list(pkg.rglob('*.py')):ast.parse(f.read_text(encoding='utf-8'))
for f in list(BASE.glob('*.json'))+list(pkg.rglob('*.json')):load(f)
links=0
for fp in [BASE/'README.md',pkg/'README.md',ROOT/'resource_research_results/README.md']:
    for link in re.findall(r'\]\(([^)]+)\)',fp.read_text(encoding='utf-8')):
        if '://' in link:continue
        assert (fp.parent/link.split('#')[0]).exists(),(str(fp),link);links+=1
result={'date':'2026-10-16','decision':'D063','status':'passed','bounded_basic_package_complete':True,'six_unchanged_D046_checks_passed':6,'new_fitted_parameters':0,'new_independent_forecast_points':0,'original_model_gate_scores_and_negative_results_preserved':True,'observed_room_labels':4608,'observed_within_file_pairs':4592,'new_independent_numeric_checks':11890,'curve_panels':8,'curve_source_labels_checked':2304,'curve_target_forecasts_checked':2288,'PNG_reviewed_SVG_same_figure':True,'SHIFDR_no_raw_or_control_admission':True,'original_runtime_fingerprints_preserved':True,'previous_three_final_package_files_verified':previous,'old_and_new_scientific_artifacts_verified':verified,'final_air_files':15,'local_links_checked':links,'all_type_P1_or_103_acceptance':False,'no_new_handoff_teacher_report_or_cross_resource_integration':True,'current_records':{n:sha(ROOT/n) for n in docs},'auditor_sha256':sha(Path(__file__))}
dump(out/'receipt.json',result);print(json.dumps({k:v for k,v in result.items() if k!='current_records'},ensure_ascii=False,indent=2))
