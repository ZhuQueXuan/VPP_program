"""Finite real command-tracking description and added-noise stability.

The original measured trace is an observation reference, never a clean physical
truth. Formal minute/kW RIDE is explicitly outside this seconds/current domain.
"""
from common import *
METHODS=['raw_features','tf_standard','cpop','labs_2026']
CONDITIONS=['original_observation','added_gaussian','added_gaussian_and_spikes']
def descriptors(case,pred):
    s=np.asarray(case['starts_s']);e=np.asarray(case['ends_s']);x=np.asarray(pred)
    req=(s>=0)&(e<=15.0000001);target=x[req]>=.9
    longest=run=0
    for v in target:run=run+1 if v else 0;longest=max(longest,run)
    def crossing(level):
        use=np.flatnonzero((s>=0)&(s<=10+1e-9)&(x>=level))
        return float(s[use[0]]) if len(use) else None
    return {'t10_seconds':crossing(.1),'t90_seconds':crossing(.9),
            'target_duration_seconds':float(target.sum()*.1),'longest_target_seconds':float(longest*.1),
            'steady_error_progress':float(np.median(x[s>=10])-1),
            'peak_progress':float(x[req].max()),'tracking_rmse_progress':float(np.sqrt(np.mean((x[req]-1)**2)))}
