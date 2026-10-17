"""Independent pandas raw parse/vector clock and centered moment WLS solution."""
from common import *
import pandas as pd,numpy as np,math,re
prep=BASE/'runs/PREP_HIL_POWER_01';run=BASE/'runs/BL_HIL_POWER_01';repeat=BASE/'runs/BL_HIL_POWER_02'
dest=run/'verification.json';assert not dest.exists()
protocol=load(BASE/'hil_power_protocol_v1.json');frames=[];rawchecks=0;signs={'negative_Q':0,'negative_outdoor_P':0}
prepared=pd.read_csv(prep/'all_rows.csv',float_precision='round_trip')
for name,source in protocol['sources'].items():
    df=pd.read_csv(ROOT/source['path'],float_precision='round_trip');n=len(df)
    times=pd.to_datetime(df['TimeStamp'],format='%Y-%m-%d %H:%M:%S');clock=(times.diff().dt.total_seconds()==1).to_numpy(copy=True);clock[0]=True
    x=pd.DataFrame({'file':name,'OAT_F':int(re.search(r'OAT(\d+)F',name)[1]),'row':np.arange(1,n+1),
      'timestamp':df['TimeStamp'],'Q_kW':df['Cooling Capacity (kW)'],'Tout_C':df['T_Outdoor (C)'],
      'outdoor_P_W':df['Outdoor Unit Power (W)'],'indoor_P_W':df['Indoor Unit Power (W)']})
    x['target_total_W']=x['outdoor_P_W']+x['indoor_P_W'];x['split']='training' if x['OAT_F'].iloc[0] in (75,95,115) else 'test'
    finite=np.isfinite(x[['Q_kW','Tout_C','outdoor_P_W','indoor_P_W']].to_numpy()).all(axis=1)
    x['admitted']=clock&finite;x['clock_invalid']=~clock;x['nonfinite']=~finite
    stored=prepared[prepared['file']==name].reset_index(drop=True)
    for col in x:
        if col in ('file','timestamp','split'):assert list(x[col])==list(stored[col]),col
        else:assert np.array_equal(x[col].to_numpy(),stored[col].to_numpy()),(name,col)
        rawchecks+=n
    signs['negative_Q']+=int((x['Q_kW']<0).sum());signs['negative_outdoor_P']+=int((x['outdoor_P_W']<0).sum())
    frames.append(x[x['admitted']]);print('independent raw',name,n,flush=True)
allrows=pd.concat(frames,ignore_index=True);train=allrows[allrows['split']=='training'];test=allrows[allrows['split']=='test'].copy()
weights=(1/train.groupby('file')['file'].transform('size')).tolist();ws=math.fsum(weights)
q=train['Q_kW'].to_numpy();a=q*(train['Tout_C'].to_numpy()-35);y=train['target_total_W'].to_numpy()
def mean(v):return math.fsum(float(w)*float(t) for w,t in zip(weights,v))/ws
mq,ma,my=mean(q),mean(a),mean(y)
vq=mean((q-mq)**2);va=mean((a-ma)**2);cqa=mean((q-mq)*(a-ma));cqy=mean((q-mq)*(y-my));cay=mean((a-ma)*(y-my))
b1=cqy/vq;fixed=[my-b1*mq,b1]
det=vq*va-cqa*cqa;assert det>0
m1=(cqy*va-cay*cqa)/det;m2=(cay*vq-cqy*cqa)/det;corrected=[my-m1*mq-m2*ma,m1,m2]
stored=load(run/'calibration.json')['parameters'];maxcoef=0.
for key,coefs in [('B_COP',fixed),('M_TEMP',corrected)]:
    maxcoef=max(maxcoef,max(abs(a-b) for a,b in zip(coefs,stored[key])));assert np.allclose(coefs,stored[key],rtol=1e-11,atol=1e-8)
