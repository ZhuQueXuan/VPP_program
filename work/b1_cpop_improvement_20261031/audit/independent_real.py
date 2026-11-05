"""Read-only real auxiliary audit; no estimator, root feature code, or R calls."""
import json,csv,hashlib
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
from independent_synthetic import independent_weights
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
hashes={};checks=Counter();maximum=0.
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):
    path=Path(path);path=path if path.is_absolute() else HERE/path
    hashes[path.relative_to(ROOT).as_posix()]=sha(path)
    return json.loads(path.read_text(encoding='utf-8'))
def table(path):
    path=Path(path);hashes[path.relative_to(ROOT).as_posix()]=sha(path)
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def check(v,label):
    assert v,label
    checks[label]+=1
def close(a,b,label,tol=1e-8):
    global maximum
    if a is None or b is None:check(a is None and b is None,label);return
    x=np.asarray(a,float);y=np.asarray(b,float);check(x.shape==y.shape,label+' shape')
    delta=float(np.max(np.abs(x-y))) if x.size else 0.;maximum=max(maximum,delta)
    check(np.isfinite(x).all() and np.isfinite(y).all() and delta<=tol*max(1.,float(np.max(np.abs(y))) if y.size else 1.),label)
def descriptors(case,pred):
    s=np.asarray(case['starts_s']);e=np.asarray(case['ends_s']);x=np.asarray(pred)
    req=(s>=0)&(e<=15.0000001);target=x[req]>=.9;longest=run=0
    for v in target:
        if v:run+=1
        else:run=0
        longest=max(longest,run)
    def first(level):
        i=np.flatnonzero((s>=0)&(s<=10.000000001)&(x>=level))
        return float(s[i[0]]) if len(i) else None
    return {'t10_seconds':first(.1),'t90_seconds':first(.9),'target_duration_seconds':float(target.sum()*.1),
       'longest_target_seconds':float(longest*.1),'steady_error_progress':float(np.median(x[s>=10])-1),
       'peak_progress':float(x[req].max()),'tracking_rmse_progress':float(np.sqrt(np.mean((x[req]-1)**2)))}
def native_replay(path,midpoints):
    groups=defaultdict(list)
    for r in table(path):groups[int(r['case_id'])].append(r)
    check(set(groups)==set(range(432)),'native432 case coverage')
    pred={}
    for i,rr in groups.items():
        check(all(r['status']=='ok' for r in rr),'native status all ok')
        nonempty=[r for r in rr if float(r['x1'])>float(r['x0'])];values=[]
        for x in midpoints[i]:
            hits=[r for r in nonempty if float(r['x0'])-1e-9<=x<=float(r['x1'])+1e-9]
            r=hits[-1] if hits else (nonempty[0] if x<float(nonempty[0]['x0']) else nonempty[-1])
            values.append(float(r['gradient'])*x+float(r['intercept']))
        pred[i]=values
    return pred
