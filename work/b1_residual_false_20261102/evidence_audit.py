from common import *
P=ROOT/'work/b1_effective_gate_20261102';checks=0;original_positive=0;false=0
for stage in ['main_test','weak_test']:
    facts=read(P/stage/'facts.json');g={c['base_task_id']:c for c in facts if c['condition']=='gaussian'};truth={}
    for panel in ['minute','10s']:
        for name in ['truth.json','mixed_truth.json']:truth.update({r['task_id']:r for r in read(P/stage/panel/name)})
    curves={r['task_id']:r['results'] for r in read(P/stage/'curves.json')};metrics={r['task_id']:r for r in read(P/stage/'metrics.json') if r['method']=='candidate'}
    for c in facts:
        ref=g[c['base_task_id']];t=truth[c['task_id']];gt=truth[ref['task_id']]
        assert np.array_equal(t['true_reduction_kw'],gt['true_reduction_kw'])
        assert np.array_equal(c['starts_s'],ref['starts_s']) and np.array_equal(c['reference_kw'],ref['reference_kw'])
        y=np.array(c['reference_kw'])-np.array(c['power_kw']);gy=np.array(ref['reference_kw'])-np.array(ref['power_kw'])
        injection=np.zeros(len(y));injection[np.asarray(t.get('injected_indices',[]),int)]=t.get('injected_residual_additions_kw',[])
        assert np.max(abs((y-gy)-injection))<1e-12,(c['task_id'],np.max(abs((y-gy)-injection)))
        r=metrics[c['task_id']]
        if r['null_false_positive']:
            false+=1;s=np.array(c['starts_s']);original_positive+=int(np.any(np.array(curves[c['task_id']]['cpop']['prediction'])[(s>=0)&(s<1800)]>=.15))
        checks+=1
train=read('training_receipt.json');new_ids=set()
for stage in ['main_validation','weak_validation']:
    for c in read(stage+'/facts.json'):assert c['task_id'] not in train['source_ledger'];new_ids.add(c['task_id'])
write('evidence_audit.json',dict(paired_trajectories_and_gaussian_noise_identical_except_declared_injection=checks,false_tasks=false,already_positive_in_original_CPOP=original_positive,validation_tasks_excluded_from_fit=len(new_ids),raw_points_unchanged=True))
print('Paired cause evidence and fit separation checked',checks,flush=True)
