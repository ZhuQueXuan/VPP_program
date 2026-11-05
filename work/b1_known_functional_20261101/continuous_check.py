"""Untuned distribution check: continuous weak amplitudes, same observed grid."""
from common import *

for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
plan=dict(seeds=[7742400,7742401,7742402,7742403],per_kind=1,peak_uniform_kw=[.07,.30],
    purpose='Additional independent weak-amplitude distribution check, not for fitting, selecting or retuning.',
    configuration=read('selected.json')['config'])
write('continuous_check_plan.json',plan)
m=load(HERE/'data.py','continuous_data_adapter')
original_read=m.read
def adapted_read(name):
    value=original_read(name)
    if str(name)=='protocol.json':value=dict(value,stress_continuous_seeds=plan['seeds'],stress_continuous_per_kind=plan['per_kind'])
    return value
m.read=adapted_read
def continuous(panel,seeds,per_kind,prefix):
    cases=m.GEN.generate(panel,seeds,per_kind,prefix+'_unscaled');truth=read(prefix+'_unscaled/truth.json');scales={};records=[]
    for base in sorted({c['base_task_id'] for c in cases}):
        seed=int.from_bytes(hashlib.sha256(('continuous'+base).encode()).digest()[:8],'little');scales[base]=float(np.random.default_rng(seed).uniform(.07,.30))
    for c,t in zip(cases,truth):
        clean=np.asarray(t['true_reduction_kw']);inside=(np.asarray(c['starts_s'])>=0)&(np.asarray(c['starts_s'])<1800);peak=clean[inside].max();scale=scales[c['base_task_id']]/peak if peak>0 else 1.
        latent=clean*scale;observed=np.asarray(c['reference_kw'])-np.asarray(c['power_kw']);c['power_kw']=np.asarray(c['reference_kw'])-(observed-clean+latent)
        t['true_reduction_kw']=latent;records.append(dict(task_id=c['task_id'],peak=scales[c['base_task_id']],scale=scale))
    write(prefix+'/facts.json',cases);write(prefix+'/truth.json',truth);write(prefix+'/generation_recipe.json',records)
    return cases
m.GEN.generate_stress=continuous
write('continuous_check_generator_sha256.json',{'continuous_check.py':sha(HERE/'continuous_check.py'),'data.py':sha(HERE/'data.py')})
m.run('stress_continuous')
