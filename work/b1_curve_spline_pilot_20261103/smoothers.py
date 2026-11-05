"""Single final-stage replacement. No nuisance learner changes."""
import numpy as np
from scipy.interpolate import make_smoothing_spline,BSpline
from scipy.optimize import brentq

SPAN=2.4
SCALE=1800.

def spline_state(dose,pseudo_outcome,lambda_mean):
    d=np.asarray(dose,float)/SPAN
    y=np.asarray(pseudo_outcome,float)/SCALE
    order=np.argsort(d,kind='stable')
    unique,first,count=np.unique(d[order],return_index=True,return_counts=True)
    # This exact aggregation preserves original squared-loss contributions.
    # It is not binning. Equal amounts alone are combined; no observation lost.
    means=np.add.reduceat(y[order],first)/count
    f=make_smoothing_spline(unique,means,w=count.astype(float),lam=len(d)*float(lambda_mean))
    return dict(knots=f.t.tolist(),coefficients=f.c.tolist(),degree=f.k,
        lambda_mean=float(lambda_mean),scipy_lambda=len(d)*float(lambda_mean),events=len(d),
        unique_doses=len(unique),observed_domain=[float(min(dose)),float(max(dose))],
        x_scale=SPAN,y_scale=SCALE)

def spline_query(state,amounts,derivative=0):
    a=np.asarray(amounts,float)
    if np.any(a<state['observed_domain'][0]) or np.any(a>state['observed_domain'][1]):
        raise ValueError('no spline extrapolation beyond observed amounts')
    f=BSpline(state['knots'],state['coefficients'],state['degree'],extrapolate=False)
    return f(a/SPAN,nu=derivative)*SCALE/(SPAN**derivative)

def crossings(query,reference,mesh,target):
    mesh=np.asarray(mesh,float)
    base=float(query(np.array([reference]))[0])
    y=np.asarray(query(mesh))-base-target
    roots=[]
    if y[0]>=0:roots.append(float(mesh[0]))
    for j in range(len(mesh)-1):
        if y[j]<0<=y[j+1]:
            roots.append(float(brentq(lambda a:float(query(np.array([a]))[0]-base-target),
                mesh[j],mesh[j+1],xtol=1e-10)))
    return dict(reached=bool(roots),first_crossing=roots[0] if roots else None,upcrossings=roots,
        resolution='predeclared .01 amount mesh locates candidate cells; roots evaluated directly')
