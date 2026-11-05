"""New declared SCM, generated after the study protocol, with analytic truth."""
from pathlib import Path
import json
import numpy as np
from scipy.special import expit, betaincc
from numpy.polynomial.legendre import leggauss

T=1800.
NAMES=['deadline_slack','demand_urgency','negative_control']


def mean_parts(a,l,u,h,kind):
    signal=0*a if kind=='zero_effect' else (np.sin(np.pi*a/2.4) if kind=='nonmonotone' else a)
    interaction=signal*(1+.35*l)
    p=expit(-1.5+1.25*interaction+.5*l-.45*u+.35*h)
    mu=expit(-.6+.8*signal+.3*l-.2*u+.15*h)
    full=expit(-3.+.7*signal)
    return p,mu,full


def generate(seed,kind,users=180,events=2):
    rng=np.random.default_rng(seed);g=np.repeat(np.arange(users),events);n=len(g)
    x=rng.uniform(-1,1,(n,3));h=rng.uniform(-.6,.6,users)[g]
    if kind=='randomized':a=rng.uniform(0,2.4,n)
    else:
        z=.45*x[:,0]-.35*x[:,1]+1.3*rng.normal(size=n)
        if kind=='hidden_confounding':z+=1.5*h
        a=2.4*expit(z)
    p,mu,full=mean_parts(a,x[:,0],x[:,1],h,kind)
    positive=rng.random(n)<p;at_full=rng.random(n)<full
    fraction=np.where(positive,np.where(at_full,1.,rng.beta(mu*20,(1-mu)*20)),0.)
    return dict(seed=int(seed),mechanism=kind,X=x.tolist(),treatment=a.tolist(),outcome=(T*fraction).tolist(),
        users=[f'new-rp1-{seed}-user{j:04d}' for j in g],
        known_density=(np.full(n,1/2.4).tolist() if kind=='randomized' else None),
        reference_status='new simulation; normalized ex-ante state factors, not real preference labels')


def population(grid,kind,group=None,rounded=False,nodes=15):
    z,w=leggauss(nodes);l,u,h=np.meshgrid(z,z,.6*z,indexing='ij')
    wl,wu,wh=np.meshgrid(w,w,w,indexing='ij');weight=(wl*wu*wh).ravel()/8
    l=l.ravel();u=u.ravel();h=h.ravel()
    if group=='below':l=(l-1)/2
    if group=='above':l=(l+1)/2
    out=[]
    for amount in grid:
        p,mu,full=mean_parts(amount,l,u,h,kind)
        if rounded:
            edges=(np.arange(1,181)-.5)/180
            expected=np.empty(len(mu))
            for j in range(0,len(mu),256):
                expected[j:j+256]=betaincc(mu[j:j+256,None]*20,(1-mu[j:j+256,None])*20,edges).sum(1)/180
        else:expected=mu
        out.append(float(T*np.sum(weight*p*(full+(1-full)*expected))))
    return np.array(out)


def truth(grid,kind,group=None,rounded=False):
    a=np.asarray(grid,float);eps=1e-4
    mean=population(a,kind,group,rounded)
    derivative=(population(a+eps,kind,group,rounded)-population(a-eps,kind,group,rounded))/(2*eps)
    return dict(mean=mean.tolist(),contrasts=(mean-mean[0]).tolist(),derivative=derivative.tolist(),
                group=group,rounded_to_10s=rounded,quadrature_nodes_per_axis=15,derivative_step=eps)
