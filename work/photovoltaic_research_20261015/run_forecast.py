"""Frozen AR2 versus persistence and trend; June fit, July one-step forecasts."""
from pathlib import Path
import argparse,csv,hashlib,json,math,platform,sys
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
sys.path.insert(0,str(ROOT/'work/teacher_storage_brief_20261014/plot_dependencies'))
import numpy as np
MODELS=('B_P','B_T','M_AR2')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def table(p,rows):
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def scores(rows,m):
    if not rows:return {'n':0}
    e=[r[m]-r['target_W'] for r in rows];a=sorted(abs(v) for v in e)
    mae=math.fsum(a)/len(a);rmse=math.sqrt(math.fsum(v*v for v in e)/len(e));i=max(range(len(rows)),key=lambda i:abs(e[i]))
    return {'n':len(rows),'mae_W':mae,'rmse_W':rmse,'bias_W':math.fsum(e)/len(e),
            'p95_abs_W':a[math.ceil(.95*len(a))-1],'max_abs_W':a[-1],
            'worst_target_time':rows[i]['target_time'],'worst_origin_time':rows[i]['origin_time'],
            'worst_target_W':rows[i]['target_W'],'worst_prediction_W':rows[i][m],
            'negative_predictions':sum(r[m]<0 for r in rows),
            'mae_div_DC_nameplate':mae/20160,'rmse_div_DC_nameplate':rmse/20160}
def execute(out):
    path=BASE/'forecast_protocol_v1.json';p=json.loads(path.read_text(encoding='utf-8'))
    assert sha(path)==json.loads((BASE/'forecast_freeze_receipt_v1.json').read_text())['protocol_sha256']
    for s in p['sources']:assert sha(ROOT/s['path'])==s['sha256']
    source=ROOT/p['sample_file'];assert sha(source)==p['sample_sha256']
    assert sha(ROOT/p['source_qa_file'])==p['source_qa_sha256']
    dump(out/'protocol_snapshot.json',p)
    with source.open(encoding='utf-8',newline='') as f:samples=list(csv.DictReader(f))
    admitted=[]
    for r in samples:
        if r['status']!='admitted':continue
        admitted.append({**r,**{k:float(r[k]) for k in ('target_W','origin_W','lag_W')}})
    fit=[r for r in admitted if r['split']=='fit']
    assert all(r['target_time']<'2019-07-01 00:00:00' for r in fit)
    X=np.array([[1,r['origin_W']/1000,r['lag_W']/1000] for r in fit]);y=np.array([r['target_W']/1000 for r in fit])
    b,residuals,rank,singular=np.linalg.lstsq(X,y,rcond=None)
    assert rank==3 and np.isfinite(b).all()
    coeff={'intercept_kW':float(b[0]),'current_weight':float(b[1]),'previous_weight':float(b[2]),
           'fit_samples':len(fit),'rank':int(rank),'singular_values':singular.tolist(),
           'max_fit_target_time':max(r['target_time'] for r in fit),'coefficient_update':'none after June'}
    dump(out/'coefficients.json',coeff)
    predictions=[]
    for r in admitted:
        pred={**r,'B_P':r['origin_W'],'B_T':2*r['origin_W']-r['lag_W'],
              'M_AR2':float(1000*(b[0]+b[1]*r['origin_W']/1000+b[2]*r['lag_W']/1000))}
        assert all(math.isfinite(pred[m]) for m in MODELS)
        predictions.append(pred)
    table(out/'predictions.csv',predictions)
    metrics={};daily=[]
    for split in ('fit','evaluation'):
        rr=[r for r in predictions if r['split']==split]
        groups={'all':rr,'origin_ge1000W':[r for r in rr if r['origin_W']>=1000],
                'origin_lt1000W':[r for r in rr if r['origin_W']<1000],
                'target_change_ge2016W':[r for r in rr if abs(r['target_W']-r['origin_W'])>=2016]}
        metrics[split]={group:{m:scores(rows,m) for m in MODELS} for group,rows in groups.items()}
        for date in sorted({r['target_time'][:10] for r in rr}):
            rows=[r for r in rr if r['target_time'].startswith(date)]
            for m in MODELS:daily.append({'date':date,'split':split,'model':m,**scores(rows,m)})
    dump(out/'metrics.json',metrics);table(out/'daily_metrics.csv',daily)
    a=metrics['evaluation']['all'];high=metrics['evaluation']['origin_ge1000W']
    dailywins=[]
    for date in sorted({r['date'] for r in daily if r['split']=='evaluation'}):
        d={r['model']:r for r in daily if r['date']==date}
        dailywins.append({'date':date,'n':d['B_P']['n'],'MAE_improves':d['M_AR2']['mae_W']<d['B_P']['mae_W'],
                          'RMSE_improves':d['M_AR2']['rmse_W']<d['B_P']['rmse_W']})
    summary={'object':p['object'],'forecast_scope':'Offline next15-minute published label, current/lag records assumed available; no future weather',
             'sample_counts':{'fit':len(fit),'evaluation':len(predictions)-len(fit)},'coefficients':coeff,
             'evaluation_all':a,'evaluation_origin_ge1000W':high,
             'AR2_skill_vs_persistence':{k:1-a['M_AR2'][k]/a['B_P'][k] for k in ('mae_W','rmse_W')},
             'positive_candidate_criterion':all(a['M_AR2'][k]<a['B_P'][k] for k in ('mae_W','rmse_W')),
             'daily_comparison':dailywins,'not_validated':p['not_validated']}
    dump(out/'summary.json',summary)
    dump(out/'receipt.json',{'status':'completed','python':platform.python_version(),'numpy':np.__version__,
                           'script_sha256':sha(Path(__file__)),'protocol_sha256':sha(path),
                           'outputs':{f.name:sha(f) for f in sorted(out.iterdir())}})
    print(json.dumps({k:v for k,v in summary.items() if k!='daily_comparison'},ensure_ascii=False,indent=2))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();assert Path(a.run_id).name==a.run_id
    out=BASE/'runs'/a.run_id;out.mkdir(parents=True,exist_ok=False)
    try:execute(out)
    except Exception as e:dump(out/'failure.json',{'error':repr(e)});raise
if __name__=='__main__':main()
