"""Existing real100ms observations; only artificial perturbation stability."""
from common import *
from candidate import refine,features

def main():
    frozen=read('validation_freeze.json')
    for p,h in frozen['source_sha256'].items():assert sha(ROOT/p)==h,p
    k=frozen['kappa'];source=OLD/'real_cases.json';cases=json.loads(source.read_text(encoding='utf-8'))
    rng=np.random.default_rng(read('protocol.json')['real_auxiliary']['seed']);items=[];cp=[];mapping={};index=0
    for c in cases:
        y=np.array(c['progress']);s=np.array(c['starts_s']);e=np.array(c['ends_s']);u=np.where(s<0,c['previous_command_A'],c['new_command_A'])
        z=rng.normal(0,.03,len(y));v=z.copy();ix=rng.choice(np.flatnonzero(s>=0),2,replace=False);v[ix]+=rng.choice([-1.,1.],2)*.30
        for condition in ['original','gaussian','single_sample_spikes']:
            value=y if condition=='original' else y+(z if condition=='gaussian' else v)
            sigma=c['noise_sigma_progress'] if condition=='original' else float(np.hypot(c['noise_sigma_progress'],.03))
            tic=time.perf_counter();a,info=refine(value,s,u,sigma,k);info['seconds']=time.perf_counter()-tic
            j=len(items);items.append(dict(event_id=c['event_id'],recording=c['recording'],condition=condition,
                starts_s=s,y=value,command=u,sigma=sigma,fine_evidence=info))
            for m,arr in [('cpop',value),('fine_cpop',a)]:
                mapping[j,m]=index;cp.append(dict(case_id=index,starts=s,ends=e,y=arr,sigma=sigma,train=np.ones(len(y),bool)));index+=1
    write('real_inputs.json',items);out,meta=cp_batch(cp,'native/real');labs,lmeta=labs_batch([r['y'] for r in items],'labs/real')
    rows=[];curves=[]
    for i,c in enumerate(items):
        results={m:out[mapping[i,m]] for m in ['cpop','fine_cpop']};results['labs']=labs[i]
        results['fine_cpop']['fine_evidence']=c['fine_evidence'];results['fine_cpop']['seconds']+=c['fine_evidence']['seconds']
        curves.append(dict(event_id=c['event_id'],condition=c['condition'],results=results))
        for m,r in results.items():
            d={key:c[key] for key in ['event_id','recording','condition']};d.update(method=m,status=r['status'],seconds=r.get('seconds',0.))
            if r['status']=='ok':d['features']=features(r['prediction'],c['starts_s'],15.,.9,.1)
            rows.append(d)
    write('real_curves.json',curves);write('real_metrics.json',rows)
    summary=[]
    for m in ['cpop','fine_cpop','labs']:
        lookup={(r['event_id'],r['condition']):r for r in rows if r['method']==m};pairs=[(lookup[c['event_id'],'gaussian'],lookup[c['event_id'],'single_sample_spikes']) for c in cases]
        good=[(a,b) for a,b in pairs if a['status']==b['status']=='ok'];d=dict(method=m,n=len(pairs),available=len(good))
        for name in ['cumulative_seconds','longest_seconds']:
            d[name+'_perturbation_change']=float(np.mean([abs(a['features'][name]-b['features'][name]) for a,b in good]))
        d['target_status_flips']=sum(a['features']['threshold_positive']!=b['features']['threshold_positive'] for a,b in good)
        d['seconds_batch_sum']=sum(r['seconds'] for r in lookup.values());summary.append(d)
    write('real_summary.json',summary);write('real_receipt.json',dict(events=len(cases),recordings=18,paired_conditions=3,inputs=len(items),method_rows=len(rows),
        available=sum(r['status']=='ok' for r in rows),latent_truth_available=False,field_holdout=False,primary_selection_from_real=False,
        input_sha256=sha(source),native_runtime=meta,labs_runtime=lmeta))
    print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
