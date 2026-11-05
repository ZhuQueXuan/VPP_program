"""Independent fixture checks; these seeds are not study cohorts."""
from pathlib import Path
import importlib.util,json
import numpy as np
from data import KINDS,signal,generate,population
from prepare import save
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('retained_data_math',HERE.parent/'b1_curve_spline_pilot_20261103/data.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
errors=[];q=np.linspace(.3,2.1,31)
for k in KINDS:
    m=population(q,k);d=population(q,k,derivative=1)
    finite=(population(q+1e-5,k)-population(q-1e-5,k))/(2e-5)
    e=float(np.max(abs(d-finite)));quad=float(max(np.max(abs(m-population(q,k,nodes=23))),np.max(abs(d-population(q,k,nodes=23,derivative=1)))))
    assert e<1e-5 and quad<1e-7,(k,e,quad)
    errors.append(dict(mechanism=k,derivative_vs_finite_difference=e,quadrature15_vs23=quad))
for k in old.KINDS:
    a=generate(90354990,k,users=20,events=2);b=old.generate(90354990,k,users=20,events=2)
    for name in ('X','treatment','outcome','known_density'):assert a[name]==b[name],(k,name)
dense=np.linspace(0,2.4,2401);s,ds=signal(dense,'two_peak')
maxima=dense[:-1][(ds[:-1]>0)&(ds[1:]<=0)]
assert len(maxima)==2,maxima
assert np.allclose(population(q,'noisy_nonmonotone'),population(q,'nonmonotone'),rtol=0,atol=0)
r=dict(passed=True,fixture_seed=90354990,new_study_cohorts=0,old_six_mechanisms_exact_at_new_fixture=True,
    two_internal_maxima=maxima.tolist(),higher_variance_mechanism_preserves_true_mean=True,errors=errors)
save(HERE/'audit_data.json',r);print(json.dumps(r))
