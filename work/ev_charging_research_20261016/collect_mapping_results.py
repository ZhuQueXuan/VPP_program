"""Curate only retained calculation/parameters/examples/aggregate evidence."""
from mapping_common import *
run=BASE/'runs/BL_EV_MAPPING_01';dest=ROOT/'resource_research_results/ev_charging'
assert load(run/'verification.json')['status']=='passed' and load(run/'summary.json')['predeclared_positive_criterion']
cal=load(run/'calibration.json');comparisons=load(run/'comparisons.json');params={'date':'2026-10-16','release_version':'1.0.0',
 'kind':'Statistically fitted mapping breakpoints, not physical maxima or capacity guarantees',
 'source_protocol_sha256':sha(BASE/'common_command_mapping_protocol_v1.json'),'groups':{}}
for g,c in cal.items():
    comp=next(r for r in comparisons if r['group_type']=='group' and r['key']==g)
    params['groups'][g]={'calibration':{k:c[k] for k in ('fitted_breakpoint_kW','minimum_training_command_kW','maximum_training_command_kW')},
        'training_trials':c['train_trials'],'training_rows':c['train_rows'],
        'heldout_both_errors_improved':comp['mae_kW_improves'] and comp['rmse_kW_improves'],
        'use':'Only the named laboratory vehicle/mode/plug calibration; no substitution for other physical instances.'}
for sub in ('parameters','results'):(dest/sub).mkdir(exist_ok=True,parents=True)
def write(path,obj):assert not path.exists();dump(path,obj)
write(dest/'parameters/evtec_common_command_v1.json',params)
for a,b in (('mapping_summary.json',run/'summary.json'),('metrics.json',run/'metrics.json'),('coverage.json',BASE/'runs/PREP_EV_MAPPING_01/coverage.json')):
    write(dest/'results'/a,load(b))
target=dest/'results/group_metrics.csv';assert not target.exists();target.write_bytes((run/'group_metrics.csv').read_bytes())
print('Published fitted parameter records and aggregate results; no raw or fitting code copied.')
