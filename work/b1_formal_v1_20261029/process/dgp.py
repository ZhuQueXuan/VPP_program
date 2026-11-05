"""Copied evaluation-only generator; formal package never imports this file."""
import numpy as np

def shape(seed,mech):
    rng=np.random.default_rng(seed+{'none':0,'step':31,'partial':61,'slow':91,
                                  'early_exit':121,'dropout':151,'curved':181,'multiplateau':211}[mech])
    d=float(rng.uniform(1,4)); level=float(rng.uniform(1.4,1.6));release=float(rng.uniform(1,3))
    if mech=='none': return dict(knots=[-15,45],values=[0,0],curved=False)
    ramp=float(rng.uniform(3,6))
    if mech=='step': ramp=.15
    if mech=='partial': level=float(rng.uniform(.65,1.1))
    if mech=='slow': ramp=float(rng.uniform(9,14))
    end=30.
    if mech=='early_exit': end=float(rng.uniform(17,24))
    knots=[-15,d,d+ramp,end,end+release,45]
    values=[0,0,level,level,0,0]
    if mech=='dropout':
        g=float(rng.uniform(15,18))
        knots=[-15,d,d+ramp,g,g+.2,g+4,g+4.2,30,30+release,45]
        values=[0,0,level,level,0,0,level,level,0,0]
    if mech=='multiplateau':
        knots=[-15,d,d+ramp,13,16,22,25,30,30+release,45]
        values=[0,0,.6,.6,1.45,1.45,.85,.85,0,0]
    return dict(knots=knots,values=values,curved=mech=='curved')

def truth_average(sh,s,e):
    """Exact integral of linear or quadratic pieces, splitting at DGP knots."""
    ks=np.asarray(sh['knots']);vs=np.asarray(sh['values']);out=np.zeros(len(s))
    for a,b,ya,yb in zip(ks[:-1],ks[1:],vs[:-1],vs[1:]):
        lo=np.clip(s,a,b);hi=np.clip(e,a,b)
        z0=(lo-a)/(b-a);z1=(hi-a)/(b-a)
        if sh['curved'] and ya==0 and yb>0:
            integral=(b-a)*yb*(z1**3-z0**3)/3
        elif sh['curved'] and ya>0 and yb==0:
            # Quadratic release, deliberately outside linear template family.
            integral=(b-a)*ya*((z1-z0)-(z1*z1-z0*z0)+(z1**3-z0**3)/3)
        else: integral=(b-a)*(ya*(z1-z0)+(yb-ya)*(z1*z1-z0*z0)/2)
        out+=integral
    return out/(e-s)