def main():
    receipt=read('real_receipt.json');protocol=read('real_protocol.json');freeze=read('validation_freeze.json')
    check(receipt['available']==receipt['output_count']==1296,'real1296 outputs available')
    check(receipt['original_events']==144 and receipt['recordings']==18,'144events18records')
    check(receipt['selected_kappa']==freeze['selected_kappa']==5.,'kappa fixed from validation')
    check(protocol['no_selection_on_real'] and receipt['no_real_accuracy_or_new_field_holdout_claim'],'no real tuning or truth claim')
    for path,digest in receipt['source_sha256'].items():check(sha(ROOT/path)==digest,'real source SHA unchanged')
    cases=read(ROOT/'work/b1_command_feature_selection_20261031/real_cases.json')
    check(sha(ROOT/'work/b1_command_feature_selection_20261031/real_cases.json')==protocol['source_sha256'],'frozen old real cases SHA')
    check(len(cases)==144 and len({c['event_id'] for c in cases})==144,'real IDs unique')
    check(len({c['recording'] for c in cases})==18,'18correlated recording groups retained')
    inputs=read('real_inputs.json');curves=read('real_curves.json');metrics=read('real_metrics.json')
    summaries=read('real_summary.json');pairs=read('real_paired_stability.json')
    check(len(inputs)==len(curves)==432,'432 paired input curves')
    check(len(metrics)==1296,'1296 metric denominator')
    cpdir=HERE/'native/real_original';cppaths=list(cpdir.glob('process_*/input.csv'))
    check(len(cppaths)==1,'one original native input batch')
    cpin=defaultdict(list);win=defaultdict(list);lin=defaultdict(list);lout=defaultdict(list)
    for r in table(cppaths[0]):cpin[int(r['case_id'])].append(r)
    for r in table(HERE/'native/real_weighted/input.csv'):win[int(r['case_id'])].append(r)
    for r in table(HERE/'labs/real/input.csv'):lin[int(r['case_id'])].append(float(r['y']))
    for r in table(HERE/'labs/real/output.csv'):
        check(r['status']=='ok','LABS native status');lout[int(r['case_id'])].append(float(r['fitted']))
    midpoints={i:(np.asarray(cases[i//3]['starts_s'])+np.asarray(cases[i//3]['ends_s']))/2 for i in range(432)}
    cppred=native_replay(cppaths[0].with_name('segments.csv'),midpoints)
    wpred=native_replay(HERE/'native/real_weighted/segments.csv',midpoints)
    bymetric={(m['event_id'],m['condition'],m['method']):m for m in metrics}
    rng=np.random.default_rng(7631300);recomputed=[]
    methods=['cpop',freeze['selected_method'],'labs'];conditions=['original','gaussian','gaussian_plus_spikes']
    for j,c in enumerate(cases):
        y=np.asarray(c['progress']);z=rng.normal(0,.03,len(y));spikes=z.copy()
        ix=rng.choice(np.flatnonzero(np.asarray(c['starts_s'])>=0),2,replace=False)
        spikes[ix]+=rng.choice([-1.,1.],2)*.30
        command=np.where(np.asarray(c['starts_s'])<0,c['previous_command_A'],c['new_command_A'])
        reference=descriptors(c,y)
        for k,condition in enumerate(conditions):
            i=3*j+k;item=inputs[i];savedcurve=curves[i]
            arr=y if k==0 else y+(z if k==1 else spikes)
            sigma=c['noise_sigma_progress'] if k==0 else float(np.hypot(c['noise_sigma_progress'],.03))
            check(item['event_id']==savedcurve['event_id']==c['event_id'],'real event binding')
            check(item['condition']==savedcurve['condition']==condition,'condition binding')
            close(item['y'],arr,'perturbed array exact reconstruction',0)
            close(item['command'],command,'command identical available current')
            close(item['sigma'],sigma,'same declared/known extra noise sigma')
            check(item['spike_indices']==(ix.tolist() if k==2 else []),'exact spike locations')
            close([float(r['x']) for r in cpin[i]],midpoints[i],'original x seconds')
            close([float(r['y']) for r in cpin[i]],arr,'original input same y')
            close([float(r['sigma']) for r in cpin[i]],np.full(200,sigma),'original scalar sd in all rows')
            check(all(r['train']=='1' for r in cpin[i]),'all200 input samples used')
            close(lin[i],arr,'LABS input same observed array')
            sd,flags,protected=independent_weights(arr,sigma,command,5.)
            close([float(r['sigma']) for r in win[i]],sd,'candidate native vector sigma')
            close([float(r['y']) for r in win[i]],arr,'candidate native same unmodified y')
            close([float(r['x']) for r in win[i]],midpoints[i],'candidate x actual seconds')
            for method in methods:
                fit=savedcurve['results'][method];check(fit['status']=='ok','all144x3x3 fits available')
                pred=fit['prediction'];check(len(pred)==200,'same200 bin curve')
                close(pred,cppred[i] if method=='cpop' else lout[i] if method=='labs' else wpred[i],'native fitted curve replay')
                if method==freeze['selected_method']:
                    diag=fit['weight_diagnostics'];close(diag['sigma_vector'],sd,'saved point sigma matches independent weights')
                    check([r['index'] for r in diag['flagged_points']]==flags,'same isolated flags')
                    check(diag['protected_indices']==protected,'same command protection')
                f=descriptors(c,pred);m=bymetric[(c['event_id'],condition,method)]
                calc={'event_id':c['event_id'],'condition':condition,'method':method,'features':f,'original_observation_features':reference,
                      'flagged_count':len(flags) if method==freeze['selected_method'] else 0,'seconds':fit['seconds']}
                check(m['status']=='ok','all output rows retained')
                close(m['seconds'],calc['seconds'],'time bookkeeping');check(m['flagged_count']==calc['flagged_count'],'flag count')
                for key,value in f.items():
                    close(m['features'][key],value,'real reconstructed feature '+key)
                    close(m['original_observation_features'][key],reference[key],'original observation reference feature')
                for key in ['target_duration_seconds','longest_target_seconds','steady_error_progress','peak_progress','tracking_rmse_progress']:
                    calc[key+'_difference']=abs(f[key]-reference[key]);close(m[key+'_difference'],calc[key+'_difference'],'original observation feature difference')
                for key in ['t10_seconds','t90_seconds']:
                    a,b=f[key],reference[key];calc[key+'_status_difference']=(a is None)!=(b is None)
                    calc[key+'_difference']=abs(a-b) if a is not None and b is not None else None
                    check(m[key+'_status_difference']==calc[key+'_status_difference'],'missing time status retained')
                    close(m[key+'_difference'],calc[key+'_difference'],'conditional real time difference')
                recomputed.append(calc)
    for summary in summaries:
        rr=[r for r in recomputed if r['method']==summary['method'] and r['condition']==summary['condition']]
        check(summary['n']==summary['available']==len(rr)==144,'summary full144 denominator')
        for key in ['target_duration_seconds_difference','longest_target_seconds_difference','steady_error_progress_difference','flagged_count','seconds']:
            close(summary[key],np.mean([r[key] for r in rr]),'real summary '+key)
        for key in ['t10_seconds','t90_seconds']:
            values=[r[key+'_difference'] for r in rr if r[key+'_difference'] is not None]
            check(summary[key+'_paired_present_n']==len(values),'conditional real timing denominator')
            check(summary[key+'_status_difference']==sum(r[key+'_status_difference'] for r in rr),'real status summary')
            close(summary[key+'_difference'],np.mean(values) if values else None,'conditional real time mean')
    for pair in pairs:
        method=pair['method'];lookup={(r['event_id'],r['condition']):r for r in recomputed if r['method']==method}
        close(pair['available_pairs'],144,'all144 matched gaussian/spike pairs')
        for key in ['target_duration_seconds','longest_target_seconds','steady_error_progress']:
            changes=[abs(lookup[(c['event_id'],'gaussian')]['features'][key]-lookup[(c['event_id'],'gaussian_plus_spikes')]['features'][key]) for c in cases]
            close(pair[key+'_change'],np.mean(changes),'same-method added-spike conditional change')
        flips=sum((lookup[(c['event_id'],'gaussian')]['features']['t90_seconds'] is None)!=(lookup[(c['event_id'],'gaussian_plus_spikes')]['features']['t90_seconds'] is None) for c in cases)
        check(pair['t90_status_flips']==flips,'same-method t90 flips')
    for path,digest in hashes.items():check(sha(ROOT/path)==digest,'all read inputs unchanged')
    result={'status':'passed','scope':'Independent saved real curves/weights/native input/output/descriptors/paired-changes audit, no estimator or R call',
      'checks':dict(checks),'n_checks':sum(checks.values()),'maximum_numeric_difference':maximum,
      'real_events':144,'recordings':18,'paired_input_variants':432,'output_rows':1296,'all_available':True,
      'selected_kappa':5.,'same_method_paired_stability':pairs,'input_sha256':hashes,
      'limits':['Original100ms observed descriptors are reference observations, not latent clean truth',
         'Same Gaussian->sameGaussian+two spikes is a controlled perturbation contrast, not real failure recovery accuracy',
         'Progress1 is pre-measured current plus command change, not necessarily the new absolute current command',
         'Preserved known-reference simulation safety-gate failure is not overturned by this auxiliary result',
         'Old144 events from18 correlated recordings are not new field holdout or independent144vehicles'],
      'no_fit':True,'no_parameter_selection':True,'no_real_accuracy_claim':True}
    with (HERE/'audit/independent_real.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'status':'passed','checks':sum(checks.values()),'events':144,'inputs':432,'outputs':1296,
          'max_difference':maximum,'pairs':pairs},ensure_ascii=False))
if __name__=='__main__':main()
