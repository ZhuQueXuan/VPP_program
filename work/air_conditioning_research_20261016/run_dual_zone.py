"""One frozen chronological5min comparison, no test-driven changes."""
from common import *
from dual_zone_kernel import predict_temperature,FEATURES
import argparse,numpy as np,pandas as pd
def metrics(d):
    obj={'rows':len(d)}
    for m in ('B_P','B_TREND','M_HEAT5'):
        e=d[m].to_numpy()-d['target_T_C'].to_numpy()
        obj[m]={'MAE_C':float(np.mean(abs(e))),'RMSE_C':float(np.sqrt(np.mean(e*e))),'bias_C':float(np.mean(e)),'max_abs_C':float(np.max(abs(e)))} if len(d) else {k:None for k in ['MAE_C','RMSE_C','bias_C','max_abs_C']}
    obj['improves_both_baselines']=bool(len(d)) and all(obj['M_HEAT5'][k]<obj[b][k] for b in ['B_P','B_TREND'] for k in ['MAE_C','RMSE_C'])
    return obj
def execute(out):
    pp=BASE/'dual_zone_protocol_v1.json';assert sha(pp)==load(BASE/'dual_zone_freeze_v1.json')['protocol_sha256'];p=load(pp)
    prep=BASE/'runs/PREP_DUAL_ZONE_01';ad=load(prep/'admission.json');assert ad['protocol_sha256']==sha(pp)
    for n,h in ad['outputs'].items():assert sha(prep/n)==h
    for r in p['sources'].values():assert sha(ROOT/r['path'])==r['sha256']
    d=pd.read_csv(prep/'candidates.csv');d=d[d['admitted']].copy();train=d[d['split']=='training'];test=d[d['split']=='test'].copy()
    params={'rooms':{},'feature_order':['constant','previous_temperature_increment','outdoor_minus_room_C','same_room_power_kW','other_room_minus_room_C'],'scope':p['information_time']};fits={}
    for zone,t in train.groupby('zone'):
        now=t['T_now_C'].to_numpy();X=np.column_stack([np.ones(len(t)),now-t['T_prev_C'].to_numpy(),t['Tout_C'].to_numpy()-now,t['P_now_W'].to_numpy()/1000.,t['T_other_C'].to_numpy()-now]);y=t['target_T_C'].to_numpy()-now
        w=1/t.groupby('file')['file'].transform('size').to_numpy();root=np.sqrt(w)
        beta,res,rank,s=np.linalg.lstsq(X*root[:,None],y*root,rcond=1e-12)
        params['rooms'][str(zone)]={'coefficients':beta.tolist(),'input_ranges':{k:[float(t[k].min()),float(t[k].max())] for k in FEATURES},'fit_weight':'equal whole training file total weight'}
        fits[str(zone)]={'rows':len(t),'rank':int(rank),'singular_values':s.tolist()}
    estimates=[predict_temperature({k:float(r[k]) for k in FEATURES},int(r['zone']),params) for r in test.to_dict(orient='records')]
    for m in ['B_P','B_TREND','M_HEAT5']:test[m]=[r[m+'_C'] for r in estimates]
    test['outside_training_input_range']=[r['outside_training_input_range'] for r in estimates]
    groups={'all':metrics(test),'current_positive_P':metrics(test[test['P_now_W']>0]),'current_zero_P':metrics(test[test['P_now_W']==0])}
    rooms=[{'zone':int(k),**metrics(t)} for k,t in test.groupby('zone')]
    days=[{'day':int(k),'date':t['timestamp'].iloc[0][:10],**metrics(t)} for k,t in test.groupby('day')]
    dailyroom=[{'day':int(k[0]),'zone':int(k[1]),**metrics(t)} for k,t in test.groupby(['day','zone'])]
    passed=groups['all']['improves_both_baselines'] and groups['current_positive_P']['improves_both_baselines'] and all(r['improves_both_baselines'] for r in rooms) and sum(r['improves_both_baselines'] for r in days)>=2
    worst={m:test.iloc[np.argsort(-abs(test[m].to_numpy()-test['target_T_C'].to_numpy()))[:10]].to_dict(orient='records') for m in ['B_P','B_TREND','M_HEAT5']}
    dump(out/'calibration.json',{'parameters':params,'fits':fits});dump(out/'metrics.json',{'groups':groups,'rooms':rooms,'days':days,'daily_rooms':dailyroom});dump(out/'worst.json',worst)
    test.to_csv(out/'predictions.csv',index=False,float_format='%.17g')
    summary={'protocol_sha256':sha(pp),'admission_sha256':sha(prep/'admission.json'),'training_rows':len(train),'test_rows':len(test),'fitted_parameters':10,'groups':groups,'rooms':rooms,'days':days,'out_of_training_range_rows':int(test['outside_training_input_range'].sum()),'predeclared_relative_success':bool(passed),'scope':p['information_time'],'not_paper_MPC_reproduction':True}
    dump(out/'summary.json',summary);dump(out/'receipt.json',{'status':'completed','runner_sha256':sha(Path(__file__)),'kernel_sha256':sha(BASE/'dual_zone_kernel.py'),'numpy':np.__version__,'pandas':pd.__version__,'outputs':{f.name:sha(f) for f in sorted(out.iterdir()) if f.is_file()}})
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();assert Path(a.run_id).name==a.run_id;out=BASE/'runs'/a.run_id;out.mkdir(exist_ok=False)
    try:execute(out)
    except Exception as e:dump(out/'failure.json',{'error':repr(e)});raise
