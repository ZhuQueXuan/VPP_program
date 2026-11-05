"""Declared multi-arm EV SCM. Parameters are assumptions, not empirical calibration."""
import numpy as np
from scipy.special import expit

def probability(name,d,x,w,u):
    base=.12+.12*(x+1)/2+.06*w+.04*u
    if name=='zero':return expit(-.5+.7*x-.6*w+.8*u)
    if name=='linear':return base+.22*d/2.4
    if name=='smooth':return expit(-2.5+4*d/2.4+.7*x-.6*w+.8*u)
    if name=='hinge':return base+.3*np.maximum(0,d-1.2)/1.2
    raise ValueError(name)

def request_observations(accepted,c,delay,noise):
    times=np.arange(600.,1800.,10.)
    power=3.-1.5*accepted[:,None]*c[:,None]*(times[None,:]>=600+delay[:,None])+noise
    y=np.sum((3.-power)*10,axis=1)/1800
    return power,y

def generate(p,raw,work):
    reps=len(p['seeds']);n=p['users']*p['events_per_user'];scenes=p['scenarios']
    arrays={k:np.empty((reps,n),int) for k in ('user','split','dose')}
    arrays['X']=np.empty((reps,n,2))
    arrays['A']=np.empty((reps,len(scenes),n),np.uint8)
    arrays['Y']=np.empty((reps,len(scenes),n))
    panel=[];check={'max_power_bound_violation':0.,'minimum_recovery_margin_kws':1e10,'rows':0}
    for ri,seed in enumerate(p['seeds']):
        rng=np.random.default_rng(seed)
        user=np.repeat(np.arange(p['users']),p['events_per_user'])
        x,w=rng.uniform(-1,1,(2,n));u=rng.uniform(-1,1,p['users'])[user]
        v=rng.uniform(size=n);di=rng.integers(0,7,n);d=np.array(p['doses_yuan_per_kwh'])[di]
        delay=10*rng.integers(0,7,n)
        order=rng.permutation(p['users']);us=np.empty(p['users'],int)
        us[order[:360]]=0;us[order[360:480]]=1;us[order[480:]]=2
        arrays['X'][ri]=np.c_[x,w];arrays['user'][ri]=user;arrays['split'][ri]=us[user];arrays['dose'][ri]=di
        c=(.4+.2*(x+1))*(.8+.2*w*w)
        noise=rng.normal(0,.05,(n,120))
        for si,name in enumerate(scenes):
            prob=probability(name,d,x,w,u)
            assert np.all((prob>=0)&(prob<=1))
            a=(v<prob).astype(np.uint8)
            power,y=request_observations(a,c,delay,noise)
            arrays['A'][ri,si]=a;arrays['Y'][ri,si]=y
            debt=1.5*a*c*(1200-delay)
            horizon=3600+1800*(x+1);extra=.5+.75*(x+1)
            margin=extra*(horizon-1800)-debt
            check['minimum_recovery_margin_kws']=min(check['minimum_recovery_margin_kws'],float(margin.min()))
            violation=max(0.,float(np.max(1.5*a*c-3.)))
            check['max_power_bound_violation']=max(check['max_power_bound_violation'],violation)
            check['rows']+=n
            if ri==0:
                for j in range(21):panel.append((si,j,x[j],w[j],int(a[j]),delay[j],c[j],power[j].copy(),y[j]))
        print(f'generate {ri+1}/{reps}',flush=True)
    assert check['minimum_recovery_margin_kws']>=-1e-9
    raw.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(raw/'observations.npz',**arrays)
    np.savez_compressed(raw/'request_panel.npz',time_edges_s=np.arange(600.,1801.,10.),
        reference_kw=np.full(120,3.),power_obs_kw=np.array([r[7] for r in panel]),indices=np.array([[r[0],r[1]] for r in panel]))
    np.savez_compressed(work/'panel_evaluator.npz',meta=np.array([[*r[:7],r[8]] for r in panel]))
    return check