def main():
    protocol={'schema':'b1.real-command-robustness.v1','source':'real_preparation_protocol.json and fixed144 selected KIT records',
       'methods':METHODS,'RIDE':'not applicable: formal production minute/kW domain differs',
       'original_reference':'Same100ms original measured-bin descriptors, not latent true response or external annotations',
       'conditions':CONDITIONS,'noise':{'seed':7621300,'gaussian_sigma_progress':.03,
           'spike_condition':'Same Gaussian array plus exactly2 postwindow bins selected uniformly without replacement; independent signs times0.30 progress',
           'known_added_sigma_to_CP_TF':'sqrt(pre-window estimated sigma squared+.03 squared); spikes excluded from Gaussian variance',
           'normalization_reference':'Original pre5s measured median and original declared step, fixed across perturbations'},
       'TF':'Existing standard estimator, lambda4 fixed, isotropic declared condition variance; no calibration or selection',
       'CP':'Existing native estimator, same seconds midpoints, beta2log(n), declared condition sigma',
       'LABS':'Fixed unmodified author M5R2 sSIC, no selection change',
       'features':'Time in seconds, progress unitless relative to command step; 100ms mean bins, project10/90, crossing start<=10s; target time over15s and last5s steady bias',
       'not_claimed':['No latent-clean or stage-label accuracy','No untouched new real field cohort; fixed reuse of existing recordings','No physical ICT-to-device latency or net-reduction reference','No temporal recovery after restoring command exists in this window','No5percent false-alarm guarantee','No parameter or winner selection from these robustness data']}
    write('real_comparison_protocol.json',protocol)
    cases=read('real_cases.json');assert len(cases)==144
    receipt=read('real_preparation_receipt.json');assert sha(HERE/'real_cases.json')==receipt['cases_sha256']
    assert all(c['status']=='ok' for c in cases)
    rng=np.random.default_rng(7621300);items=[]
    for c in cases:
        y=np.asarray(c['progress']);z=rng.normal(0,.03,len(y));spike=z.copy()
        index=rng.choice(np.flatnonzero(np.asarray(c['starts_s'])>=0),2,replace=False)
        spike[index]+=rng.choice([-1.,1.],2)*.30
        for condition in CONDITIONS:
            arr=y if condition==CONDITIONS[0] else y+(z if condition==CONDITIONS[1] else spike)
            sigma=c['noise_sigma_progress'] if condition==CONDITIONS[0] else float(np.hypot(c['noise_sigma_progress'],.03))
            items.append({'event_id':c['event_id'],'recording':c['recording'],'direction':c['direction'],'case':c,
                          'condition':condition,'y':arr,'sigma':sigma,'added_spike_indices':index.tolist() if condition==CONDITIONS[2] else []})
    write('real_perturbed_inputs.json',[{k:v for k,v in i.items() if k!='case'} for i in items])
    out={};cp=[]
    for j,item in enumerate(items):
        c=item['case'];y=item['y'];sigma=item['sigma']
        tic=time.perf_counter();fit=fit_curve(y,sigma*sigma,4);fit['seconds']=time.perf_counter()-tic
        out[j]={'raw_features':{'status':'ok','prediction':y,'seconds':0.},'tf_standard':fit}
        cp.append({'case_id':j,'starts':np.asarray(c['starts_s']),'ends':np.asarray(c['ends_s']),
                   'y':y,'sigma':sigma,'train':np.ones(len(y),bool)})
        if (j+1)%72==0:print('real TF',j+1,'/',len(items),flush=True)
    fits,backend=fit_cases(cp,runtime('native/real'));assert backend['status']=='ok',backend
    labs,meta=labs_batch([i['y'] for i in items],'labs/real')
    metrics=[];saved=[]
    for j,item in enumerate(items):
        out[j]['cpop']=fits.get(j,{'status':'unavailable'});out[j]['labs_2026']=labs[j]
        reference=descriptors(item['case'],item['case']['progress'])
        saved.append({'event_id':item['event_id'],'condition':item['condition'],'results':out[j]})
        for method,r in out[j].items():
            d={'event_id':item['event_id'],'recording':item['recording'],'direction':item['direction'],
               'condition':item['condition'],'method':method,'status':r['status'],'seconds':r.get('seconds',0)}
            if r['status']=='ok':
                f=descriptors(item['case'],r['prediction']);d.update(features=f,original_observation_features=reference)
                for k in ['t10_seconds','t90_seconds']:
                    p=f[k];t=reference[k];d[k+'_status_disagreement']=(p is None)!=(t is None)
                    d[k+'_absolute_difference']=abs(p-t) if p is not None and t is not None else None
                for k in ['target_duration_seconds','longest_target_seconds','steady_error_progress','peak_progress','tracking_rmse_progress']:
                    d[k+'_absolute_difference']=abs(f[k]-reference[k])
                d['curve_difference_rms_progress']=float(np.sqrt(np.mean((np.asarray(r['prediction'])-np.asarray(item['case']['progress']))**2)))
            else:d['reason']=r.get('reason',r.get('error'))
            metrics.append(d)
    write('real_outputs.json',saved);write('real_metrics.json',metrics)
    summary=[]
    for condition in CONDITIONS:
      for method in METHODS:
        rr=[r for r in metrics if r['condition']==condition and r['method']==method];valid=[r for r in rr if r['status']=='ok']
        d={'condition':condition,'method':method,'n':len(rr),'available':len(valid)}
        if valid:
            for k in ['target_duration_seconds_absolute_difference','longest_target_seconds_absolute_difference','steady_error_progress_absolute_difference','curve_difference_rms_progress','seconds']:
                d[k]=float(np.mean([r[k] for r in valid]))
            for k in ['t10_seconds','t90_seconds']:
                d[k+'_status_disagreement']=sum(r[k+'_status_disagreement'] for r in valid)
                values=[r[k+'_absolute_difference'] for r in valid if r[k+'_absolute_difference'] is not None]
                d[k+'_absolute_difference']=float(np.mean(values)) if values else None;d[k+'_paired_present_n']=len(values)
        summary.append(d)
    write('real_summary.json',summary)
    write('real_comparison_receipt.json',{'status':'completed','real_records':144,'recordings':18,'added_conditions_per_record':2,
        'total_inputs':len(items),'methods':4,'outputs':len(metrics),'available':sum(r['status']=='ok' for r in metrics),
        'no_field_accuracy_or_winner_claim':True,'production_RIDE_not_forced_into_domain':True,
        'original_inputs_sha256':{'real_cases.json':sha(HERE/'real_cases.json'),'real_preparation_protocol.json':sha(HERE/'real_preparation_protocol.json')},
        'source_sha256':{p:sha(HERE/p) for p in ['run_real.py','real_comparison_protocol.json','common.py','labs_batch.R']},
        'CP_backend':backend,'LABS':meta})
    print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
