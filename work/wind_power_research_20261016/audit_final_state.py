"""Final identity/navigation audit, without repeating unchanged experiments."""
from common import *
import ast,re
dest=ROOT/'resource_research_results/wind_power';release=load(dest/'results/release_validation_v1_1.json')
assert release['bounded_basic_package_complete'] and release['checks_passed']==6
for n,h in release['verified_files'].items():assert sha(dest/n)==h,n
old=load(dest/'results/release_validation.json')
assert sha(ROOT/release['previous_README_snapshot_path'])==old['verified_files']['README.md']
for n,h in release['original_code_parameters_examples_metrics_unchanged'].items():assert sha(dest/n)==h==old['verified_files'][n]
assert load(dest/'results/basic_research_acceptance_v1_1.json')['checks_passed']==6
assert sha(BASE/'curve_protocol_v1.json')==load(BASE/'curve_freeze_v1.json')['protocol_sha256']==load(BASE/'runs/VERIFY_CURVE_01/receipt.json')['protocol_sha256']
assert sha(BASE/'characteristic_protocol_v1.json')==load(BASE/'runs/VERIFY_CHAR_CURVE_01/receipt.json')['protocol_sha256']
links=0
for f in [BASE/'README.md',dest/'README.md',ROOT/'work/process_notes/2026-10-16_风电资源研究.md']:
    for href in re.findall(r'\]\(([^)]+)\)',f.read_text(encoding='utf-8')):
        if '://' in href or href.startswith('#'):continue
        target=(f.parent/href.split('#')[0]).resolve();assert target.exists(),(str(f),href);links+=1
prior=load(dest/'results/release_validation.json')['prior_four_packages']
for name,receipt,key in [('lithium_ion_storage','release_validation.json','artifact_sha256'),('distributed_photovoltaic','release_validation_v1_2.json','verified_files'),('ev_charging','release_validation_v1_1.json','verified_files'),('air_conditioning','release_validation_v1_1.json','verified_files')]:
    folder=ROOT/'resource_research_results'/name;rr=load(folder/'results'/receipt)
    for n,h in rr[key].items():assert sha(folder/n)==h
for path,token in [('AGENTS.md','现用D066'),('项目文件索引.md','现用D066'),('docs/DATA_CARD.md','DC-20261016-12'),('outputs/ROADMAP_v2.md','最新执行（D066）'),('outputs/第一阶段两周执行计划_v2_20261013.md','最新执行（D066）'),('docs/EXPERIMENT_LOG.md','CHAR-WIND-20261016'),('docs/DECISION_LOG.md','## D066｜')]:assert token in (ROOT/path).read_text(encoding='utf-8')
parsed=0
for f in list(BASE.glob('*.py'))+list(dest.rglob('*.py')):
    ast.parse(f.read_text(encoding='utf-8'));parsed+=1
value={'status':'passed','date':'2026-10-16','current':'D066 / DC-20261016-12 / wind1.1.0',
 'wind_release_files_sha256_verified':len(release['verified_files']),'original_four_release_files_unchanged':sum(x['files'] for x in prior),
 'original_runtime_and_scientific_files_unchanged':len(release['original_code_parameters_examples_metrics_unchanged']),
 'local_new_document_links_checked':links,'python_sources_parsed':parsed,
 'scientific_experiments_repeated_for_bookkeeping':False,'fifth_bounded_basic_package_complete':True,
 'sixth_resource_selected':False,'fullP1_or103_passed':False,'handoff_or_teacher_artifacts_edited':False,
 'verifier_sha256':sha(Path(__file__))}
dump(BASE/'runs/PACKAGE_WIND_V1_1_01/final_state_audit.json',value);print(json.dumps(value,indent=2))
