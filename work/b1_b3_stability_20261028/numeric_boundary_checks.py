"""Targeted regression for legitimate NumPy real state scalars; raw strings/bools remain rejected."""
import copy
import numpy as np
from core_io import BASE,ROOT,read,write,sha,integrity
from contracts import number
from legacy_guard import query_previous
from loaders import isolated
def main():
    integrity();c=read(ROOT/'data/B3_feedback_v1_20261028/cases.json')[0]['public'];c['agents']=[dict(permission=True,accepted=True) for _ in range(4)];checks=0
    for cls in [float,np.float64,np.float32,np.int64,np.int32]:assert number(cls(1),'numeric')==1.;checks+=1
    for bad in [True,np.bool_(False),'1',float('nan'),float('inf')]:
        try:number(bad,'numeric')
        except ValueError:checks+=1
        else:raise AssertionError('invalid raw domain accepted')
    state=dict(t=1,backlog=[np.float64(.15),np.float64(.2)],energy=np.float64(c['initial_kwh']-.1),last_factors=[1.,1.,1.,1.]);current=query_previous(c,state)
    with isolated('bridge') as old:expected=old.query_b3(c,state)
    assert current==expected and current['status']=='feasible_under_declared_model';checks+=1
    # Input scalar types are the only extension; saved primary outputs retain exact identity.
    r=read(BASE/'corrective_identity.json');assert sha(BASE/'runs.json')==r['primary_run_sha_before'] and sha(BASE/'results.json')==r['primary_results_sha_before'];checks+=2
    write(BASE/'numeric_boundary_checks.json',dict(status='passed',checks=checks,numpy_real_inputs_accepted=True,strings_boolean_nonfinite_still_rejected=True,primary_outputs_unchanged=True));print('numeric boundary passed',checks,flush=True)
if __name__=='__main__':main()
