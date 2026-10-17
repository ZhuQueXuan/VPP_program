"""Independent raw sampling, scalar clear-sky/POA arithmetic and scoring.

Scalar equations follow published Ineichen/isotropic relations. Astronomy and
climatology remain pvlib inputs, not independent physical truth measurements.
"""
from pathlib import Path
import argparse,hashlib,json,math,sys
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
for d in ('work/teacher_storage_brief_20261014/plot_dependencies','work/python_packages/storage_ecm_20261015','work/python_packages/pvlib_smart_20261015'):
    sys.path.insert(0,str(ROOT/d))
import numpy as np
import pandas as pd
import pvlib
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);ap.add_argument('--replay-id',required=True);a=ap.parse_args()
    run=BASE/'runs'/a.run_id;replay=BASE/'runs'/a.replay_id;dest=run/'verification.json';assert not dest.exists()
    pp=BASE/'smart_forecast_protocol_v1.json';p=json.loads(pp.read_text(encoding='utf-8'));c=p['geometry_config']
    assert sha(pp)==json.loads((BASE/'smart_forecast_freeze_receipt_v1.json').read_text())['protocol_sha256']
    frames=[]
    for src in p['sources']:
        file=ROOT/src['path'];assert sha(file)==src['sha256']
        d=pd.read_csv(file);d['time']=pd.to_datetime(d.measured_on,format='%Y-%m-%d %H:%M:%S');frames.append(d)
    source=pd.concat(frames,ignore_index=True).sort_values('time').set_index('time');assert not source.index.duplicated().any()
    exact=(source.index.minute%15==0)&(source.index.second==0)&(source.index.microsecond==0)
    labels=pd.date_range('2019-07-31','2019-09-01',freq='15min',inclusive='left')
    power=source[exact]['ac_power_metered_kw__3015'].reindex(labels)
    tab=pd.DataFrame({'target_W':power,'origin_W':power.shift(1),'lag_W':power.shift(2)}).loc['2019-08-01':]
    admitted=np.isfinite(tab.to_numpy()).all(axis=1)
    prepared=pd.read_csv(ROOT/p['sample_file'])
    assert prepared.target_time.tolist()==tab.index.strftime('%Y-%m-%d %H:%M:%S').tolist()
    assert np.array_equal(prepared.status.eq('admitted'),admitted)
    assert np.array_equal(prepared.pair_available,np.isfinite(tab[['target_W','origin_W']]).all(axis=1))
    valid=tab[admitted];pred=pd.read_csv(run/'predictions.csv')
    assert pred.target_time.tolist()==valid.index.strftime('%Y-%m-%d %H:%M:%S').tolist()
    for name in ('target_W','origin_W','lag_W'):assert np.array_equal(pred[name],valid[name])
    assert pred.origin_time.tolist()==(valid.index-pd.Timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S').tolist()
    assert pred.lag_time.tolist()==(valid.index-pd.Timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S').tolist()
    geom=pd.read_csv(run/'clear_sky_geometry.csv').set_index('time');geom_max=0.;cs_max=0.
    radians=math.radians;tilt=radians(c['tilt_deg']);azimuth=radians(c['azimuth_deg']);alt=c['altitude_m']
    # Re-evaluate scalar equations without importing the runner or pvlib's
    # clear-sky/transposition functions. SPA/Linke inputs remain shared.
    for t,r in geom.iterrows():
        z=radians(r.apparent_zenith_deg);az=radians(r.solar_azimuth_deg);cz=max(0.,math.cos(z))
        if math.isfinite(r.airmass_absolute):
            am=r.airmass_absolute;tl=r.linke_turbidity;extra=r.dni_extra_W_m2
            h1=math.exp(-alt/8000);h2=math.exp(-alt/1250)
            ghi=(.868+.0000509*alt)*extra*cz*math.exp(-(.0387+.0000392*alt)*am*(h1+h2*(tl-1)))
            first=(.664+.163/h1)*extra*math.exp(-.09*am*(tl-1))
            correction=(1-(.1-.2*math.exp(-tl))/(.1+.882/h1))/cz
            dni=min(first,ghi*min(max(correction,0.),1e20));dhi=ghi-dni*cz
        else:ghi=dni=dhi=0.
        cs_max=max(cs_max,abs(ghi-r.cs_ghi_W_m2),abs(dni-r.cs_dni_W_m2),abs(dhi-r.cs_dhi_W_m2))
        incidence=math.cos(tilt)*math.cos(z)+math.sin(tilt)*math.sin(z)*math.cos(az-azimuth)
        beam=max(0.,incidence)*dni;sky=dhi*(1+math.cos(tilt))/2;ground=ghi*c['albedo']*(1-math.cos(tilt))/2
        geom_max=max(geom_max,abs(beam+sky+ground-r.cs_poa_W_m2),abs(beam-r.poa_direct_W_m2),
                     abs(sky-r.poa_sky_diffuse_W_m2),abs(ground-r.poa_ground_W_m2))
    assert cs_max<1e-7 and geom_max<1e-7
    # Different astronomical routine within the SAME library: a diagnostic,
    # not independent sensor calibration or proof of metadata/time semantics.
    local=pd.DatetimeIndex(geom.index).tz_localize(c['timezone']);utc=pd.DatetimeIndex(pd.to_datetime(geom.utc_time)).tz_localize('UTC')
    assert np.array_equal(local.tz_convert('UTC'),utc)
    ep=pvlib.solarposition.ephemeris(local,c['latitude'],c['longitude'],pressure=pvlib.atmosphere.alt2pres(c['altitude_m']),temperature=c['standard_temperature_C'])
    zenith_diff=float(np.max(np.abs(ep.zenith.to_numpy()-geom.zenith_deg.to_numpy())))
    geommap=geom.cs_poa_W_m2.to_dict();b=json.loads((ROOT/p['ar2_file']).read_text())
    calc=[];branches=[];ratios=[]
    for row in pred.itertuples(index=False):
        now=geommap[row.origin_time];future=geommap[row.target_time]
        isscaled=now>=c['minimum_current_clear_poa_W_m2'];ratio=future/now if isscaled else 1.
        branches.append('scaled' if isscaled else 'persistence_fallback');ratios.append(ratio)
        calc.append(row.origin_W*ratio)
        assert abs(row.clear_current_W_m2-now)<1e-9 and abs(row.clear_target_W_m2-future)<1e-9
    assert branches==pred.smart_branch.tolist()
    calculated={'B_P':valid.origin_W.to_numpy(),'M_SP':np.array(calc),
                'F_AR2':1000*b['intercept_kW']+b['current_weight']*valid.origin_W.to_numpy()+b['previous_weight']*valid.lag_W.to_numpy()}
    diffs={m:float(np.max(np.abs(pred[m]-v))) for m,v in calculated.items()};assert max(diffs.values())<1e-7
    metrics=json.loads((run/'metrics.json').read_text());daily=pd.read_csv(run/'daily_metrics.csv');checks=0;metricmax=0.
    def check(rows,m,r):
        nonlocal checks,metricmax
        e=rows[m].to_numpy()-rows.target_W.to_numpy();ae=np.sort(abs(e));i=int(np.argmax(abs(e)))
        values={'mae_W':np.mean(ae),'rmse_W':np.sqrt(np.mean(e*e)),'bias_W':np.mean(e),
                'p95_abs_W':ae[math.ceil(.95*len(ae))-1],'max_abs_W':ae[-1],
                'mae_div_DC_nameplate':np.mean(ae)/20160,'rmse_div_DC_nameplate':np.sqrt(np.mean(e*e))/20160}
        assert int(r['n'])==len(rows) and int(r['negative_predictions'])==int((rows[m]<0).sum())
        for k,v in values.items():metricmax=max(metricmax,abs(float(r[k])-float(v)));checks+=1
        assert r['worst_target_time']==rows.iloc[i].target_time and r['worst_origin_time']==rows.iloc[i].origin_time
        metricmax=max(metricmax,abs(float(r['worst_target_W'])-float(rows.iloc[i].target_W)),abs(float(r['worst_prediction_W'])-float(rows.iloc[i][m])))
    groups={'all':pred,'origin_ge1000W':pred[pred.origin_W>=1000],'origin_lt1000W':pred[pred.origin_W<1000],
            'target_change_ge2016W':pred[abs(pred.target_W-pred.origin_W)>=2016]}
    for group,rr in groups.items():
        for m in calculated:check(rr.reset_index(drop=True),m,metrics[group][m])
    for date,rr in pred.groupby(pred.target_time.str[:10]):
        for m in calculated:
            r=daily[(daily.date==date)&(daily.model==m)];assert len(r)==1;check(rr.reset_index(drop=True),m,r.iloc[0].to_dict())
    assert metricmax<1e-7
    artifacts=json.loads((run/'receipt.json').read_text())['outputs'];same={n:sha(run/n)==sha(replay/n) for n in artifacts}
    assert all(same.values()) and all(sha(run/n)==h for n,h in artifacts.items())
    worst=pd.Timestamp(metrics['all']['M_SP']['worst_target_time'])
    source.loc[worst-pd.Timedelta(hours=1):worst+pd.Timedelta(hours=1)].to_csv(run/'worst_point_source_context.csv')
    result={'status':'passed','sources':32,'expected_targets':len(tab),'common_samples':len(valid),
            'pair_available_samples':int(np.isfinite(tab[['target_W','origin_W']]).all(axis=1).sum()),
            'independent_parser':'pandas original CSV vs stdlib preparation','clear_sky_scalar_max_diff_W_m2':cs_max,
            'isotropic_scalar_max_diff_W_m2':geom_max,'same_library_ephemeris_vs_SPA_max_zenith_diff_degrees':zenith_diff,
            'prediction_max_diff_W':diffs,'metric_numeric_checks':checks,'metric_max_diff_W':metricmax,
            'replay_artifacts_equal':same,'protocol_sha256':sha(pp),'verifier_sha256':sha(Path(__file__)),
            'limits':'SPA/Linke still library supplied; metadata, physical sensor timing/calibration and independent-site generalization unverified.'}
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
