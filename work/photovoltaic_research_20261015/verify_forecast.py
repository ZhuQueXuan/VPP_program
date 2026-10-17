"""Independent original CSV sampling, centered normal-equation fit and metrics."""
from pathlib import Path
import argparse,hashlib,json,math,sys
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
sys.path.insert(0,str(ROOT/'work/teacher_storage_brief_20261014/plot_dependencies'))
import numpy as np
import pandas as pd
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);ap.add_argument('--replay-id',required=True);a=ap.parse_args()
    run=BASE/'runs'/a.run_id;replay=BASE/'runs'/a.replay_id;dest=run/'verification.json';assert not dest.exists()
    pp=BASE/'forecast_protocol_v1.json';p=json.loads(pp.read_text(encoding='utf-8'))
    assert sha(pp)==json.loads((BASE/'forecast_freeze_receipt_v1.json').read_text())['protocol_sha256']
    frames=[]
    for s in p['sources']:
        file=ROOT/s['path'];assert sha(file)==s['sha256']
        f=pd.read_csv(file);f['time']=pd.to_datetime(f.measured_on,format='%Y-%m-%d %H:%M:%S');frames.append(f)
    data=pd.concat(frames,ignore_index=True).sort_values('time').set_index('time')
    assert not data.index.duplicated().any() and data.system_id.eq(1239).all()
    exact=(data.index.minute%15==0)&(data.index.second==0)&(data.index.microsecond==0)
    target=pd.date_range('2019-06-01','2019-08-01',freq='15min',inclusive='left')
    power=data[exact]['ac_power_metered_kw__3015'].reindex(target)
    samples=pd.DataFrame({'target_W':power,'origin_W':power.shift(1),'lag_W':power.shift(2)})
    valid=np.isfinite(samples.to_numpy()).all(axis=1)
    prepared=pd.read_csv(ROOT/p['sample_file'])
    assert prepared.target_time.tolist()==target.strftime('%Y-%m-%d %H:%M:%S').tolist()
    assert np.array_equal(prepared.status.eq('admitted'),valid)
    observed_times=set(data[exact].index)
    # Audit every reason, including the two initial lags outside the study window.
    reason=[]
    for i,t in enumerate(target):
        flags=[]
        for key,offset in (('target',0),('origin',1),('lag',2)):
            at=t-pd.Timedelta(minutes=15*offset)
            if at not in observed_times:flags.append('missing_'+key)
            elif not math.isfinite(float(data.loc[at,'ac_power_metered_kw__3015'])):flags.append('nonfinite_'+key)
        reason.append(';'.join(flags) if flags else 'admitted')
    assert reason==prepared.status.tolist()
    good=samples[valid];isfit=good.index<pd.Timestamp('2019-07-01')
    fit=good[isfit]
    xx=(fit.origin_W/1000).tolist();zz=(fit.lag_W/1000).tolist();yy=(fit.target_W/1000).tolist();n=len(xx)
    mx=math.fsum(xx)/n;mz=math.fsum(zz)/n;my=math.fsum(yy)/n
    u=[v-mx for v in xx];v=[w-mz for w in zz];w=[q-my for q in yy]
    suu=math.fsum(a*a for a in u);svv=math.fsum(a*a for a in v);suv=math.fsum(a*b for a,b in zip(u,v))
    suy=math.fsum(a*b for a,b in zip(u,w));svy=math.fsum(a*b for a,b in zip(v,w));det=suu*svv-suv*suv
    b1=(suy*svv-svy*suv)/det;b2=(svy*suu-suy*suv)/det;b0=my-b1*mx-b2*mz
    actual=pd.read_csv(run/'predictions.csv')
    assert actual.target_time.tolist()==good.index.strftime('%Y-%m-%d %H:%M:%S').tolist()
    assert np.array_equal(actual.split.eq('fit'),isfit)
    assert actual.origin_time.tolist()==(good.index-pd.Timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S').tolist()
    assert actual.lag_time.tolist()==(good.index-pd.Timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S').tolist()
    for key in ('target_W','origin_W','lag_W'):assert np.array_equal(actual[key],good[key])
    calc={'B_P':good.origin_W.to_numpy(),'B_T':(2*good.origin_W-good.lag_W).to_numpy(),
          'M_AR2':1000*b0+b1*good.origin_W.to_numpy()+b2*good.lag_W.to_numpy()}
    pdiff={key:float(np.max(np.abs(actual[key]-values))) for key,values in calc.items()};assert max(pdiff.values())<1e-7
    coefficients=json.loads((run/'coefficients.json').read_text());cdiff=max(abs(coefficients[k]-v) for k,v in (('intercept_kW',b0),('current_weight',b1),('previous_weight',b2)))
    assert cdiff<1e-10 and coefficients['max_fit_target_time']=='2019-06-30 23:45:00'
    metrics=json.loads((run/'metrics.json').read_text());daily=pd.read_csv(run/'daily_metrics.csv');maximum=0.;checks=0
    def check(rows,m,stored):
        nonlocal maximum,checks
        e=rows[m].to_numpy()-rows.target_W.to_numpy();ae=np.sort(abs(e));i=int(np.argmax(abs(e)))
        numeric={'mae_W':np.mean(ae),'rmse_W':np.sqrt(np.mean(e**2)),'bias_W':np.mean(e),
                 'p95_abs_W':ae[math.ceil(.95*len(ae))-1],'max_abs_W':ae[-1],
                 'mae_div_DC_nameplate':np.mean(ae)/20160,'rmse_div_DC_nameplate':np.sqrt(np.mean(e**2))/20160}
        assert int(stored['n'])==len(rows) and int(stored['negative_predictions'])==int((rows[m]<0).sum())
        for key,val in numeric.items():maximum=max(maximum,abs(float(stored[key])-float(val)));checks+=1
        assert stored['worst_target_time']==rows.iloc[i].target_time and stored['worst_origin_time']==rows.iloc[i].origin_time
        maximum=max(maximum,abs(float(stored['worst_target_W'])-float(rows.iloc[i].target_W)),abs(float(stored['worst_prediction_W'])-float(rows.iloc[i][m])))
    for split in ('fit','evaluation'):
        rr=actual[actual.split==split]
        groups={'all':rr,'origin_ge1000W':rr[rr.origin_W>=1000],'origin_lt1000W':rr[rr.origin_W<1000],
                'target_change_ge2016W':rr[abs(rr.target_W-rr.origin_W)>=2016]}
        for key,rows in groups.items():
            for m in calc:check(rows.reset_index(drop=True),m,metrics[split][key][m])
        for date,rows in rr.groupby(rr.target_time.str[:10]):
            for m in calc:
                record=daily[(daily.date==date)&(daily.model==m)];assert len(record)==1
                check(rows.reset_index(drop=True),m,record.iloc[0].to_dict())
    assert maximum<1e-7
    artifacts=json.loads((run/'receipt.json').read_text())['outputs']
    same={key:sha(run/key)==sha(replay/key) for key in artifacts};assert all(same.values())
    assert all(sha(run/key)==value for key,value in artifacts.items())
    failed=BASE/'runs/BL_PV_FORECAST_01'
    unchanged_partial={name:sha(failed/name)==sha(run/name) for name in ('coefficients.json','predictions.csv','protocol_snapshot.json')}
    assert all(unchanged_partial.values())
    # Prespecified bounded post-score context for the worst candidate forecast.
    worst=pd.Timestamp(metrics['evaluation']['all']['M_AR2']['worst_target_time'])
    data.loc[worst-pd.Timedelta(hours=1):worst+pd.Timedelta(hours=1)].to_csv(run/'worst_point_source_context.csv')
    result={'status':'passed','source_files':61,'raw_rows':len(data),'expected_target_labels':len(samples),
            'fit_samples':len(fit),'evaluation_samples':len(good)-len(fit),'sample_status_rows_verified':len(reason),
            'independent_parser':'pandas raw CSV vs stdlib preparation','independent_fit':'centered scalar covariance closed-form vs numpy SVD',
            'max_coefficient_diff':cdiff,'max_prediction_diff_W':pdiff,'numeric_metric_checks':checks,'max_metric_diff_W':maximum,
            'replay_artifacts_equal':same,'failed01_partial_outputs_equal':unchanged_partial,
            'forecast_time_order_and_train_target_boundary_checked':True,'protocol_sha256':sha(pp),'verifier_sha256':sha(Path(__file__)),
            'limit':'Numeric/sample-time checks only. Cannot verify row upload delay/average boundaries, independently identify low-output causes, or establish operational deployment.'}
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
