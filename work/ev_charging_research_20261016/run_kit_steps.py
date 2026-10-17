"""Recorded step characterisation, no learned model or error improvement claim."""
from kit_common import *
from recorded_step_kernel import analyze_recorded_step
from collections import defaultdict,Counter
import argparse,math,statistics
def dist(values):
    if not values:return {'n':0,'median':None,'p95':None,'max':None}
    v=sorted(values);return {'n':len(v),'median':statistics.median(v),'p95':v[math.ceil(.95*len(v))-1],'max':v[-1]}
def aggregate(rr):
    observed=[r for r in rr if r['t90_observed']]
    return {'phase_events':len(rr),'unique_command_edges':len({(r['charging_uuid'],r['edge_index']) for r in rr}),
        'recording_sets':len({r['charging_uuid'] for r in rr}),'t10_observed':sum(r['t10_observed'] for r in rr),
        't90_observed':len(observed),'t90_not_observed_within10s':len(rr)-len(observed),
        'observed_t10_seconds':dist([r['t10_sample_s'] for r in rr if r['t10_observed']]),
        'observed_t90_seconds':dist([r['t90_sample_s'] for r in observed]),
        'observed_transition10_to90_seconds':dist([r['transition_10_to90_s'] for r in observed]),
        'steady_absolute_error_A':dist([r['steady_abs_error_A'] for r in rr]),
        'steady_signed_mean_error_A':math.fsum(r['steady_error_from_new_command_A'] for r in rr)/len(rr) if rr else None,
        'largest_steady_error_event':max(rr,key=lambda r:r['steady_abs_error_A'])['event_id'] if rr else None}
def execute(out):
    pp=BASE/'kit_step_protocol_v1.json';p=load(pp);assert sha(pp)==load(BASE/'kit_step_freeze_v1.json')['protocol_sha256']
    for s in p['sources'].values():assert sha(ROOT/s['path'])==s['sha256']
    prep=BASE/'runs/PREP_KIT_STEPS_01';ad=load(prep/'admission.json');assert all(sha(prep/n)==h for n,h in ad['outputs'].items())
    candidates=[r for r in read(prep/'all_phase_candidates.csv') if r['status']=='admitted'];bytrace=defaultdict(list)
    for r in candidates:bytrace[r['charging_uuid']].append(r)
    con=connection();features=[]
    for uid,rr in bytrace.items():
        d=trace(con,uid);t=d['t_us']
        for r in rr:
            i=int(r['edge_index']);end=int(r['post_end_index']);t0=int(r['edge_time_us']);phase=int(r['phase'][1:]);initial=float(r['pre_observed_current_A'])
            feat=analyze_recorded_step([int(x)-t0 for x in t[i:end]],[float(x) for x in d['i'+str(phase)][i:end]],initial,
                                      float(r['previous_command_A']),float(r['new_command_A']))
            features.append({**r,'edge_index':i,'pre_observed_current_A':initial,**feat})
    table(out/'phase_step_features.csv',features)
    grouped={'all':aggregate(features),'up':aggregate([r for r in features if r['direction']=='up']),
             'down':aggregate([r for r in features if r['direction']=='down'])}
    for phase in ('L1','L2','L3'):grouped[phase]=aggregate([r for r in features if r['phase']==phase])
    dump(out/'groups.json',grouped)
    recording=[]
    for meta in read(SOURCE/'charging.csv'):
        rr=[r for r in features if r['charging_uuid']==meta['charging_uuid']]
        for direction in ('all','up','down'):
            recording.append({**meta,'direction':direction,**aggregate(rr if direction=='all' else [r for r in rr if r['direction']==direction])})
    dump(out/'recording_metrics.json',recording)
    summary={'date':'2026-10-16','protocol_sha256':sha(pp),'admission_sha256':sha(prep/'admission.json'),
             'source':'KIT Zenodo17866847v1.0.0, independently acquired LF original file',
             'coverage':load(prep/'summary.json'),'all':grouped['all'],'up':grouped['up'],'down':grouped['down'],
             'interpretation':'Descriptive recorded phase step features only, no fitted/predictive model, no implied delay for censored response;10/90 is command-step magnitude not official accuracy.',
             'not_verified':p['not_verified']}
    dump(out/'summary.json',summary)
    dump(out/'receipt.json',{'status':'completed','protocol_sha256':sha(pp),'script_sha256':sha(Path(__file__)),
                            'kernel_sha256':sha(BASE/'recorded_step_kernel.py'),'outputs':{f.name:sha(f) for f in sorted(out.iterdir())}})
    print(json.dumps({k:v for k,v in summary.items() if k not in ('coverage','not_verified')},ensure_ascii=False,indent=2))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();assert Path(a.run_id).name==a.run_id
    out=BASE/'runs'/a.run_id;out.mkdir(parents=True,exist_ok=False)
    try:execute(out)
    except Exception as e:dump(out/'failure.json',{'error':repr(e)});raise
