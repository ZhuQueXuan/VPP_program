"""Read-only acceptance of evidence plus versioned source release packaging."""
from pathlib import Path
import ast,csv,hashlib,json,re,sys,zipfile
ROOT=Path(__file__).resolve().parents[2];BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rd(rel):return json.loads((BASE/rel).read_text(encoding='utf-8-sig'))
checks={}
for rel in ['reference/checks.json','effects/verification_receipt.json','process/checks.json',
 'process/batch_checks.json','process/test/audit.json','pipeline_verification.json','reference_chain_receipt.json']:
 assert rd(rel)['passed'],rel
checks['component_and_pipeline_acceptance']=True
freeze=rd('process/test/freeze.json')
for name,expected in freeze['code_sha256'].items():assert sha(ROOT/'b1_algorithm/process'/name)==expected,name
for item in rd('reference/source_manifest.json')['formal_files']:
 assert sha(ROOT/item['path'])==item['sha256'],item['path']
checks['frozen_formal_process_and_reference_sources_unchanged']=True
study=rd('process/test/receipt.json');assert study['variants']==960 and study['independent_blocks']==20
assert study['shipped_policy']['default']=='guarded' and study['main_code_unchanged']
paired=list(csv.DictReader((BASE/'process/test/paired.csv').open(encoding='utf-8-sig',newline='')))
comparison=next(r for r in paired if r['candidate']=='unified_default' and r['comparator']=='conservative' and r['delta']=='all')
assert int(comparison['wins'])==20 and float(comparison['mc95_high'])<0
coarse=next(r for r in paired if r['candidate']=='unified_default' and r['comparator']=='RIDE_original' and r['delta']=='15.0')
assert float(coarse['mean_difference'])>0
checks['new_holdout_improvement_and_coarse_negative_result_retained']=True

# Old supplied source and previous report remain snapshots; no report authoring.
old=ROOT/'work/ride_b1_v02_reproduction_20261029'
manifest=json.loads((old/'source_manifest.json').read_text(encoding='utf-8'))
for item in manifest['files']:assert sha(old/'source'/item['path'])==item['sha256'],item['path']
assert sha(Path(manifest['archive']))==manifest['archive_sha256']
previous=json.loads((ROOT/'work/b1_mainline_20261029/report/build_receipt.json').read_text(encoding='utf-8'))
export=json.loads((ROOT/'work/b1_mainline_20261029/report/word_export.json').read_text(encoding='utf-8-sig'))
assert sha(previous['docx'])==previous['docx_sha256']
assert sha(previous['source'])==previous['source_sha256']
assert sha(export['pdf']).lower()==export['pdf_sha256'].lower()
checks['original_RIDE46_and_archive_unchanged']=True
checks['previous_report_files_unchanged_no_new_report']=True

for p in (ROOT/'b1_algorithm').rglob('*.py'):
 tree=ast.parse(p.read_text(encoding='utf-8'))
 for node in ast.walk(tree):
  if isinstance(node,ast.Import):
   assert all(not x.name.startswith(('work','ride.','run_process')) for x in node.names),str(p)
  elif isinstance(node,ast.ImportFrom) and node.level==0:
   assert not (node.module or '').startswith(('work','ride.','run_process')),str(p)
checks['formal_python_has_no_research_script_imports']=True

import b123_api
before=b123_api.extract_event([0.,10.,20.,30.,40.],[3.]*4,[3.,2.,2.,3.],10.,30.,1.5)
from b1_api import analyze_event,provided_reference
task=dict(task_id='release',user_id='release-user',meter_id='release-meter',start_min=0.,end_min=30.,notice_min=-15.,request_kw=1.5,task_pre_treatment=True)
reference=provided_reference(task,[-15.,0.,15.,30.],[0.,15.,30.,45.],[3.]*4,available_at_min=-15.)
event=analyze_event(task,[-15.,0.,15.,30.],[0.,15.,30.,45.],[3.,2.5,2.5,3.],reference,.05)
assert event['status']=='ok'
after=b123_api.extract_event([0.,10.,20.,30.,40.],[3.]*4,[3.,2.,2.,3.],10.,30.,1.5)
assert before==after and before['status']=='ok'
checks['old_b123_event_result_preserved_after_formal_import']=True

docpaths=[ROOT/'b1_algorithm/README.md',BASE/'README.md',ROOT/'.review/2026-10-29-b1-formal-v1.md']
links=0
for p in docpaths:
 for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
  if target.startswith(('https://','http://')):continue
  assert (p.parent/target).exists(),(str(p),target)
  links+=1
checks['local_links_verified']=links

files=[ROOT/'b1_api.py',ROOT/'run_b1_demo.cmd']
files+=sorted(p for p in (ROOT/'b1_algorithm').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.R','.json','.md','.txt') and p.name!='RELEASE_MANIFEST.json')
release=dict(version='1.0.0',date='2026-10-29',status='formal_integrated_scientific_implementation_validated_in_declared_domain',
 package_files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in files],
 dependencies='Python requirements plus explicitly configured external R4.6.1/cpop1.0.10; R runtime not included in source ZIP',
 limitations=['finite task domain','real data not validated','coarse timing not identified','full reference/process uncertainty not propagated'])
releasepath=ROOT/'b1_algorithm/RELEASE_MANIFEST.json'
releasepath.write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf-8')
archive=ROOT/'outputs/B1正式算法_v1.0.0_20261029.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in files+[releasepath]:z.write(p,p.relative_to(ROOT).as_posix())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for item in release['package_files']:assert hashlib.sha256(z.read(item['path'])).hexdigest()==item['sha256']
checks['release_zip_and_all_source_hashes_verified']=True
checks['release']=dict(version='1.0.0',files=len(files),zip=str(archive),zip_sha256=sha(archive),bytes=archive.stat().st_size)
checks['process_holdout']=dict(independent_seed_blocks=20,paired_variants=960,improved_blocks=20,
 mean_request_rmse_difference_kw=float(comparison['mean_difference']),mc95=[float(comparison['mc95_low']),float(comparison['mc95_high'])],
 coarse_vs_RIDE_difference_kw=float(coarse['mean_difference']))
checks['reference_chain']=rd('reference_chain_receipt.json')
checks['pipeline_checks']=rd('pipeline_verification.json')['n_checks']
checks['passed']=True
(BASE/'release_receipt.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(checks,ensure_ascii=False,indent=2))
