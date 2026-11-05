"""Descriptive post-test calibration by training-defined history strata."""
import csv,json,numpy as np
from prepare import HERE,save

with (HERE/'features_peak_history.csv').open(encoding='utf-8-sig',newline='') as f:
    h=list(csv.DictReader(f))
edges=np.quantile([float(r['mean_peak_history_kwh']) for r in h if r['split']=='train'],[.25,.5,.75])
key=lambda r:(r['ID'],r['Date'],r['Group'])
lookup={key(r):float(r['mean_peak_history_kwh']) for r in h if r['split']=='test'}
with (HERE/'test_predictions.csv').open(encoding='utf-8',newline='') as f:
    pred=list(csv.DictReader(f))
d=json.loads((HERE/'decision.json').read_text(encoding='utf-8'));names=[d['selected'][k] for k in ('reference','candidate')]
y=np.array([float(r['actual_peak_2h_kwh']) for r in pred]);groups=np.searchsorted(edges,[lookup[key(r)] for r in pred],side='right')
out=[]
for i in range(4):
    keep=groups==i
    res={n:np.array([float(r[n]) for r in pred])[keep]-y[keep] for n in names}
    out.append(dict(history_quartile=i+1,n=int(keep.sum()),results={n:dict(bias=float(a.mean()),rmse=float(np.sqrt(np.mean(a*a)))) for n,a in res.items()}))
assert sum(r['n'] for r in out)==2419
save(HERE/'history_bias_diagnostic.json',dict(cuts_source='train-only mean matched peak history quartiles',cuts_kwh=edges.tolist(),
    strata=out,descriptive_only=True,used_for_fit_or_selection=False))
print(json.dumps(out))
