"""Independent aggregation/CI and runtime-query parity after prediction freeze."""
import copy,math
import numpy as np
from scipy.stats import t
from io_utils import BASE,RAW,read,write,sha
from api import predict_with_history

def main():
    res=read(BASE/'results.json');rows=res['records'];checks=0
    for group,summary in res['summary'].items():
        rr=[v for v in rows if v['group']==group]
        for name,m in summary.items():
            for metric,value in m.items():
                values=[x[metric] for x in rr if x['method']==name];assert abs(sum(values)/20-value)<1e-12;checks+=1
        for pair,metrics in res['contrasts'][group].items():
            a,b=pair.split('-')
            for metric,receipt in metrics.items():
                aa=[v[metric] for v in rr if v['method']==a];bb=[v[metric] for v in rr if v['method']==b];d=[x-y for x,y in zip(aa,bb)];mean=sum(d)/20;se=math.sqrt(sum((v-mean)**2 for v in d)/19/20);c=t.ppf(.975,19)*se
                assert abs(mean-receipt['mean'])<1e-12 and max(abs(x-y) for x,y in zip([mean-c,mean+c],receipt['ci95']))<1e-12;assert sum(v<0 for v in d)==receipt['improved'];checks+=3
    raw=np.load(RAW/'observations.npz');d=np.load(BASE/'replicate_00.npz');selected=read(BASE/'selection.json')['selected'][0];maximum=0.
    # Fixed first eligible test rows, covering all three paired regimes; not error-selected.
    from datetime import datetime,timedelta
    start=datetime.fromisoformat('2026-10-01T00:00:00+08:00')
    for scene in range(3):
        ids=np.flatnonzero((d['split']==2)&d['eligible']&(d['scene']==scene))[:4]
        for row in ids:
            u=int(d['user'][row]);j=int(d['event'][row]);case=dict(resource_id=f'EV-{u}',event_id=f'event-{j}',start=(start+timedelta(minutes=180*j)).isoformat(),information_cutoff=(start+timedelta(minutes=180*j)).isoformat(),current={},history=[])
            for k in ['b','T','q','E','low','high','prob','reference','green_preference','green_attribute','risk','permission']:case['current'][k]=raw[k][0,u,j].item()
            for past in range(j-3,j):
                a=start+timedelta(minutes=180*past);end=a+timedelta(minutes=120);b=float(raw['b'][0,u,past]);T=float(raw['T'][0,u,past]);q=float(raw['q'][0,u,past]);case['history'].append(dict(resource_id=f'EV-{u}',event_id=f'event-{past}',start=a.isoformat(),observation_end=end.isoformat(),available_at=end.isoformat(),b=b,T=T,q=q,reference_kw=(b*(np.arange(120)<T)).tolist(),measured_kw=raw['power'][0,scene,u,past].tolist()))
            pred=predict_with_history(case);assert pred['status']=='ok',pred;err=float(abs(np.array(pred['six_outcome_probabilities'])-d['probabilities'][selected,row]).max());maximum=max(maximum,err);assert err<1e-11;checks+=6
            v=copy.deepcopy(case);v['history']=v['history'][:2];r=predict_with_history(v);assert r['history_method']=='C0' and np.allclose(r['six_outcome_probabilities'],d['probabilities'][0,row],atol=1e-11);checks+=1
    f=read(BASE/'source_freeze.json');from io_utils import ROOT
    for n,h in f['protected'].items():assert sha(ROOT/n)==h;checks+=1
    write(BASE/'supplement_checks.json',dict(status='passed',checks=checks,query_parity_cases=12,max_query_probability_difference=maximum,ci_aggregation='independent scalar mean/sample variance/t19',old_files_unchanged=len(f['protected'])))
    print('supplement passed',checks,flush=True)

if __name__=='__main__':main()
