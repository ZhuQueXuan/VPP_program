"""Necessary migration checks; one fixed panel, not a new performance search."""
from pathlib import Path
import sys,hashlib,json,copy,dataclasses,warnings,time
import numpy as np
warnings.filterwarnings('ignore',message='X does not have valid feature names')
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[2]
sys.path.insert(0,str(PROJECT))
sys.path.insert(0,str(PROJECT/'work/b1_mainline_20261029/reference'))
from b1_algorithm.reference import (
    ReferenceWindow,ReferenceTrainingRecord,WindowCalibrationRecord,
    feature_matrix,fit_reference,predict_reference,calibrate_window_reference,
    save_reference_model,load_reference_model,
)
from reference_api import SafeGBDT, safe_features,split_users
from run_reference import make
from ride.baseline import fill_nan_time,cbl_prev

SEED=975000
def make_window(obs,i,task_id,user,prior,temp,weekday,prefix,task_start=10000.,source_count=9):
    lead=float(obs.meta['lead'].iat[i]);notice=task_start-lead
    pre=obs.ends<=-lead+1e-9
    return ReferenceWindow(task_id=task_id,user_id=str(user),meter_id='meter-'+str(user),
        resource_type='EV' if obs.meta['is_ev'].iat[i] else 'AC',
        task_start_min=task_start,task_end_min=task_start+float(obs.meta['W'].iat[i]),
        request_kw=float(obs.meta['q'].iat[i]),notice_min=notice,
        starts_min=task_start+obs.starts,ends_min=task_start+obs.ends,
        pre_starts_min=task_start+obs.starts[pre],pre_ends_min=task_start+obs.ends[pre],pre_power_kw=prefix[pre],pre_available_min=notice,
        prior_mean_kw=prior,prior_available_min=notice-1,prior_source_count=source_count,
        prior_source_ids=tuple('independent-prior-'+task_id+'-'+str(j) for j in range(source_count)),
        clock_hour=float(obs.meta['hour'].iat[i]),weekday=int(weekday),calendar_available_min=notice-1,
        temperature_c=float(temp),temperature_available_min=notice-1)

