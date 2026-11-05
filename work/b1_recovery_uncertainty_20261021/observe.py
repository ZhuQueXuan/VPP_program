"""New synthetic observed curves, parameter sources are declared assumptions."""
import numpy as np

def physical_power(t,mechanism,target_debt):
    left=t[:-1];p=np.full(len(left),3.)
    if mechanism!='no_action':
        p[(left>=600)&(left<1800)]=1.5
        p[(left>=1800)&(left<2520)]+=5*(.5-target_debt)
    return p

def generate(protocol):
    rng=np.random.default_rng(protocol['seed'])
    t=np.arange(0,3601,10,dtype=float)
    n=len(t)-1;reps=protocol['repetitions_per_cell'];sig=.05;rho=.8
    # Shared external innovations across observation variants, independent repetitions.
    z=rng.normal(size=(len(protocol['mechanisms']),reps,n))
    iid=sig*z
    ar=np.empty_like(z);ar[...,0]=sig*z[...,0]
    for j in range(1,n):ar[...,j]=rho*ar[...,j-1]+sig*np.sqrt(1-rho*rho)*z[...,j]
    pstar=np.array([physical_power(t,m,debt) for m,debt in protocol['mechanisms'].items()])
    observations=np.empty((5,len(pstar),reps,n))
    reference=np.full((5,n),3.)
    for s,name in enumerate(protocol['observation_models']):
        err=ar if name.startswith('ar1') else iid
        observations[s]=pstar[:,None,:]+err
        if name.startswith('reference_bias'):reference[s]+=.02
    assert pstar.min()>=0 and pstar.max()<=6
    return dict(time_edges_s=t,reference_kw=reference,power_obs_kw=observations)
