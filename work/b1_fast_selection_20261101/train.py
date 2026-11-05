from common import *
from candidates import fit_segments
from learned import features,export_model,predict_model
from sklearn.ensemble import HistGradientBoostingRegressor

def main():
    write('learning_protocol.json',dict(objective='Improve actual duration accuracy; runtime is secondary, per user clarification.',
        method='Segment fit plus regression denoising near the physical threshold; preserve raw samples and energy, no isolated-point removal.',
        train_seeds=list(range(7660000,7660008)),train_per_kind=4,
        labels='Known synthetic latent physical power, not observed outlier labels. Train amplitude scales span both sides of effective threshold, including weak gaps.',
        selection='Seen development only for model/weight/band. Freeze before newly generated validation/test. Early stopping off, no random row split selection.',
        libraries='Existing scikit-learn1.7.2 HistGradientBoostingRegressor BSD3, maintained upstream; no installation/upgrade. Export deterministic JSON for inference.',
        model_grid=[dict(leaves=15,l2=10.),dict(leaves=31,l2=20.)],weights=[.25,.5,1.],bands_sigma=[1.,2.,3.],
        no_claim='Not field-trained, not universal physical fault classification. Strong isolated true actions and identical spikes remain intrinsically ambiguous.'))
    # The old generator source is reused, not its held-out observations.
    protocol=dict(simulation=dict(kinds=['smooth_strong','smooth_weak','brief_weak','interrupted','early_exit','oscillatory','delayed_rebound','null','one_minute_response','one_minute_gap','one_finebin_response','one_finebin_gap'],conditions=['gaussian','single_sample_spikes','persistent_bursts'],train10s=dict(seeds=list(range(7660000,7660008)),per_kind=4)))
    write('protocol.json',protocol)
    v1=load_module(V1/'simulation.py','_newtrain_v1');v3=load_module(ROOT/'work/b1_cpop_fine_v3_20261031/simulation.py','_newtrain_v3')
    minute=[];truth_min=[]
    for seed in range(7660000,7660008):
        a,b=v1.block(seed,4);minute+=a;truth_min+=b
    fine=v3.generate('train10s');truth_fine=read('evaluator/train10s.json')
    Xs=[];ys=[];records=[];scalings=[]
    for panel,cases,truths in [('minute',minute,truth_min),('10s',fine,truth_fine)]:
        rng=np.random.default_rng(7669000+(panel=='10s'))
        for i,(c,t) in enumerate(zip(cases,truths)):
            tid=c.get('task_id',c.get('task',{}).get('task_id'));clean=np.array(t['true_reduction_kw']);raw=np.array(c['reference_kw'])-np.array(c['power_kw'])
            if 'weak' in c['kind']:scale=float(rng.uniform(.35,2.))
            elif rng.random()<.35:scale=float(rng.uniform(.04,.4))
            else:scale=float(rng.uniform(.7,1.2))
            target=clean*scale;observed=raw-clean+target;sigma=c['sigma'];delta=10. if panel=='10s' else 60.
            fit=fit_segments(observed,sigma,3.,0.);X=features(observed,fit['prediction'],sigma,delta)
            Xs.append(X);ys.append(target/sigma);scalings.append(dict(panel=panel,task_id=tid,scale=scale))
            records.append(dict(panel=panel,task_id=tid,kind=c['kind'],sigma=sigma,delta_s=delta,observed_reduction_kw=observed,true_reduction_kw=target))
            if (i+1)%240==0:print('training features',panel,i+1,'/',len(cases),flush=True)
    X=np.vstack(Xs);y=np.concatenate(ys);write('training_scalings.json',scalings);write('training_records.json',records)
    with (HERE/'training_features.npz').open('xb') as f:np.savez_compressed(f,X=X,y=y)
    result=[]
    for leaves,l2 in [(15,10.),(31,20.)]:
        tic=time.perf_counter();model=HistGradientBoostingRegressor(max_iter=120,max_leaf_nodes=leaves,min_samples_leaf=40,l2_regularization=l2,learning_rate=.08,early_stopping=False,random_state=7669001).fit(X,y)
        payload=export_model(model);name=f'model_l{leaves}.json';write(name,payload)
        sample=X[::max(1,len(X)//3000)];a=model.predict(sample);b=predict_model(payload,sample);difference=float(np.max(abs(a-b)));assert difference<1e-10
        result.append(dict(model=name,leaves=leaves,l2=l2,training_seconds=time.perf_counter()-tic,export_max_difference=difference))
    write('training_receipt.json',dict(cases=len(records),rows=len(y),features=X.shape[1],models=result,seeds=list(range(7660000,7660008)),no_field_truth_used=True))
    print(json.dumps(read('training_receipt.json')),flush=True)
if __name__=='__main__':main()
