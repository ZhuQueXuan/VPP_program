"""Independent saved-data audit; no study, estimator or simulation imports."""
from pathlib import Path
from collections import defaultdict
import os
for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[variable] = '1'
import hashlib, json
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / 'data/B1_metered_effects_v1_20261030'
LEVELS = np.arange(7)*.4


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def boolean(value):
    if isinstance(value,str):
        assert value in ('True','False')
        return value=='True'
    return bool(value)


def cluster_interval(scores,groups,seed):
    # Independently reconstruct lexical user-string ordering and cluster sums.
    labels=['user-'+str(int(g)) for g in groups]
    users=sorted(set(labels));lookup={user:i for i,user in enumerate(users)}
    inverse=np.array([lookup[user] for user in labels])
    differences=scores[:,1:]-scores[:,[0]]
    center=np.mean(differences,axis=0)
    sums=np.zeros((len(users),6))
    for arm in range(6):
        sums[:,arm]=np.bincount(inverse,weights=differences[:,arm]-center[arm],minlength=len(users))
    sums*=np.sqrt(len(users)/(len(users)-1))
    se=np.sqrt(np.sum(sums**2,axis=0))/len(groups)
    draws=np.random.default_rng(seed+73).standard_normal((999,len(users)))
    active=se>1e-14
    if np.any(active):
        maxima=np.max(np.abs(draws@sums[:,active]/len(groups))/se[active],axis=1)
    else:
        maxima=np.zeros(999)
    critical=float(np.quantile(maxima,.95))
    return np.r_[0.,center-critical*se],np.r_[0.,center+critical*se]


