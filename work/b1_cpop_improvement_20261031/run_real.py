"""Previously frozen KIT records, new fixed perturbation seed; no clean truth."""
from common import *
from candidate import observation_weights
def descriptor_kernel():
    spec=importlib.util.spec_from_file_location('_previous_real_descriptor',PREVIOUS/'run_real.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m.descriptors
def main():
    selected=read('validation_freeze.json');kappa=selected['selected_kappa'];method=selected['selected_method']
    for p,h in selected['source_sha256'].items():assert sha(ROOT/p)==h
    source=PREVIOUS/'real_cases.json';cases=json.loads(source.read_text(encoding='utf-8'))
    assert len(cases)==144 and all(c['status']=='ok' for c in cases)
    protocol={'scope':'Old fixed KIT144 observations/18 recordings with new fixed perturbations, auxiliary only',
       'selected_kappa_from_simulation_validation':kappa,'source_sha256':sha(source),
       'conditions':['original','gaussian','gaussian_plus_spikes'],'seed':7631300,
       'gaussian_progress_sigma':.03,'spikes':'Same Gaussian+exactly two random distinct post bins with independent sign times .30',
       'shared_metadata':'Original normalization and pre-sigma; combined sqrt(pre_sigma2+.032) given CP/candidate for perturbations; command is actual old/new current',
       'comparison':'Same measured original100ms descriptors, not latent truth. Same-method Gaussian->Gaussian+spikes change also reported.',
       'no_selection_on_real':True,'original_RIDE_not_applicable':True,'methods':['cpop',method,'labs']}
    write('real_protocol.json',protocol)
    rng=np.random.default_rng(7631300);items=[];weighted=[];original=[];diags={}
    for c in cases:
        y=np.asarray(c['progress']);z=rng.normal(0,.03,len(y));p=z.copy()
        indices=rng.choice(np.flatnonzero(np.asarray(c['starts_s'])>=0),2,replace=False)
        p[indices]+=rng.choice([-1.,1.],2)*.30
        command=np.where(np.asarray(c['starts_s'])<0,c['previous_command_A'],c['new_command_A'])
        for condition in protocol['conditions']:
            arr=y if condition=='original' else y+(z if condition=='gaussian' else p)
            sigma=c['noise_sigma_progress'] if condition=='original' else float(np.hypot(c['noise_sigma_progress'],.03))
            i=len(items);s=np.asarray(c['starts_s']);e=np.asarray(c['ends_s'])
            w=observation_weights(arr,sigma,command,kappa=kappa);diags[i]=w
            items.append({'case':c,'event_id':c['event_id'],'recording':c['recording'],'condition':condition,
              'y':arr,'sigma':sigma,'command':command,'spike_indices':indices.tolist() if condition=='gaussian_plus_spikes' else []})
            original.append({'case_id':i,'starts':s,'ends':e,'y':arr,'sigma':sigma,'train':np.ones(len(y),bool)})
            weighted.append({'case_id':i,'starts':s,'ends':e,'y':arr,'sigma_vector':w['sigma_vector']})
    write('real_inputs.json',[{k:v for k,v in r.items() if k!='case'} for r in items])
    old,ometa=fit_cases(original,runtime('native/real_original'));assert ometa['status']=='ok'
    improved,imeta=weighted_batch(weighted,'native/real_weighted')
    labs,lmeta=labs_batch([r['y'] for r in items],'labs/real')
    desc=descriptor_kernel();curves=[];metrics=[]
    for i,item in enumerate(items):
        c=item['case'];results={'cpop':old[i],method:improved[i],'labs':labs[i]}
        results[method]['weight_diagnostics']=diags[i]
        reference=desc(c,c['progress'])
        curves.append({'event_id':c['event_id'],'condition':item['condition'],'results':results})
        for m,result in results.items():
            r={'event_id':c['event_id'],'recording':c['recording'],'condition':item['condition'],'method':m,
               'status':result['status'],'seconds':result.get('seconds',0.),'flagged_count':len(result.get('weight_diagnostics',{}).get('flagged_points',[]))}
            if result['status']=='ok':
                features=desc(c,result['prediction']);r.update(features=features,original_observation_features=reference)
                for key in ['target_duration_seconds','longest_target_seconds','steady_error_progress','peak_progress','tracking_rmse_progress']:
                    r[key+'_difference']=abs(features[key]-reference[key])
                for key in ['t10_seconds','t90_seconds']:
                    a,b=features[key],reference[key];r[key+'_status_difference']=(a is None)!=(b is None)
                    r[key+'_difference']=abs(a-b) if a is not None and b is not None else None
            else:r['reason']=result.get('reason',result.get('error'))
            metrics.append(r)
    summary=[];pairs=[]
    for m in ['cpop',method,'labs']:
      for condition in protocol['conditions']:
        rr=[r for r in metrics if r['method']==m and r['condition']==condition];v=[r for r in rr if r['status']=='ok']
        d={'method':m,'condition':condition,'n':len(rr),'available':len(v)}
        if v:
            for key in ['target_duration_seconds_difference','longest_target_seconds_difference','steady_error_progress_difference','flagged_count','seconds']:
                d[key]=float(np.mean([r[key] for r in v]))
            for key in ['t10_seconds','t90_seconds']:
                d[key+'_status_difference']=sum(r[key+'_status_difference'] for r in v)
                values=[r[key+'_difference'] for r in v if r[key+'_difference'] is not None]
                d[key+'_difference']=float(np.mean(values)) if values else None;d[key+'_paired_present_n']=len(values)
        summary.append(d)
      lookup={(r['event_id'],r['condition']):r for r in metrics if r['method']==m}
      valid=[]
      for c in cases:
        a=lookup[(c['event_id'],'gaussian')];b=lookup[(c['event_id'],'gaussian_plus_spikes')]
        if a['status']==b['status']=='ok':valid.append((a,b))
      p={'method':m,'all_base_events':144,'available_pairs':len(valid),'reference':'Same-method Gaussian->sameGaussian+spikes'}
      for key in ['target_duration_seconds','longest_target_seconds','steady_error_progress']:
        p[key+'_change']=float(np.mean([abs(a['features'][key]-b['features'][key]) for a,b in valid])) if valid else None
      p['t90_status_flips']=sum((a['features']['t90_seconds'] is None)!=(b['features']['t90_seconds'] is None) for a,b in valid)
      pairs.append(p)
    write('real_curves.json',curves);write('real_metrics.json',metrics);write('real_summary.json',summary);write('real_paired_stability.json',pairs)
    write('real_receipt.json',{'status':'complete','original_events':144,'recordings':18,'input_variants':432,
       'output_count':len(metrics),'available':sum(r['status']=='ok' for r in metrics),'same_original_SHA':sha(source)==protocol['source_sha256'],
       'no_real_accuracy_or_new_field_holdout_claim':True,'selected_kappa':kappa,'original_runtime':ometa,'candidate_runtime':imeta,'labs_runtime':lmeta,
       'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in [HERE/'run_real.py',HERE/'candidate.py',source,PREVIOUS/'run_real.py']}})
    print(json.dumps({'pairs':pairs,'summary':summary},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
