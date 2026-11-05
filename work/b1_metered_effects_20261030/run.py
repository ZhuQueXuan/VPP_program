"""One frozen new-seed input-target comparison, without estimator tuning."""
from setup_study import *
import time
from datetime import datetime,timezone

def main():
    out=HERE/'results'
    if out.exists():raise RuntimeError('results exist; do not overwrite')
    checks=json.loads((HERE/'checks.json').read_text(encoding='utf-8'));assert checks['passed']
    protocol=json.loads((HERE/'protocol.json').read_text(encoding='utf-8'))
    files=[HERE/p for p in ('prototype.py','setup_study.py','run.py','check.py','protocol.json')]
    files+=list((ROOT/'B1算法/b1_algorithm/effects').glob('*.py'))
    files+=[ROOT/'B1算法/b1_algorithm/contracts.py',ROOT/'work/b1_mainline_20261029/causal/simulation.py']
    frozen={str(p.relative_to(ROOT)):sha(p) for p in files}
    out.mkdir();(out/'freeze.json').write_text(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),hashes=frozen),indent=2),encoding='utf-8')
    data_dir=ROOT/'data/B1_metered_effects_v1_20261030';data_dir.mkdir(exist_ok=False)
    rows=[];curves=[];started=time.perf_counter();direct_difference=0.;identity_difference=0.
    for seed in protocol['seeds']:
        for scenario in protocol['scenarios']:
            a,b,bhat,z,yhat,users,records=panel(seed,scenario,protocol['n_users'])
            known=a['assignment_pi'] if scenario=='rct_positive' else None
            cfg=EffectConfig(seed=seed,n_boot=999,return_audit=True)
            declared=assumptions(scenario)
            kwargs=dict(levels=LEVELS,assumptions=declared,known_pi=known,config=cfg)
            outcomes={'oracle_eta':a['y'],'predicted_eta':yhat,'metered_Z':z}
            identity=float(np.max(np.abs(((a['potential']-b[:,None])-(a['potential']-b[:,None])[:,[0]])-(a['potential']-a['potential'][:,[0]]))))
            identity_difference=max(identity_difference,identity)
            assert identity<1e-12
            observed,_groups,_pre=metered._metered_outcomes(records)
            assert np.max(np.abs(observed-z))<1e-12
            stem=f'{seed}_{scenario}'
            np.savez_compressed(data_dir/(stem+'.npz'),X=a['X'],d=a['d'],groups=a['groups'],
                actual_power=np.array([r['power_kw'] for r in records]),actual_starts=np.array([r['starts_min'] for r in records]),
                actual_ends=np.array([r['ends_min'] for r in records]),baseline=b,predicted_reference=bhat,
                eta=a['y'],z=z,predicted_eta=yhat,potential=a['potential'],truth_tau=a['truth_tau'])
            audits={}
            for name,y in outcomes.items():
                if name=='metered_Z':
                    result=metered.estimate_metered_effects(records,a['X'],a['d'],levels=LEVELS,assumptions=declared,
                        known_pi=known,effect_config=cfg)
                    direct=fit_effects(a['X'],a['d'],z,users,task=task_context('negative_normalized_actual_energy'),**kwargs)
                    assert result['status']==direct['status']
                    if result['status']=='causal':
                        delta=float(np.max(np.abs(np.asarray(result['causal_curve']['contrasts'])-direct['causal_curve']['contrasts'])))
                        direct_difference=max(delta,direct_difference);assert delta<1e-12
                else:result=fit_effects(a['X'],a['d'],y,users,task=task_context(),**kwargs)
                row=dict(seed=seed,scenario=scenario,outcome=name,status=result['status'],curve_rmse=None,
                    plugin_rmse=None,joint_coverage=None,threshold_contains_truth=None,
                    extra_reference_error_rmse=float(np.sqrt(np.mean((y-a['y'])**2))) if name!='metered_Z' else None)
                if result['status']=='causal':
                    point=np.asarray(result['causal_curve']['contrasts']);truth=a['truth_tau'];band=result['inference']
                    row.update(curve_rmse=float(np.sqrt(np.mean((point[1:]-truth[1:])**2))),
                        plugin_rmse=float(np.sqrt(np.mean((np.asarray(result['comparators']['plugin_shared_auxiliary']['contrasts'])[1:]-truth[1:])**2))),
                        joint_coverage=bool(np.all((truth>=np.asarray(band['lower']))&(truth<=np.asarray(band['upper'])))))
                    threshold=result['threshold_set'];row['threshold_contains_truth']=bool(
                        a['true_first'] in threshold['first_grid_crossing_indices'] if a['true_first']>=0 else threshold['not_reached_possible'])
                    for j,dose in enumerate(LEVELS):
                        curves.append(dict(seed=seed,scenario=scenario,outcome=name,level=dose,truth=truth[j],estimate=point[j],lower=band['lower'][j],upper=band['upper'][j]))
                    audit=result['audit']
                    for key in ('auxiliary_result_predictions','propensity_predictions','aipw_scores','fold_by_event','dose_index'):
                        audits[name+'_'+key]=np.asarray(audit[key])
                else:
                    assert result['status']=='unsupported',result['reasons']
                    row['reason_codes']=';'.join(r['code'] for r in result['reasons'])
                rows.append(row)
            np.savez_compressed(out/(stem+'_audit.npz'),**audits)
        pd.DataFrame(rows).to_csv(out/'metrics_partial.csv',index=False)
        print('completed',seed,'seconds',round(time.perf_counter()-started,1),flush=True)
    frame=pd.DataFrame(rows);frame.to_csv(out/'metrics.csv',index=False);pd.DataFrame(curves).to_csv(out/'curves.csv',index=False)
    summary=frame.groupby(['scenario','outcome']).agg(repetitions=('seed','size'),causal_outputs=('curve_rmse','count'),
        mean_curve_rmse=('curve_rmse','mean'),mean_plugin_rmse=('plugin_rmse','mean'),joint_coverage=('joint_coverage','mean'),
        coverage_denominator=('joint_coverage','count'),threshold_containment=('threshold_contains_truth','mean'),extra_reference_error_rmse=('extra_reference_error_rmse','mean')).reset_index()
    summary.to_csv(out/'summary.csv',index=False)
    assert all(sha(ROOT/p)==h for p,h in frozen.items())
    receipt=dict(complete=True,independent_seed_blocks=20,paired_scenarios=4,n_users=600,events_per_user=6,
        underlying_event_variants=20*4*600*6,outcome_method_rows=len(frame),
        wrapper_vs_direct_AIPW_max_difference=direct_difference,potential_contrast_identity_max_difference=identity_difference,
        protected_code_unchanged=True,elapsed_seconds=time.perf_counter()-started,
        scope='optional relative-energy input functionality and finite synthetic comparison; not a new causal estimator or universal precision gain')
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt,indent=2),flush=True)

if __name__=='__main__':main()
