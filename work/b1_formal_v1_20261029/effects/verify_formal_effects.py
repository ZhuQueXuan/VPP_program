"""Formal API contract, frozen numerical identity and native DoubleML checks.

This is a small verification suite, not a new performance or model-selection run.
"""
from pathlib import Path
import copy, hashlib, json, sys
import numpy as np

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[2]
sys.path.insert(0,str(REPO))
from b1_algorithm.effects import fit_effects,fit_binary_saturated,EffectConfig
from b1_algorithm.effects.core import aipw_scores,cluster_band,threshold_set

TASK=dict(task_id='fixed_task_30min_1p5kw',outcome_name='net_delivery_ratio',outcome_unit='ratio',
          window_minutes=[0.,30.],q_kw=1.5,target_population='supplied_events_equal_weight',
          task_pre_treatment=True,reference_status='provided_estimate',reference_uncertainty='not_propagated')
ASSUMPTIONS=dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,
                 same_outcome_definition=True,conditional_exchangeability=True,randomized_assignment=False)
LEVELS=[0.,.4,.8,1.2,1.6,2.,2.4]


def fixture():
    rng=np.random.default_rng(541093)
    userX=rng.uniform(-1,1,(140,3))
    X=np.repeat(userX,7,axis=0)
    users=np.repeat(np.arange(140),7)
    idx=np.tile(np.arange(7),140)
    y=.3+.1*X[:,0]+.04*idx+rng.normal(0,.02,len(idx))
    return dict(X=X,treatment=np.array(LEVELS)[idx],outcome=y,users=users)


def checked(result):
    json.dumps(result,allow_nan=False)
    assert result['schema_version']=='b1.effects.v1'
    assert 'identified' not in result
    for reason in result['reasons']:
        assert set(reason)=={'code','field','detail'} and reason['detail']
    return result


