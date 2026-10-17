"""Independent raw parsing, ZoneInfo masks, scalar physics and metric replay."""
from crossseason_common import *
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import math
import numpy as np
import pandas as pd
import pvlib
P=frozen();prep=BASE/'runs/PREP_CROSSSEASON_02';run=BASE/'runs/BL_CROSSSEASON_01';replay=BASE/'runs/BL_CROSSSEASON_02'
dest=run/'verification.json';assert not dest.exists()
sources=json.loads((prep/'source_manifest.json').read_text());frames=[]
for s in sources:
    file=ROOT/s['path'];assert sha(file)==s['sha256'];frames.append(pd.read_csv(file))
raw=pd.concat(frames,ignore_index=True);raw['time']=pd.to_datetime(raw.measured_on,format='%Y-%m-%d %H:%M:%S')
assert not raw.time.duplicated().any()
power=raw.set_index('time').ac_power_metered_kw__3015
labels=pd.date_range('2019-08-31 23:30','2020-05-31 23:45',freq='15min')
series=power.reindex(labels);vals=pd.DataFrame({'target_W':series,'origin_W':series.shift(1),'lag_W':series.shift(2)}).iloc[2:]
zone=ZoneInfo('America/New_York');clock={}
for ts in labels:
    t=ts.to_pydatetime();choices=set()
    for fold in (0,1):
        utc=t.replace(tzinfo=zone,fold=fold).astimezone(timezone.utc)
        if utc.astimezone(zone).replace(tzinfo=None)==t:choices.add(utc)
    clock[t]=next(iter(choices)) if len(choices)==1 else None
mask=[];pairs=[]
for ts,row in vals.iterrows():
    t=ts.to_pydatetime();tt=[t,t-timedelta(minutes=15),t-timedelta(minutes=30)];uu=[clock[x] for x in tt]
    ok=[u is not None for u in uu]
    pair=all(ok[:2]) and (uu[0]-uu[1]).total_seconds()==900 and np.isfinite(row[['target_W','origin_W']]).all()
    pairs.append(pair);mask.append(pair and ok[2] and (uu[1]-uu[2]).total_seconds()==900 and np.isfinite(row.lag_W))
prepared=pd.read_csv(prep/'samples.csv');assert prepared.target_time.tolist()==vals.index.strftime('%Y-%m-%d %H:%M:%S').tolist()
assert np.array_equal(prepared.status.eq('admitted'),mask) and np.array_equal(prepared.pair_available,pairs)
valid=vals[np.array(mask)];pred=pd.read_csv(run/'predictions.csv')
assert pred.target_time.tolist()==valid.index.strftime('%Y-%m-%d %H:%M:%S').tolist()
for k in ('target_W','origin_W','lag_W'):assert np.allclose(pred[k],valid[k],rtol=0,atol=1e-9)
for key,delta in (('target',0),('origin',15),('lag',30)):
    expected=[clock[t.to_pydatetime()-timedelta(minutes=delta)].strftime('%Y-%m-%d %H:%M:%S') for t in valid.index]
    assert pred[key+'_utc'].tolist()==expected
c=P['geometry_config'];times=pd.DatetimeIndex(pd.to_datetime(pred.origin_utc,utc=True)).append(pd.DatetimeIndex(pd.to_datetime(pred.target_utc,utc=True))).unique().sort_values().tz_convert(c['timezone'])
loc=pvlib.location.Location(c['latitude'],c['longitude'],tz=c['timezone'],altitude=c['altitude_m'])
sp=loc.get_solarposition(times,method='nrel_numpy',temperature=12,delta_t=67)
tl=pvlib.clearsky.lookup_linke_turbidity(times,c['latitude'],c['longitude'],interp_turbidity=True)
extra=pvlib.irradiance.get_extra_radiation(times,method='spencer');am=loc.get_airmass(solar_position=sp).airmass_absolute
poa=[];alt=c['altitude_m'];tilt=math.radians(c['tilt_deg']);azimuth=math.radians(c['azimuth_deg'])
for i in range(len(times)):
    z=math.radians(sp.apparent_zenith.iloc[i]);az=math.radians(sp.azimuth.iloc[i]);cz=max(0.,math.cos(z))
    if math.isfinite(am.iloc[i]):
        h1=math.exp(-alt/8000);h2=math.exp(-alt/1250);a=am.iloc[i];t=tl.iloc[i];e=extra.iloc[i]
        ghi=(.868+.0000509*alt)*e*cz*math.exp(-(.0387+.0000392*alt)*a*(h1+h2*(t-1)))
        first=(.664+.163/h1)*e*math.exp(-.09*a*(t-1))
        correction=(1-(.1-.2*math.exp(-t))/(.1+.882/h1))/cz
        dni=min(first,ghi*min(max(correction,0.),1e20));dhi=ghi-dni*cz
    else:ghi=dni=dhi=0.
    incidence=math.cos(tilt)*math.cos(z)+math.sin(tilt)*math.sin(z)*math.cos(az-azimuth)
    poa.append(max(0.,incidence)*dni+dhi*(1+math.cos(tilt))/2+ghi*.25*(1-math.cos(tilt))/2)
