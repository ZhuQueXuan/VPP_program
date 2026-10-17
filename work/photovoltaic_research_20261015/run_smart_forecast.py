"""Frozen August clear-sky POA ratio forecast, no power parameter fitting."""
from pathlib import Path
import argparse,csv,hashlib,importlib.metadata as md,json,math,platform,sys
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
for d in ('work/teacher_storage_brief_20261014/plot_dependencies','work/python_packages/storage_ecm_20261015','work/python_packages/pvlib_smart_20261015'):
    sys.path.insert(0,str(ROOT/d))
import numpy as np
import pandas as pd
import pvlib
MODELS=('B_P','M_SP','F_AR2')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def table(p,rows):
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def score(rows,m):
    if not rows:return {'n':0}
    err=[r[m]-r['target_W'] for r in rows];ae=sorted(abs(e) for e in err);i=max(range(len(rows)),key=lambda i:abs(err[i]))
    mae=math.fsum(ae)/len(ae);rmse=math.sqrt(math.fsum(e*e for e in err)/len(err))
    return {'n':len(rows),'mae_W':mae,'rmse_W':rmse,'bias_W':math.fsum(err)/len(err),
            'p95_abs_W':ae[math.ceil(.95*len(ae))-1],'max_abs_W':ae[-1],
            'worst_target_time':rows[i]['target_time'],'worst_origin_time':rows[i]['origin_time'],
            'worst_target_W':rows[i]['target_W'],'worst_prediction_W':rows[i][m],
            'negative_predictions':sum(r[m]<0 for r in rows),
            'mae_div_DC_nameplate':mae/20160,'rmse_div_DC_nameplate':rmse/20160}
