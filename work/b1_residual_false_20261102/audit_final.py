from common import *
train=read('training_receipt.json');seen=set(train['source_ledger']);validation=set();records=[];checks=0;coverage=[]
for stage in ['main_validation','weak_validation']:validation.update(c['task_id'] for c in read(stage+'/facts.json'))
confirmation=len(sys.argv)>1 and sys.argv[1]=='confirmation'
if confirmation:
    for stage in ['main_test','weak_test']:validation.update(c['task_id'] for c in read(stage+'/facts.json'))
for stage in (['main_confirmation','weak_confirmation'] if confirmation else ['main_test','weak_test']):
    cases=read(stage+'/facts.json');truth={};curves={r['task_id']:r['results'] for r in read(stage+'/curves.json')};rows=read(stage+'/metrics.json');rr={(r['task_id'],r['method']):r for r in rows}
    assert len(rr)==4*len(cases)
    for panel in ['minute','10s']:
        for name in ['truth.json','mixed_truth.json']:truth.update({r['task_id']:r for r in read(HERE/stage/panel/name)})
    gaussian={c['base_task_id']:c for c in cases if c['condition']=='gaussian'}
    for c in cases:
        tid=c['task_id'];assert tid not in seen and tid not in validation
        g=gaussian[c['base_task_id']];t=truth[tid];gt=truth[g['task_id']]
        assert np.array_equal(t['true_reduction_kw'],gt['true_reduction_kw'])
        y=np.array(c['reference_kw'])-np.array(c['power_kw']);gy=np.array(g['reference_kw'])-np.array(g['power_kw']);a=np.zeros(len(y));a[np.asarray(t.get('injected_indices',[]),int)]=t.get('injected_residual_additions_kw',[])
        assert max(abs(y-gy-a))<1e-12
        before=rr[tid,'retained'];after=rr[tid,'candidate']
        if not after['rejected']:assert all(before[k]==after[k] for k in ['predicted_cumulative_seconds','predicted_longest_seconds','localized_miss','positive_prediction'])
        else:assert before['positive_prediction'] and not after['positive_prediction']
        s=np.asarray(c['starts_s']);use=(s>=0)&(s<1800);raw_med=float(np.median(y[use]));records.append(dict(task_id=tid,base_task_id=c['base_task_id'],seed=c['seed'],panel=c['panel'],condition=c['condition'],quiet=raw_med<=.075,rejected=after['rejected'],physical_no_action=after['physical_no_action'],positive_truth=after['positive_truth']))
        checks+=1
    if stage.startswith('weak_'):
      for panel in ['minute','10s']:
        recipe={r['task_id']:r for r in read(stage+'/'+panel+'/generation_recipe.json')}
        for seed in sorted({c['seed'] for c in cases}):
          for kind in sorted({c['kind'] for c in cases if c['panel']==panel}):
            selected=[c for c in cases if c['panel']==panel and c['seed']==seed and c['kind']==kind and c['condition']=='gaussian'];requested=[recipe[c['task_id']]['requested_peak'] for c in selected]
            assert len(selected)==6 and sorted(int((v-.07)/(.23/6)) for v in requested)==list(range(6));coverage.append(dict(panel=panel,seed=seed,kind=kind,peaks=requested))
out=dict(tasks_checked=checks,all_final_ids_excluded_from_training_and_validation=True,paired_noise_and_truth_exact=True,raw_points_unchanged=True,weak_shape_seed_strata_groups=len(coverage),
    rejected=sum(r['rejected'] for r in records),rejected_quiet=sum(r['rejected'] and r['quiet'] for r in records),rejected_sustained_weak=sum(r['rejected'] and not r['quiet'] for r in records),
    rejected_no_physical_action=sum(r['rejected'] and r['physical_no_action'] for r in records),rejected_weak_physical=sum(r['rejected'] and not r['physical_no_action'] for r in records),
    newly_rejected_true_tasks=sum(r['rejected'] and r['positive_truth'] for r in records),true_effective_duration_values_unchanged=not any(r['rejected'] and r['positive_truth'] for r in records),
    per_seed={str(seed):dict(rejected=sum(r['rejected'] for r in records if r['seed']==seed),new_true_reject=sum(r['rejected'] and r['positive_truth'] for r in records if r['seed']==seed)) for seed in sorted({r['seed'] for r in records})})
write('confirmation_audit.json' if confirmation else 'final_audit.json',out);write('confirmation_coverage.json' if confirmation else 'coverage.json',coverage);print(json.dumps(out),flush=True)
