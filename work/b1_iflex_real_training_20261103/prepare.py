"""Freeze the real measured-outcome comparison before reading outcomes."""
from pathlib import Path
import csv,hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
DATA=HERE.parent/'b1_real_response_data_20261103'

def save(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

if __name__=='__main__':
    s=json.loads((DATA/'real_data_protocol.json').read_text(encoding='utf-8'))
    p=dict(scope='Part3 real household auxiliary outcome modeling at observed iFlex P paths only',
        data='https://zenodo.org/records/8248802',license='CC-BY-4.0',
        prepared_data_sha256=sha(DATA/'prepared_P_events.csv'),data_protocol_sha256=sha(DATA/'real_data_protocol.json'),
        counts=dict(train=9581,validation=2213,test=2419),dates=dict(train=20,validation=5,test=5),
        dates_assignment=s['splits_by_whole_date'],assignment_grain='group-date repeated household panel',
        target='actual_peak_2h_kwh: measured original Hour17+18',
        feature_sets=dict(base=['pre24_kwh','pre168_kwh','pre24_temperature','group x region','day of week'],
            peak_addition='one feature: mean_peak_history_kwh over complete paired Hour17/18 days inside the preceding168h, both measurements completed by notice'),
        feature_availability='Use only completed history before notification and known calendar/group/offer. Meter database delivery lag is not recorded.',
        forbidden=['future or current measured load/temp','ID as a regressor','realized reward','counterfactual labels','synthetic prices'],
        observed_quote_levels=[2,5,10,15],predictions_at_actual_assigned_quote_only=True,
        exposure='observed full P price path encoded by assigned nominal level; other22 slots identical',
        methods=dict(history_ridge='same covariates, no quote; history-only baseline',
            linear_ridge='same covariates + numeric quote and interactions',
            spline_ridge='adapt retained DR auxiliary result model structure: same poly2 covariates, 6 fixed cubic amount knots, interactions and Ridge; not full DR',
            price_hgb='HistGradientBoostingRegressor on EXACT same spline-expanded feature design as spline_ridge',
            history_hgb='same HGB on history-only covariates, price-feature ablation'),
        ridge_alpha_grid=[.1,1.,10.,100.],hgb_grid=[dict(leaves=l,l2=a) for l in (7,15) for a in (1.,10.)],
        hgb_fixed=dict(loss='squared_error',learning_rate=.05,max_iter=180,min_samples_leaf=40,
            early_stopping=False,max_bins=128,random_state=341),
        primary='Mean over dates of within-date household-event RMSE in kWh (not square root after averaging MSEs)',
        secondary=['pooled RMSE/MAE','group-date mean RMSE','per-observed-price calibration',
            'per-date errors and paired wins','price/no-price ablation on matched learner','bias by historical peak and group'],
        schedule=['fit base methods on20 dates; select each of 5 configurations families on5 validation dates; diagnose',
            'one predeclared candidate feature: preceding matched peak average; same method/budget validation',
            'lock before numeric test outcomes read; refit all selected configurations on25 train+validation dates; evaluate once on5 test dates'],
        tuning='Exactly four configurations per learner per feature set; ties use simpler/stronger-regularized model.',
        price_aware=['linear_ridge','spline_ridge','price_hgb'],
        baseline_selection='best base feature price-aware existing Ridge (linear or spline) on validation only',
        candidate_selection='best price-aware base on validation, or best price-aware added-peak model if latter improves validation date-equal RMSE by at least1%; choose without test',
        adoption='Real auxiliary model only: candidate must lower test date-equal RMSE by at least5% versus frozen existing Ridge reference, win at least4/5 dates, and cover all2419 events. Always keep original EV and other modules.',
        scientific_scope='Forecast measured kWh at known assigned prices; prediction scores cannot certify causal effects, dose interpolation, EV effective-duration performance, or unseen-user generalization.',
        split_timing='Already frozen at data preparation; no choice based on test scores. Test price5 absent;15 observed on one date.',
        no_test_feedback=True)
    save(HERE/'protocol.json',p)
    files=list((ROOT/'B1算法').rglob('*.py'))+list((ROOT/'B1算法').rglob('*.json'))
    save(HERE/'formal_before.json',{str(f.relative_to(ROOT)):sha(f) for f in files})
    print(json.dumps(dict(protocol_frozen=True,formal_files=len(files),data_sha256=p['prepared_data_sha256'])))
