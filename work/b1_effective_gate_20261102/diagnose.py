from common import *
PREVIOUS=ROOT/'work/b1_duration_joint_20261102';rows=[];facts={};truth={}
for stage in ['main_test','weak_test']:
    rows += [dict(r,stage=stage) for r in read(PREVIOUS/stage/'metrics.json') if r['method']=='candidate']
    facts.update({r['task_id']:r for r in read(PREVIOUS/stage/'facts.json')})
    for panel in ['minute','10s']:
        for name in ['truth.json','mixed_truth.json']:truth.update({r['task_id']:r for r in read(PREVIOUS/stage/panel/name)})
fp=[];cohorts={}
for r in rows:
    c=facts[r['task_id']];s=np.asarray(c['starts_s']);task=(s>=0)&(s<1800);y=np.asarray(c['reference_kw'])-np.asarray(c['power_kw']);peak=float(max(np.asarray(truth[r['task_id']]['true_reduction_kw'])[task]));median=float(np.median(y[task]))
    scope=.075<median<.20
    row=dict(r,raw_task_median_kw=median,latent_peak_kw=peak,physical_no_action=peak<=.04,potential_sustained_weak_scope=scope)
    if r['null_false_positive']:fp.append(row)
    cohorts.setdefault('scope' if scope else 'outside',[]).append(row)
def summarize(rr):return dict(n=len(rr),false=sum(r['null_false_positive'] for r in rr),positive=sum(r['positive_truth'] for r in rr),whole_miss=sum(r['whole_miss'] for r in rr),genuine_short=sum(r['genuine_short_n'] for r in rr),
    fp_physical_no_action=sum(r['null_false_positive'] and r['physical_no_action'] for r in rr),fp_real_underthreshold=sum(r['null_false_positive'] and not r['physical_no_action'] for r in rr))
summary=dict(all=summarize([r for rr in cohorts.values() for r in rr]),cohorts={k:summarize(v) for k,v in cohorts.items()},
    by_kind={k:summarize([r for rr in cohorts.values() for r in rr if r['kind']==k]) for k in sorted({r['kind'] for r in rows})},
    note='False effective response is not necessarily no physical action; scope variables are observed-only. Latent labels only diagnose.')
write('diagnosis.json',summary);write('false_examples.json',fp)
write('protected_before.json',{p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts})
print(json.dumps(native(summary)),flush=True)