mapping=dict(zip(times.tz_convert('UTC').strftime('%Y-%m-%d %H:%M:%S'),poa))
now=np.array([mapping[t] for t in pred.origin_utc]);future=np.array([mapping[t] for t in pred.target_utc]);ratio=np.ones(len(pred));np.divide(future,now,out=ratio,where=now>=20)
b=json.loads((ROOT/P['frozen_artifacts']['ar2']['path']).read_text())
calc={'B_P':pred.origin_W.to_numpy(),'M_SP':pred.origin_W.to_numpy()*ratio,
      'F_AR2':1000*b['intercept_kW']+b['current_weight']*pred.origin_W.to_numpy()+b['previous_weight']*pred.lag_W.to_numpy()}
diff={m:float(np.max(abs(v-pred[m]))) for m,v in calc.items()};assert max(diff.values())<1e-7
geometrydiff=max(float(np.max(abs(now-pred.clear_current_W_m2))),float(np.max(abs(future-pred.clear_target_W_m2))))
assert geometrydiff<1e-7 and np.max(abs(ratio-pred.ratio))<1e-10
assert pred.branch.tolist()==np.where(now>=20,'scaled','persistence_fallback').tolist()
metricmax=0.;checks=0
def check(rr,m,s):
    global metricmax,checks
    if not len(rr):assert s['n']==0;return
    e=rr[m].to_numpy()-rr.target_W.to_numpy();ae=np.sort(abs(e));idx=int(np.argmax(abs(e)));worst=rr.iloc[idx]
    d={'mae_W':np.mean(ae),'rmse_W':np.sqrt(np.mean(e*e)),'bias_W':np.mean(e),'p95_abs_W':ae[math.ceil(.95*len(ae))-1],
       'max_abs_W':ae[-1],'worst_target_W':worst.target_W,'worst_prediction_W':worst[m],
       'mae_div_DC_nameplate':np.mean(ae)/20160,'rmse_div_DC_nameplate':np.sqrt(np.mean(e*e))/20160}
    assert int(s['n'])==len(rr) and int(s['negative_predictions'])==sum(rr[m]<0)
    assert s['worst_target_time']==worst.target_time and s['worst_origin_time']==worst.origin_time
    for k,v in d.items():metricmax=max(metricmax,abs(float(s[k])-float(v)));checks+=1
groups={'all':pred,'origin_ge1000W':pred[pred.origin_W>=1000],'origin_lt1000W':pred[pred.origin_W<1000],
        'target_change_ge2016W':pred[abs(pred.target_W-pred.origin_W)>=2016]}
metrics=json.loads((run/'metrics.json').read_text())
for g,rr in groups.items():
    for m in calc:check(rr,m,metrics[g][m])
for s in read(run/'group_metrics.csv'):
    typ=s['group_type'];key=s['group'];rr=pred[pred.target_time.str[:10].eq(key)] if typ=='date' else pred[pred[typ].eq(key)]
    check(rr,s['model'],s)
assert metricmax<1e-7
artifacts=json.loads((run/'receipt.json').read_text())['outputs'];same={n:sha(run/n)==sha(replay/n)==h for n,h in artifacts.items()};assert all(same.values())
# Descriptive source diagnostics after errors; do not change cohort or models.
profiles=[]
for month,rr in raw[raw.time.ge('2019-09-01')].groupby(raw.time.dt.strftime('%Y-%m')):
    v=rr.ac_power_metered_kw__3015.to_numpy();finite=v[np.isfinite(v)]
    profiles.append({'month':month,'raw_rows':len(rr),'finite_power':len(finite),'negative_rows':int(sum(finite<0)),
        'zero_rows':int(sum(finite==0)),'power_ge1000W_rows':int(sum(finite>=1000)),
        'power_min_W':float(np.min(finite)),'power_max_W':float(np.max(finite)),'power_p95_W':float(np.quantile(finite,.95))})
table(run/'source_monthly_profile.csv',profiles)
worst=metrics['all']['M_SP']['worst_target_time'];wt=pd.Timestamp(worst)
raw[raw.time.between(wt-pd.Timedelta(hours=1),wt+pd.Timedelta(hours=1))].to_csv(run/'worst_source_context.csv',index=False)
result={'status':'passed','protocol_sha256':sha(BASE/'crossseason_protocol_v1.json'),'admission_sha256':sha(prep/'admission.json'),
    'sources':len(sources),'expected_targets':len(vals),'common_samples':len(pred),'pair_samples':sum(bool(v) for v in pairs),
    'independent_parser':'pandas original CSV vs stdlib preparation','independent_clock':'ZoneInfo two-fold roundtrip vs pandas NaT localization',
    'clock_all_expected_masks_equal':True,'scalar_poa_max_difference_W_m2':geometrydiff,'prediction_max_difference_W':diff,
    'metric_numeric_checks':checks,'metric_max_difference_W':metricmax,'replay_artifacts_equal':same,
    'verifier_sha256':sha(Path(__file__)),'post_score_profile':'Descriptive only; no cohort selection or cause inference',
    'limits':'Solar astronomy and climatology shared library inputs, not physical calibration. Sparse low-output observations do not establish normal all-season generation.'}
dump(dest,result);print(json.dumps(result,ensure_ascii=False,indent=2))