def main():
    tests=[]
    data=fixture()
    options=dict(task=TASK,assumptions=ASSUMPTIONS,levels=LEVELS,config={'n_boot':99,'return_audit':True})
    valid=checked(fit_effects(**data,**options))
    assert valid['status']=='causal' and valid['support_pass'] and valid['causal_assumptions_confirmed']
    assert valid['causal_curve'] and valid['inference'] and valid['threshold_set']
    assert valid['uncertainty']['reference_process_uncertainty_propagated'] is False
    tests.append('causal_requires_support_and_explicit_assumptions')
    result=checked(fit_effects(**data,task=TASK,config={'n_boot':99}))
    assert result['status']=='association' and result['support_pass']
    assert result['standardized_association'] and result['causal_curve'] is None and result['inference'] is None and result['threshold_set'] is None
    tests.append('unconfirmed_assumptions_only_standardized_association')
    pi=np.full((len(data['outcome']),7),1/7)
    result=checked(fit_effects(**data,task=TASK,known_pi=pi,config={'n_boot':99}))
    assert result['status']=='association' and not result['causal_assumptions_confirmed']
    tests.append('known_probabilities_do_not_prove_randomization')
    randomized=dict(ASSUMPTIONS,randomized_assignment=True,conditional_exchangeability=None)
    result=checked(fit_effects(**data,task=TASK,known_pi=pi,assumptions=randomized,config={'n_boot':99}))
    assert result['status']=='causal' and result['comparators']['arm_mean_randomized']
    tests.append('declared_constant_randomization_has_arm_mean_baseline')
    result=checked(fit_effects(**data,task=TASK,assumptions=randomized,config={'n_boot':99}))
    assert result['status']=='invalid_input' and result['reasons'][0]['code']=='randomization_probabilities_required'
    tests.append('randomization_declaration_needs_design_probabilities')
    # A covariate-dependent randomized design cannot use unadjusted population arm means.
    moving=pi.copy();moving[:,0]+=.015*data['X'][:,0];moving[:,1]-=.015*data['X'][:,0]
    result=checked(fit_effects(**data,task=TASK,known_pi=moving,assumptions=randomized,config={'n_boot':99}))
    assert result['status']=='causal' and result['comparators']['arm_mean_randomized'] is None
    assert result['comparators']['arm_mean_randomized_unavailable_reason']
    tests.append('covariate_dependent_randomization_withholds_unadjusted_mean_baseline')
    unknown_task=dict(TASK,task_pre_treatment=False)
    result=checked(fit_effects(**data,task=unknown_task,assumptions=ASSUMPTIONS,config={'n_boot':99}))
    assert result['status']=='association' and 'task_pre_treatment' in result['unconfirmed_assumptions']
    tests.append('post_treatment_task_declaration_prevents_causal_claim')
    onehot=np.eye(7)[np.tile(np.arange(7),140)]
    result=checked(fit_effects(**data,task=TASK,known_pi=onehot,assumptions=randomized,config={'n_boot':99}))
    assert result['status']=='unsupported' and not result['support_pass'] and result['causal_curve'] is None
    assert any(r['code']=='insufficient_common_support' for r in result['reasons'])
    tests.append('deterministic_assignment_withholds_conclusions')
    sparse=dict(X=np.zeros((140,3)),treatment=np.repeat(LEVELS,20),outcome=np.ones(140),users=np.repeat(np.arange(7),20))
    result=checked(fit_effects(**sparse,task=TASK,assumptions=ASSUMPTIONS,config={'n_boot':99}))
    assert result['status']=='unsupported' and any(r['code']=='sparse_training_arm' for r in result['reasons'])
    assert result['diagnostics']['training_counts']
    tests.append('sparse_training_arm_has_explicit_fold_and_arm_reasons')
    invalid=[]
    for field,bad_value in [
        ('X',np.where(np.arange(data['X'].size).reshape(data['X'].shape)==0,np.nan,data['X'])),
        ('outcome',[True]+data['outcome'][1:].tolist()),
        ('outcome',['0.1']+data['outcome'][1:].tolist()),
        ('outcome',np.r_[np.inf,data['outcome'][1:]]),
        ('users',[None]+data['users'][1:].tolist()),
        ('users',[np.nan]+data['users'][1:].tolist()),
        ('users',[True]+data['users'][1:].tolist()),
        ('users',['']+data['users'][1:].tolist()),
        ('treatment',np.r_[.3,data['treatment'][1:]])]:
        changed=dict(data);changed[field]=bad_value
        result=checked(fit_effects(**changed,**options));assert result['status']=='invalid_input'
        invalid.append(field)
    tests.append('nonfinite_missing_boolean_string_and_unknown_dose_rejected_'+str(len(invalid)))
    configs=[{'n_boot':True},{'n_boot':3},{'n_folds':1},{'alpha':1.},{'alpha':0.},
             {'kappa':np.nan},{'ridge_alpha':0.},{'propensity_C':-1.},{'smd_limit':0.},
             {'propensity_clip':.2},{'return_audit':'false'},{'unexpected':1}]
    for cfg in configs:
        result=checked(fit_effects(**data,task=TASK,assumptions=ASSUMPTIONS,config=cfg))
        assert result['status']=='invalid_input'
    tests.append('configuration_domains_checked_'+str(len(configs)))
    for name in ['q_kw','ridge_alpha']:
        if name=='q_kw':
            bad_task=dict(TASK,q_kw=10**999)
            result=checked(fit_effects(**data,task=bad_task,assumptions=ASSUMPTIONS,config={'n_boot':99}))
        else:
            result=checked(fit_effects(**data,task=TASK,assumptions=ASSUMPTIONS,config={'n_boot':99,'ridge_alpha':10**999}))
        assert result['status']=='invalid_input' and result['reasons'][0]['code']=='numeric_domain'
    tests.append('out_of_float64_scalar_domain_structured_rejection')
    for bad in [np.full_like(pi,np.nan),np.full_like(pi,1.),pi[:2],np.where(np.arange(pi.size).reshape(pi.shape)==0,-.1,pi)]:
        result=checked(fit_effects(**data,task=TASK,known_pi=bad,assumptions=ASSUMPTIONS,config={'n_boot':99}))
        assert result['status']=='invalid_input'
    tests.append('known_pi_shape_probability_and_finiteness_checked')
    bad_context=dict(TASK,reference_uncertainty='fully_propagated')
    result=checked(fit_effects(**data,task=bad_context,assumptions=ASSUMPTIONS,config={'n_boot':99}))
    assert result['status']=='invalid_input' and result['reasons'][0]['code']=='uncertainty_not_implemented'
    tests.append('cannot_declare_unimplemented_full_uncertainty_propagation')
    bad_assumptions=dict(ASSUMPTIONS,no_interference='true')
    result=checked(fit_effects(**data,task=TASK,assumptions=bad_assumptions,config={'n_boot':99}))
    assert result['status']=='invalid_input'
    tests.append('assumption_flags_reject_truthy_strings')
    # Independent score and user-cluster arithmetic from the formal result.
    audit=valid['audit'];mu=np.array(audit['auxiliary_result_predictions']);prop=np.array(audit['propensity_predictions'])
    idx=np.array(audit['dose_index']);y=data['outcome']
    loop=np.array([[mu[i,j]+int(idx[i]==j)*(y[i]-mu[i,j])/max(prop[i,j],.01) for j in range(7)] for i in range(len(y))])
    np.testing.assert_allclose(loop,audit['aipw_scores'],atol=1e-12)
    c=loop[:,1:]-loop[:,[0]];cbar=c.mean(0)
    sums=np.array([(c[data['users']==u]-cbar).sum(0) for u in np.unique(data['users'])])
    se=np.sqrt(140/139*np.sum(sums*sums,axis=0))/len(y)
    np.testing.assert_allclose(se,valid['inference']['standard_errors'][1:],atol=1e-12)
    tests.append('independent_AIPW_loop_and_cluster_standard_errors')
    folds=np.array(audit['fold_by_event'])
    assert all(len(np.unique(folds[data['users']==u]))==1 for u in np.unique(data['users']))
    tests.append('original_user_never_crosses_training_and_evaluation_fold')
    nonmonotone=threshold_set([0,0,0,0],[0,.2,.22,.06],[0,.4,.8,1.2],.1)
    assert nonmonotone['first_grid_crossing_indices']==[1,2] and nonmonotone['not_reached_possible']
    tests.append('nonmonotone_first_crossing_candidates_not_isotonically_tightened')
    # Legacy G1 reproduces a fully saturated binary adjustment exactly.
    binaryX=np.repeat(np.array([[0,0],[0,1],[1,0],[1,1]]),40,axis=0)
    bd=np.tile(np.repeat([0.,1.],20),4)
    by=.3+.1*binaryX[:,0]-.2*binaryX[:,1]+.2*bd
    targetX=np.array([[0,0],[0,1],[1,0],[1,1]])
    legacy=dict(X_train=binaryX,treatment=bd,outcome=by,users_train=np.arange(160),
                X_target=targetX,users_target=np.arange(1000,1004),task=TASK,assumptions=ASSUMPTIONS)
    saturated=checked(fit_binary_saturated(**legacy))
    assert saturated['status']=='causal' and saturated['inference'] is None
    np.testing.assert_allclose(saturated['causal_curve']['contrasts'],[0,.2],atol=1e-12)
    bad=dict(legacy);bad['X_train']=binaryX.astype(float).copy();bad['X_train'][0,0]=.2
    assert checked(fit_binary_saturated(**bad))['status']=='invalid_input'
    bad=dict(legacy);bad['users_target']=np.arange(4)
    assert checked(fit_binary_saturated(**bad))['status']=='invalid_input'
    bad=dict(legacy);bad['min_cell']=21
    fail_legacy=checked(fit_binary_saturated(**bad))
    assert fail_legacy['status']=='unsupported' and fail_legacy['causal_curve'] is None
    tests.append('legacy_binary_G1_valid_domain_exact_and_no_sparse_cell_dropping')
    # Read an existing frozen seed fixture; no 20-seed study is rerun.
    frozen_path=REPO/'work/b1_mainline_20261029/causal/results/external_prediction_reference.npz'
    frozen=np.load(frozen_path)
    fresh=checked(fit_effects(frozen['X'],frozen['d'],frozen['y'],frozen['groups'],task=TASK,
                              assumptions=ASSUMPTIONS,config={'n_boot':99,'seed':291000,'return_audit':True}))
    assert fresh['status']=='causal'
    np.testing.assert_allclose(fresh['audit']['aipw_scores'],frozen['scores'],atol=1e-12,rtol=0)
    tests.append('formal_default_matches_one_frozen_research_fixture_score_no_study_rerun')
    # Native DoubleML point-score check from formal auxiliary predictions.
    import doubleml
    from doubleml import DoubleMLAPOS,DoubleMLData
    from sklearn.linear_model import Ridge,LogisticRegression
    a=fresh['audit'];fm=np.asarray(a['auxiliary_result_predictions']);fp=np.asarray(a['propensity_predictions'])
    fi=np.asarray(a['dose_index']);ff=np.asarray(a['fold_by_event'])
    dml_data=DoubleMLData.from_arrays(frozen['X'],frozen['y'],fi)
    official=DoubleMLAPOS(dml_data,Ridge(alpha=1.),LogisticRegression(C=1.,max_iter=2000),treatment_levels=list(range(7)),
                         n_folds=3,n_rep=1,normalize_ipw=False,trimming_threshold=.01,draw_sample_splitting=False)
    official.set_sample_splitting([(np.flatnonzero(ff!=k),np.flatnonzero(ff==k)) for k in range(3)])
    ext={j:{'ml_g_d_lvl1':fm[:,j,None],
            'ml_g_d_lvl0':((fp*fm).sum(1)-fp[:,j]*fm[:,j])[:,None]/np.maximum(1-fp[:,j,None],1e-12),
            'ml_m':fp[:,j,None]} for j in range(7)}
    official.fit(n_jobs_models=1,n_jobs_cv=1,external_predictions=ext)
    contrasts=official.causal_contrast(0).thetas
    np.testing.assert_allclose(contrasts,fresh['causal_curve']['contrasts'][1:],atol=1e-12,rtol=0)
    tests.append('native_DoubleMLAPOS_0p11p4_same_formal_predictions_and_user_folds')
    source=REPO/'b1_algorithm/effects'
    receipt=dict(passed=True,check_groups=tests,n_groups=len(tests),
                 score_loop_max_error=float(abs(loop-np.asarray(audit['aipw_scores'])).max()),
                 frozen_score_max_error=float(abs(np.asarray(fresh['audit']['aipw_scores'])-frozen['scores']).max()),
                 native_DoubleML_version=doubleml.__version__,
                 native_DoubleML_contrast_max_error=float(abs(contrasts-np.asarray(fresh['causal_curve']['contrasts'][1:])).max()),
                 official_iid_SE_used=False,all_API_results_JSON_allow_nan_false=True,main_20_seed_study_rerun=False,
                 source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('*.py')})
    (ROOT/'verification_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    (ROOT/'causal_example.json').write_text(json.dumps({k:v for k,v in valid.items() if k!='audit'},indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
