"""Independent EV physical and choice simulator, not called by learner."""
import numpy as np
from scipy.special import expit

def main(p,raw,work):
    R=p['repetitions'];N=p['users'];S=4
    power=np.empty((R,S,N,360),np.float32);reference=np.empty((R,N,360),np.float32)
    xout=np.empty((R,N),np.uint8);wout=np.empty_like(xout);deadlineout=np.empty((R,N),int);splits=np.empty_like(xout)
    aa=np.empty((R,S,N),np.uint8);dd=np.empty_like(aa);tau=np.empty((R,S,N));delays=np.empty((R,N),int)
    minpower=10.;maxpower=-10.;error=0.
    times=np.arange(360)*10
    for r in range(R):
        rng=np.random.default_rng(p['seed_start']+r);x=rng.integers(0,2,N);w=rng.integers(0,2,N)
        deadline=2700+600*x-300*w+10*rng.integers(-30,31,N);delay=10*rng.integers(0,7,N)
        ud,ua=rng.uniform(size=(2,N));noise=rng.normal(0,.05,(N,360))
        order=rng.permutation(N);split=np.empty(N,np.uint8);split[order[:1200]]=0;split[order[1200:1600]]=1;split[order[1600:]]=2
        ref=3.*(times[None,:]<deadline[:,None]);reference[r]=ref
        xout[r]=x;wout[r]=w;deadlineout[r]=deadline;splits[r]=split;delays[r]=delay
        for s,name in enumerate(p['scenarios']):
            propensity=np.full(N,.5) if name.startswith('randomized') else .3+.4*w+.1*x
            d=(ud<propensity).astype(np.uint8);a=(ua<expit(-.2+p['acceptance_dose_coefficients'][s]*d-.8*w)).astype(np.uint8)
            duration=a*np.minimum(1200-delay,deadline-1800)
            reduction=1.5*((times[None,:]>=600+delay[:,None])&(times[None,:]<600+delay[:,None]+duration[:,None]))
            repayment=1.5*((times[None,:]>=1800)&(times[None,:]<1800+duration[:,None]))
            latent=ref-reduction+repayment
            minpower=min(minpower,float(latent.min()));maxpower=max(maxpower,float(latent.max()))
            err=float(np.max(abs((latent-ref).sum(axis=1)*10)));error=max(error,err)
            assert latent.min()>=0 and latent.max()<=4.5 and err<1e-10
            assert np.all(1800+duration<=deadline)
            power[r,s]=(latent+noise).astype(np.float32);aa[r,s]=a;dd[r,s]=d;tau[r,s]=duration
        if (r+1)%5==0:print('generate',r+1,flush=True)
    raw.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(raw/'observations.npz',power_obs_kw=power,reference_kw=reference,X=xout,W=wout,D=dd,A=aa,declared_deadline_s=deadlineout,user_split=splits)
    np.savez_compressed(work/'hidden_evaluator.npz',duration_s=tau,delay_s=delays)
    return dict(base_events=R*N,scenario_variants=R*N*S,minimum_latent_power_kw=minpower,maximum_latent_power_kw=maxpower,maximum_full_cycle_net_kws=error)
