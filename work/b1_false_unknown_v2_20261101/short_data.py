"""Same reference/meter/noise, paired native60s physical action and no action."""
from common import *
from task_model import features
from copy import deepcopy

def main(stage):
    spec=read('protocol.json');d=spec['short_stages'][stage]
    script=load(HERE/'data_run.py','extra_short_generator');local=deepcopy(spec);local['unknown_variants']=['null'];local['clock_shifts'][stage+'_source']=d['clock_shift'];script.read=lambda path:local
    if stage=='short_test':
        for path,expected in read('test_freeze.json')['source_sha256'].items():assert sha(ROOT/path)==expected,path
    source=script.unknown(stage+'_source',d['seeds'],d['users']);truth={r['task_id']:r for r in read(stage+'_source/unknown/truth.json')};rng=np.random.default_rng(d['seeds'][0]+7)
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
    write(stage+'/all_facts.json',cases);write(stage+'/unknown/truth.json',labels)
    for name in ['cpop','labs']:(HERE/stage/'native'/name).mkdir(parents=True,exist_ok=True)
    original,labs,_=script.GEN.baseline_batches(cases,stage+'/native');retained=preserved_curves(cases,[original[i] for i in range(len(cases))])
    curves=[dict(task_id=c['task_id'],results=dict(cpop=original[i],labs=labs[i],retained=retained[i])) for i,c in enumerate(cases)];write(stage+'/curves.json',curves)
    X=np.vstack([features(c,original[i]['prediction'],retained[i]['prediction']) for i,c in enumerate(cases)]);np.save(HERE/stage/'features.npy',X)
    write(stage+'/generation_receipt.json',dict(n=len(cases),users=d['users']*len(d['seeds']),half_true60s=True,
        clean_amplitude_kw=[.45,1.5],original_reference_unchanged=True,original_meter_grid_1min=True,
        natural_trajectory_generator='original independent EV mechanism; true60s rectangular response is a declared controlled intervention, not an observed field action',
        all_raw_samples_retained=True))
    print(stage,'complete',len(cases),flush=True)
if __name__=='__main__':main(sys.argv[1])
