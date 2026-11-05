"""Independent synthetic longitudinal EV observations, complete past curves."""
import numpy as np
from scipy.special import expit

def main(p,raw,work):
    reps=p['repetitions'];nu=p['users'];ne=p['events_per_user'];scenes=len(p['scenarios'])
    power=np.empty((reps,scenes,nu,ne,120),np.float32);cond=np.empty((reps,nu,ne,3));ys=np.empty((reps,scenes,nu,ne));aa=np.empty((reps,scenes,nu,ne),np.uint8);splits=np.empty((reps,nu),np.uint8)
    hidden=[];minp=10.;maxp=-1.;neterr=0.
    for r in range(reps):
        rng=np.random.default_rng(p['seed_start']+r)
        traits=rng.uniform(-1,1,(3,nu));event_traits=rng.uniform(-1,1,(3,nu,ne))
        x,w=rng.uniform(-1,1,(2,nu,ne));di=rng.integers(0,7,(nu,ne));dose=di*.4
        v=rng.uniform(size=(nu,ne));noise=rng.normal(0,.05,(nu,ne,120))
        order=rng.permutation(nu);spl=np.empty(nu,np.uint8);spl[order[:240]]=0;spl[order[240:320]]=1;spl[order[320:]]=2;splits[r]=spl
        cond[r]=np.stack([dose/2.4,x,w],axis=-1)
        for s,name in enumerate(p['scenarios']):
            tr=np.broadcast_to(traits[:,:,None],(3,nu,ne)).copy()
            if name=='uninformative_history':tr=event_traits.copy()
            if name=='behavior_shift':tr[:,:,9:]*=-1
            a,b,h=tr;c=.55+.2*x+.15*a;prob=expit(-.3+1.1*dose/2.4+.4*x-.3*w+1.1*h);accept=v<prob
            delay=np.floor(3*(b+1)).astype(int);ramp=2+np.floor(8*(b+1)/2).astype(int)
            elapsed=np.arange(40)[None,None,:]-delay[:,:,None]
            reduction=np.zeros((nu,ne,120));reduction[:,:,20:60]=1.5*accept[:,:,None]*c[:,:,None]*np.clip(elapsed/ramp[:,:,None],0,1)
            debt=reduction[:,:,20:60].sum(axis=2)*30;remaining=debt.copy()
            for j in range(60,120):
                amount=np.minimum(45,remaining);reduction[:,:,j]=-amount/30;remaining-=amount
            assert np.max(abs(remaining))<1e-8
            latent=3-reduction;minp=min(minp,float(latent.min()));maxp=max(maxp,float(latent.max()));neterr=max(neterr,float(np.max(abs(reduction.sum(axis=2)*30))))
            assert latent.min()>=0 and latent.max()<=6
            # Round stored meter readings first; Y exactly follows stored curves.
            observed=(latent+noise).astype(np.float32);power[r,s]=observed
            ys[r,s]=np.sum((3-observed[:,:,20:60].astype(float))*30,axis=2)/1800;aa[r,s]=accept
        hidden.append(dict(seed=p['seed_start']+r,traits=traits.tolist()))
        if (r+1)%5==0:print('generate',r+1,flush=True)
    raw.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(raw/'observations.npz',power_obs_kw=power,conditions=cond,Y=ys,A=aa,user_split=splits,event_start_s=np.arange(ne)*86400)
    import json
    (work/'hidden_traits.json').write_text(json.dumps(hidden),encoding='utf-8')
    return dict(independent_repetitions=reps,base_user_draws=reps*nu,base_events=reps*nu*ne,scenario_event_variants=reps*scenes*nu*ne,minimum_latent_power_kw=minp,maximum_latent_power_kw=maxp,maximum_full_cycle_net_kws=neterr)
