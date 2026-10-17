"""Preregister one bounded Sep2019-May2020 confirmation before new values."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    package=ROOT/'resource_research_results/distributed_photovoltaic'
    old=json.loads((BASE/'smart_forecast_protocol_v1.json').read_text(encoding='utf-8'))
    refs={name:{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)} for name,p in {
        'kernel':package/'code/clear_sky_forecast.py',
        'geometry':package/'parameters/pvdaq1239_smart_geometry_v1.json',
        'environment':BASE/'smart_forecast_environment.json',
        'ar2':BASE/'runs/BL_PV_FORECAST_02/coefficients.json',
        'previous_protocol':BASE/'smart_forecast_protocol_v1.json',
        'previous_release':package/'results/release_validation_v1_1.json'}.items()}
    protocol={'id':'PV_CROSSSEASON_CONFIRM_V1','decision':'D055','date':'2026-10-16',
        'frozen_utc':datetime.now(timezone.utc).isoformat(),
        'purpose':'Complete PV basic research acceptance by testing existing frozen next-label forecast across a prespecified continuous autumn/winter/spring period; no method search.',
        'object':'Same PVDAQ1239 roof published AC power, conditional offline15-minute next-label forecast; not independent plant or operational timing validation.',
        'period':{'start':'2019-09-01 00:00:00','end_exclusive':'2020-06-01 00:00:00',
                  'months':['2019-09','2019-10','2019-11','2019-12','2020-01','2020-02','2020-03','2020-04','2020-05'],
                  'seasons':{'autumn':['2019-09','2019-10','2019-11'],'winter':['2019-12','2020-01','2020-02'],'spring':['2020-03','2020-04','2020-05']},
                  'boundary_history':'2019-08-31 already downloaded, raw preserved'},
        'frozen_artifacts':refs,'geometry_config':old['geometry_config'],
        'models':{'B_P':'P(t)','M_SP':'Existing final kernel exactly unchanged: clear_POA(t)>=20 then P(t)*clear_POA(t+15)/clear_POA(t), else P(t)',
                  'F_AR2':'Original June-only coefficients exactly unchanged; diagnostic comparator, no refit.'},
        'input':'Only complete current P(t), time/metadata; AR2 also P(t-15). No future observed G/T or target power used for forecasts, no retraining, calibration, clipping or day/season switching.',
        'source_plan':'List and acquire every available original daily CSV for all9 full calendar months, not selected by model scores. Missing source days remain missing targets, never replaced by zero. Cross-format clock checks on five prespecified dates.',
        'clock_check_dates':['2019-10-15','2019-11-03','2020-01-15','2020-03-08','2020-04-15'],
        'sample_rule':'Enumerate all15-minute local target labels in period. Main needs unique exact original target/current/lag labels, finite AC at all3, and timezone-resolvable consecutive900second UTC intervals. Report target/current-only pair availability separately. All raw/offgrid/missing/nonfinite/duplicate/negative rows kept in audit.',
        'DST_policy':'Use source America/New_York. Ambiguous or nonexistent local labels receive explicit unresolved flags and are excluded before scores, never guessed by row order or power. Duplicate local labels exclude every ambiguous source row from main. Clock check Parquet is diagnostic only; do not use it to choose favorable values or silently rewrite CSV.',
        'time_limit':'Naive published labels interpreted as point times; averaging windows/delivery and2019-2020 hardware configuration unverified. Cross-format offsets are publication-format consistency, not independent physical timing calibration.',
        'source_binding':'After acquisition, create immutable source manifest, complete sample table, QA and admission receipt with hashes BEFORE any prediction error. Protocol itself frozen before new source values.',
        'metrics':{'primary':['MAE_W','RMSE_W'],'mandatory':['pooled_all9','each3monthseason','every9month','everyavailabledate','worst/p95/bias','coverage_and_exclusion','origin_ge1000W/lt1000W','retrospective_target_change_ge2016W','negative_outputs','scaled/fallback_counts'],
                   'normalization':'20160W DC diagnostic only, not official accuracy or verified AC cap.'},
        'interpretation':{'crossseason_positive':'Both pooled MAE/RMSE improve versus B_P AND both improve within each of autumn,winter,spring; each season must have observed evaluable samples. Every month/daily exception remains reported. No absolute business-accuracy target inferred.',
                          'otherwise':'Restrict claims to observed successful ranges or report failure; do not tune20guard/geometry/coefficient/cohort/objective after errors. Stage work still closes with an evidence-based limitation decision.',
                          'coverage':'No arbitrary coverage threshold implies generalization to unobserved labels; quantify all expected labels and valid sample fraction permonth/season.'},
        'reproducibility':'One complete evaluation, deterministic replay, independent original CSV/clock/samples and lower-level geometry/branch/metrics verification, final kernel fingerprints unchanged.',
        'stage_acceptance':'Recheck six D046 basic-package items, add this bounded confirmation and clear capability/unknown table, retain final compute code/parameters/examples/aggregate results only. Stop at this larger node; no automatic new resource/integration/advanced model or handoff/teacher report.',
        'not_validated':['independent site/climate','physical online15min lead time','true future weather','maximum/controllable AC capacity','dispatch delay','103 official90percent']}
    path=BASE/'crossseason_protocol_v1.json'
    with path.open('x',encoding='utf-8') as f:json.dump(protocol,f,ensure_ascii=False,indent=2);f.write('\n')
    receipt={'protocol_sha256':sha(path),'freeze_script_sha256':sha(Path(__file__)),'state':'frozen_before_new_crossseason_values_and_errors','client_date':'2026-10-16'}
    with (BASE/'crossseason_freeze_receipt_v1.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2)
    print(json.dumps(receipt))
if __name__=='__main__':main()
