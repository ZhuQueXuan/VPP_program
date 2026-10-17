"""Frozen small per-room ARX vs persistence/trend; no test-set tuning."""
from common import *
import sys,argparse,math
sys.path.insert(0,str(ROOT/'work/python_packages/pv_metadata_20261015'))
import duckdb,numpy as np,pandas as pd

def design(a):
    heat=(a['state']==1)&(a['mode']==1);cool=(a['state']==1)&(a['mode']==2)
    diff=a['setpoint']-a['temp']
    return np.column_stack([np.ones(len(diff)),a['temp']-a['prev_temp'],heat*diff,cool*diff,heat,cool])
def metrics(d):
    out={'rows':len(d)}
    for model in ('B_P','B_TREND','M_ARX'):
        err=d[model].to_numpy()-d['target_temp'].to_numpy()
        out[model]={'MAE_C':float(np.mean(abs(err))),'RMSE_C':float(np.sqrt(np.mean(err**2))),
                    'bias_C':float(np.mean(err)),'max_abs_error_C':float(np.max(abs(err)))}
    out['ARX_improves_both_vs_persistence']=all(out['M_ARX'][k]<out['B_P'][k] for k in ('MAE_C','RMSE_C'))
    return out
def execute(out):
    pp=BASE/'temperature_protocol_v1.json';assert sha(pp)==load(BASE/'temperature_freeze_v1.json')['protocol_sha256']
    prep=BASE/'runs/PREP_TEMPERATURE_01';ad=load(prep/'admission.json')
    for n,h in ad['outputs'].items():assert sha(prep/n)==h,n
    con=duckdb.connect();con.execute("SET memory_limit='768MB'");con.execute('SET threads=2')
    rows=load(prep/'room_coverage.json');params=[];frames=[]
    for room in rows:
        if not room['admitted_room']:continue
        a=con.execute("SELECT * FROM read_parquet(?) WHERE block=? AND room=? AND quality_admitted AND admitted_room ORDER BY origin_ms",[str(prep/'all_candidates.parquet'),room['block'],room['room']]).fetchnumpy()
        train=a['split']=='training';test=a['split']=='test';X=design(a);y=a['target_temp']-a['temp']
        beta,residuals,rank,singular=np.linalg.lstsq(X[train],y[train],rcond=1e-12)
        params.append({'block':room['block'],'room':room['room'],'train_rows':int(train.sum()),'test_rows':int(test.sum()),
          'beta':beta.tolist(),'rank':int(rank),'singular_values':singular.tolist(),'fit':'OLS rcond1e-12; no test labels'})
        d={k:a[k][test] for k in ('block','room','sensor_id','hvac_id','srcrow','prev_ms','origin_ms','target_ms','hvac_ms','prev_temp','temp','target_temp','state','mode','setpoint')}
        d['B_P']=a['temp'][test];d['B_TREND']=2*a['temp'][test]-a['prev_temp'][test]
        d['M_ARX']=a['temp'][test]+X[test]@beta
        frames.append(pd.DataFrame(d))
    df=pd.concat(frames,ignore_index=True);df['month']=pd.to_datetime(df['origin_ms'],unit='ms',utc=True).dt.strftime('%Y-%m')
    df['state_group']=np.where(df['state']==0,'off',np.where(df['mode']==1,'on_heating','on_cooling'))
    calibration={'feature_order':['intercept','delta_previous_temperature','heating_on_setpoint_gap','cooling_on_setpoint_gap','heating_on','cooling_on'],
      'rooms':params,'limits':'Statistical one-step coefficients; not physical thermal parameters, causal control effects, COP or capacity.'}
    dump(out/'calibration.json',calibration)
    groups={'all':metrics(df),'on':metrics(df[df['state']==1]),'off':metrics(df[df['state']==0])}
    for key,g in df.groupby('state_group'):groups['state:'+key]=metrics(g)
    for key,g in df.groupby('month'):groups['month:'+key]=metrics(g)
    room_results=[{'block':block,'room':room,**metrics(g)} for (block,room),g in df.groupby(['block','room'])]
    equal={model:{k:float(np.mean([r[model][k] for r in room_results])) for k in ('MAE_C','RMSE_C')} for model in ('B_P','B_TREND','M_ARX')}
    improved=sum(r['ARX_improves_both_vs_persistence'] for r in room_results)
    success=groups['all']['ARX_improves_both_vs_persistence'] and groups['on']['ARX_improves_both_vs_persistence'] and all(equal['M_ARX'][k]<equal['B_P'][k] for k in ('MAE_C','RMSE_C')) and improved>=len(room_results)/2
    dump(out/'metrics.json',{'groups':groups,'room_equal_mean_metrics':equal,'rooms':room_results})
    worst={}
    for m in ('B_P','B_TREND','M_ARX'):
        idx=np.argsort(-abs(df[m].to_numpy()-df['target_temp'].to_numpy()))[:10]
        worst[m]=df.iloc[idx].to_dict(orient='records')
    dump(out/'worst_errors.json',worst)
    # DuckDB1.4 predates pandas3 StringDtype; explicit Python objects preserve text.
    for col in ('block','room','month','state_group'):df[col]=df[col].astype(object)
    con.register('predictions',df);con.execute("COPY predictions TO '"+str(out/'predictions.parquet').replace('\\','/')+"' (FORMAT PARQUET,COMPRESSION ZSTD)")
    summary={'date':'2026-10-16','protocol_sha256':sha(pp),'admission_sha256':sha(prep/'admission.json'),
      'training_rows':sum(r['train_rows'] for r in params),'test_rows':len(df),'rooms':len(params),'parameters':6*len(params),
      'all':groups['all'],'on':groups['on'],'room_equal_mean_metrics':equal,'rooms_double_improved':improved,
      'predeclared_relative_success':bool(success),'scope':'Next original approximately10minute temperature under last recorded state availability, same36rooms/site; not control-response or electrical capacity validation.',
      'failures_retained':True,'no_posthoc_tuning':True}
    dump(out/'summary.json',summary)
    dump(out/'receipt.json',{'status':'completed','script_sha256':sha(Path(__file__)),'numpy':np.__version__,'duckdb':duckdb.__version__,
      'outputs':{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();assert Path(a.run_id).name==a.run_id
    out=BASE/'runs'/a.run_id;out.mkdir(parents=True,exist_ok=False)
    try:execute(out)
    except Exception as e:dump(out/'failure.json',{'error':repr(e)});raise
