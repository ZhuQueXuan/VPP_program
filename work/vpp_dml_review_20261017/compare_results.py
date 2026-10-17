"""Compare rerun numeric outputs with delivered outputs; ignore timing only."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
SOURCE=HERE/'vpp_dml_framework/results'
RUN=HERE/'run_full_repaired/results'

def main():
    receipt=json.loads((HERE/'full_repaired_run_receipt.json').read_text(encoding='utf-8'))
    if receipt.get('returncode')!=0: raise RuntimeError('full run not completed successfully')
    records=[]
    for p in sorted(SOURCE.glob('*.csv')):
        if p.name.startswith('coverage_'): continue
        a=pd.read_csv(p); b=pd.read_csv(RUN/p.name)
        rec={'file':p.name,'same_shape':a.shape==b.shape,'same_columns':a.columns.tolist()==b.columns.tolist()}
        numeric=[]; categorical=[]
        if rec['same_shape'] and rec['same_columns']:
            for col in a:
                if col=='runtime_s': continue
                if pd.api.types.is_numeric_dtype(a[col]) and pd.api.types.is_numeric_dtype(b[col]):
                    x=a[col].to_numpy(float); y=b[col].to_numpy(float)
                    ok=np.allclose(x,y,atol=1e-8,rtol=1e-6,equal_nan=True)
                    valid=np.isfinite(x)&np.isfinite(y)
                    numeric.append({'column':col,'allclose':bool(ok),'max_abs_diff':float(np.max(np.abs(x[valid]-y[valid]))) if valid.any() else 0})
                else:
                    categorical.append({'column':col,'equal':bool(a[col].fillna('<NA>').equals(b[col].fillna('<NA>')))})
        rec['numeric']=numeric;rec['other']=categorical
        rec['allclose']=rec['same_shape'] and rec['same_columns'] and all(c['allclose'] for c in numeric) and all(c['equal'] for c in categorical)
        records.append(rec)
    original=json.loads((SOURCE/'summary.json').read_text(encoding='utf-8'))
    rerun=json.loads((RUN/'summary.json').read_text(encoding='utf-8'))
    def flatten(x,prefix=''):
        out={}
        if isinstance(x,dict):
            for k,v in x.items(): out.update(flatten(v,prefix+'/'+k))
        elif isinstance(x,list):
            for k,v in enumerate(x):out.update(flatten(v,prefix+'/'+str(k)))
        else:out[prefix]=x
        return out
    a,b=flatten(original),flatten(rerun)
    summary=[]
    for k,x in a.items():
        y=b.get(k)
        ok=np.isclose(x,y,atol=1e-8,rtol=1e-6) if isinstance(x,(int,float)) and not isinstance(x,bool) else x==y
        summary.append({'path':k,'equal':bool(ok),'original':x,'rerun':y})
    report={'tolerance':{'atol':1e-8,'rtol':1e-6},'excluded':['runtime_s'],
            'csv':records,'summary_json':summary,
            'all_csv_within_tolerance':all(r['allclose'] for r in records),
            'summary_within_tolerance':all(r['equal'] for r in summary),
            'coverage_new_repetitions':0,'repair':receipt['repair'], 'elapsed_s':receipt['elapsed_s']}
    (HERE/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    metrics=pd.read_csv(RUN/'benchmark.csv')
    cols=['method','nrmse_tau_up','nrmse_tau_down','nrmse_th_C','response_bias_event_pct','cluster_ari']
    metrics[cols].to_csv(HERE/'comparison_key_metrics.csv',index=False,encoding='utf-8-sig')
    print(json.dumps({k:v for k,v in report.items() if k not in ['csv','summary_json']},ensure_ascii=False))
    print(metrics[cols].to_string(index=False))
    for r in records:
        print(r['file'],r['allclose'],[(x['column'],x['max_abs_diff']) for x in r['numeric'] if not x['allclose']])

if __name__=='__main__':main()
