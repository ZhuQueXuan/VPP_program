from common import *
P=ROOT/'work/b1_effective_gate_20261102';items=[]
for stage in ['main_test','weak_test']:
    rr=[r for r in read(P/stage/'metrics.json') if r['method']=='candidate'];gaussian={r['base_task_id']:r for r in rr if r['condition']=='gaussian'}
    assert len(gaussian)==len({r['base_task_id'] for r in rr})
    for r in rr:
        g=gaussian[r['base_task_id']]
        assert r['positive_truth']==g['positive_truth']
        if r['null_false_positive']:items.append(dict(task_id=r['task_id'],base_task_id=r['base_task_id'],condition=r['condition'],panel=r['panel'],already_false_without_contamination=g['null_false_positive']))
out=dict(false_tasks=len(items),false_with_contamination=sum(r['condition']!='gaussian' for r in items),
    contaminated_false_with_clean_pair_correct=sum(r['condition']!='gaussian' and not r['already_false_without_contamination'] for r in items),
    false_also_in_clean_pair=sum(r['already_false_without_contamination'] for r in items),
    note='Same latent trajectory and Gaussian noise paired, fixed additional simulated contamination. Attribution to comparison of these observed variants, not field-fault identification.')
write('paired_diagnosis.json',out);print(json.dumps(out),flush=True)
