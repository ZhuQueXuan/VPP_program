"""Independent first/second-order controllers, not inverse RIDE/TF/LABS generation.

This is a known-reference process comparison, not a hidden-baseline field test.
Fine-grid state is integrated before meter averaging; truths are evaluator-only.
"""
from common import np,write,read,sha,HERE
KINDS=['smooth_strong','smooth_weak','brief_weak','interrupted','early_exit',
       'oscillatory','delayed_rebound','null']
def block(seed,per_kind):
    rng=np.random.default_rng(seed);cases=[];truths=[]
    fine=-15+(np.arange(3600)+.5)/60
    for kind in KINDS:
      for j in range(per_kind):
        q=1.5;W=30.;baseline=float(rng.uniform(2.7,3.5));sigma=.05
        delay=float(rng.uniform(.2,2.));tau=float(rng.uniform(.35,1.8))
        finish=float(rng.uniform(16,25)) if kind=='early_exit' else W
        amplitude=float(rng.uniform(.16,.27)) if kind in ('smooth_weak','brief_weak') else float(rng.uniform(1.32,1.62))
        if kind=='null':amplitude=0.
        if kind=='brief_weak':
            delay=float(rng.uniform(2,8));finish=delay+float(rng.uniform(2,6));tau=float(rng.uniform(.15,.5))
        target=np.zeros(len(fine));on=(fine>=delay)&(fine<finish);target[on]=amplitude
        if kind=='interrupted':
            g=float(rng.uniform(8,13));target[(fine>=g)&(fine<g+float(rng.uniform(2,5)))]=0
        release=float(rng.uniform(.15,1.5));rbstart=finish+(float(rng.uniform(2,5)) if kind=='delayed_rebound' else float(rng.uniform(.05,.6)))
        if kind!='null':
            rbamp=float(rng.uniform(.2,1.0));rbdur=float(rng.uniform(2,6))
            if kind=='delayed_rebound':rbamp=float(rng.uniform(.8,1.8));rbdur=float(rng.uniform(6,14))
            target[(fine>=rbstart)&(fine<rbstart+rbdur)]=-rbamp
        state=0.;velocity=0.;trajectory=np.zeros(len(fine));dt=1/60
        for k,t in enumerate(fine):
            if kind=='oscillatory':
                omega=2.3;zeta=.28
                velocity+=dt*(omega*omega*(target[k]-state)-2*zeta*omega*velocity)
                state+=dt*velocity
            else:
                localtau=tau if target[k]>state and t<finish else release
                state+=(1-np.exp(-dt/localtau))*(target[k]-state)
            trajectory[k]=state
        clean=trajectory.reshape(60,60).mean(axis=1)
        noise=rng.normal(0,sigma,60)
        task={'task_id':f'command-sim-{seed}-{kind}-{j}','user_id':f'user-{seed}-{kind}-{j}',
              'meter_id':f'meter-{seed}-{kind}-{j}','resource_type':'EV',
              'start_min':0.,'end_min':W,'notice_min':-15.,'request_kw':q}
        observed=baseline-clean+noise
        assert np.min(baseline-trajectory)>=0 and np.max(baseline-trajectory)<=7.2
        cases.append({'task':task,'kind':kind,'seed':seed,'sigma':sigma,
                      'starts':list(range(-15,45)),'ends':list(range(-14,46)),
                      'power_kw':observed.tolist(),'reference_kw':[baseline]*60,
                      'reference_source':'explicit_known_simulation_baseline_not_command_or_prediction',
                      'command_kw':[baseline-q if 0<=t<W else baseline for t in range(-15,45)]})
        truths.append({'task_id':task['task_id'],'true_reduction_kw':clean.tolist(),
                       'generator_parameters':{'delay':delay,'tau':tau,'finish':finish,'amplitude':amplitude},
                       'fine_signal_min':float(trajectory.min()),'fine_signal_max':float(trajectory.max())})
    return cases,truths
def generate(stage):
    design=read('protocol.json');spec=design['simulation'][stage]
    cases=[];truths=[]
    for seed in spec['seeds']:
        c,t=block(seed,spec['per_kind']);cases+=c;truths+=t
    write(f'facts/{stage}.json',cases);write(f'evaluator/{stage}.json',truths)
    return cases,truths

if __name__=='__main__':
    import sys
    stage=sys.argv[1]
    if stage=='test':
        freeze=read('validation_freeze.json')
        for name,value in freeze['source_sha256'].items():assert sha(HERE/name)==value
    c,t=generate(stage);print(stage,len(c),'new independent simulated tasks; no prediction model')