assert abs(my-stored['B_MEAN_W'])<1e-8
test['B_MEAN']=my;test['B_COP']=fixed[0]+fixed[1]*test['Q_kW'];test['M_TEMP']=corrected[0]+corrected[1]*test['Q_kW']+corrected[2]*test['Q_kW']*(test['Tout_C']-35)
mins={'Q_kW':[float(q.min()),float(q.max())],'Tout_C':[float(train['Tout_C'].min()),float(train['Tout_C'].max())]}
for key in mins:assert np.allclose(mins[key],stored['training_ranges'][key],rtol=0,atol=1e-12),key
test['outside_training_input_range']=~test['Q_kW'].between(*mins['Q_kW'])|~test['Tout_C'].between(*mins['Tout_C'])
prediction=pd.read_csv(run/'predictions.csv',float_precision='round_trip');assert list(zip(test['file'],test['row']))==list(zip(prediction['file'],prediction['row']))
reference_difference=float(np.max(abs(test['target_total_W'].to_numpy()-prediction['target_total_W'].to_numpy())))
assert reference_difference<1e-9
maxpred=0.
for m in ('B_MEAN','B_COP','M_TEMP'):
    delta=float(np.max(abs(test[m].to_numpy()-prediction[m].to_numpy())));maxpred=max(maxpred,delta);assert delta<1e-8
assert np.array_equal(test['outside_training_input_range'],prediction['outside_training_input_range'])
assert np.array_equal(test['M_TEMP']<0,prediction['negative_temperature_corrected_estimate'])
metrics=load(run/'metrics.json');checks=0;maxmetric=0.;recomputed={}
def compare(df,expected):
    global checks,maxmetric
    assert len(df)==expected['rows'];results={}
    for m in ('B_MEAN','B_COP','M_TEMP'):
        e=(df[m]-df['target_total_W']).tolist();n=len(e)
        vals={'MAE_W':math.fsum(map(abs,e))/n,'RMSE_W':math.sqrt(math.fsum(x*x for x in e)/n),'bias_W':math.fsum(e)/n,'max_abs_error_W':max(map(abs,e))}
        for k,value in vals.items():
            diff=abs(value-expected[m][k]);assert diff<1e-8;maxmetric=max(maxmetric,diff);checks+=1
        results[m]=vals
    assert all(results['M_TEMP'][k]<results['B_COP'][k] for k in ('MAE_W','RMSE_W'))==expected['M_TEMP_double_improves_B_COP']
    return results
for key,df in [('all',test),('Q_ge1kW',test[test['Q_kW']>=1]),('Q_lt1kW',test[test['Q_kW']<1])]:compare(df,metrics['groups'][key])
perfile=[]
for file in metrics['files']:perfile.append(compare(test[test['file']==file['file']],file))
for m in ('B_MEAN','B_COP','M_TEMP'):
    for k in ('MAE_W','RMSE_W'):
        value=math.fsum(r[m][k] for r in perfile)/2;diff=abs(value-metrics['equal_file_mean_metrics'][m][k]);assert diff<1e-8;checks+=1;maxmetric=max(maxmetric,diff)
replay={n:sha(run/n)==sha(repeat/n) for n in load(run/'receipt.json')['outputs']};assert all(replay.values())
assert not load(run/'summary.json')['predeclared_relative_success']
result={'date':'2026-10-16','status':'passed','protocol_sha256':sha(BASE/'hil_power_protocol_v1.json'),
 'original_rows_independent_parser':len(allrows),'original_field_flag_checks':rawchecks,'training_rows':len(train),'test_rows':len(test),
 'independent_fit':'centered equal-file weighted moment closed forms vs numpy weighted least squares; no runner/kernel import',
 'maximum_coefficient_difference_W':maxcoef,'maximum_prediction_difference_W':maxpred,'maximum_reference_parser_difference_W':reference_difference,'metric_checks':checks,'maximum_metric_difference_W':maxmetric,
 'all_negative_source_values_retained':signs,'replay_artifacts_equal':replay,'verifier_sha256':sha(Path(__file__)),
 'scientific_conclusion':'Overall/85F improvement but105F MAE/RMSE worse, so fixed relative gate failed. No new model release or posthoc route change.',
 'scope':'One-device HIL same-record reconstruction; no field capacity/control timing validation.'}
dump(dest,result);print(json.dumps(result,ensure_ascii=False,indent=2))
