from common import *
P=ROOT/'work/b1_effective_gate_20261102'
rows=[]; examples=[]
for stage in ['main_test','weak_test']:
    facts={c['task_id']:c for c in read(P/stage/'facts.json')}
    curves={c['task_id']:c['results'] for c in read(P/stage/'curves.json')}
    truth={}
    for panel in ['minute','10s']:
        for name in ['truth.json','mixed_truth.json']:truth.update({t['task_id']:t for t in read(P/stage/panel/name)})
    mm=read(P/stage/'metrics.json'); before={r['task_id']:r for r in mm if r['method']=='retained'}
    for r in mm:
        if r['method']!='candidate':continue
        c=facts[r['task_id']];s=np.array(c['starts_s']);use=(s>=0)&(s<1800);y=np.array(c['reference_kw'])-np.array(c['power_kw']);clean=np.array(truth[r['task_id']]['true_reduction_kw']);med=float(np.median(y[use]));pk=float(max(clean[use]))
        category='quiet' if med<=.075 else 'sustained_weak' if med<.20 else 'strong'
        row=dict(r,stage=stage,raw_median=med,latent_peak=pk,median_category=category,prior_gap_c=before[r['task_id']]['predicted_cumulative_seconds'],cp_positive=any(np.array(curves[r['task_id']]['cpop']['prediction'])[use]>=.15))
        rows.append(row)
        if r['null_false_positive']:examples.append(row)
def count(rr):return dict(n=len(rr),fp=sum(r['null_false_positive'] for r in rr),whole_miss=sum(r['whole_miss'] for r in rr),true_positive=sum(r['positive_truth'] for r in rr),genuine_short=sum(r['genuine_short_n'] for r in rr),fp_no_physical=sum(r['null_false_positive'] and r['physical_no_action'] for r in rr),fp_weak_physical=sum(r['null_false_positive'] and not r['physical_no_action'] for r in rr))
out=dict(all=count(rows))
for key in ['condition','kind','median_category','panel']:
    out['by_'+key]={str(k):count([r for r in rows if r[key]==k]) for k in sorted({r[key] for r in rows})}
out['sustained_weak_duration_caps']={str(cap):count([r for r in rows if r['median_category']=='sustained_weak' and r['prior_gap_c']<=cap]) for cap in [60,180,600,1800]}
out['quiet_by_condition']={k:count([r for r in rows if r['median_category']=='quiet' and r['condition']==k]) for k in sorted({r['condition'] for r in rows})}
out['false_score_quantiles']=dict(zip(['min','q25','median','q75','max'],np.quantile([r['effective_score'] for r in examples],[0,.25,.5,.75,1]).tolist()))
write('diagnosis.json',out);write('false_examples.json',examples)
write('protected_before.json',{p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts})
print(json.dumps(native(out)),flush=True)
