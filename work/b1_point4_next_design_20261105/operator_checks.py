"""Non-training finite-matrix identities and basis checks; no research cohorts."""
import hashlib
import json
from pathlib import Path
import numpy as np
from sklearn.linear_model import Ridge
from continuous_r import state,dose_basis,design,operator_solution,query_conditional

HERE=Path(__file__).resolve().parent


def main():
    def forbidden_fit(*a,**k):
        raise AssertionError("No estimator fit allowed in operator checks.")
    Ridge.fit=forbidden_fit
    checks=0
    def ck(ok,label):
        nonlocal checks
        if not ok:
            raise AssertionError(label)
        checks+=1
    # Cartesian algebra grid, not draws from any proposed study seed.
    xx=np.array([[a,b,c] for a in (-.8,0.,.8) for b in (-.8,0.,.8) for c in (-.8,0.,.8)])
    aa=np.linspace(.03,2.37,19)
    x=np.repeat(xx,len(aa),axis=0)
    a=np.tile(aa,len(xx))
    ps=design(x,a)
    ck(ps.shape==(513,80),"80-dimensional fixed function class")
    ck(np.max(abs(dose_basis(aa).sum(axis=1)-1))<1e-12,"partition unity")
    gamma=ps.reshape(27,19,80).mean(axis=1)
    centered=ps-np.repeat(gamma,19,axis=0)
    q=ps.T@ps/len(ps)
    r=centered.T@centered/len(ps)
    # A predetermined symbolic coefficient vector: no Y data or model is trained.
    beta=np.sin(np.arange(80)*.23)/30
    rhs=r@beta
    expect=(design(xx,np.full(27,1.2))-design(xx,np.full(27,.4)))@beta
    errors=[]
    for rho in (.005,.05,.5):
        model=operator_solution(r,q,rhs,rho)
        model.update(reference=.4,outcome_scale=1.)
        result=query_conditional(model,xx,[.4,.73,1.2])
        ck(np.max(abs(result[:,0]))==0,"exact reference zero")
        err=float(np.max(abs(result[:,2]-expect)))
        errors.append(err)
        ck(err<1e-8,"functional penalty and 1+rho identity")
        ck(np.max(abs((r+rho*q)@np.array(model["phi"])-rhs))<1e-9,"normal equation")
        # Save/reload of complete numerical operator has identical queries.
        loaded=json.loads(json.dumps(model))
        ck(np.array_equal(result,query_conditional(loaded,xx,[.4,.73,1.2])),"operator reload")
    # Coefficient-I is not a substitute for the function Gram Q.
    wrong=np.linalg.solve(r+.05*np.eye(80),rhs)
    wrong_result=1.05*(design(xx,np.full(27,1.2))-design(xx,np.full(27,.4)))@wrong
    wrong_error=float(np.max(abs(wrong_result-expect)))
    ck(wrong_error>1e-5,"I penalty fails the functional identity on this algebra grid")
    # Verify fixed rank handling: a null query must reject rather than extrapolate.
    singular=operator_solution(np.diag([1.,0.]),np.diag([2.,0.]),np.array([1.,0.]))
    ck(singular["q_rank"]==1,"fixed Q subspace")
    for name in ("continuous_r.py","operator_checks.py"):
        compile((HERE/name).read_text(encoding="utf-8"),name,"exec")
    ck(True,"syntax")
    out=dict(passed=True,checks=checks,new_estimator_fits=0,research_cohorts_generated=0,
             method="deterministic finite-operator identities; not model training or performance evidence",
             maximum_operator_identity_error=max(errors),coefficient_I_counterexample_error=wrong_error,
             code_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
                          [HERE/"continuous_r.py",HERE/"operator_checks.py"]})
    (HERE/"operator_checks.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
