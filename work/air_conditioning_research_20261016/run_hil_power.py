"""Frozen whole-temperature-experiment power mapping; no posthoc selection."""
from common import *
from hil_power_kernel import reconstruct_power
import argparse,numpy as np,pandas as pd

def metrics(df):
    obj={'rows':len(df)}
    for m in ('B_MEAN','B_COP','M_TEMP'):
        e=df[m].to_numpy()-df['target_total_W'].to_numpy()
        obj[m]={'MAE_W':float(np.mean(abs(e))),'RMSE_W':float(np.sqrt(np.mean(e**2))),'bias_W':float(np.mean(e)),'max_abs_error_W':float(np.max(abs(e)))}
    obj['M_TEMP_double_improves_B_COP']=all(obj['M_TEMP'][k]<obj['B_COP'][k] for k in ('MAE_W','RMSE_W'))
    return obj
def execute(out):
    pp=BASE/'hil_power_protocol_v1.json';assert sha(pp)==load(BASE/'hil_power_freeze_v1.json')['protocol_sha256']
    prep=BASE/'runs/PREP_HIL_POWER_01';ad=load(prep/'admission.json')
    assert all(sha(prep/n)==h for n,h in ad['outputs'].items())
    for source in load(pp)['sources'].values():assert sha(ROOT/source['path'])==source['sha256']
    df=pd.read_csv(prep/'all_rows.csv');df=df[df['admitted']].copy();train=df[df['split']=='training'];test=df[df['split']=='test'].copy()
    q=train['Q_kW'].to_numpy();t=train['Tout_C'].to_numpy();y=train['target_total_W'].to_numpy()
    n=train.groupby('file')['file'].transform('size').to_numpy();w=1/n;root=np.sqrt(w)
    X=np.column_stack([np.ones(len(q)),q,q*(t-35.)]);fits={}
    params={'B_MEAN_W':float(np.dot(w,y)/w.sum()),'training_ranges':{'Q_kW':[float(min(q)),float(max(q))],'Tout_C':[float(min(t)),float(max(t))]},
      'training_files':sorted(train['file'].unique().tolist()),'fit_weight':'each whole training file equal total weight'}
    for model,k in [('B_COP',2),('M_TEMP',3)]:
        beta,res,rank,s=np.linalg.lstsq(X[:,:k]*root[:,None],y*root,rcond=1e-12)
        params[model]=beta.tolist();fits[model]={'rank':int(rank),'singular_values':s.tolist(),'parameters':k}
    values=[reconstruct_power(q,t,params) for q,t in zip(test['Q_kW'],test['Tout_C'])]
    test['B_MEAN']=params['B_MEAN_W'];test['B_COP']=[r['B_COP_W'] for r in values];test['M_TEMP']=[r['M_TEMP_W'] for r in values]
    test['outside_training_input_range']=[r['outside_training_input_range'] for r in values]
    test['negative_temperature_corrected_estimate']=[r['negative_temperature_corrected_estimate'] for r in values]
    grouped={'all':metrics(test),'Q_ge1kW':metrics(test[test['Q_kW']>=1]),'Q_lt1kW':metrics(test[test['Q_kW']<1])}
    files=[{'file':name,'OAT_F':int(d['OAT_F'].iloc[0]),**metrics(d)} for name,d in test.groupby('file',sort=True)]
    equal={m:{k:float(np.mean([f[m][k] for f in files])) for k in ('MAE_W','RMSE_W')} for m in ('B_MEAN','B_COP','M_TEMP')}
    success=all(grouped[g]['M_TEMP_double_improves_B_COP'] for g in ('all','Q_ge1kW')) and all(f['M_TEMP_double_improves_B_COP'] for f in files)
    worst={m:test.iloc[np.argsort(-abs(test[m].to_numpy()-test['target_total_W'].to_numpy()))[:10]].to_dict(orient='records') for m in ('B_MEAN','B_COP','M_TEMP')}
    dump(out/'calibration.json',{'parameters':params,'fit_diagnostics':fits,'interpretation':'Same-record statistical mapping; intercept/slopes not physical COP/firm bounds.'})
    dump(out/'metrics.json',{'groups':grouped,'files':files,'equal_file_mean_metrics':equal});dump(out/'worst_errors.json',worst)
    test.to_csv(out/'predictions.csv',index=False,float_format='%.17g')
    summary={'date':'2026-10-16','protocol_sha256':sha(pp),'admission_sha256':sha(prep/'admission.json'),
      'training_rows':len(train),'test_rows':len(test),'training_files':3,'test_files':2,'same_physical_AC_devices':1,
      'all':grouped['all'],'Q_ge1kW':grouped['Q_ge1kW'],'files':files,'equal_file_mean_metrics':equal,
      'outside_training_input_range_rows':sum(r['outside_training_input_range'] for r in values),
      'negative_M_TEMP_estimates':sum(r['negative_temperature_corrected_estimate'] for r in values),
      'predeclared_relative_success':bool(success),'scope':'Thermal-Q/ambient-conditioned same-record electric-power mapping on one HIL AC, not chronological forecasting/dispatch or available power capacity.',
      'no_posthoc_tuning':True}
    dump(out/'summary.json',summary);dump(out/'receipt.json',{'status':'completed','runner_sha256':sha(Path(__file__)),
      'kernel_sha256':sha(BASE/'hil_power_kernel.py'),'numpy':np.__version__,'pandas':pd.__version__,
      'outputs':{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();assert Path(a.run_id).name==a.run_id
    out=BASE/'runs'/a.run_id;out.mkdir(parents=True,exist_ok=False)
    try:execute(out)
    except Exception as e:dump(out/'failure.json',{'error':repr(e)});raise
