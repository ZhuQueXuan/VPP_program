"""Declared full-cycle EV power scenarios, independent of extraction code."""
import json
import numpy as np

def main(p,raw,work):
    n=360;times=np.arange(0,3600,10);rngs=p['seed_start']+np.arange(p['repetitions'])
    hidden=[];latent_meta=[];panels=[];index=[];maxbound=0.;maxdebt=0.
    for rep,seed in enumerate(rngs):
        rng=np.random.default_rng(int(seed));delay=int(30*rng.integers(0,5));part=float(rng.uniform(.45,1.05))
        early=int(1200+30*rng.integers(0,5));drop=int(960+30*rng.integers(0,4));dropdur=int(60+30*rng.integers(0,5))
        noise=rng.normal(size=n)
        for case,name in enumerate(p['mechanisms']):
            onset=600+delay;r=np.zeros(n);active=(times>=onset)&(times<1800)
            if name=='step':r[active]=1.5
            elif name=='partial':r[active]=part
            elif name=='slow_ramp':r[active]=1.5*np.minimum((times[active]-onset)/600,1)
            elif name=='early_exit':r[active&(times<early)]=1.5
            elif name=='interrupted':r[active&~((times>=drop)&(times<drop+dropdur))]=1.5
            elif name!='no_action':raise ValueError(name)
            debt=float(np.sum(r)*10)
            remaining=debt
            for j in range(180,360):
                repayment=min(15.,remaining);r[j]=-repayment/10;remaining-=repayment
            assert abs(remaining)<1e-9 and abs(r.sum()*10)<1e-8
            assert np.all((3-r>=0)&(3-r<=6))
            hidden.append(r.copy());lid=len(hidden)-1
            latent_meta.append(dict(rep=rep,mechanism=name,delay_s=delay,partial_kw=part,early_end_s=early,drop_start_s=drop,drop_duration_s=dropdur,physical_action_onset_s=None if name=='no_action' else onset,request_debt_kws=debt))
            for sigma in p['noise_sigma_native_kw']:
                observed=3-r+sigma*noise
                for dt in p['dt_s']:
                    factor=dt//10;means=observed.reshape(-1,factor).mean(axis=1);tt=np.arange(0,3600+dt,dt)
                    for oi,obs in enumerate(p['observations']):
                        val=means.copy();end=3600
                        if obs=='short_post':end=2100;val=val[:end//dt]
                        if obs.startswith('missing_'):
                            a,b=p['grid'][obs];val[(tt[:-1]>=a)&(tt[:-1]<b)]=np.nan
                        padded=np.full(n,np.nan);padded[:len(val)]=val;panels.append(padded)
                        index.append(dict(id=len(index),latent_id=lid,rep=rep,mechanism=name,observation=obs,dt_s=dt,end_s=end,n=len(val),sigma_native_kw=sigma,sigma_effective_kw=float(sigma/np.sqrt(factor))))
    raw.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(raw/'observations.npz',power_obs_kw=np.array(panels),reference_kw=np.full(n,3.))
    (raw/'observation_index.json').write_text(json.dumps(index,ensure_ascii=False),encoding='utf-8')
    np.savez_compressed(work/'hidden_native.npz',reduction_kw=np.array(hidden))
    (work/'hidden_meta.json').write_text(json.dumps(latent_meta),encoding='utf-8')
    return dict(independent_base_draws=p['repetitions'],mechanism_event_variants=len(hidden),observation_variants=len(index),maximum_full_cycle_absolute_net_kws=float(np.max(abs(np.array(hidden).sum(axis=1)*10))),minimum_latent_power_kw=float(np.min(3-np.array(hidden))),maximum_latent_power_kw=float(np.max(3-np.array(hidden))))
