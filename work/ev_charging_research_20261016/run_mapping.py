"""Preregistered experiment-equal training of a single breakpoint per group."""
from mapping_common import *
from common_command_kernel import predict_grid_power_kW
from collections import Counter,defaultdict
import argparse,math
MODELS=('B_SET','M_CAP')
def metrics(rr,m):
    if not rr:return {'n':0}
    e=[r[m]-r['actual_grid_kW'] for r in rr];ae=sorted(abs(v) for v in e);i=max(range(len(rr)),key=lambda i:abs(e[i]))
    return {'n':len(rr),'mae_kW':math.fsum(ae)/len(rr),'rmse_kW':math.sqrt(math.fsum(v*v for v in e)/len(rr)),
        'bias_kW':math.fsum(e)/len(rr),'p95_abs_kW':ae[math.ceil(.95*len(rr))-1],'max_abs_kW':ae[-1],
        'worst_member':rr[i]['member'],'worst_record_index':rr[i]['record_index'],'worst_epoch_ms':rr[i]['epoch_ms'],
        'worst_actual_kW':rr[i]['actual_grid_kW'],'worst_prediction_kW':rr[i][m],
        'negative_actual_rows':sum(r['actual_grid_kW']<0 for r in rr),'negative_predictions':sum(r[m]<0 for r in rr)}
def fit(rr):
    ns=Counter(r['member'] for r in rr);u=sorted({r['common_command_kW'] for r in rr});candidates={0.,max(u)};candidates.update(u)
    for a,b in zip(sorted(candidates),sorted(candidates)[1:]):
        active=[r for r in rr if r['common_command_kW']>a]
        w=math.fsum(1/ns[r['member']] for r in active)
        if w:candidates.add(min(b,max(a,math.fsum(r['actual_grid_kW']/ns[r['member']] for r in active)/w)))
    loss=lambda c:math.fsum((min(r['common_command_kW'],c)-r['actual_grid_kW'])**2/ns[r['member']] for r in rr)/len(ns)
    values=[(loss(c),-c) for c in candidates];best,negative_c=min(values);c=-negative_c
    return {'fitted_breakpoint_kW':c,'objective_experiment_equal_MSE_kW2':best,'train_trials':len(ns),'train_rows':len(rr),
        'minimum_training_command_kW':min(u),'maximum_training_command_kW':max(u),'candidate_breakpoints':len(candidates)}
def execute(out):
    pp=BASE/'common_command_mapping_protocol_v1.json';p=load(pp);assert sha(pp)==load(BASE/'common_command_mapping_freeze_v1.json')['protocol_sha256']
    for s in p['sources'].values():assert sha(ROOT/s['path'])==s['sha256']
    prep=BASE/'runs/PREP_EV_MAPPING_01';ad=load(prep/'admission.json')
    assert ad['protocol_sha256']==sha(pp) and all(sha(prep/n)==h for n,h in ad['outputs'].items())
    rows=[r for r in read(prep/'samples.csv') if r['status']=='admitted']
    for r in rows:
        for k in ('common_command_kW','actual_grid_kW','epoch_ms'):r[k]=float(r[k])
        r['record_index']=int(r['record_index'])
    calibration={g:fit([r for r in rows if r['group']==g and r['split']=='train']) for g in sorted({r['group'] for r in rows})}
    dump(out/'calibration.json',calibration)
    pred=[]
    for r in rows:
        if r['split']!='test':continue
        c=calibration[r['group']];u=r['common_command_kW']
        pred.append({**r,'B_SET':u,'M_CAP':predict_grid_power_kW(u,c['fitted_breakpoint_kW']),
                     'command_outside_training_range':not c['minimum_training_command_kW']<=u<=c['maximum_training_command_kW']})
    table(out/'predictions.csv',pred)
    bins={'all':pred,'AC':[r for r in pred if r['mode']=='AC'],'DC':[r for r in pred if r['mode']=='DC'],
          'command_zero':[r for r in pred if r['common_command_kW']==0],'command_positive':[r for r in pred if r['common_command_kW']>0]}
    mm={g:{m:metrics(rr,m) for m in MODELS} for g,rr in bins.items()};dump(out/'metrics.json',mm)
    grouped=[];comparisons=[]
    for typ in ('group','member'):
        for key in sorted({r[typ] for r in pred}):
            rr=[r for r in pred if r[typ]==key];d={m:metrics(rr,m) for m in MODELS}
            for m in MODELS:grouped.append({'group_type':typ,'key':key,'model':m,**d[m]})
            comparisons.append({'group_type':typ,'key':key,'n':len(rr),
                                **{k+'_improves':d['M_CAP'][k]<d['B_SET'][k] for k in ('mae_kW','rmse_kW')}})
    table(out/'group_metrics.csv',grouped);dump(out/'comparisons.json',comparisons)
    summary={'date':'2026-10-16','protocol_sha256':sha(pp),'admission_sha256':sha(prep/'admission.json'),
        'object':p['object'],'train_trials':20,'test_trials':28,'test_rows':len(pred),'group_count':len(calibration),
        'all':mm['all'],'AC':mm['AC'],'DC':mm['DC'],'command_positive':mm['command_positive'],
        'relative_gain':{k:1-mm['all']['M_CAP'][k]/mm['all']['B_SET'][k] for k in ('mae_kW','rmse_kW')},
        'predeclared_positive_criterion':all(mm[g]['M_CAP']['n']>0 and all(mm[g]['M_CAP'][k]<mm[g]['B_SET'][k] for k in ('mae_kW','rmse_kW')) for g in ('all','AC','DC')),
        'groups_both_improve':sum(r['mae_kW_improves'] and r['rmse_kW_improves'] for r in comparisons if r['group_type']=='group'),
        'trials_both_improve':sum(r['mae_kW_improves'] and r['rmse_kW_improves'] for r in comparisons if r['group_type']=='member'),
        'experiment_equal_mean_metrics':{m:{k:math.fsum(r[k] for r in grouped if r['group_type']=='member' and r['model']==m)/28 for k in ('mae_kW','rmse_kW')} for m in MODELS},
        'out_of_training_command_range':sum(r['command_outside_training_range'] for r in pred),'fitted_breakpoints':{g:c['fitted_breakpoint_kW'] for g,c in calibration.items()},
        'interpretation':'Static observed-record mapping only; current complete row assumed available, no STATE enum/connected-state claim, no response latency or available capacity.',
        'unverified':p['unverified']}
    dump(out/'summary.json',summary)
    dump(out/'receipt.json',{'status':'completed','runner_sha256':sha(Path(__file__)),'kernel_sha256':sha(BASE/'common_command_kernel.py'),
        'protocol_sha256':sha(pp),'admission_sha256':sha(prep/'admission.json'),'outputs':{f.name:sha(f) for f in sorted(out.iterdir())}})
    print(json.dumps({k:v for k,v in summary.items() if k not in ('fitted_breakpoints','unverified','all','AC','DC','command_positive')},ensure_ascii=False,indent=2))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();assert Path(a.run_id).name==a.run_id
    out=BASE/'runs'/a.run_id;out.mkdir(parents=True,exist_ok=False)
    try:execute(out)
    except Exception as e:dump(out/'failure.json',{'error':repr(e)});raise
