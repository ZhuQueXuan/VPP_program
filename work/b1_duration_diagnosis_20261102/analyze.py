"""Read-only attribution of adopted duration errors before changing extraction."""
import json,hashlib
from pathlib import Path
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;OLD=ROOT/'work/b1_local_rescue_v2_20261102'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows=[]
for stage in ['main_test','weak_test']:
    rows += [dict(r,stage=stage) for r in read(OLD/stage/'metrics.json') if r['method']=='candidate']
panels=sorted({r['panel'] for r in rows});weights={}
for panel in panels:
    conditions=sorted({r['condition'] for r in rows if r['panel']==panel})
    for cond in conditions:
        subset=[r for r in rows if r['panel']==panel and r['condition']==cond]
        for r in subset:weights[r['task_id']]=1/len(panels)/len(conditions)/len(subset)
for r in rows:
    tc,tl=r['true_cumulative_seconds'],r['true_longest_seconds'];pc,pl=r['predicted_cumulative_seconds'],r['predicted_longest_seconds']
    r['group']='no_effective_response' if tc==0 else 'whole_miss' if pc==0 else 'short_effective' if tc<=60 else 'long_effective'
    r['cumulative_signed_error']=pc-tc;r['longest_signed_error']=pl-tl
def summarize(rr):
    w=sum(weights[r['task_id']] for r in rr)
    return dict(n=len(rr),weight=w,weighted_duration_MAE_contribution=sum(weights[r['task_id']]*r['primary_seconds'] for r in rr),
        conditional_duration_MAE=sum(weights[r['task_id']]*r['primary_seconds'] for r in rr)/w,
        cumulative_contribution=sum(weights[r['task_id']]*abs(r['cumulative_signed_error']) for r in rr),
        longest_contribution=sum(weights[r['task_id']]*abs(r['longest_signed_error']) for r in rr),
        cumulative_over_contribution=sum(weights[r['task_id']]*max(r['cumulative_signed_error'],0) for r in rr),
        cumulative_under_contribution=sum(weights[r['task_id']]*max(-r['cumulative_signed_error'],0) for r in rr),
        longest_over_contribution=sum(weights[r['task_id']]*max(r['longest_signed_error'],0) for r in rr),
        longest_under_contribution=sum(weights[r['task_id']]*max(-r['longest_signed_error'],0) for r in rr))
summary={'overall':summarize(rows)}
for key in ['group','kind','condition','panel','stage']:
    summary[key]={v:summarize([r for r in rows if r[key]==v]) for v in sorted({r[key] for r in rows})}
top=sorted(rows,key=lambda r:weights[r['task_id']]*r['primary_seconds'],reverse=True)
protected={p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
for name,value in [('diagnosis.json',summary),('top_errors.json',top[:80]),('protected_sha256.json',protected)]:
    with (HERE/name).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
print(json.dumps(summary),flush=True)
