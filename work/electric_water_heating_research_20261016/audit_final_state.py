from common import *
import re,ast
out=BASE/'runs/PACKAGE_TEMPERATURE_01/final_state_audit.json';assert not out.exists()
dest=ROOT/'resource_research_results/electric_water_heating';release=load(dest/'results/release_validation.json')
for n,h in release['verified_files'].items():assert sha(dest/n)==h,n
review=load(dest/'results/basic_research_acceptance.json');assert review['bounded_basic_package_complete'] and review['checks_passed']==6 and len(review['criteria'])==6
model=load(BASE/'runs/VERIFY_TEMPERATURE_01/receipt.json');assert model['status']=='passed'
pp=BASE/'temperature_protocol_v1.json';assert sha(pp)==model['protocol_sha256']==load(BASE/'temperature_freeze_v1.json')['protocol_sha256']
assert sha(BASE/'runs/PREP_TEMPERATURE_01/admission.json')==model['admission_sha256']
source=load(BASE/'downloads/SOURCE_01/dataset.json');manifest={f['filename']:f for f in source['files']}
for item in load(pp)['files']:
    f=ROOT/item['path'];assert f.stat().st_size==manifest[item['name']]['size'] and sha(f)==item['sha256']==manifest[item['name']]['content_details']['sha256_hash']
for n,h in load(BASE/'runs/SOURCE_QA_02/receipt.json')['outputs'].items():assert sha(BASE/'runs/SOURCE_QA_02'/n)==h
links=0
for f in [BASE/'README.md',dest/'README.md',ROOT/'work/process_notes/2026-10-16_储热式电热水器研究.md']:
    for href in re.findall(r'\]\(([^)]+)\)',f.read_text(encoding='utf-8')):
        if '://' in href or href.startswith('#'):continue
        target=(f.parent/href.split('#')[0]).resolve();assert target.exists(),(str(f),href);links+=1
for path,token in [('AGENTS.md','现用D067'),('项目文件索引.md','现用D067'),('docs/DATA_CARD.md','DC-20261016-13'),('outputs/ROADMAP_v2.md','最新执行（D067）'),('outputs/第一阶段两周执行计划_v2_20261013.md','最新执行（D067）'),('docs/EXPERIMENT_LOG.md','BL-WATER-TEMPERATURE-20261016'),('docs/DECISION_LOG.md','## D067｜')]:assert token in (ROOT/path).read_text(encoding='utf-8')
oldfiles=0
for name,receipt,key in [('lithium_ion_storage','release_validation.json','artifact_sha256'),('distributed_photovoltaic','release_validation_v1_2.json','verified_files'),('ev_charging','release_validation_v1_1.json','verified_files'),('air_conditioning','release_validation_v1_1.json','verified_files'),('wind_power','release_validation_v1_1.json','verified_files')]:
    folder=ROOT/'resource_research_results'/name;r=load(folder/'results'/receipt)
    for n,h in r[key].items():assert sha(folder/n)==h
    oldfiles+=len(r[key])
py=list(BASE.glob('*.py'))+list(dest.rglob('*.py'))
for f in py:ast.parse(f.read_text(encoding='utf-8'))
result={'status':'passed','date':'2026-10-16','current':'D067/DC-20261016-13/electric_water_heating1.0',
 'release_files_sha256_verified':len(release['verified_files']),'main_source_files_publisher_size_and_sha256_verified':7,
 'prior_five_packages_files_unchanged':oldfiles,'new_local_document_links_checked':links,'python_source_files_parsed':len(py),
 'six_bounded_basic_packages':True,'industrial_boiler_or_true_energy_or_control_validated':False,'allP1_or103passed':False,
 'handoff_or_teacher_artifacts_edited':False,'scientific_experiments_repeated_for_bookkeeping':False,'verifier_sha256':sha(Path(__file__))}
dump(out,result);print(json.dumps(result,indent=2))
