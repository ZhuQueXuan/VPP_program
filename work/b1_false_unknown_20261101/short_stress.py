"""Additional unseen-user unknown-reference60s safety test, before any adoption."""
from common import *
from task_model import features
from copy import deepcopy
from train_choose import evaluate

def main():
    selected=read('selected.json');script=load(HERE/'data_run.py','new_short_holdout_generator')
    spec=deepcopy(read('protocol.json'));spec['unknown_variants']=['null'];spec['clock_shifts']['short_source']=12096000
    script.read=lambda path:spec
    write('short_stress_protocol.json',dict(seed=7713500,users=16,events_per_user=2,
        task='30min; compare a true60s rectangular reduction at unchanged native1min measurement versus no action, both ordinary/spikes',
        model_sha256=sha(HERE/selected['model']),no_fitting_or_selection=True,
        safety='Candidate cannot add localized short misses relative to retained method. Failure prevents new candidate adoption.'))
    source=script.unknown('short_source',[7713500],16);truth={r['task_id']:r for r in read('short_source/unknown/truth.json')};rng=np.random.default_rng(7713501)
    recipes={};cases=[];labels=[]
    for c in source:
        base=c['base_task_id']
        if base not in recipes:recipes[base]=(int(rng.integers(18,42)),float(rng.uniform(.45,1.5)))
        index,amplitude=recipes[base]
        for variant in ['null','short']:
            x=deepcopy(c);clean=np.zeros(60)
            if variant=='short':clean[index]=amplitude
            x['task_id']+='-'+variant;x['base_task_id']+='-'+variant;x['kind']='one_minute_response' if variant=='short' else 'null';x['power_kw']=np.array(x['power_kw'])-clean
            cases.append(x);labels.append(dict(task_id=x['task_id'],true_reduction_kw=clean,true_reference_kw=truth[c['task_id']]['true_reference_kw']))
    write('short_stress/all_facts.json',cases);write('short_stress/unknown/truth.json',labels)
    for method in ['cpop','labs']:(HERE/'short_stress/native'/method).mkdir(parents=True,exist_ok=True)
    original,labs,_=script.GEN.baseline_batches(cases,'short_stress/native');retained=preserved_curves(cases,[original[i] for i in range(len(cases))])
    curves=[dict(task_id=c['task_id'],results=dict(cpop=original[i],labs=labs[i],retained=retained[i])) for i,c in enumerate(cases)];write('short_stress/curves.json',curves)
    X=np.vstack([features(c,original[i]['prediction'],retained[i]['prediction']) for i,c in enumerate(cases)]);np.save(HERE/'short_stress/features.npy',X)
    # evaluate expects the primary known panel files for non-train stages; the
    # stress is unknown-only, so score directly instead of inventing known rows.
    probabilities=expit(DF._tree_predict(read(selected['model']),X));rows=[]
    for c,t,r,p in zip(cases,labels,curves,probabilities):
        fits=dict(r['results']);pred=np.array(fits['retained']['prediction']);fits['candidate']=dict(prediction=pred if p>=selected['threshold'] else np.zeros(len(pred)))
        for method,fit in fits.items():
            metric=measure(fit['prediction'],t['true_reduction_kw'],np.array(c['starts_s']),60.)
            short=metric['positive_truth'] and metric['true_cumulative_seconds']<=60.
            rows.append(dict(**{k:c[k] for k in ['task_id','base_task_id','regime','panel','seed','kind','condition']},method=method,short_n=short,short_local_miss=short and metric['localized_miss'],**metric))
    write('short_stress/metrics.json',rows);ss=summary(rows);write('short_stress/summary.json',ss);by={r['method']:r for r in ss}
    write('short_stress/decision.json',dict(passed=by['candidate']['short_local_miss']<=by['retained']['short_local_miss'],summary=ss));print(json.dumps(native(ss)),flush=True)
if __name__=='__main__':main()
