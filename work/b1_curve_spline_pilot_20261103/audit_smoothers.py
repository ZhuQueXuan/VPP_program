"""Deterministic mathematical preflight only; no study cohorts or nuisance fits."""
from pathlib import Path
import importlib.util
import hashlib
import json
import sys
import numpy as np
import scipy
from scipy.interpolate import BSpline, make_smoothing_spline
from numpy.polynomial.legendre import leggauss

HERE = Path(__file__).resolve().parent
def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

S = module('audit_spline_functions', 'smoothers.py')
D = module('audit_spline_truth', 'data.py')
checks = []
def check(name, value, tolerance, **details):
    value = float(value)
    ok = bool(np.isfinite(value) and value <= tolerance)
    checks.append(dict(name=name, maximum_absolute_error=value, tolerance=tolerance, passed=ok, **details))

# Fixed mathematical arrays, not random development/confirmation data.
d = np.linspace(0.08, 2.32, 61)
q = np.linspace(0.3, 2.1, 37)
y = 600 + 180*np.sin(2*d) + 11*np.cos(13*d)
for lam in (1e-6, 1e-5, 1e-4, 1e-3, 1e-2):
    state = S.spline_state(d, y, lam)
    f = BSpline(state['knots'], state['coefficients'], state['degree'])
    # Independently construct the weighted normal equations in normalized units.
    t = np.asarray(state['knots']); c = np.asarray(state['coefficients'])
    basis = BSpline(t, np.eye(len(c)), state['degree'])
    B = basis(d/S.SPAN)
    z, w = leggauss(5)
    R = np.zeros((len(c), len(c)))
    knots = np.unique(t)
    for lo, hi in zip(knots[:-1], knots[1:]):
        xx = (lo+hi)/2 + (hi-lo)*z/2
        second = basis(xx, nu=2)
        R += second.T @ ((w*(hi-lo)/2)[:,None]*second)
    residual_gradient = B.T@(B@c-y/S.SCALE) + len(d)*lam*R@c
    denominator = max(1., float(np.max(np.abs(B.T@(y/S.SCALE)))))
    check(f'normal_equations_mean_objective_lambda_{lam}', np.max(abs(residual_gradient))/denominator, 2e-7)
    check(f'normalization_value_lambda_{lam}', np.max(abs(S.spline_query(state,q)-f(q/2.4)*1800)), 1e-10)
    check(f'normalization_derivative_lambda_{lam}', np.max(abs(S.spline_query(state,q,1)-f(q/2.4,nu=1)*1800/2.4)), 1e-10)
    eps=1e-5
    fd=(S.spline_query(state,q+eps)-S.spline_query(state,q-eps))/(2*eps)
    check(f'derivative_finite_difference_lambda_{lam}', np.max(abs(fd-S.spline_query(state,q,1))), 2e-5)
    for repeat in (2,7):
        replicated=S.spline_state(np.repeat(d,repeat),np.repeat(y,repeat),lam)
        check(f'exact_event_replication_mean_loss_lambda_{lam}_n{repeat}',np.max(abs(S.spline_query(state,q)-S.spline_query(replicated,q))),2e-6)
    roundtrip=json.loads(json.dumps(state,allow_nan=False))
    check(f'serialized_state_lambda_{lam}',np.max(abs(S.spline_query(state,q)-S.spline_query(roundtrip,q))),0.)
    inserted=np.sort(np.r_[q,0.731])
    old=np.searchsorted(inserted,q)
    check(f'query_insertion_lambda_{lam}',np.max(abs(S.spline_query(state,q)-S.spline_query(state,inserted)[old])),0.)
    check(f'query_single_scalar_lambda_{lam}',abs(float(S.spline_query(state,.731))-S.spline_query(state,[.731])[0]),0.)

for name, target, slope in [('constant', np.full_like(d,720.),0.),('linear',100.+400.*d,400.)]:
    for lam in (1e-6,1e-2):
        state=S.spline_state(d,target,lam)
        truth=np.full_like(q,720.) if name=='constant' else 100.+400.*q
        check(name+f'_reproduction_lambda_{lam}',np.max(abs(S.spline_query(state,q)-truth)),2e-6)
        check(name+f'_derivative_lambda_{lam}',np.max(abs(S.spline_query(state,q,1)-slope)),2e-6)

# Unequal counts and within-equal-dose residual variation must preserve the loss.
counts=1+np.arange(len(d))%4
dd=np.repeat(d,counts)
yy=np.repeat(y,counts)+np.concatenate([np.linspace(-9,9,n) if n>1 else np.zeros(1) for n in counts])
state=S.spline_state(dd,yy,1e-4)
reference=make_smoothing_spline(d/2.4,y/1800,w=counts.astype(float),lam=len(dd)*1e-4)
check('exact_duplicate_dose_weighted_equivalence',np.max(abs(S.spline_query(state,q)-reference(q/2.4)*1800)),2e-6)
fitted=S.spline_query(state,d)
lhs=np.sum((yy-np.repeat(fitted,counts))**2)
within=np.sum((yy-np.repeat(y,counts))**2)
rhs=np.sum(counts*(y-fitted)**2)+within
check('duplicate_dose_loss_identity',abs(lhs-rhs)/max(1.,abs(lhs)),2e-12)
linear=S.spline_state(d,100.+100.*d,1e-3)
root=S.crossings(lambda a:S.spline_query(linear,a),.3,np.linspace(.3,2.1,181),120.)
check('threshold_units_and_reference',abs(root['first_crossing']-1.5),2e-7)

# Analytic truth derivative checked by an independent numerical perturbation.
for kind in D.KINDS:
    a=np.array([.31,.73,1.17,1.83,2.09]);eps=1e-5
    analytic=D.population(a,kind,derivative=1)
    fd=(D.population(a+eps,kind)-D.population(a-eps,kind))/(2*eps)
    check('truth_derivative_'+kind,np.max(abs(analytic-fd)),3e-5)
    low=D.population(a,kind,nodes=15)
    high=D.population(a,kind,nodes=23)
    check('truth_quadrature_stability_'+kind,np.max(abs(low-high)),2e-5)

source_names=('prepare.py','smoothers.py','study.py','data.py')
result=dict(activity='Deterministic smoother algebra and truth integration; no generated cohorts or nuisance learner fits',
    scipy_version=scipy.__version__,numpy_version=np.__version__,python=sys.executable,
    files={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in source_names},
    checks=checks,passed=all(c['passed'] for c in checks),check_count=len(checks),
    source_review=dict(shared_pseudo_outcomes=True,scale_derivative_correct=True,
        mean_loss_lambda_n_correct=True,development_only_policy_selection=True,
        independent_replication_unit='seed; mechanisms paired within seed',
        full_cohort_denominator='aggregate contains successful-only diagnostic means; adoption must require all designated cohorts',
        field_validation=False,limitations=['No empirical performance measured here','Crossing mesh may miss two crossings inside one cell; explicitly resolution-limited']))
with (HERE/'audit_preflight.json').open('x',encoding='utf-8') as f:
    json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
print(json.dumps(dict(passed=result['passed'],checks=len(checks),failures=[c for c in checks if not c['passed']]),ensure_ascii=False))
if not result['passed']:
    raise SystemExit(1)