def main():
    started=time.time();checks=[]
    sim,obs=make(SEED,True,80)
    roles=split_users(obs.meta['user'],SEED+5)
    legacy=SafeGBDT(SEED).fit(obs,roles['train'])
    h=obs.Hist.shape[1];hist=fill_nan_time(obs.Hist)
    loo=(hist.sum(1,keepdims=True)-hist)/(h-1)
    old_features=safe_features(obs,'hist',loo)
    records=[]
    for i in np.flatnonzero(obs.meta['user'].isin(roles['train']).to_numpy()):
        for j in range(h):
            w=make_window(obs,i,'history-'+str(i)+'-'+str(j),obs.meta['user'].iat[i],loo[i,j],obs.day_meta['hist_temp'][i,j],obs.day_meta['hist_weekday'][i,j],hist[i,j])
            np.testing.assert_array_equal(feature_matrix(w),old_features[i*h+j])
            records.append(ReferenceTrainingRecord(w,obs.Hist[i,j],10100.,True))
    checks.append('all legal feature matrices bitwise align with old SafeGBDT fixture')
    model=fit_reference(records,11000.,SEED)
    target=legacy.predict(obs);prior=cbl_prev(obs)
    predictions=[];maxdiff=0.
    for i in np.flatnonzero(obs.meta['user'].isin(roles['test']).to_numpy()):
        w=make_window(obs,i,'event-'+str(i),obs.meta['user'].iat[i],prior[i],obs.meta['temp'].iat[i],obs.meta['weekday'].iat[i],obs.P[i],task_start=20000.,source_count=h)
        out=predict_reference(model,w)
        assert out.reference_status=='available',out.reasons
        assert out.task_start_min==w.task_start_min and out.task_end_min==w.task_end_min
        assert out.request_kw==w.request_kw and out.notice_min==w.notice_min
        np.testing.assert_allclose(out.reference_kw,target[i],atol=1e-12,rtol=0)
        maxdiff=max(maxdiff,float(np.max(np.abs(out.reference_kw-target[i]))))
        predictions.append((w,out))
    checks.append('fixed held-out panel predictions match legacy SafeGBDT')
    checks.append('available references bind task start/end/request/notice in addition to IDs and grid')
    first,out=predictions[0]
    subset=(np.asarray(first.starts_min)>=first.task_start_min-15)&(np.asarray(first.ends_min)<=first.task_start_min+45)
    sub=dataclasses.replace(first,starts_min=np.asarray(first.starts_min)[subset],ends_min=np.asarray(first.ends_min)[subset],prior_mean_kw=np.asarray(first.prior_mean_kw)[subset])
    subpred=predict_reference(model,sub)
    assert subpred.reference_status=='available',subpred.reasons
    np.testing.assert_array_equal(subpred.reference_kw,out.reference_kw[subset])
    checks.append('same event prediction subgrid preserves prefix features and predictions')
    fixture=dataclasses.asdict(first)
    fixture={k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in fixture.items()}
    (ROOT/'query_fixture.json').write_text(json.dumps(fixture,indent=2),encoding='utf-8')
    # Required data fail explicitly; no silent imputation.
    mutations={
        'missing_temperature':dict(temperature_c=None),
        'post_notice_temperature':dict(temperature_available_min=first.notice_min+1),
        'late_meter_prefix':dict(pre_available_min=first.notice_min+1),
        'future_historical_reference':dict(prior_available_min=first.notice_min+1),
        'post_notice_power':dict(pre_starts_min=np.asarray(first.pre_starts_min)+1,pre_ends_min=np.asarray(first.pre_ends_min)+1),
        'boolean_request':dict(request_kw=True),
        'string_calendar':dict(clock_hour='12'),
        'nonfinite_prior':dict(prior_mean_kw=np.full(len(first.starts_min),np.nan)),
        'unsupported_resolution':dict(ends_min=np.asarray(first.starts_min)+2),
        'own_task_in_prior':dict(prior_source_ids=(first.task_id,)+first.prior_source_ids[1:]),
        'ambiguous_prior_timestamp':dict(prior_available_min=None),
        'overflow_prior_feature':dict(prior_mean_kw=np.full(len(first.starts_min),1e300)),
        'duplicate_prior_source':dict(prior_source_ids=(first.prior_source_ids[0],)*first.prior_source_count),
        'mixed_boolean_vector':dict(prior_mean_kw=[True]+list(first.prior_mean_kw)[1:]),
        'mixed_string_vector':dict(prior_mean_kw=['1.0']+list(first.prior_mean_kw)[1:]),
    }
    for name,changes in mutations.items():
        result=predict_reference(model,dataclasses.replace(first,**changes))
        assert result.reference_status=='unavailable',(name,result)
        assert result.reference_kw is None
        assert result.task_start_min is None and result.task_end_min is None and result.request_kw is None and result.notice_min is None
    checks.append('15 missing, leakage, timing and numeric boundary cases unavailable')
    known=dataclasses.replace(first,user_id=model.training_users[0])
    assert predict_reference(model,known).reference_status=='unavailable'
    allowed=predict_reference(model,known,allow_seen_user=True)
    assert allowed.reference_status=='available' and allowed.role=='seen_training_user'
    checks.append('held-out role rejects training users; operational override explicitly marked')
    historical=predict_reference(None,first,method='prev10')
    np.testing.assert_array_equal(historical.reference_kw,np.asarray(first.prior_mean_kw,dtype='float32').astype(float))
    checks.append('transparent historical mean preserved')
    # Independent pseudo-event users; calibration uses whole-window residual, not point sigma.
    cal=[]
    for typ in ('EV','AC'):
        for j in range(10):
            w=dataclasses.replace(first,task_id='cal-'+typ+str(j),user_id='cal-user-'+typ+str(j),meter_id='cal-meter-'+typ+str(j),resource_type=typ)
            p=predict_reference(model,w)
            cal.append(WindowCalibrationRecord(w,p.reference_kw+.15,20100.,True))
    # Shift the synthetic query clock earlier for calibration, preserving all relative features.
    def shift(w,minutes):
        names=('task_start_min','task_end_min','notice_min','pre_available_min','prior_available_min','calendar_available_min','temperature_available_min')
        change={n:getattr(w,n)+minutes for n in names}
        for n in ('starts_min','ends_min','pre_starts_min','pre_ends_min'):change[n]=np.asarray(getattr(w,n))+minutes
        return dataclasses.replace(w,**change)
    cal=[WindowCalibrationRecord(shift(r.window,-5000),r.observed_non_event_power_kw,15100.,True) for r in cal]
    calibrate_window_reference(model,cal,16000.)
    calibrated=predict_reference(model,first)
    assert calibrated.reference_status=='available' and calibrated.pointwise_noise_sigma_kw is None
    assert calibrated.window_band_eta['pointwise_sigma'] is False
    assert model.calibration['by_resource']['EV']['n_users']==10
    bad=WindowCalibrationRecord(dataclasses.replace(cal[0].window,user_id=model.training_users[0]),cal[0].observed_non_event_power_kw,15100.,True)
    try:calibrate_window_reference(model,[bad],16000.)
    except ValueError:pass
    else:raise AssertionError('overlap calibration accepted')
    checks.append('user-block window calibration and train/calibration separation')
    artifact=ROOT/'artifact'
    if (artifact/'metadata.json').exists():
        saved=json.loads((artifact/'metadata.json').read_text(encoding='utf-8'))
        assert saved['model_id']==model.model_id
    else:saved=save_reference_model(model,artifact)
    restored=load_reference_model(artifact)
    loaded=predict_reference(restored,first)
    np.testing.assert_array_equal(loaded.reference_kw,calibrated.reference_kw)
    assert loaded.window_band_eta==calibrated.window_band_eta
    assert loaded.task_id==first.task_id and loaded.meter_id==first.meter_id
    checks.append('native model plus JSON reload is bitwise identical and ID-bound')
    # Corrupt only an isolated copy of a locally generated artifact.
    broken=ROOT/'corrupt_fixture';broken.mkdir(exist_ok=True)
    (broken/'model.txt').write_bytes((artifact/'model.txt').read_bytes())
    meta=copy.deepcopy(saved);meta['feature_names'][0]='bad_feature'
    (broken/'metadata.json').write_text(json.dumps(meta),encoding='utf-8')
    try:load_reference_model(broken)
    except ValueError:pass
    else:raise AssertionError('bad feature schema accepted')
    meta=copy.deepcopy(saved);meta['model_sha256']='0'*64
    (broken/'metadata.json').write_text(json.dumps(meta),encoding='utf-8')
    try:load_reference_model(broken)
    except ValueError:pass
    else:raise AssertionError('bad model hash accepted')
    checks.append('artifact feature schema and SHA corruption rejected')
    panel=dict(seed=SEED,n_users=80,n_events=len(obs.meta),n_training_windows=len(records),n_heldout_events=len(predictions),max_legacy_prediction_difference_kw=maxdiff,
               timing_fixture='explicit synthetic availability declarations for numerical migration only; not original simulator historical timestamps',
               role='fixed small migration panel, not a new performance experiment')
    (ROOT/'fixed_panel.json').write_text(json.dumps(panel,indent=2),encoding='utf-8')
    receipt=dict(passed=True,checks=checks,elapsed_seconds=time.time()-started,panel=panel,
                 native_artifact_model_id=model.model_id)
    (ROOT/'checks.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
