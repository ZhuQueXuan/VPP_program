"""Frozen synthetic EV request observations. No empirical calibration."""
import numpy as np

def increments(d,di):
    return np.array([.3*np.maximum(0,d-1.2)/1.2,
        np.array([0,.05,.35,.05,.32,.02,.36])[di],np.zeros(len(d)),.19*d/2.4])

def main(p,raw,work):
    reps=p['repetitions'];n=p['users']*p['events_per_user'];user=np.repeat(np.arange(p['users']),p['events_per_user'])
    xout=np.empty((reps,n));wout=np.empty_like(xout);diout=np.empty((reps,n),np.uint8)
    ys=np.empty((reps,4,n));aa=np.empty((reps,4,n),np.uint8);panel=[];meta=[]
    margin_min=1e10;pmin=1.;pmax=0.
    for r in range(reps):
        rng=np.random.default_rng(p['seed_start']+r)
        x,w=rng.uniform(-1,1,(2,n));u=rng.uniform(-1,1,p['users'])[user]
        v=rng.uniform(size=n);di=rng.integers(0,7,n);d=np.array(p['doses'])[di]
        delay=10*rng.integers(0,7,n);c=(.4+.2*(x+1))*(.8+.2*w*w)
        noise=rng.normal(0,.05,(n,120));base=.12+.12*(x+1)/2+.06*w+.04*u
        probs=base[None,:]+increments(d,di)
        assert probs.min()>=0 and probs.max()<=1
        pmin=min(pmin,float(probs.min()));pmax=max(pmax,float(probs.max()))
        accepted=(v[None,:]<probs).astype(np.uint8)
        for s in range(4):
            power=3-1.5*accepted[s,:,None]*c[:,None]*(np.arange(600,1800,10)[None,:]>=600+delay[:,None])+noise
            y=((3-power)*10).sum(axis=1)/1800
            ys[r,s]=y;aa[r,s]=accepted[s]
            debt=1.5*accepted[s]*c*(1200-delay)
            margin=(.5+.75*(x+1))*(1800+1800*(x+1))-debt
            margin_min=min(margin_min,float(margin.min()))
            assert np.all(3-1.5*accepted[s]*c>=0)
            if r==0:
                for j in range(21):
                    panel.append(power[j]);meta.append([s,j,int(accepted[s,j]),c[j],delay[j],y[j]])
        xout[r]=x;wout[r]=w;diout[r]=di
        if (r+1)%20==0:print('generate',r+1,flush=True)
    assert margin_min>=0
    raw.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(raw/'observations.npz',user=user,x=xout,w=wout,dose=diout,A=aa,Y=ys)
    np.savez_compressed(raw/'request_panel.npz',power_obs_kw=panel,time_edges_s=np.arange(600,1801,10),indices=np.array(meta)[:,:2].astype(int),reference_kw=np.full(120,3.))
    np.savez_compressed(work/'panel_evaluator.npz',meta=meta)
    return dict(base_events=reps*n,fact_variants=reps*n*4,user_draws=reps*p['users'],minimum_analytic_recovery_margin_kws=margin_min,acceptance_probability_range=[pmin,pmax])