def main():
    out=HERE/'results'
    assert (out/'receipt.json').is_file(),'Wait for completed scientific results'
    audit_path=out/'audit_receipt.json'
    if audit_path.exists():raise RuntimeError('Audit receipt exists; preserve it')
    receipt=json.loads((out/'receipt.json').read_text(encoding='utf-8'))
    assert receipt['complete']
    freeze=json.loads((out/'freeze.json').read_text(encoding='utf-8'))
    for relative,expected in freeze['hashes'].items():
        assert digest(ROOT/relative)==expected,relative
    protocol=json.loads((HERE/'protocol.json').read_text(encoding='utf-8'))
    metrics=pd.read_csv(out/'metrics.csv')
    curve_rows=pd.read_csv(out/'curves.csv')
    maximum=defaultdict(float);counts=defaultdict(int);independent=[]

    def close(name,a,b,tolerance=1e-10):
        aa=np.asarray(a,dtype=float);bb=np.asarray(b,dtype=float)
        assert aa.shape==bb.shape,(name,aa.shape,bb.shape)
        error=float(np.max(np.abs(aa-bb))) if aa.size else 0.
        maximum[name]=max(maximum[name],error)
        counts[name]+=aa.size
        assert np.isfinite(error) and error<=tolerance,(name,error)

    scenario_data={}
    for seed in protocol['seeds']:
        for scenario in protocol['scenarios']:
            stem=f'{seed}_{scenario}'
            data=np.load(DATA/(stem+'.npz'));audit=np.load(out/(stem+'_audit.npz'))
            X=data['X'];d=data['d'];groups=data['groups'];baseline=data['baseline'];potential=data['potential']
            bhat=data['predicted_reference'];eta=data['eta'];z=data['z'];yhat=data['predicted_eta']
            assert X.shape==(3600,3) and potential.shape==(3600,7)
            assert len(np.unique(groups))==600 and np.all(np.bincount(groups)==6)
            starts=data['actual_starts'];ends=data['actual_ends'];power=data['actual_power']
            assert starts.shape==ends.shape==power.shape==(3600,30)
            close('one_minute_width',ends-starts,np.ones_like(starts))
            close('complete_contiguous_task',starts[:,1:],ends[:,:-1])
            close('thirty_minute_window',ends[:,-1]-starts[:,0],np.full(3600,30.))
            integrated=np.array([-sum(float(p)*float(e-s) for p,s,e in zip(pp,ss,ee))/45
                                 for pp,ss,ee in zip(power,starts,ends)])
            close('raw_meter_integral',integrated,z)
            close('eta_to_meter_outcome',z,eta-baseline)
            close('predicted_eta_definition',yhat,eta+bhat-baseline)
            close('pre_treatment_reference',bhat,2.75+.2*X[:,0]+.2*X[:,1])
            latent=np.random.default_rng(seed+54321).normal(size=600)[groups]
            close('natural_reference',baseline,3+.35*X[:,0]+.2*X[:,1]+.15*X[:,2]+.1*X[:,0]**2+.12*latent)
            assert np.min(baseline[:,None]-potential)>0.
            assert np.all(power>=0.),'This finite meter panel should remain positive without clipping'
            reference_free_potential=potential-baseline[:,None]
            close('potential_contrast_identity',reference_free_potential-reference_free_potential[:,[0]],potential-potential[:,[0]])
            truth=np.mean(potential-potential[:,[0]],axis=0)
            close('potential_truth_curve',truth,data['truth_tau'])
            scenario_data[(seed,scenario)]=(X,groups)
            if scenario!='rct_positive':
                shared_X,shared_g=scenario_data[(seed,'rct_positive')]
                close('paired_scenario_covariates',X,shared_X)
                close('paired_scenario_users',groups,shared_g)
            match=np.isclose(d[:,None],LEVELS[None,:],rtol=0,atol=1e-10)
            assert np.all(match.sum(axis=1)==1)
            idx=np.argmax(match,axis=1)
            case=metrics[(metrics.seed==seed)&(metrics.scenario==scenario)]
            assert len(case)==3
            if scenario=='deterministic_no_overlap':
                assert len(audit.files)==0
                assert set(case.status)=={'unsupported'}
                assert case.curve_rmse.isna().all() and case.joint_coverage.isna().all()
                assert case.threshold_contains_truth.isna().all()
                assert not ((curve_rows.seed==seed)&(curve_rows.scenario==scenario)).any()
                assert case.reason_codes.notna().all()
                counts['unsupported_outcomes_checked']+=3
                continue
            assert set(case.status)=={'causal'}
            branch_pi=None;branch_folds=None;branch_mu={};branch_scores={}
            outcomes={'oracle_eta':eta,'predicted_eta':yhat,'metered_Z':z}
            for name,y in outcomes.items():
                row=case[case.outcome==name].iloc[0]
                mu=audit[name+'_auxiliary_result_predictions']
                pi=audit[name+'_propensity_predictions']
                saved_scores=audit[name+'_aipw_scores']
                folds=audit[name+'_fold_by_event'];given_idx=audit[name+'_dose_index']
                assert mu.shape==pi.shape==saved_scores.shape==(3600,7)
                close('dose_index',given_idx,idx)
                assert np.all(np.isfinite(mu)) and np.all(pi>0)
                close('propensity_row_sums',pi.sum(axis=1),np.ones(3600))
                for user in np.unique(groups):
                    assert len(np.unique(folds[groups==user]))==1
                    counts['user_fold_integrity']+=1
                unique_labels=sorted({'user-'+str(int(g)) for g in groups})
                label_index={label:i for i,label in enumerate(unique_labels)}
                perm=np.random.default_rng(seed).permutation(600)
                assignment=np.empty(600,dtype=int);assignment[perm]=np.arange(600)%3
                expected_folds=np.array([assignment[label_index['user-'+str(int(g))]] for g in groups])
                close('seeded_group_folds',folds,expected_folds)
                if branch_pi is None:
                    branch_pi=pi.copy();branch_folds=folds.copy()
                else:
                    close('shared_propensity_across_outcomes',pi,branch_pi,0.)
                    close('shared_folds_across_outcomes',folds,branch_folds,0.)
                if scenario=='rct_positive':close('known_rct_probability',pi,np.full_like(pi,1/7),0.)
                # Explicit arm loops recompute the standard AIPW score.
                scores=mu.copy()
                for arm in range(7):
                    selected=(idx==arm)
                    scores[selected,arm]+=(y[selected]-mu[selected,arm])/np.maximum(pi[selected,arm],.01)
                close('sample_aipw_scores',scores,saved_scores)
                means=scores.mean(axis=0);tau=means-means[0]
                plugin=mu.mean(axis=0);plugin-=plugin[0]
                rmse=float(np.sqrt(np.mean((tau[1:]-truth[1:])**2)))
                plugin_rmse=float(np.sqrt(np.mean((plugin[1:]-truth[1:])**2)))
                close('aipw_curve_rmse',np.asarray(row.curve_rmse),np.asarray(rmse))
                close('plugin_curve_rmse',np.asarray(row.plugin_rmse),np.asarray(plugin_rmse))
                curves=curve_rows[(curve_rows.seed==seed)&(curve_rows.scenario==scenario)&(curve_rows.outcome==name)].sort_values('level')
                assert len(curves)==7
                close('reported_levels',curves.level.to_numpy(),LEVELS)
                close('reported_effect_curve',curves.estimate.to_numpy(),tau)
                close('reported_truth_curve',curves.truth.to_numpy(),truth)
                lower,upper=cluster_interval(scores,groups,seed)
                close('cluster_lower_band',curves.lower.to_numpy(),lower)
                close('cluster_upper_band',curves.upper.to_numpy(),upper)
                covered=bool(np.all((truth>=lower)&(truth<=upper)))
                assert covered==boolean(row.joint_coverage)
                true_first=next((j for j in range(1,7) if truth[j]>=.1),-1)
                candidates=[j for j in range(1,7) if upper[j]>=.1 and all(lower[k]<.1 for k in range(j))]
                possible_unreached=bool(all(v<.1 for v in lower))
                contains=(true_first in candidates) if true_first>=0 else possible_unreached
                assert contains==boolean(row.threshold_contains_truth)
                counts['coverage_and_threshold_checks']+=2
                if name!='metered_Z':
                    extra=float(np.sqrt(np.mean((y-eta)**2)))
                    close('extra_reference_error',np.asarray(row.extra_reference_error_rmse),np.asarray(extra))
                else:
                    assert pd.isna(row.extra_reference_error_rmse)
                branch_mu[name]=mu;branch_scores[name]=scores
                independent.append(dict(seed=seed,scenario=scenario,outcome=name,rmse=rmse,plugin_rmse=plugin_rmse,
                    joint_coverage=covered,threshold_contains_truth=contains))
            # Same-function subtraction from Y and auxiliary mu preserves contrasts.
            before=branch_scores['predicted_eta']
            shifted_mu=branch_mu['predicted_eta']-bhat[:,None]
            shifted=shifted_mu.copy()
            for arm in range(7):
                selected=(idx==arm)
                shifted[selected,arm]+=(yhat[selected]-bhat[selected]-shifted_mu[selected,arm])/np.maximum(branch_pi[selected,arm],.01)
            close('synchronous_auxiliary_shift',shifted-shifted[:,[0]],before-before[:,[0]])
    assert len(metrics)==240 and len(independent)==180
    assert len(curve_rows)==180*7
    computed=pd.DataFrame(independent)
    summary=pd.read_csv(out/'summary.csv')
    for (scenario,name),values in computed.groupby(['scenario','outcome']):
        row=summary[(summary.scenario==scenario)&(summary.outcome==name)].iloc[0]
        close('summary_mean_curve_rmse',np.asarray(row.mean_curve_rmse),np.asarray(values.rmse.mean()))
        close('summary_mean_plugin_rmse',np.asarray(row.mean_plugin_rmse),np.asarray(values.plugin_rmse.mean()))
        close('summary_joint_coverage',np.asarray(row.joint_coverage),np.asarray(values.joint_coverage.mean()))
        close('summary_threshold_containment',np.asarray(row.threshold_containment),np.asarray(values.threshold_contains_truth.mean()))
        assert row.coverage_denominator==20 and row.causal_outputs==20
    result=dict(passed=True,independent_seed_blocks=20,paired_scenarios=4,outcome_rows=240,
        causal_outcome_rows=180,unsupported_rows=counts['unsupported_outcomes_checked'],
        checked_numeric_items=int(sum(counts.values())),checks_by_type=dict(counts),maximum_difference_by_type=dict(maximum),
        frozen_hashes_checked=len(freeze['hashes']),independent_cluster_bands_checked=180,
        note='Nuisance regressions are separately refit for each outcome; their finite-sample contrasts need not be identical. This audit verifies common mathematical targets, not universal accuracy gains.',
        audit_sha256=digest(__file__))
    computed.to_csv(out/'audit_independent_metrics.csv',index=False)
    audit_path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
