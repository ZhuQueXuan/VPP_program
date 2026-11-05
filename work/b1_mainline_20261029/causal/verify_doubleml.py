"""Native DoubleMLAPOS point-estimation check with identical external auxiliaries.

Official iid standard errors are intentionally not used as user-cluster inference.
"""
from pathlib import Path
import json,inspect,hashlib,warnings
import numpy as np
import doubleml
from doubleml import DoubleMLAPOS,DoubleMLData
from sklearn.linear_model import Ridge,LogisticRegression
from api import LEVELS

ROOT=Path(__file__).parent


def main():
    data=np.load(ROOT/'results/external_prediction_reference.npz')
    X,y,idx,mu,pi,folds=[data[k] for k in ['X','y','d_idx','mu','pi','folds']]
    dml_data=DoubleMLData.from_arrays(X,y,idx)
    model=DoubleMLAPOS(dml_data,Ridge(alpha=1.),LogisticRegression(C=1.,max_iter=2000),
                      treatment_levels=list(range(7)),n_folds=3,n_rep=1,normalize_ipw=False,
                      trimming_threshold=.01,draw_sample_splitting=False)
    smpls=[(np.flatnonzero(folds!=k),np.flatnonzero(folds==k)) for k in range(3)]
    model.set_sample_splitting(smpls)
    external={}
    for j in range(7):
        g0=(np.sum(pi*mu,axis=1)-pi[:,j]*mu[:,j])/np.maximum(1-pi[:,j],1e-12)
        external[j]={'ml_g_d_lvl1':mu[:,j,None],'ml_g_d_lvl0':g0[:,None],'ml_m':pi[:,j,None]}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        model.fit(n_jobs_models=1,n_jobs_cv=1,external_predictions=external)
        contrasts=model.causal_contrast(0)
    own_apo=data['scores'].mean(0)
    own_tau=own_apo[1:]-own_apo[0]
    np.testing.assert_allclose(model.coef,own_apo,atol=1e-12,rtol=0)
    np.testing.assert_allclose(contrasts.thetas,own_tau,atol=1e-12,rtol=0)
    own_centered=data['scores']-own_apo
    # Each native APO score is psi_b - mean(psi_b), because psi_a == -1.
    official_centered=np.column_stack([m.psi[:,0,0] for m in model.modellist])
    np.testing.assert_allclose(official_centered,own_centered,atol=1e-12,rtol=0)
    source=Path(inspect.getfile(DoubleMLAPOS))
    result=dict(passed=True,doubleml_version=doubleml.__version__,n_events=len(y),n_folds=3,
                same_external_auxiliary_predictions=True,folds_grouped_by_original_user=True,
                normalize_ipw=False,trimming_threshold=.01,
                physical_dose_levels=LEVELS.tolist(),treatment_indices=list(range(7)),
                native_apo=model.coef.tolist(),own_apo=own_apo.tolist(),
                native_contrasts=contrasts.thetas.tolist(),own_contrasts=own_tau.tolist(),
                maximum_apo_difference=float(abs(model.coef-own_apo).max()),
                maximum_contrast_difference=float(abs(contrasts.thetas-own_tau).max()),
                maximum_centered_score_difference=float(abs(official_centered-own_centered).max()),
                official_iid_standard_errors_used=False,official_iid_bootstrap_used=False,
                warnings=[str(w.message) for w in caught],
                official_APOS_source_file=str(source),official_APOS_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    (ROOT/'results/doubleml_reference_check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
