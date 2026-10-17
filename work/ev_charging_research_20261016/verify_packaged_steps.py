"""Replay the curated step kernel on all admitted original LF windows."""
from kit_common import *
from collections import defaultdict
import subprocess,sys,math

package=ROOT/'resource_research_results/ev_charging'
dest=package/'results/release_validation_v1_1.json';assert not dest.exists()
previous=load(package/'results/release_validation.json')
unchanged={n:sha(package/n)==h for n,h in previous['verified_files'].items() if n!='README.md'}
assert all(unchanged.values())
assert sha(package/'code/recorded_step_response.py')==sha(BASE/'recorded_step_kernel.py')
sys.path.insert(0,str(package/'code'))
from recorded_step_response import analyze_recorded_step

run=BASE/'runs/CHAR_KIT_STEPS_01';rr=read(run/'phase_step_features.csv')
curated=read(package/'results/recorded_step_phase_features.csv');assert len(rr)==len(curated)==4928
assert all(all(a[k]==v for k,v in b.items()) for a,b in zip(rr,curated))
bytrace=defaultdict(list)
for r in rr:bytrace[r['charging_uuid']].append(r)
con=connection();checks=0;maximum=0.;count=0
for uid,events in bytrace.items():
    d=trace(con,uid)
    for r in events:
        start=int(r['edge_index']);end=int(r['post_end_index']);t0=int(r['edge_time_us'])
        result=analyze_recorded_step([int(t)-t0 for t in d['t_us'][start:end]],
          [float(v) for v in d['i'+r['phase'][1:]][start:end]],float(r['pre_observed_current_A']),
          float(r['previous_command_A']),float(r['new_command_A']))
        for k,v in result.items():
            checks+=1
            if v is None:assert r[k]==''
            elif isinstance(v,(bool,str)):assert r[k]==str(v)
            else:
                diff=abs(v-float(r[k]));maximum=max(maximum,diff);assert diff<1e-12
        count+=1
    print('packaged replay',uid,len(events),flush=True)
assert count==4928

t=list(range(0,15000000,20000));i=[6.]*len(t)
flat=analyze_recorded_step(t,i,6,6,10)
assert flat['t90_sample_s'] is None and not flat['t90_observed'] and flat['transition_10_to90_s'] is None
bad_inputs=[(t[:-10],i[:-10],6,6,10),
 (t,[float('nan')]+i[1:],6,6,10),
 ([0,100000]+t[2:],i,6,6,10),
 (t,i,0,6,10)]
rejected=0
for args in bad_inputs:
    try:analyze_recorded_step(*args)
    except ValueError:rejected+=1
assert rejected==len(bad_inputs)
executions={}
for script in ('run_example.py','run_step_example.py'):
    p=subprocess.run([sys.executable,'-X','utf8','-B',str(package/script)],cwd=ROOT.parent,
      capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert p.returncode==0,p.stderr
    executions[script]={'exit_code':p.returncode,'stdout':p.stdout,'input_kind':'constructed'}
dump(run/'packaged_examples_v1_1.json',executions)
for final,source in [('recorded_step_summary.json',run/'summary.json'),
 ('recorded_step_recording_metrics.json',run/'recording_metrics.json'),
 ('recorded_step_coverage.json',BASE/'runs/PREP_KIT_STEPS_01/summary.json')]:
    assert sha(package/'results'/final)==sha(source)
pv=ROOT/'resource_research_results/distributed_photovoltaic'
assert all(sha(pv/n)==h for n,h in load(pv/'results/release_validation_v1_2.json')['verified_files'].items())
files={p.relative_to(package).as_posix():sha(p) for p in sorted(package.rglob('*')) if p.is_file() and p!=dest}
assert not any('__pycache__' in n or n.startswith(('downloads/','runs/')) for n in files)
result={'status':'passed','date':'2026-10-16','release_version':'1.1.0',
 'step_phase_events_replayed':count,'step_field_checks':checks,'maximum_step_numeric_difference':maximum,
 'previous_static_v1_0_code_parameters_results_unchanged':unchanged,
 'previous_static_v1_0_validation':'Historical receipt retains159003point replay. README intentionally updated; original scientific code/parameters/results identical.',
 'step_kernel_identical_to_frozen_research_kernel':True,'curated_derived_features_match':True,
 'invalid_or_incomplete_step_inputs_rejected':rejected,'censored_example_remains_null':True,
 'both_constructed_examples_from_outside_directory':True,'previous_PV_v1_2_files_unchanged':True,
 'protocol_sha256':sha(BASE/'kit_step_protocol_v1.json'),'step_research_verification':load(run/'verification.json'),
 'verified_files':files,'verifier_sha256':sha(Path(__file__)),
 'limits':'Packaging replay plus prior independent arithmetic verification; not independent physical timing truth, end-to-end dispatch or capacity validation. Recorded-event features are descriptive, not predictive holdout accuracy.'}
dump(dest,result)
print(json.dumps({k:v for k,v in result.items() if k not in ('verified_files','step_research_verification','previous_static_v1_0_code_parameters_results_unchanged')},ensure_ascii=False,indent=2))
