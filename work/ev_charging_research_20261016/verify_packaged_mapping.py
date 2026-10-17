"""Replay every held-out row with the curated code and parameters."""
from mapping_common import *
import math,subprocess,sys
package=ROOT/'resource_research_results/ev_charging';run=BASE/'runs/BL_EV_MAPPING_01'
dest=package/'results/release_validation.json';assert not dest.exists()
sys.path.insert(0,str(package/'code'))
from common_command_mapping import Calibration,map_common_command
params=load(package/'parameters/evtec_common_command_v1.json');cal={g:Calibration(**v['calibration']) for g,v in params['groups'].items()}
largest=0.;n=0;outofrange=0
for r in read(run/'predictions.csv'):
    rr=map_common_command(*[float(r['command_ID'+str(i)+'_kW']) for i in (2,3,4)],cal[r['group']])
    largest=max(largest,abs(rr['baseline_grid_kW']-float(r['B_SET'])),abs(rr['estimated_grid_kW']-float(r['M_CAP'])))
    assert rr['outside_training_command_range']==(r['command_outside_training_range']=='True')
    outofrange+=rr['outside_training_command_range'];n+=1
assert n==159003 and largest<1e-10 and outofrange==0
bad=0
for values in ((1,2,1),(-1,-1,-1),(math.nan,math.nan,math.nan),(math.inf,math.inf,math.inf)):
    try:map_common_command(*values,next(iter(cal.values())))
    except ValueError:bad+=1
assert bad==4
proc=subprocess.run([sys.executable,'-X','utf8','-B',str(package/'run_example.py')],cwd=ROOT.parent,capture_output=True,text=True,encoding='utf-8',timeout=30)
assert proc.returncode==0,proc.stderr
dump(run/'packaged_example_execution.json',{'status':'passed','exit_code':proc.returncode,'stdout':proc.stdout,'input_kind':'constructed'})
for name,source in (('mapping_summary.json',run/'summary.json'),('metrics.json',run/'metrics.json'),('group_metrics.csv',run/'group_metrics.csv'),('coverage.json',BASE/'runs/PREP_EV_MAPPING_01/coverage.json')):
    assert sha(package/'results'/name)==sha(source)
pv=ROOT/'resource_research_results/distributed_photovoltaic';pvreceipt=load(pv/'results/release_validation_v1_2.json')
assert all(sha(pv/n)==h for n,h in pvreceipt['verified_files'].items())
files={f.relative_to(package).as_posix():sha(f) for f in sorted(package.rglob('*')) if f.is_file() and f!=dest}
assert not any('__pycache__' in n or n.startswith(('downloads/','runs/')) for n in files)
result={'status':'passed','date':'2026-10-16','release_version':'1.0.0','rows_replayed':n,
 'maximum_prediction_difference_kW':largest,'range_flags_match':True,'out_of_training_range_rows':outofrange,
 'invalid_or_unequal_commands_rejected':bad,'constructed_example_from_outside_directory':True,
 'aggregate_results_match':True,'previous_PV_release_v1_2_files_unchanged':True,
 'protocol_sha256':sha(BASE/'common_command_mapping_protocol_v1.json'),'research_verification':load(run/'verification.json'),
 'verified_files':files,'verifier_sha256':sha(Path(__file__)),
 'limits':'Packaging identity only. Retained static command mapping is not validated control, capacity, physical timing or unobserved vehicle/site capability.'}
dump(dest,result)
print(json.dumps({k:v for k,v in result.items() if k not in ('verified_files','research_verification')},ensure_ascii=False,indent=2))
