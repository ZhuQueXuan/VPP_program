"""Record prospective comparison before development or confirmation draws."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)

def formal_hashes():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(list((ROOT/'B1算法').rglob('*.py'))+list((ROOT/'B1算法').rglob('*.json')))}

if __name__=='__main__':
    mechanisms=['randomized_saturation','observed_saturation','nonmonotone','zero_effect','sigmoidal','assignment_mixture']
    p=dict(scope='Only part3 final curve stability; retain previous spline lambda_mean=1e-4',
        hypothesis='User-held-out convex aggregation with shrinkage toward retained spline can improve cross-cohort bias/variance tradeoff; not a dedicated reference bias correction.',
        parts_unchanged=[1,2,4,5,6],adjustment=['deadline_slack','demand_urgency'],
        diagnostic_only=['negative_control'],outcome='all invited simulated events cumulative seconds, zero/full retained',
        domain=[0.,2.4],reference=.3,grid=[round(.3+.06*i,10) for i in range(31)],
        mesh=[round(.3+.01*i,10) for i in range(181)],target_seconds=120.,
        retained=dict(method='Kennedy DR final cubic smoothing spline',lambda_mean=1e-4),
        strong_smoothing_control=dict(method='same DR final local linear',bandwidth_multiplier=2.),
        extra_context='original fixed-bandwidth local linear, no retuning',
        candidate=dict(method='strict nested whole-user CV convex blend',outer_user_folds=3,inner_user_folds=3,
            raw_alpha='weight on retained spline, clipped analytic least-squares optimum in [0,1]',
            alpha_effective='1 - gamma * (1 - raw_alpha)',gamma_grid=[0.,.25,.5,.75,1.],
            cv_validation_amount_range=[.3,2.1],
            cv_risk='equal-event squared held-out pseudo-outcome level risk over observed validation amounts, not uniform-grid contrast risk',
            train_curve='For each held-out user fold V, nuisance cross-fitting and curve construction use only T; full-T nuisance models construct validation pseudo-outcomes.',
            fallback='Any failed density/local-support/amount support fold or <20 valid events or <15 valid users: record complete failure, alpha=1 retained spline for this cohort. No row dropping by outcome.',
            no_curve_clipping=True,no_monotonicity=True),
        fixed_blend_control=dict(formula='beta*S + (1-beta)*LL2',beta_grid=[0.,.25,.5,.75,1.],
            purpose='same five development choices; distinguish adaptive weights from generic averaging'),
        development=dict(seeds=list(range(90351001,90351005)),mechanisms=mechanisms,users=240,events_per_user=2),
        confirmation=dict(seeds=list(range(90352001,90352013)),
            mechanisms=mechanisms+['noisy_nonmonotone','two_peak'],users=240,events_per_user=2),
        independence='only seed blocks independent; mechanisms within seed are paired; final 12 blocks/96 curves, not 96 independent repeats',
        common_final_fit='Exactly one formal full-data Kennedy DR fit per cohort; same cached full-data xi/GPS/folds in all four final curves.',
        selection='Choose one global gamma and one beta on new development mean per-curve contrast RMSE; require complete common outputs. Ties prefer gamma smaller and beta larger. No identity/seed/mechanism rules.',
        primary='mean per-curve contrast RMSE on 31 uniform evaluation amounts relative to .3',
        adoption=dict(gain_vs_retained_at_least=.05,gain_vs_tuned_constant_blend_at_least=.05,
            seed_wins_vs_retained_at_least=9,seed_wins_vs_fixed_blend_at_least=8,
            all_96_designated_curves_output=True,
            zero_effect_false_reached_no_more_than_both=True),
        secondary=['per mechanism errors','per seed differences/worst regression','level MAE and reference error',
            'raw/effective weight distributions','fallback count','diagnostic derivative and target crossing scores'],
        final_rule='Freeze after development, then generate all 12 fixed confirmation blocks once including if gamma=0; no later gamma/beta changes or replacement draws.',
        diagnosis_use='Previous two bad blocks and all other old blocks read only for diagnosis/hypothesis, never used to select alpha/gamma/beta. Their confirmation remains consumed.',
        limitation='Related logistic/Beta simulation family with two new variants, not field compensation or independent physical validation; no new inference procedure.')
    save(HERE/'protocol.json',p)
    save(HERE/'formal_before.json',formal_hashes())
    old=HERE.parent/'b1_curve_spline_pilot_20261103'
    old_hashes={str(f.relative_to(old)):hashlib.sha256(f.read_bytes()).hexdigest() for f in old.rglob('*') if f.is_file() and '__pycache__' not in f.parts}
    save(HERE/'retained_before.json',old_hashes)
    print(json.dumps(dict(protocol_recorded=True,formal_files=len(formal_hashes()),retained_artifacts=len(old_hashes))))
