"""Freeze this single-smoother comparison before generating any study samples."""
from pathlib import Path
import hashlib,json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def save(path,value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)

def hashes():
    files=list((ROOT/'B1算法').rglob('*.py'))+list((ROOT/'B1算法').rglob('*.json'))
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}

if __name__=='__main__':
    protocol=dict(
        question='Only replace final smoothing of the same Kennedy DR pseudo-outcomes; does a global cubic smoothing spline improve the continuous population contrast?',
        stages=['factor-role audit','new development comparison','lock selected policies and source','one fixed new confirmation','independent verification'],
        parts_unchanged=[1,2,4,5,6],
        factor_audit_application=dict(adjustment=['deadline_slack','demand_urgency'],
            diagnostic_only=['negative_control'],post_treatment_not_adjusted=['participation','response'],
            shared_for_all_methods=True,scope='declared simulated SCM only; not proof of a field adjustment set'),
        dose_domain=[0.,2.4],reference=.3,grid=[round(.3+.06*j,10) for j in range(31)],
        threshold_mesh=[round(.3+.01*j,10) for j in range(181)],target_seconds=120.,
        outcome='population event-equal cumulative response seconds including zeros and full durations',
        development=dict(seeds=[90341001,90341002,90341003],users=240,events_per_user=2,
            mechanisms=['randomized_saturation','observed_saturation','nonmonotone','zero_effect']),
        confirmation=dict(seeds=list(range(90342001,90342009)),users=240,events_per_user=2,
            mechanisms=['randomized_saturation','observed_saturation','nonmonotone','zero_effect','sigmoidal','assignment_mixture']),
        seed_unit='Only seed blocks are independent replications; mechanisms within a seed share exogenous conditions.',
        baseline='formal fit_continuous_effects Kennedy_DR_local_linear, fixed production bandwidth rule',
        nuisance=dict(outcome='unchanged poly2(X) x six-knot cubic dose spline Ridge alpha=.1',
            gps='unchanged logit-normal Ridge with inner user folds, randomized density known only for uniform design',
            folds=3,n_boot=99,shared_cached_pseudo_outcomes=True),
        candidate=dict(method='SciPy 1.15.3 make_smoothing_spline',x_scale='u=dose/2.4',y_scale='pseudo_outcome/1800',
            objective='mean squared residual loss + lambda_mean * integral (g_second_derivative(u))^2 du',
            scipy_lambda='n_events * lambda_mean; equal event weights',
            lambda_mean_grid=[1e-6,1e-5,1e-4,1e-3,1e-2],
            clip_outcome_or_pseudo_outcome_or_curve=False,monotone_constraint=False,
            source='Bonvini-Kennedy Algorithm 1 two-stage regression + established cubic smoothing spline; not a full HOIF replication'),
        tuning_control=dict(method='same local-linear smoother, tuned bandwidth multiplier',grid=[.8,1.,1.25,1.6,2.]),
        support='All methods must pass original local support at requested points; tuned LL must additionally pass its own bandwidth support; no extrapolation beyond observed dose extremes for spline.',
        selection='One global lambda and one global LL multiplier; minimum development mean per-curve contrast RMSE among policies with no loss of full-curve outputs relative to fixed LL. Ties choose stronger smoothing. Simulation truth used only in development/evaluation, never in nuisance fits.',
        primary='mean of per-cohort contrast RMSE on 31 declared amounts; same reference .3, all designed cohorts recorded; missing curves cannot improve a mean by exclusion',
        confirmation_adoption=dict(relative_rmse_gain_vs_each_baseline_at_least=.05,
            paired_seed_blocks_improved_vs_each_baseline_at_least=6,
            full_curve_outputs_at_least_each_baseline=True,
            zero_effect_false_target_reached_no_more_than_each_baseline=True,
            handling='If any designated cohort fails, record it and do not declare overall gain using a successful-only subset.',
            downstream='Derivative/target scoring only, without changing parts5/6. Improved mean curve alone does not authorize a claim of whole-chain improvement.'),
        diagnostics=['mean level MAE','max absolute contrast error','analytic derivative RMSE of each fitted curve',
            'target reached confusion and first-crossing amount error','zero-effect estimated contrast magnitude',
            'per mechanism results and per seed paired differences','fit/query time'],
        final_use='Generate all eight predeclared confirmation blocks once after policy freeze, even if development fails. No post-confirmation tuning, replacement seeds, extra confirmations or default changes.',
        physical_or_field_validation=False,group_model_fitting=False,inference_band_fitting=False,
        limitations='New seeds and two held-out mechanism variants remain a related logistic/Beta simulator family, not an independent physical simulator or field evidence.')
    save(HERE/'protocol.json',protocol)
    save(HERE/'formal_before.json',hashes())
    print(json.dumps(dict(protocol='frozen before data generation',formal_files=len(hashes()))))