def execute(out):
    path=BASE/'smart_forecast_protocol_v1.json';p=json.loads(path.read_text(encoding='utf-8'))
    assert sha(path)==json.loads((BASE/'smart_forecast_freeze_receipt_v1.json').read_text())['protocol_sha256']
    for s in p['sources']+[p['metadata'],p['index']]:assert sha(ROOT/s['path'])==s['sha256']
    for file,key in (('sample_file','sample_sha256'),('qa_file','qa_sha256'),('environment_file','environment_sha256'),('ar2_file','ar2_sha256')):
        assert sha(ROOT/p[file])==p[key]
    assert sha(BASE/'smart_geometry_config_v1.json')==p['geometry_config_sha256']
    env=json.loads((ROOT/p['environment_file']).read_text());lib=Path(pvlib.__file__).parent
    assert all(md.version(name)==v for name,v in env['versions'].items())
    assert sha(lib/'data/LinkeTurbidities.h5')==env['climatology_sha256']
    assert all(sha(lib/f)==h for f,h in env['core_module_sha256'].items())
    dump(out/'protocol_snapshot.json',p)
    c=p['geometry_config'];times=pd.date_range('2019-07-31 23:45','2019-08-31 23:45',freq='15min').tz_localize(c['timezone'],ambiguous='raise',nonexistent='raise')
    loc=pvlib.location.Location(c['latitude'],c['longitude'],tz=c['timezone'],altitude=c['altitude_m'])
    sp=loc.get_solarposition(times,method=c['solarposition_method'],temperature=c['standard_temperature_C'],delta_t=c['delta_t_seconds'])
    tl=pvlib.clearsky.lookup_linke_turbidity(times,c['latitude'],c['longitude'],interp_turbidity=True)
    extra=pvlib.irradiance.get_extra_radiation(times,method='spencer')
    am=loc.get_airmass(solar_position=sp)
    cs=loc.get_clearsky(times,model=c['clear_sky_model'],solar_position=sp,linke_turbidity=tl,dni_extra=extra)
    poa=pvlib.irradiance.get_total_irradiance(c['tilt_deg'],c['azimuth_deg'],sp.apparent_zenith,sp.azimuth,
                                           cs.dni,cs.ghi,cs.dhi,albedo=c['albedo'],model=c['transposition'])
    assert np.isfinite(poa.poa_global).all() and poa.poa_global.ge(0).all()
    geometry=pd.DataFrame({'time':times.tz_localize(None).strftime('%Y-%m-%d %H:%M:%S'),
                          'utc_time':times.tz_convert('UTC').strftime('%Y-%m-%d %H:%M:%S'),
                          'apparent_zenith_deg':sp.apparent_zenith.to_numpy(),'zenith_deg':sp.zenith.to_numpy(),
                          'solar_azimuth_deg':sp.azimuth.to_numpy(),'linke_turbidity':tl.to_numpy(),
                          'dni_extra_W_m2':extra.to_numpy(),'airmass_absolute':am.airmass_absolute.to_numpy(),
                          'cs_ghi_W_m2':cs.ghi.to_numpy(),'cs_dni_W_m2':cs.dni.to_numpy(),'cs_dhi_W_m2':cs.dhi.to_numpy(),
                          'cs_poa_W_m2':poa.poa_global.to_numpy(),'poa_direct_W_m2':poa.poa_direct.to_numpy(),
                          'poa_sky_diffuse_W_m2':poa.poa_sky_diffuse.to_numpy(),'poa_ground_W_m2':poa.poa_ground_diffuse.to_numpy()})
    geometry.to_csv(out/'clear_sky_geometry.csv',index=False)
    csmap=dict(zip(geometry.time,geometry.cs_poa_W_m2))
    with (ROOT/p['sample_file']).open(newline='',encoding='utf-8') as f:rawsamples=list(csv.DictReader(f))
    b=json.loads((ROOT/p['ar2_file']).read_text());pred=[]
    for r in rawsamples:
        if r['status']!='admitted':continue
        vals={k:float(r[k]) for k in ('target_W','origin_W','lag_W')};now=csmap[r['origin_time']];future=csmap[r['target_time']]
        branch=now>=c['minimum_current_clear_poa_W_m2'];ratio=future/now if branch else 1.0
        row={**r,**vals,'clear_current_W_m2':float(now),'clear_target_W_m2':float(future),
             'smart_branch':'scaled' if branch else 'persistence_fallback','clear_ratio_applied':float(ratio),
             'B_P':vals['origin_W'],'M_SP':float(vals['origin_W']*ratio),
             'F_AR2':1000*(b['intercept_kW']+b['current_weight']*vals['origin_W']/1000+b['previous_weight']*vals['lag_W']/1000)}
        assert all(math.isfinite(row[m]) for m in MODELS);pred.append(row)
    table(out/'predictions.csv',pred)
    groups={'all':pred,'origin_ge1000W':[r for r in pred if r['origin_W']>=1000],
            'origin_lt1000W':[r for r in pred if r['origin_W']<1000],
            'target_change_ge2016W':[r for r in pred if abs(r['target_W']-r['origin_W'])>=2016]}
    metrics={k:{m:score(rows,m) for m in MODELS} for k,rows in groups.items()};dump(out/'metrics.json',metrics)
    daily=[];wins=[]
    for date in sorted({r['target_time'][:10] for r in pred}):
        rows=[r for r in pred if r['target_time'].startswith(date)];dd={m:score(rows,m) for m in MODELS}
        for m,mm in dd.items():daily.append({'date':date,'model':m,**mm})
        wins.append({'date':date,'n':len(rows),'MAE_improves':dd['M_SP']['mae_W']<dd['B_P']['mae_W'],
                     'RMSE_improves':dd['M_SP']['rmse_W']<dd['B_P']['rmse_W']})
    table(out/'daily_metrics.csv',daily)
    a=metrics['all'];summary={'object':p['object'],'samples':len(pred),'new_fitted_power_parameters':0,'all':a,
                             'origin_ge1000W':metrics['origin_ge1000W'],
                             'M_SP_skill_vs_B_P':{k:1-a['M_SP'][k]/a['B_P'][k] for k in ('mae_W','rmse_W')},
                             'positive_candidate_criterion':all(a['M_SP'][k]<a['B_P'][k] for k in ('mae_W','rmse_W')),
                             'scaled_samples':sum(r['smart_branch']=='scaled' for r in pred),
                             'fallback_samples':sum(r['smart_branch']=='persistence_fallback' for r in pred),
                             'ratio_min':min(r['clear_ratio_applied'] for r in pred),'ratio_max':max(r['clear_ratio_applied'] for r in pred),
                             'daily_comparison':wins,'not_validated':p['not_validated']}
    dump(out/'summary.json',summary)
    dump(out/'receipt.json',{'status':'completed','script_sha256':sha(Path(__file__)),'protocol_sha256':sha(path),
                           'python':platform.python_version(),'environment':env,
                           'outputs':{f.name:sha(f) for f in sorted(out.iterdir())}})
    print(json.dumps({k:v for k,v in summary.items() if k!='daily_comparison'},ensure_ascii=False,indent=2))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();assert Path(a.run_id).name==a.run_id
    out=BASE/'runs'/a.run_id;out.mkdir(parents=True,exist_ok=False)
    try:execute(out)
    except Exception as e:dump(out/'failure.json',{'error':repr(e)});raise
if __name__=='__main__':main()
