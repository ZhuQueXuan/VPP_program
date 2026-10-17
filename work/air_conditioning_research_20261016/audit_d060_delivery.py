"""Check source/evidence identity, negative gate and maintained navigation."""
from common import *
import re,ast
out=BASE/'runs/D060_DELIVERY_01';out.mkdir(parents=True,exist_ok=False)
pp=BASE/'hil_power_protocol_v1.json';protocol=load(pp)
assert sha(pp)==load(BASE/'hil_power_freeze_v1.json')['protocol_sha256']
for source in list(protocol['sources'].values())+list(protocol['documents'].values()):assert sha(ROOT/source['path'])==source['sha256']
for name,receiptname in [('HIL_AC_QA_01','receipt.json'),('PREP_HIL_POWER_01','admission.json'),('BL_HIL_POWER_01','receipt.json'),('BL_HIL_POWER_02','receipt.json')]:
    folder=BASE/'runs'/name;r=load(folder/receiptname)
    for n,h in r['outputs'].items():assert sha(folder/n)==h,(name,n)
v=load(BASE/'runs/BL_HIL_POWER_01/verification.json');assert v['status']=='passed' and all(v['replay_artifacts_equal'].values())
s=load(BASE/'runs/BL_HIL_POWER_01/summary.json');assert s['training_rows']==211383 and s['test_rows']==130256
assert s['all']['M_TEMP_double_improves_B_COP'] and not s['predeclared_relative_success']
assert sum(r['M_TEMP_double_improves_B_COP'] for r in s['files'])==1
assert load(BASE/'runs/HIL_DOCUMENT_CHECK_01/receipt.json')['all_matrix_dates_match_file_first_dates']
notice=(BASE/'downloads/HIL_AC_SOURCE_01/LICENSE_NREL_DATASET.txt').read_text(encoding='utf-8')
assert len(notice)==2451 and 'IN NO EVENT' in notice
# Preserve all prior datasets/components; verify the old final fingerprints available.
previous={}
for resource,receipt in [('ev_charging','release_validation_v1_1.json'),('distributed_photovoltaic','release_validation_v1_2.json')]:
    folder=ROOT/'resource_research_results'/resource;r=load(folder/'results'/receipt)
    assert all(sha(folder/n)==h for n,h in r['verified_files'].items()),resource
    previous[resource]=len(r['verified_files'])
oldrun=BASE/'runs/BL_TEMPERATURE_02';old=load(oldrun/'receipt.json')
assert all(sha(oldrun/n)==h for n,h in old['outputs'].items())
assert load(oldrun/'summary.json')['predeclared_relative_success'] is False
assert not (ROOT/'resource_research_results/air_conditioning').exists()
docs=['AGENTS.md','docs/DECISION_LOG.md','docs/DATA_CARD.md','docs/EXPERIMENT_LOG.md','outputs/ROADMAP_v2.md',
 'outputs/第一阶段两周执行计划_v2_20261013.md','项目文件索引.md','resource_research_results/README.md',
 'work/process_notes/2026-10-16_空调资源研究.md','work/air_conditioning_research_20261016/README.md']
for name in docs:assert 'D060' in (ROOT/name).read_text(encoding='utf-8'),name
assert '卡版本：DC-20261016-06' in (ROOT/'docs/DATA_CARD.md').read_text(encoding='utf-8')
for p in BASE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
for p in BASE.glob('*.json'):load(p)
links=0
for target in re.findall(r'\]\(([^)]+)\)',(BASE/'README.md').read_text(encoding='utf-8')):
    if '://' in target:continue
    assert (BASE/target.split('#')[0]).exists(),target;links+=1
result={'date':'2026-10-16','decision':'D060','status':'passed','scientific_relative_gate':'failed_not_overridden',
 'original_AC_files':5,'raw_rows':341639,'training_rows':211383,'test_rows':130256,
 'independent_metric_checks':66,'five_scientific_artifacts_replay_identical':True,
 'PDF_measurement_boundary_visually_reviewed':True,'original_NREL_license_retained':True,
 'PLEIA_failure_and_scientific_files_unchanged':True,'previous_final_package_files_verified':previous,
 'no_new_final_AC_package':True,'process_links_checked':links,
 'current_records':{n:sha(ROOT/n) for n in docs},'protocol_sha256':sha(pp),'auditor_sha256':sha(Path(__file__))}
dump(out/'receipt.json',result);print(json.dumps({k:v for k,v in result.items() if k!='current_records'},ensure_ascii=False,indent=2))
