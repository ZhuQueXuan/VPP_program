"""Independent1s physical trajectories aggregated to new10s observations."""
from common import *

def generate(stage):
    p=read('protocol.json');spec=p['simulation'][stage];facts=[];truth=[]
    fine=-900+np.arange(3600)+.5;s=np.arange(-900,2700,10.);dt=1/60
    for seed in spec['seeds']:
        rng=np.random.default_rng(seed)
        for kind in p['simulation']['kinds']:
          for j in range(spec['per_kind']):
            baseline=float(rng.uniform(2.7,3.5));delay=float(rng.uniform(.2,2.));tau=float(rng.uniform(.35,1.8));finish=float(rng.uniform(16,25)) if kind=='early_exit' else 30.
            amplitude=float(rng.uniform(.16,.27)) if kind in ('smooth_weak','brief_weak') else float(rng.uniform(1.32,1.62))
            if kind=='null':amplitude=0.
            if kind=='brief_weak':delay=float(rng.uniform(2,8));finish=delay+float(rng.uniform(2,6));tau=float(rng.uniform(.15,.5))
            target=np.zeros(3600);t=fine/60;target[(t>=delay)&(t<finish)]=amplitude
            if kind=='interrupted':
                gap=float(rng.uniform(8,13));target[(t>=gap)&(t<gap+float(rng.uniform(2,5)))]=0.
            release=float(rng.uniform(.15,1.5));rbstart=finish+(float(rng.uniform(2,5)) if kind=='delayed_rebound' else float(rng.uniform(.05,.6)))
            if kind!='null':
                rbamp=float(rng.uniform(.2,1.0));rbdur=float(rng.uniform(2,6))
                if kind=='delayed_rebound':rbamp=float(rng.uniform(.8,1.8));rbdur=float(rng.uniform(6,14))
                target[(t>=rbstart)&(t<rbstart+rbdur)]=-rbamp
            trajectory=np.zeros(3600);state=velocity=0.
            for k in range(3600):
                if kind=='oscillatory':
                    velocity+=dt*(2.3**2*(target[k]-state)-2*.28*2.3*velocity);state+=dt*velocity
                else:
                    localtau=tau if target[k]>state and t[k]<finish else release
                    state+=(1-np.exp(-dt/localtau))*(target[k]-state)
                trajectory[k]=state
            if kind.startswith('one_'):
                trajectory[:]=0.;width=60 if kind.startswith('one_minute') else 10
                index=int(rng.integers(120,1500)//10*10)
                if kind.endswith('response'):trajectory[(fine>=index)&(fine<index+width)]=float(rng.uniform(.45,1.5))
                else:
                    trajectory[(fine>=0)&(fine<1800)]=1.5
                    trajectory[(fine>=index)&(fine<index+width)]=0.
                    trajectory[fine>=1800]=-.6*np.exp(-(fine[fine>=1800]-1800)/180)
            assert np.min(baseline-trajectory)>=0 and np.max(baseline-trajectory)<=7.2
            clean=trajectory.reshape(360,10).mean(axis=1);noise=rng.normal(0,.05,360)
            spike_indices=rng.choice(np.arange(90,270),2,replace=False);spike_values=rng.choice([-1.,1.],2)*rng.uniform(.4,.9,2)
            a=int(rng.integers(90,266));b=int(rng.choice([x for x in range(90,266) if abs(x-a)>=4]));burst_ix=np.r_[np.arange(a,a+4),np.arange(b,b+4)]
            burst_values=np.repeat(rng.choice([-1.,1.],2)*rng.uniform(.4,.9,2),4)
            baseid=f'fine-{seed}-{kind}-{j}'
            for condition in p['simulation']['conditions']:
                addition=np.zeros(360);ix=[];values=[]
                if condition=='single_sample_spikes':ix=spike_indices.tolist();values=spike_values.tolist()
                if condition=='persistent_bursts':ix=burst_ix.tolist();values=burst_values.tolist()
                addition[ix]=values
                tid=baseid+'-'+condition
                facts.append(dict(task_id=tid,base_task_id=baseid,seed=seed,kind=kind,condition=condition,
                    starts_s=s,ends_s=s+10.,power_kw=baseline-clean+noise-addition,reference_kw=np.repeat(baseline,360),
                    command_kw=np.where((s>=0)&(s<1800),baseline-1.5,baseline),sigma=.05,q_kw=1.5,task_seconds=1800.,
                    reference_source='known_simulated_untreated_baseline_not_prediction',meter_seconds=10.))
                truth.append(dict(task_id=tid,true_reduction_kw=clean,injected_indices=ix,injected_residual_additions_kw=values,
                    generator_parameters=dict(delay=delay,tau=tau,finish=finish,amplitude=amplitude),independent1s_trajectory=True))
    write(f'facts/{stage}.json',facts);write(f'evaluator/{stage}.json',truth);return facts
if __name__=='__main__':print(sys.argv[1],len(generate(sys.argv[1])),flush=True)
