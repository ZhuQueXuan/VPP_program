"""Verify current evidence, unchanged prior science and maintained entries."""
from common import *
import ast,re
out=BASE/'runs/D061_DELIVERY_01';out.mkdir(exist_ok=False)
pp=BASE/'hil_diagnostic_protocol_v1.json';p=load(pp);assert sha(pp)==load(BASE/'hil_diagnostic_freeze_v1.json')['protocol_sha256']
for s in p['sources'].values():assert sha(ROOT/s['path'])==s['sha256']
assert sha(BASE/'runs/BL_HIL_POWER_01/calibration.json')==p['calibration_sha256']
assert sha(BASE/'runs/BL_HIL_POWER_01/predictions.csv')==p['old_predictions_sha256']
verified={}
for foldername in ['HIL_DIAGNOSTIC_01','HIL_DIAGNOSTIC_02','SPLITSMART_QA_01','SPLITSMART_QA_02','BL_HIL_POWER_01','BL_HIL_POWER_02','BL_TEMPERATURE_02']:
    folder=BASE/'runs'/foldername;r=load(folder/'receipt.json')
    for name,h in r['outputs'].items():assert sha(folder/name)==h,(foldername,name)
    verified[foldername]=len(r['outputs'])
for foldername in ['SPLITSMART_PREVIEW_01','CONTROL_CANDIDATE_01']:
    folder=BASE/'downloads'/foldername;r=load(folder/'receipt.json')
    assert all(x['status']=='downloaded' and sha(folder/x['name'])==x['sha256'] for x in r['files'])
prefix=BASE/'downloads/SPLITSMART_HEADERS_01';r=load(prefix/'receipt.json')
assert len(r['files'])==8
assert all(x['status']=='prefix_only' and x['bytes']==16384 and x['http_status']==206 and sha(prefix/(x['name']+'.prefix'))==x['prefix_sha256'] for x in r['files'])
v=load(BASE/'runs/HIL_DIAGNOSTIC_01/verification.json');assert v['status']=='passed' and all(v['replay_equal'].values())
assert load(BASE/'runs/BL_HIL_POWER_01/summary.json')['predeclared_relative_success'] is False
assert load(BASE/'runs/BL_TEMPERATURE_02/summary.json')['predeclared_relative_success'] is False
qa=load(BASE/'runs/SPLITSMART_QA_02/summary.json');assert qa['rows']==1092 and qa['backward']==88
assert qa['numeric_fields']['room_temp']['distinct_finite']==3
assert qa['numeric_fields']['Real_Power']['nonempty']==0 and not any(qa['admission'][k] for k in ['command_stage_response_validation','independent_real_active_power_validation','room_control_temperature_validation'])
previous={}
for resource,receipt in [('ev_charging','release_validation_v1_1.json'),('distributed_photovoltaic','release_validation_v1_2.json')]:
    folder=ROOT/'resource_research_results'/resource;r=load(folder/'results'/receipt)
    assert all(sha(folder/n)==h for n,h in r['verified_files'].items()),resource
    previous[resource]=len(r['verified_files'])
assert not (ROOT/'resource_research_results/air_conditioning').exists()
docs=['AGENTS.md','docs/DECISION_LOG.md','docs/DATA_CARD.md','docs/EXPERIMENT_LOG.md','outputs/ROADMAP_v2.md','outputs/第一阶段两周执行计划_v2_20261013.md','项目文件索引.md','resource_research_results/README.md','work/process_notes/2026-10-16_空调资源研究.md','work/air_conditioning_research_20261016/README.md']
for name in docs:assert 'D061' in (ROOT/name).read_text(encoding='utf-8'),name
assert '卡版本：DC-20261016-07' in (ROOT/'docs/DATA_CARD.md').read_text(encoding='utf-8')
ag=(ROOT/'AGENTS.md').read_text(encoding='utf-8');assert '先读D061' in ag and '2026-10-16现用D061' in ag
for f in BASE.glob('*.py'):ast.parse(f.read_text(encoding='utf-8'))
for f in BASE.glob('*.json'):load(f)
links=0
for t in re.findall(r'\]\(([^)]+)\)',(BASE/'README.md').read_text(encoding='utf-8')):
    if '://' in t:continue
    assert (BASE/t.split('#')[0]).exists(),t;links+=1
result={'date':'2026-10-16','decision':'D061','status':'passed','purpose':'posthoc description and candidate use check only, no new fitting or relative-success claim',
 'source_rows':341639,'observed_jump_rows':312,'old_test_predictions':130256,'independent_numeric_checks':6801,
 'full_SplitSmart_files_checked':1,'SplitSmart_full_rows':1092,'other_SplitSmart_files_prefix_only':8,
 'diagnostic_four_artifacts_replay_equal':True,'old_HVAC_failures_preserved':True,'final_HVAC_directory_absent':True,
 'existing_final_package_fingerprints_checked':previous,'scientific_outputs_verified':verified,'local_process_links':links,
 'current_records':{n:sha(ROOT/n) for n in docs},'protocol_sha256':sha(pp),'auditor_sha256':sha(Path(__file__))}
dump(out/'receipt.json',result);print(json.dumps({k:v for k,v in result.items() if k!='current_records'},ensure_ascii=False,indent=2))
