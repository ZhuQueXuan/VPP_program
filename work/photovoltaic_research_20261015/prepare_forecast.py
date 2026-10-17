"""Source QA, exact-label forecast samples and protocol freeze before fitting."""
from pathlib import Path
from datetime import datetime,timedelta,timezone
import csv,hashlib,json,math
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def table(p,rows):
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def num(s):
    try:
        n=float(s);return n if math.isfinite(n) else None
    except (TypeError,ValueError):return None
def main():
    out=BASE/'runs/PREP_PV_FORECAST_01';out.mkdir(parents=True,exist_ok=False)
    old=json.loads((BASE/'reconstruction_protocol_v1.json').read_text(encoding='utf-8'))
    src=list(old['sources'])
    receipt=json.loads((BASE/'downloads/PVDAQ_FORECAST_JULY_01/receipt.json').read_text())
    for entry in receipt['files']:
        assert entry['status']=='downloaded'
        file=BASE/'downloads/PVDAQ_FORECAST_JULY_01'/entry['name']
        src.append({'path':file.relative_to(ROOT).as_posix(),'sha256':entry['sha256'],'url':entry['url']})
        assert hashlib.md5(file.read_bytes()).hexdigest()==entry['etag'].strip('"')
    assert len(src)==61
    raw=[];grid={};seen=set();monthly={}
    for s in src:
        file=ROOT/s['path'];assert sha(file)==s['sha256']
        with file.open(encoding='utf-8',newline='') as f:
            rows=list(csv.DictReader(f))
        assert len(rows)>0
        for line,r in enumerate(rows,2):
            t=datetime.fromisoformat(r['measured_on']);assert r['system_id']=='1239' and t not in seen
            assert datetime(2019,6,1)<=t<datetime(2019,8,1);seen.add(t)
            p=num(r['ac_power_metered_kw__3015']);isgrid=t.minute%15==0 and t.second==0 and t.microsecond==0
            rec={'source':s['path'],'line':line,'time':t.isoformat(sep=' '),'power_W':p,'exact_grid':isgrid,
                 'negative_power':p is not None and p<0,'power_finite':p is not None}
            raw.append(rec)
            if isgrid:grid[t]=rec
    raw.sort(key=lambda r:r['time'])
    start=datetime(2019,6,1);cutoff=datetime(2019,7,1);end=datetime(2019,8,1)
    samples=[];step=timedelta(minutes=15);t=start
    while t<end:
        origin=t-step;lag=t-2*step;flags=[];values=[];records=[]
        for label,tm in (('target',t),('origin',origin),('lag',lag)):
            r=grid.get(tm);records.append(r)
            if r is None:flags.append('missing_'+label)
            elif r['power_W'] is None:flags.append('nonfinite_'+label)
            values.append(r['power_W'] if r else None)
        samples.append({'target_time':str(t),'origin_time':str(origin),'lag_time':str(lag),
                        'split':'fit' if t<cutoff else 'evaluation','target_W':values[0],
                        'origin_W':values[1],'lag_W':values[2],'status':';'.join(flags) if flags else 'admitted'})
        t+=step
    for month in ('2019-06','2019-07'):
        rr=[r for r in raw if r['time'].startswith(month)];ss=[s for s in samples if s['target_time'].startswith(month)]
        pp=[r['power_W'] for r in rr if r['power_finite']]
        monthly[month]={'raw_rows':len(rr),'exact_grid_rows':sum(r['exact_grid'] for r in rr),
                        'off_grid_rows':sum(not r['exact_grid'] for r in rr),'power_finite_raw':len(pp),
                        'negative_raw_power':sum(r['negative_power'] for r in rr),'power_min_W':min(pp),'power_max_W':max(pp),
                        'expected_target_labels':len(ss),'admitted_samples':sum(s['status']=='admitted' for s in ss),
                        'sample_status':{k:sum(s['status']==k for s in ss) for k in sorted({s['status'] for s in ss})}}
    table(out/'all_raw_power_rows.csv',raw);table(out/'all_target_samples.csv',samples)
    dump(out/'source_manifest.json',src)
    summary={'monthly':monthly,'source_files':61,'July_ETag_MD5_checked':31,
             'sample_rule':'exact target/origin/lag at15min spacing, finite power only, all negative values retained; no G/T requirement or interpolation',
             'source_unit':'Published metric3015 W, same sensor dictionary as D050; no name-based kW conversion.',
             'latency_limit':'Row at origin assumed fully available; averaging boundaries and delivery delay unverified. Offline next-label forecast only.'}
    dump(out/'summary.json',summary)
    protocol={
        'id':'PVDAQ_15MIN_FORECAST_V1','decision':'D053','date':'2026-10-15','frozen_utc':datetime.now(timezone.utc).isoformat(),
        'object':'PVDAQ roof system1239 published AC power W; DC nameplate20.16kW; June2019 fit, next full July2019 evaluation.',
        'question':'Can a fixed-order linear AR2 improve next published15minute-label power forecasts over persistence on a new month?',
        'sources':src,'sample_file':(out/'all_target_samples.csv').relative_to(ROOT).as_posix(),'sample_sha256':sha(out/'all_target_samples.csv'),
        'source_qa_file':(out/'summary.json').relative_to(ROOT).as_posix(),'source_qa_sha256':sha(out/'summary.json'),
        'input_time':'Forecast origin t; only P(t) and P(t-15min). Target is P(t+15min). Never future G/T, target power, control status or heldout-derived parameters.',
        'availability':'Conditional on complete row t being available at forecast issue; upload/average boundaries not verified, so no claim of operational15-minute lead time or physical delay.',
        'split':'By TARGET label: June1 00:00<=target<July1 fit; July1<=target<Aug1 evaluation. Boundary lag/origin may lie in June for first July targets. Rolling one-step actual past July observations allowed, no parameter update.',
        'prior_exposure':'June source and reconstruction scores already seen, June used for fitting. July was preselected as next complete month before inspecting its data. July QA/ranges seen before this freeze; no forecast errors computed. Same-site retrospective chronological holdout, not independent site or blind online trial.',
        'sample_rule':summary['sample_rule'],
        'models':{
            'B_P':'P_hat(t+15)=P(t), zero fitted parameters.',
            'B_T':'P_hat(t+15)=2P(t)-P(t-15), fixed linear trend with the same two past samples; zero fitted parameters.',
            'M_AR2':'In kW: P_hat(t+15)=b0+b1*P(t)+b2*P(t-15). Three coefficients ordinary least squares, June admitted samples only. Order2 fixed a priori, no hyperparameter selection or day/night switching.'},
        'numerics':'numpy.linalg.lstsq; rank must3, all coefficients/predictions finite; numerical failure stops, no silent prediction removal. kW scaling fixed, no learned normalization.',
        'output_limits':'Retain negative targets and predictions, no zero/nameplate/26kW clipping. No verified AC cap. Empirical statistical forecasts are not feasible dispatch commands.',
        'metrics':{'primary':['MAE_W','RMSE_W'],'groups':['all','origin_power_ge1000W','origin_power_lt1000W','absolute_target_change_ge2016W'],
                   'bins':'Fixed engineering reporting bins only; target-change bin uses future target for retrospective scoring only, never prediction inputs. Not official ramp-event labels or deployment gates.',
                   'secondary':['bias_W','nearest_rank_p95_W','max_abs_error_and_timestamp','daily MAE/RMSE','negative_predictions','coverage','skill1-error/error_persistence'],
                   'normalization':'MAE/RMSE divided20160W DC diagnostic only, not accuracy/103 or true AC rating.'},
        'criterion':'AR2 positive comparative evidence only if both evaluation all-sample MAE and RMSE lower than B_P. Also report trend baseline, all bins/days/failures; no universal or absolute operational threshold inferred.',
        'stop':'One fit/evaluation, deterministic replay and independent raw sample/fit/metric verification. No tuning order, features, split, clipping or coefficients after July scores. Publish only preserved validated calculation with exact outcome scope; failed candidate not promoted.',
        'method_sources':['https://arxiv.org/abs/1809.03574','https://docs.nlr.gov/docs/fy15osti/63876.pdf'],
        'method_scope':'AR family and persistence benchmarking have primary literature support; custom minimal AR(2) experiment, not precise reproduction of hourly ARMA, smart persistence or a full paper.',
        'not_validated':['online acquisition timing','clear-sky smart-persistence comparison','independent site or season transfer','future weather forecast','controllable reserve','103 official accuracy']}
    path=BASE/'forecast_protocol_v1.json'
    with path.open('x',encoding='utf-8') as f:json.dump(protocol,f,ensure_ascii=False,indent=2);f.write('\n')
    freeze={'protocol_sha256':sha(path),'prepare_script_sha256':sha(Path(__file__)),'state':'frozen_before_forecast_fit_or_errors'}
    with (BASE/'forecast_freeze_receipt_v1.json').open('x',encoding='utf-8') as f:json.dump(freeze,f,indent=2)
    dump(out/'receipt.json',{'freeze':freeze,'outputs':{f.name:sha(f) for f in sorted(out.iterdir())}})
    print(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(freeze))
if __name__=='__main__':main()
