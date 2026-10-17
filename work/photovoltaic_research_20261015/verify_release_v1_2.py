"""Final artifact identity, aggregate consistency and runnable constructed examples."""
from crossseason_common import *
import os,subprocess
P=frozen();package=ROOT/'resource_research_results/distributed_photovoltaic';run=BASE/'runs/BL_CROSSSEASON_01'
dest=package/'results/release_validation_v1_2.json';assert not dest.exists()
old=json.loads((package/'results/release_validation_v1_1.json').read_text())
unchanged={n:sha(package/n)==h for n,h in old['verified_files'].items() if n!='README.md'}
assert all(unchanged.values())
check=json.loads((run/'verification.json').read_text());assert check['status']=='passed'
assert sha(BASE/'verify_crossseason.py')==check['verifier_sha256']
for n,h in json.loads((run/'receipt.json').read_text())['outputs'].items():assert sha(run/n)==h
results=package/'results'
for a,b in (('crossseason_forecast_bins.json','metrics.json'),('crossseason_source_profile.csv','source_monthly_profile.csv')):
    assert sha(results/a)==sha(run/b)
assert sha(results/'crossseason_coverage.json')==sha(BASE/'runs/PREP_CROSSSEASON_02/coverage.json')
groups=read(run/'group_metrics.csv');assert read(results/'crossseason_forecast_group_metrics.csv')==[r for r in groups if r['group_type']!='date']
summary=json.loads((results/'crossseason_forecast_summary.json').read_text())
origin=json.loads((run/'summary.json').read_text());assert all(summary[k]==v for k,v in origin.items())
comparisons=json.loads((run/'comparisons.json').read_text())
months=[r for r in comparisons if r['group_type']=='month'];days=[r for r in comparisons if r['group_type']=='date']
assert sum(r['mae_W_improves'] and r['rmse_W_improves'] for r in months)==5==summary['month_both_improve']
assert sum(r['mae_W_improves'] and r['rmse_W_improves'] for r in days)==91==summary['daily_both_improve']
flatmonths=('2020-01','2020-02','2020-04','2020-05');values={m:set() for m in flatmonths}
for r in read(BASE/'runs/PREP_CROSSSEASON_02/raw_power_rows.csv'):
    if r['time'][:7] in values and r['power_W']!='':values[r['time'][:7]].add(float(r['power_W']))
assert all(v=={0.,20.} for v in values.values())
env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
env['PYTHONPATH']=os.pathsep.join(str(ROOT/d) for d in ('work/python_packages/pvlib_smart_20261015','work/python_packages/storage_ecm_20261015','work/teacher_storage_brief_20261014/plot_dependencies'))
examples={}
for n in ('run_example.py','run_forecast_example.py'):
    proc=subprocess.run([sys.executable,'-X','utf8','-B',str(package/n)],cwd=ROOT.parent,env=env,capture_output=True,text=True,encoding='utf-8',timeout=60)
    assert proc.returncode==0,(n,proc.stderr)
    examples[n]={'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr,'data':'constructed inputs, not measured validation'}
dump(run/'release_examples_v1_2.json',examples)
acceptance=json.loads((results/'basic_research_acceptance.json').read_text())
assert len(acceptance['checks'])==6 and acceptance['release_version']=='1.2.0'
files={f.relative_to(package).as_posix():sha(f) for f in sorted(package.rglob('*')) if f.is_file() and f!=dest}
assert not any(n.startswith(('downloads/','runs/')) or '__pycache__' in n for n in files)
release={'status':'passed','release_version':'1.2.0','date':'2026-10-16','compute_code_and_parameters_unchanged_since_v1_1':True,
 'v1_1_files_except_README_unchanged':unchanged,'conditional_crossseason_rows_verified':23286,
 'independent_verification':check,'flat_months_finite_unique_W':{m:sorted(v) for m,v in values.items()},
 'aggregate_consistency_passed':True,'constructed_examples_from_outside_package':{n:v['exit_code']==0 for n,v in examples.items()},
 'previous_releases':'release_validation.json and release_validation_v1_1.json retained as historical receipts; their README fingerprints are historical.',
 'verified_files':files,'verifier_sha256':sha(Path(__file__)),
 'limit':'Engineering parity and scoped research acceptance only; not healthy all-season/online/control or official103 validation.'}
dump(dest,release)
print(json.dumps({k:v for k,v in release.items() if k not in ('verified_files','independent_verification','v1_1_files_except_README_unchanged')},ensure_ascii=False,indent=2))
