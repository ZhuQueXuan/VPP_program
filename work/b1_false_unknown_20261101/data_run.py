from common import *
from dataclasses import asdict
from b1_algorithm.reference.core import ReferenceWindow
from b1_algorithm.reference.reliable import load_ev_reliable_reference_model,predict_ev_reliable_reference
from task_model import features

GEN=load(OLD/'generation.py','known_generator_reused')

def unknown(stage,seeds,users):
    generator=load(ROOT/'work/b1_reliability_20261031/study/generator.py','unknown_original_generator')
    model=load_ev_reliable_reference_model(ROOT/'work/b1_reliability_20261031/study/models/reliable_reference.json')
    spec=read('protocol.json');cases=[];truth=[];ledger=[];source=[]
    for seed in seeds:
        sets=generator.generate_reliability(seed,users,events_per_user=2,variants=tuple(spec['unknown_variants']),clock_shift_min=spec['clock_shifts'][stage])
        rng=np.random.default_rng(seed+290000)
        # One fault realization per original user-task, paired across variants.
        additions=[]
        for i in range(users*2):
            ix=rng.choice(np.arange(15,45),2,replace=False);v=rng.choice([-1.,1.],2)*rng.uniform(.4,.9,2);a=np.zeros(60);a[ix]=v;additions.append(a)
        for variant,(facts,labels,meta) in sets.items():
          for index,(f,t) in enumerate(zip(facts,labels)):
            w=ReferenceWindow(**f['reference_window']);prediction=predict_ev_reliable_reference(model,w)
            assert prediction.reference_status=='available',prediction.reasons
            assert prediction.available_at_min<=f['task']['notice_min'] and prediction.role=='unseen_user'
            assert max(w.pre_ends_min)<=f['task']['notice_min']
            s=(np.array(f['starts_min'])-f['task']['start_min'])*60;e=(np.array(f['ends_min'])-f['task']['start_min'])*60
            base=f['task']['task_id']+'-'+variant
            for condition in spec['unknown_conditions']:
                tid=base+'-'+condition;power=np.array(f['power_kw'])-(additions[index] if condition=='spikes' else 0.)
                cases.append(dict(task_id=tid,base_task_id=base,physical_task_id=f['task']['task_id'],user_id=f['task']['user_id'],seed=seed,kind=variant,
                    regime='unknown',panel='minute',condition=condition,starts_s=s,ends_s=e,reference_kw=prediction.reference_kw,power_kw=power,sigma=.05))
                truth.append(dict(task_id=tid,true_reduction_kw=t['true_reduction_kw'],true_reference_kw=t['true_reference_kw']))
            source.append(f);ledger.append(dict(task_id=base,reference=asdict(prediction),notice_min=f['task']['notice_min'],prefix_end=max(w.pre_ends_min),
                fit_cutoff_min=model.fit_cutoff_min,inputs='reference_window only; current power, variant, labels not used'))
    write(stage+'/unknown/source_facts.json',source);write(stage+'/unknown/reference_ledger.json',ledger)
    write(stage+'/unknown/facts.json',cases);write(stage+'/unknown/truth.json',truth)
    return cases

def run(stage):
    if stage=='test':
        for path,expected in read('test_freeze.json')['source_sha256'].items():assert sha(ROOT/path)==expected,path
    spec=read('protocol.json');cases=[]
    if stage!='train':
        for panel in ['minute','10s']:
            block=GEN.generate(panel,spec[stage+'_known_seeds'],spec['known_per_kind'],stage+'/known_'+panel)
            for c in block:c['regime']='known'
            cases+=block
    seeds=spec['train_unknown_seeds'] if stage=='train' else spec[stage+'_unknown_seeds']
    users=spec[{'train':'training_unknown_users','validation':'validation_unknown_users','test':'test_unknown_users'}[stage]]
    cases+=unknown(stage,seeds,users)
    write(stage+'/all_facts.json',cases)
    for name in ['cpop','labs']:(HERE/stage/'native'/name).mkdir(parents=True,exist_ok=True)
    original,labs,meta=GEN.baseline_batches(cases,stage+'/native');retained=preserved_curves(cases,[original[i] for i in range(len(cases))])
    curves=[dict(task_id=c['task_id'],results=dict(cpop=original[i],labs=labs[i],retained=retained[i])) for i,c in enumerate(cases)]
    write(stage+'/curves.json',curves)
    X=np.vstack([features(c,original[i]['prediction'],retained[i]['prediction']) for i,c in enumerate(cases)])
    np.save(HERE/stage/'features.npy',X)
    write(stage+'/native_receipt.json',dict(n=len(cases),statuses={m:sum(r['results'][m]['status']=='ok' for r in curves) for m in ['cpop','labs','retained']},baseline_shared_reference=True))
    print(stage,'completed',len(cases),X.shape,flush=True)
if __name__=='__main__':run(sys.argv[1])
