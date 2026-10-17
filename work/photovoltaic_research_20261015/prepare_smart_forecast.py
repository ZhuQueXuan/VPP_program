"""QA and freeze a new August holdout before clear-sky persistence errors."""
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
def numeric(x):
    try:
        v=float(x);return v if math.isfinite(v) else None
    except (TypeError,ValueError):return None
def main():
    out=BASE/'runs/PREP_SMART_FORECAST_01';out.mkdir(parents=True,exist_ok=False)
    old=json.loads((BASE/'forecast_protocol_v1.json').read_text(encoding='utf-8'))
    tail=[s for s in old['sources'] if Path(s['path']).name=='system_1239__date_2019_07_31.csv'];assert len(tail)==1
    src=list(tail);receipt=json.loads((BASE/'downloads/PVDAQ_SMART_AUGUST_01/receipt.json').read_text())
    for e in receipt['files']:
        file=BASE/'downloads/PVDAQ_SMART_AUGUST_01'/e['name'];assert e['status']=='downloaded' and sha(file)==e['sha256']
        assert hashlib.md5(file.read_bytes()).hexdigest()==e['etag'].strip('"')
        src.append({'path':file.relative_to(ROOT).as_posix(),'sha256':sha(file),'url':e['url']})
    assert len(src)==32
    metadata_file=BASE/'downloads/PVDAQ_CANDIDATE_FILES_01/system_1239_metadata.json'
    meta=json.loads(metadata_file.read_text());index_file=BASE/'downloads/PVDAQ_INDEX_02/systems.csv'
    with index_file.open(encoding='utf-8-sig',newline='') as f:
        index=[r for r in csv.DictReader(f) if r['system_id']=='1239']
    assert len(index)==1;tz=index[0]['timezone_or_utc_offset'];assert tz=='America/New_York'
    site=meta['Site'];mount=meta['Mount']['Mount 0']
    config={'latitude':float(site['latitude']),'longitude':float(site['longitude']),'altitude_m':float(site['elevation']),
            'timezone':tz,'tilt_deg':float(mount['tilt']),'azimuth_deg':float(mount['azimuth']),
            'solarposition_method':'nrel_numpy','standard_temperature_C':12.0,'delta_t_seconds':67.0,
            'clear_sky_model':'ineichen','linke_turbidity':'pvlib packaged climatology, daily interpolation',
            'transposition':'isotropic','albedo':0.25,'minimum_current_clear_poa_W_m2':20.0}
    raw=[];grid={};seen=set()
    for s in src:
        file=ROOT/s['path'];assert sha(file)==s['sha256']
        with file.open(newline='',encoding='utf-8') as f:
            for line,r in enumerate(csv.DictReader(f),2):
                t=datetime.fromisoformat(r['measured_on']);assert r['system_id']=='1239' and t not in seen;seen.add(t)
                p=numeric(r['ac_power_metered_kw__3015']);exact=t.minute%15==0 and t.second==0 and t.microsecond==0
                rec={'source':s['path'],'line':line,'time':str(t),'power_W':p,'exact_grid':exact,'negative_power':p is not None and p<0}
                raw.append(rec)
                if exact:grid[t]=rec
    raw.sort(key=lambda r:r['time']);step=timedelta(minutes=15);t=datetime(2019,8,1);end=datetime(2019,9,1);samples=[]
    while t<end:
        flags=[];v=[];pair_ok=True
        for name,at in (('target',t),('origin',t-step),('lag',t-2*step)):
            r=grid.get(at)
            if r is None:flags.append('missing_'+name)
            elif r['power_W'] is None:flags.append('nonfinite_'+name)
            v.append(r['power_W'] if r else None)
            if name!='lag' and (r is None or r['power_W'] is None):pair_ok=False
        samples.append({'target_time':str(t),'origin_time':str(t-step),'lag_time':str(t-2*step),
                        'target_W':v[0],'origin_W':v[1],'lag_W':v[2],'pair_available':pair_ok,
                        'status':';'.join(flags) if flags else 'admitted'})
        t+=step
    aug=[r for r in raw if r['time'].startswith('2019-08')];finite=[r['power_W'] for r in aug if r['power_W'] is not None]
    summary={'August_raw_rows':len(aug),'August_exact_grid_rows':sum(r['exact_grid'] for r in aug),
             'August_off_grid_rows':sum(not r['exact_grid'] for r in aug),'August_finite_raw_power':len(finite),
             'August_negative_raw_power':sum(r['negative_power'] for r in aug),'min_power_W':min(finite),'max_power_W':max(finite),
             'expected_target_labels':len(samples),'main_common_samples':sum(r['status']=='admitted' for r in samples),
             'pair_available_samples':sum(r['pair_available'] for r in samples),
             'all_status':{s:sum(r['status']==s for r in samples) for s in sorted({r['status'] for r in samples})},
             'source_files':32,'August_ETag_MD5_checked':31,
             'scope':'Main comparison requires same target/current/lag sample as frozen AR2; pair_available separately reports persistence/clear-sky intrinsic sample availability.'}
    table(out/'all_raw_power_rows.csv',raw);table(out/'all_target_samples.csv',samples);dump(out/'summary.json',summary);dump(out/'source_manifest.json',src)
    environment=BASE/'smart_forecast_environment.json';env=json.loads(environment.read_text())
    arfile=BASE/'runs/BL_PV_FORECAST_02/coefficients.json'
    configfile=BASE/'smart_geometry_config_v1.json'
    with configfile.open('x',encoding='utf-8') as f:json.dump(config,f,indent=2);f.write('\n')
    protocol={
        'id':'PVDAQ_SMART_PERSISTENCE_V1','decision':'D054','date':'2026-10-15','frozen_utc':datetime.now(timezone.utc).isoformat(),
        'object':'PVDAQ1239 next15-minute published AC label, new full August2019 holdout. No new power fitting.',
        'sources':src,'metadata':{'path':metadata_file.relative_to(ROOT).as_posix(),'sha256':sha(metadata_file)},
        'index':{'path':index_file.relative_to(ROOT).as_posix(),'sha256':sha(index_file)},
        'sample_file':(out/'all_target_samples.csv').relative_to(ROOT).as_posix(),'sample_sha256':sha(out/'all_target_samples.csv'),
        'qa_file':(out/'summary.json').relative_to(ROOT).as_posix(),'qa_sha256':sha(out/'summary.json'),
        'environment_file':environment.relative_to(ROOT).as_posix(),'environment_sha256':sha(environment),'versions':env['versions'],
        'geometry_config':config,'geometry_config_sha256':sha(configfile),
        'ar2_file':arfile.relative_to(ROOT).as_posix(),'ar2_sha256':sha(arfile),
        'ar2_origin':'D053 June-only coefficients preserved, not re-fit on July or August; prior July failure remains.',
        'prior_exposure':'Method chosen after July AR2 tradeoff. August preselected before value inspection; QA/ranges seen, no August forecast errors. Same-site retrospective temporal holdout, not blind online or independent site confirmation.',
        'input':'Current complete P(t), metadata/time; AR2 secondary additionally P(t-15). Future clear-sky values use only known astronomy/packaged historical climatology, never future measured G/T or future power.',
        'time_assumption':'Published naive clock labels interpreted with source index America/New_York. Point-label solar geometry; averaging start/center/end and delivery unknown. Conditional offline next-label forecast, no verified physical15-minute lead time.',
        'models':{
            'B_P':'P(t), unchanged persistence baseline.',
            'M_SP':'If clear_POA(t)>=20 W/m2, P(t)*clear_POA(t+15)/clear_POA(t); otherwise exactly P(t). Threshold engineering denominator guard, fixed before errors, not a learned quality/night classifier.',
            'F_AR2':'Frozen June b0+b1P(t)+b2P(t-15) in kW, secondary comparison, no retuning.'},
        'geometry_limit':'Ineichen climatology and isotropic POA with source geometry are clear-sky power-shape proxies, no temp/inverter/loss model. Albedo.25, temp12C and delta_t67 are fixed representative/library defaults, not local measurements. Metadata installation not independently verified for2019. Not exact NREL REST2+power-chain reproduction.',
        'sample_rule':'All exact15min target/current/lag power finite, common cohort for all three; raw missing/offgrid/negative values retained, no interpolation/zero or nameplate clipping. Main extra lag condition is for fair frozen-AR2 comparison, not an intrinsic smart-persistence requirement.',
        'metrics':{'primary':['MAE_W','RMSE_W'],'bins':['all','origin_power_ge1000W','origin_power_lt1000W','target_change_ge2016W'],
                   'secondary':['bias_W','nearest_rank_p95_W','max_abs_error_and_time','daily_all31','negative_predictions','branch_counts','denominator/ratio_range'],
                   'target_change':'Retrospective scoring only, never sample selection/predictor','normalization':'20160 W DC diagnostic, not accuracy or AC capacity/103.'},
        'criterion':'M_SP must improve BOTH all-common-cohort MAE and RMSE versus B_P to count as positive candidate evidence; report frozen AR2, every day/bin/worst even if overall improves. No post-hoc threshold/objective change or selection.',
        'failure':'All geometry and predictions finite/nonnegative clear POA; any failed geometry stops rather than drops rows. Negative observed/predicted AC retained. No cap or threshold tuning after August scores.',
        'verification':'Deterministic replay, independent raw sampling/ratio branch/metrics and isotropic component arithmetic. Same-library solarposition crosscheck is not independent physical sensor/geometry validation.',
        'stop':'One fixed evaluation plus necessary replay/verification. Candidate success/failure then limited conclusion. No automatic next model/month sweep if it fails; do not chase dual metric improvements indefinitely.',
        'method_sources':['https://docs.nlr.gov/docs/fy15osti/63876.pdf','https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.clearsky.ineichen.html'],
        'not_validated':['real-time measurement availability','independent site/season','true future weather','maximum available AC power','dispatchable capacity','103 official accuracy']}
    path=BASE/'smart_forecast_protocol_v1.json'
    with path.open('x',encoding='utf-8') as f:json.dump(protocol,f,ensure_ascii=False,indent=2);f.write('\n')
    freeze={'protocol_sha256':sha(path),'prepare_script_sha256':sha(Path(__file__)),'state':'frozen_before_August_forecast_errors'}
    with (BASE/'smart_forecast_freeze_receipt_v1.json').open('x',encoding='utf-8') as f:json.dump(freeze,f,indent=2)
    dump(out/'receipt.json',{'freeze':freeze,'outputs':{p.name:sha(p) for p in sorted(out.iterdir())}})
    print(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(freeze))
if __name__=='__main__':main()
