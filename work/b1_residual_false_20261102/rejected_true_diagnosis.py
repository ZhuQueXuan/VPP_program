from common import *
from model import extra_features
stage='weak_confirmation';rows=read(stage+'/metrics.json');bad=[r for r in rows if r['method']=='candidate' and r['rejected_positive_truth']];facts={c['task_id']:c for c in read(stage+'/facts.json')};curves={r['task_id']:r['results'] for r in read(stage+'/curves.json')};truth={};X=np.load(HERE/stage/'effective_X.npy');cases=read(stage+'/facts.json');index={c['task_id']:i for i,c in enumerate(cases)};out=[]
for panel in ['minute','10s']:
    for name in ['truth.json','mixed_truth.json']:truth.update({r['task_id']:r for r in read(stage+'/'+panel+'/'+name)})
for r in bad:
    c=facts[r['task_id']];t=truth[c['task_id']];s=np.array(c['starts_s']);dt=c['ends_s'][0]-s[0];use=(s>=0)&(s<1800);clean=np.array(t['true_reduction_kw']);raw=np.array(c['reference_kw'])-np.array(c['power_kw']);cp=np.array(curves[c['task_id']]['cpop']['prediction']);target=use&(clean>=.15);before=next(v for v in rows if v['task_id']==r['task_id'] and v['method']=='retained')
    out.append(dict(metric=r,before=before,latent_peak_kw=max(clean[use]),observed_median_kw=float(np.median(raw[use])),true_effective_positions_seconds=s[target],true_effective_raw=raw[target],true_effective_cpop=cp[target],
        original_CPOP_true_location_hit=bool(np.any(cp[target]>=.15)),raw_true_location_hit=bool(np.any(raw[target]>=.15)),
        inferred_cause='Whole-task qualifier falsely negative for an oscillatory/weak history; original location already missed. Not deletion or minimum-short-duration suppression; whole-task miss is nevertheless new and counted.',
        selected_model_sha256=sha(HERE/'verifier31.json'),feature_vector=X[index[c['task_id']]]))
write('rejected_true_diagnosis.json',out);print(json.dumps(native([{k:v for k,v in item.items() if k not in ['feature_vector','true_effective_positions_seconds','true_effective_raw','true_effective_cpop']} for item in out])),flush=True)
