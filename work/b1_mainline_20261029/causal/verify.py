"""Independent arithmetic and API boundary checks needed for scientific validity."""
import json
from pathlib import Path
import numpy as np
from api import aipw_scores, cluster_inference, threshold_candidates, fit_discrete, group_folds
from simulation import generate


def main():
    checks = []
    rng = np.random.default_rng(290001)
    y = rng.normal(size=42)
    idx = np.arange(42)%7
    mu = rng.normal(size=(42,7))
    pi = rng.uniform(.1,1,(42,7)); pi /= pi.sum(1,keepdims=True)
    actual = aipw_scores(y, idx, mu, pi)
    independent = np.array([[mu[i,j]+(y[i]-mu[i,j])/max(pi[i,j],.01)*(idx[i]==j) for j in range(7)] for i in range(42)])
    np.testing.assert_allclose(actual, independent, atol=1e-12); checks.append('AIPW_score_independent_loop')
    groups = np.repeat(np.arange(14),3)
    inf = cluster_inference(actual, groups, n_boot=99, seed=12)
    c = actual[:,1:]-actual[:,[0]]
    cbar = c.mean(0)
    loop_sums = np.array([(c[groups==g]-cbar).sum(0) for g in np.unique(groups)])
    independent_se = np.sqrt(14/13*np.sum(loop_sums**2,axis=0))/42
    np.testing.assert_allclose(inf['se'][1:], independent_se, atol=1e-12); checks.append('cluster_SE_independent_user_sums')
    folds = group_folds(groups,3,9)
    assert all(len(np.unique(folds[groups==g]))==1 for g in np.unique(groups)); checks.append('user_fold_no_leakage')
    # No isotonic projection: retain a feasible nonmonotone first crossing.
    lo, hi = [0,0,0,0], [0,.20,.22,.06]
    threshold = threshold_candidates(lo,hi,[0,.4,.8,1.2])
    assert threshold['indices']==[1,2] and threshold['not_reached']; checks.append('nonmonotone_threshold_set_keeps_truth')
    exact = threshold_candidates([0,.05,.12,.07],[0,.05,.12,.07],[0,.4,.8,1.2])
    assert exact['indices']==[2] and not exact['not_reached']; checks.append('nonmonotone_exact_first_crossing')
    # A common covariate-only outcome shift with matched mu leaves AIPW contrasts invariant.
    shift = rng.normal(size=42)
    shifted = aipw_scores(y-shift,idx,mu-shift[:,None],pi)
    np.testing.assert_allclose(actual[:,1:]-actual[:,[0]],shifted[:,1:]-shifted[:,[0]],atol=1e-12)
    checks.append('common_reference_shift_contrast_invariance')
    data = generate(290001,'rct_positive',n_users=60,events_per_user=6)
    result = fit_discrete(data['X'],data['d'],data['y'],data['groups'],known_pi=data['assignment_pi'],n_boot=99,seed=290001)
    assert result['audit'] is not None and np.isfinite(result['audit']['scores']).all(); checks.append('external_outcome_API_runs')
    for key,bad in [('y',data['y'].copy()),('d',data['d'].copy())]:
        bad[0] = np.nan
        args = {k:data[k] for k in ['X','d','y','groups']}; args[key]=bad
        try: fit_discrete(**args,n_boot=10)
        except ValueError: pass
        else: raise AssertionError(key+' nonfinite accepted')
    checks.append('nonfinite_input_rejected')
    receipt = dict(passed=True,checks=checks, n_checks=len(checks), maximum_score_discrepancy=float(abs(actual-independent).max()),
                   maximum_SE_discrepancy=float(abs(inf['se'][1:]-independent_se).max()))
    (Path(__file__).parent/'verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__': main()
