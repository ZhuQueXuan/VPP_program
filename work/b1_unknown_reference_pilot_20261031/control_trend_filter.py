"""Meaningful constructed numerical controls, no study facts or truth read."""
import sys
sys.dont_write_bytecode = True
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
import json
from pathlib import Path
import numpy as np
from scipy.optimize import minimize, LinearConstraint, Bounds
from trend_filter import fit_curve, second_difference

checks=[]
def check(name, condition, **details):
    checks.append(dict(name=name, passed=bool(condition), **details))
    if not condition:
        raise AssertionError(name+': '+str(details))

def solved(y, cov, penalty):
    result=fit_curve(y,cov,penalty)
    check('checked_solution',result['status']=='ok',n=len(y),penalty=penalty,
        reason=result['reason'],gap=result['raw_gap'],tolerance=result['gap_tolerance'])
    json.dumps(result,allow_nan=False)
    return np.array(result['prediction']),result

rng=np.random.default_rng(731011)
y=rng.normal(size=60)
x,r=solved(y,.0025,0.)
check('lambda_zero_exact',np.array_equal(x,y) and r['primal']==0 and r['dual']==0)
grid=np.arange(60.)
for signal in (np.full(60,2.5),.3+.017*grid):
    x,r=solved(signal,.0025,64.)
    check('constant_or_line_invariant',np.max(np.abs(x-signal))<1e-9,max_error=float(np.max(np.abs(x-signal))))
y=.15*np.sin(grid/3.)+.04*rng.normal(size=60)
x,r=solved(y,.0025,8.)
xn,rn=solved(-y,.0025,8.)
check('sign_symmetry',np.max(np.abs(x+xn))<1e-9)
xd,rd=solved(y,.0025*np.eye(60),8.)
check('scalar_full_isotropic_equal',np.max(np.abs(x-xd))<1e-10)
scale=7.
xs,rs=solved(scale*y,scale**2*.0025,8./scale)
check('physical_unit_scale_equivariance',np.max(np.abs(xs-scale*x))<1e-8)
xs,rs=solved(scale*y,.0025,8.*scale)
check('fixed_covariance_scale_equivariance',np.max(np.abs(xs-scale*x))<1e-8)
D=second_difference(60);u=np.asarray(r['dual_solution'])
check('stationarity_identity',np.max(np.abs(x-y+.0025*D.T@u))<1e-12)
check('gap_complementarity_identity',abs(r['raw_gap']-(8.*np.sum(np.abs(D@x))-u@(D@x)))<1e-9)
check('dual_feasible',np.max(np.abs(u))<=8.+1e-10)

# Independent primal epigraph QP, using SLSQP rather than dual least squares.
direct=[]
for n,lam in ((7,.7),(9,2.3),(12,.2)):
    yy=.2*rng.normal(size=n)+np.linspace(-.1,.3,n)
    indices=np.arange(n)
    cov=.03*.7**np.abs(indices[:,None]-indices[None,:])+.01*np.eye(n)
    xx,rr=solved(yy,cov,lam);D=second_difference(n)
    precision=np.linalg.inv(cov)
    m=n-2
    def objective(v):
        z=v[:n]-yy
        return .5*z@precision@z+lam*np.sum(v[n:])
    def gradient(v):
        return np.r_[precision@(v[:n]-yy),np.full(m,lam)]
    constraints=LinearConstraint(np.vstack([np.c_[D,-np.eye(m)],np.c_[-D,-np.eye(m)]]),
        np.full(2*m,-np.inf),np.zeros(2*m))
    initial=np.r_[yy,np.abs(D@yy)]
    result=minimize(objective,initial,jac=gradient,method='SLSQP',
        constraints=constraints,bounds=Bounds(np.r_[np.full(n,-np.inf),np.zeros(m)],np.full(n+m,np.inf)),
        options=dict(ftol=1e-12,maxiter=2000))
    err=float(np.max(np.abs(result.x[:n]-xx)))
    objective_error=abs(float(result.fun)-rr['primal'])
    check('full_covariance_vs_independent_primal_qp',result.success and err<3e-6 and objective_error<1e-8,
        n=n,prediction_max_difference=err,objective_difference=objective_error,message=str(result.message))
    direct.append(dict(n=n,lambda_value=lam,max_difference=err,objective_difference=objective_error))

for bad_y,bad_cov,bad_penalty in (([0.,float('nan'),1.],1.,1.),([0.,1.,2.],0.,1.),
    ([0.,1.,2.],[[1.,2.,0.],[0.,1.,0.],[0.,0.,1.]],1.),
    ([0.,1.,2.],np.ones((3,3)),1.),([0.,1.,2.],1.,True),([0.,1.,2.],1.,-1.)):
    rr=fit_curve(bad_y,bad_cov,bad_penalty)
    check('invalid_inputs_unavailable_without_fallback',rr['status']=='unavailable' and rr['prediction'] is None and not rr['raw_fallback'],reason=rr['reason'])
    json.dumps(rr,allow_nan=False)

# A deliberately corrupted optimizer result must not be certified merely
# because it reports success. This controls the independent gap/KKT gates.
import trend_filter as tf
original=tf.lsq_linear
class Bogus:
    x=np.zeros(58);success=True;nit=1;optimality=0.;status=1;message='constructed bogus success'
tf.lsq_linear=lambda *args,**kwargs:Bogus()
try:
    rr=tf.fit_curve(y,.0025,8.)
finally:
    tf.lsq_linear=original
check('false_solver_success_rejected_by_math_gate',rr['status']=='unavailable' and rr['prediction'] is None and not rr['gap_pass'],reason=rr['reason'])

receipt=dict(scope='Small constructed numerical controls only; no study facts, fits, selection or performance claim.',
    passed=True,check_count=len(checks),checks=checks,independent_primal_checks=direct,
    implementation='standard L1 trend filter; H=I on native meter means; no clipping or offset',
    python=sys.executable,numpy=np.__version__)
path=Path(__file__).with_name('trend_filter_controls.json')
path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
print(json.dumps(dict(passed=True,check_count=len(checks),independent_primal_checks=direct),ensure_ascii=False))
