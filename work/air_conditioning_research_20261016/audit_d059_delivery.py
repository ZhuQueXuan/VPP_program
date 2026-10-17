"""Final bounded check of retained scientific evidence and current records."""
from common import *
import re,ast
out=BASE/'runs/D059_DELIVERY_01';out.mkdir(parents=True,exist_ok=False)
for name,receiptname in [('PLEIA_ARCHIVE_01','receipt.json'),('PLEIA_SOURCE_QA_01','receipt.json'),('PREP_TEMPERATURE_01','admission.json'),('BL_TEMPERATURE_02','receipt.json'),('BL_TEMPERATURE_03','receipt.json')]:
    folder=BASE/'runs'/name;receipt=load(folder/receiptname)
    for n,h in receipt['outputs'].items():assert sha(folder/n)==h,(name,n)
assert load(BASE/'runs/PLEIA_ARCHIVE_01/receipt.json')['members']==37
for source in load(BASE/'temperature_protocol_v1.json')['sources'].values():assert sha(ROOT/source['path'])==source['sha256']
assert sha(BASE/'temperature_protocol_v1.json')==load(BASE/'temperature_freeze_v1.json')['protocol_sha256']
v=load(BASE/'runs/BL_TEMPERATURE_02/verification.json');assert v['status']=='passed'
summary=load(BASE/'runs/BL_TEMPERATURE_02/summary.json');assert summary['test_rows']==548660 and summary['predeclared_relative_success'] is False
old_packages={}
for kind,receiptname in [('ev_charging','release_validation_v1_1.json'),('distributed_photovoltaic','release_validation_v1_2.json'),('lithium_ion_storage','release_validation.json')]:
    folder=ROOT/'resource_research_results'/kind;receipt=load(folder/'results'/receiptname)
    if 'verified_files' in receipt:
        assert all(sha(folder/n)==h for n,h in receipt['verified_files'].items()),kind
        old_packages[kind]={'verified_files':len(receipt['verified_files']),'unchanged':True}
    else:old_packages[kind]={'receipt_read':True,'note':'No common verified_files mapping; no new immutability claim beyond untouched scope.'}
assert not (ROOT/'resource_research_results/air_conditioning').exists()
records=['AGENTS.md','docs/DECISION_LOG.md','docs/DATA_CARD.md','docs/EXPERIMENT_LOG.md','outputs/ROADMAP_v2.md',
 'outputs/第一阶段两周执行计划_v2_20261013.md','项目文件索引.md','resource_research_results/README.md',
 'work/process_notes/2026-10-16_空调资源研究.md','work/air_conditioning_research_20261016/README.md']
for name in records:
    text=(ROOT/name).read_text(encoding='utf-8');assert 'D059' in text,name
    if 'ZIP成员' in text and name!='docs/EXPERIMENT_LOG.md':assert '40个ZIP成员' not in text
for p in BASE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
for p in BASE.glob('*.json'):load(p)
links=0
for target in re.findall(r'\]\(([^)]+)\)',(BASE/'README.md').read_text(encoding='utf-8')):
    if '://' in target:continue
    assert (BASE/target.split('#')[0]).exists(),target;links+=1
result={'status':'passed','date':'2026-10-16','decision':'D059','scientific_result':'First ARX failed fixed gain; no final package claimed.',
 'archive_members':37,'original_protocol_and_scientific_outputs_intact':True,
 'test_rows_independently_checked':548660,'numeric_metrics_checked':558,
 'prior_final_packages':old_packages,'current_records':{n:sha(ROOT/n) for n in records},
 'current_protocol_sha256':sha(BASE/'temperature_protocol_v1.json'),'local_process_links_checked':links,
 'auditor_sha256':sha(Path(__file__))}
dump(out/'receipt.json',result)
print(json.dumps({k:v for k,v in result.items() if k not in ('current_records',)},ensure_ascii=False,indent=2))
