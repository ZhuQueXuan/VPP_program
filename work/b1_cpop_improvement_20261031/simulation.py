"""New observations from immutable independent dynamics, with short-action checks."""
from common import *
def previous_generator():
    path=PREVIOUS/'simulation.py'
    spec=importlib.util.spec_from_file_location('_independent_ode_block',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
def block(seed,per_kind):
    module=previous_generator();cases,truths=module.block(seed,per_kind)
    rng=np.random.default_rng(seed+100000)
    for kind in ['one_bin_response','one_bin_gap']:
      for j in range(per_kind):
        base=float(rng.uniform(2.8,3.5));sigma=.05;q=1.5
        clean=np.zeros(60);idx=int(rng.integers(21,40))
        if kind=='one_bin_response':clean[idx]=float(rng.uniform(.45,1.5))
        else:
            clean[16:45]=1.5;clean[idx]=0.
            clean[45:]=-.6*np.exp(-np.arange(15)/3)
        noise=rng.normal(0,sigma,60)
        task={'task_id':f'cpop-short-{seed}-{kind}-{j}','user_id':f'short-user-{seed}-{kind}-{j}',
          'meter_id':f'short-meter-{seed}-{kind}-{j}','resource_type':'EV','start_min':0.,'end_min':30.,'notice_min':-15.,'request_kw':q}
        cases.append({'task':task,'kind':kind,'seed':seed,'sigma':sigma,'starts':list(range(-15,45)),
          'ends':list(range(-14,46)),'power_kw':(base-clean+noise).tolist(),'reference_kw':[base]*60,
          'reference_source':'explicit_known_simulation_not_prediction_or_command',
          'command_kw':[base-q if 0<=t<30 else base for t in range(-15,45)]})
        truths.append({'task_id':task['task_id'],'true_reduction_kw':clean.tolist(),
          'generator_parameters':{'genuine_onebin_index':idx,'not_measurement_fault':True},
          'fine_signal_min':float(clean.min()),'fine_signal_max':float(clean.max())})
    paired=[];evaluator=[]
    spike_rng=np.random.default_rng(seed+200000)
    for case,truth in zip(cases,truths):
        assert case['task']['task_id']==truth['task_id']
        indices=spike_rng.choice(np.arange(15,45),2,replace=False)
        delta=spike_rng.choice([-1.,1.],2)*spike_rng.uniform(.4,.9,2)
        for condition in ['gaussian','gaussian_plus_spikes']:
            c=json.loads(json.dumps(case));t=json.loads(json.dumps(truth));c['condition']=condition
            c['base_task_id']=case['task']['task_id']
            c['task']['task_id']+='-'+condition;t['task_id']=c['task']['task_id']
            if condition=='gaussian_plus_spikes':
                measured=np.asarray(c['power_kw']);measured[indices]-=delta;c['power_kw']=measured.tolist()
            t['injected_indices']=indices.tolist() if condition=='gaussian_plus_spikes' else []
            t['injected_residual_additions_kw']=delta.tolist() if condition=='gaussian_plus_spikes' else []
            t['base_task_id']=case['task']['task_id'];t['condition']=condition
            paired.append(c);evaluator.append(t)
    return paired,evaluator
def generate(stage):
    spec=read('protocol.json')['simulation'][stage];facts=[];truth=[]
    for seed in spec['seeds']:
        c,t=block(seed,spec['per_kind']);facts+=c;truth+=t
    write(f'facts/{stage}.json',facts);write(f'evaluator/{stage}.json',truth)
    return facts
if __name__=='__main__':
    if sys.argv[1]=='test':
        f=read('validation_freeze.json')
        for p,h in f['source_sha256'].items():assert sha(ROOT/p)==h,p
    f=generate(sys.argv[1]);print(sys.argv[1],len(f),'paired inputs;',len(f)//2,'independent base tasks')
