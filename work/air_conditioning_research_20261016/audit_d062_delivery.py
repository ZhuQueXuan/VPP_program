"""Verify source versions, science identity, limited promotion and current entries."""
from common import *
import ast,re
out=BASE/'runs/D062_DELIVERY_01';out.mkdir(exist_ok=False)
pp=BASE/'dual_zone_protocol_v1.json';p=load(pp);assert sha(pp)==load(BASE/'dual_zone_freeze_v1.json')['protocol_sha256']
for source in p['sources'].values():assert sha(ROOT/source['path'])==source['sha256']
metadata=load(BASE/'downloads/DUAL_ZONE_METADATA_01/dataset.json');assert len(metadata['files'])==8 and sum(f['size'] for f in metadata['files'])==94326
qa=load(BASE/'runs/DUAL_ZONE_QA_02/summary.json');assert qa['total_rows']==2304 and all(f['non300s_intervals']==0 for f in qa['files'])
assert load(BASE/'runs/DUAL_ZONE_QA_01/failure.json')['status']=='technical_parser_failed_before_QA_output'
oldoutputs={}
for foldername,receiptname in [('DUAL_ZONE_QA_02','receipt.json'),('PREP_DUAL_ZONE_01','admission.json'),('BL_DUAL_ZONE_01','receipt.json'),('BL_DUAL_ZONE_02','receipt.json'),('HIL_DIAGNOSTIC_01','receipt.json'),('HIL_DIAGNOSTIC_02','receipt.json'),('BL_HIL_POWER_01','receipt.json'),('BL_HIL_POWER_02','receipt.json'),('BL_TEMPERATURE_02','receipt.json')]:
    folder=BASE/'runs'/foldername;r=load(folder/receiptname)
    for n,h in r['outputs'].items():assert sha(folder/n)==h,(foldername,n)
    oldoutputs[foldername]=len(r['outputs'])
v=load(BASE/'runs/BL_DUAL_ZONE_01/verification.json');assert v['status']=='passed' and all(v['replay_equal'].values())
s=load(BASE/'runs/BL_DUAL_ZONE_01/summary.json');assert s['predeclared_relative_success'] and s['test_rows']==2288
assert all(d['improves_both_baselines'] for d in s['days']) and len(s['days'])==4
zero=s['groups']['current_zero_P'];assert zero['M_HEAT5']['MAE_C']>zero['B_P']['MAE_C']
assert load(BASE/'runs/BL_HIL_POWER_01/summary.json')['predeclared_relative_success'] is False
assert load(BASE/'runs/BL_TEMPERATURE_02/summary.json')['predeclared_relative_success'] is False
pkg=ROOT/'resource_research_results/air_conditioning';release=load(pkg/'results/release_validation_v1_0.json');assert release['status']=='passed' and release['max_prediction_difference_C']==0.
assert all(sha(pkg/n)==h for n,h in release['verified_files'].items())
assert release['resource_basic_package_acceptance']=='not_yet_declared'
expected={'README.md','code/room_temperature.py','parameters/dual_zone_temperature_v1.json','examples/constructed_inputs.json','run_example.py','运行示例.cmd','source_manifest.json','results/validation_metrics.json','results/evidence_summary.json','results/release_validation_v1_0.json'}
actual={str(f.relative_to(pkg)).replace('\\','/') for f in pkg.rglob('*') if f.is_file()};assert actual==expected,(actual,expected)
previous={}
for resource,receipt in [('ev_charging','release_validation_v1_1.json'),('distributed_photovoltaic','release_validation_v1_2.json')]:
    folder=ROOT/'resource_research_results'/resource;r=load(folder/'results'/receipt)
    assert all(sha(folder/n)==h for n,h in r['verified_files'].items()),resource;previous[resource]=len(r['verified_files'])
docs=['AGENTS.md','docs/DECISION_LOG.md','docs/DATA_CARD.md','docs/EXPERIMENT_LOG.md','outputs/ROADMAP_v2.md','outputs/第一阶段两周执行计划_v2_20261013.md','项目文件索引.md','resource_research_results/README.md','work/process_notes/2026-10-16_空调资源研究.md','work/air_conditioning_research_20261016/README.md']
for n in docs:assert 'D062' in (ROOT/n).read_text(encoding='utf-8'),n
assert '卡版本：DC-20261016-08' in (ROOT/'docs/DATA_CARD.md').read_text(encoding='utf-8')
assert '先读D062' in (ROOT/'AGENTS.md').read_text(encoding='utf-8')
assert '2026-10-16现用D062' in (ROOT/'AGENTS.md').read_text(encoding='utf-8')
for f in list(BASE.glob('*.py'))+list(pkg.rglob('*.py')):ast.parse(f.read_text(encoding='utf-8'))
for f in list(BASE.glob('*.json'))+list(pkg.rglob('*.json')):load(f)
links=0
for fp in [BASE/'README.md',pkg/'README.md',ROOT/'resource_research_results/README.md']:
    for link in re.findall(r'\]\(([^)]+)\)',fp.read_text(encoding='utf-8')):
        if '://' in link:continue
        assert (fp.parent/link.split('#')[0]).exists(),(str(fp),link);links+=1
result={'date':'2026-10-16','decision':'D062','status':'passed','new_raw_CSV':8,'raw_rows':2304,'raw_bytes':94326,'publisher_source_SHA256_all_match':True,'protocol_sha256':sha(pp),'new_test_rows':2288,'relative_gate_passed':True,'zero_power_MAE_failure_preserved':True,'independent_metric_checks':204,'five_scientific_artifacts_identical':True,'final_test_replay_difference_C':0.,'final_component_files':len(actual),'resource_basic_package_acceptance':'not_yet_declared','old_HVAC_failures_preserved':True,'old_scientific_outputs_verified':oldoutputs,'existing_final_package_fingerprints_checked':previous,'links_checked':links,'current_records':{n:sha(ROOT/n) for n in docs},'auditor_sha256':sha(Path(__file__))}
dump(out/'receipt.json',result);print(json.dumps({k:v for k,v in result.items() if k!='current_records'},ensure_ascii=False,indent=2))
