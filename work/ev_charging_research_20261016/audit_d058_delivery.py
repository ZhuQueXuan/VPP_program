"""Read-only final artifact/record consistency audit; save one process receipt."""
from mapping_common import *
import re,ast

out=BASE/'runs/D058_DELIVERY_CHECK_01';out.mkdir(exist_ok=False)
package=ROOT/'resource_research_results/ev_charging'
release=load(package/'results/release_validation_v1_1.json')
assert release['status']=='passed'
for n,h in release['verified_files'].items():assert sha(package/n)==h,n
pp=BASE/'kit_step_protocol_v1.json';protocol=load(pp)
assert sha(pp)==load(BASE/'kit_step_freeze_v1.json')['protocol_sha256']
for source in protocol['sources'].values():assert sha(ROOT/source['path'])==source['sha256']
for name in ('KIT_SOURCE_QA_01','PREP_KIT_STEPS_01','CHAR_KIT_STEPS_01','CHAR_KIT_STEPS_02'):
    folder=BASE/'runs'/name
    receipt=load(folder/('admission.json' if name.startswith('PREP') else 'receipt.json'))
    for n,h in receipt['outputs'].items():assert sha(folder/n)==h,(name,n)
acceptance=load(package/'results/basic_research_acceptance_v1_1.json')
assert len(acceptance['checks'])==6 and all(r['status']=='complete_with_scope' for r in acceptance['checks'])
summary=load(package/'results/recorded_step_summary.json')
assert summary['all']['phase_events']==4928
assert summary['all']['t90_observed']+summary['all']['t90_not_observed_within10s']==4928
assert summary['all']['t90_not_observed_within10s']==665
links=0
for p in (package/'README.md',ROOT/'resource_research_results/README.md'):
    for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
        if '://' in target or target.startswith('#'):continue
        assert (p.parent/target.split('#')[0]).resolve().exists(),(str(p),target)
        links+=1
for p in package.rglob('*.json'):load(p)
for p in package.rglob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
docs=['docs/DECISION_LOG.md','docs/DATA_CARD.md','docs/EXPERIMENT_LOG.md',
 'outputs/ROADMAP_v2.md','outputs/第一阶段两周执行计划_v2_20261013.md',
 'work/process_notes/2026-10-16_电动汽车充电设施研究.md','work/ev_charging_research_20261016/README.md',
 'AGENTS.md','项目文件索引.md','resource_research_results/README.md']
for n in docs:assert 'D058' in (ROOT/n).read_text(encoding='utf-8'),n
assert '卡版本：DC-20261016-04' in (ROOT/'docs/DATA_CARD.md').read_text(encoding='utf-8')
result={'status':'passed','date':'2026-10-16','decision':'D058','release_version':'1.1.0',
 'final_files_verified':len(release['verified_files']),'local_delivery_links_verified':links,
 'source_protocol_scientific_receipts_intact':True,'six_basic_acceptance_items_bounded':True,
 'observations':4928,'observed90':4263,'not_observed90':665,
 'current_delivery_receipt_sha256':sha(package/'results/release_validation_v1_1.json'),
 'maintained_records':{n:sha(ROOT/n) for n in docs},'auditor_sha256':sha(Path(__file__)),
 'limits':'Final consistency check only; physical capacity/end-to-end control and formal P1/103 acceptance remain unverified.'}
dump(out/'receipt.json',result)
print(json.dumps({k:v for k,v in result.items() if k!='maintained_records'},ensure_ascii=False,indent=2))
