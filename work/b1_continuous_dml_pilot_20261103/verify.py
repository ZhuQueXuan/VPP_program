from common import *
import collections,math,csv
from data import population_curve
checks=collections.Counter()
for n,h in read(ROOT/'work/b1_residual_false_20261102/protected_before.json').items():assert sha(ROOT/n)==h,n;checks['formal_files_unchanged']+=1
for source,key in [('work/b1_first_block_close_20261103/completion_receipt.json','first_block_closed_artifacts_unchanged'),('work/b1_response_method_review_20261103/completion_receipt.json','literature_artifacts_unchanged')]:
    for n,h in read(ROOT/source)['artifact_sha256'].items():assert sha(ROOT/n)==h,n;checks[key]+=1
for name in ['protocol_freeze.json','freeze.json','endtoend/source_freeze.json']:
    for n,h in read(HERE/name)['files'].items():assert sha(ROOT/n)==h,n;checks['frozen_source_hashes']+=1
assert read(HERE/'technical_checks.json')['status']=='passed'
spec=read(HERE/'protocol.json');dev=read(HERE/'development/summary.json');final=read(HERE/'final/summary.json');e2e=read(HERE/'endtoend/summary.json');decision=read(HERE/'decision.json')
assert len(dev['baseline_entries'])==12 and len(final['entries'])==24 and len(final['weak_support'])==4
staged_users=collections.defaultdict(set);canonical_users=collections.defaultdict(set);stagefacts=collections.Counter();independent_metric_rows=[]
def compare_result(result,truth,stored,scenario):
    if result['status']!='ok':assert stored['status']=='unsupported' and stored['penalized_rmse_seconds']==1800.;return
    values=[float(v) for v in result['contrast_seconds']];target=[float(t-truth[0]) for t in truth];rmse=math.sqrt(sum((a-b)**2 for a,b in zip(values,target))/len(target));level=sum(abs(float(a)-float(b)) for a,b in zip(result['mean_seconds'],truth))/len(truth)
    assert math.isclose(rmse,stored['penalized_rmse_seconds'],abs_tol=1e-9);assert math.isclose(level,stored['level_mae_seconds'],abs_tol=1e-9);assert np.array_equal(result['grid'],GRID);assert values[0]==0.
    if scenario=='zero_effect':
        flag=any(float(v)>0 for v in result['inference']['lower']) or any(float(v)<0 for v in result['inference']['upper']);assert flag==stored['zero_effect_false_claim']
    if 'final_curve_clipped' in result:assert result['final_curve_clipped'] is False
    checks['independent_curve_scores']+=1
for stage,entries in [('development',dev['baseline_entries']),('final',final['entries'])]:
    for entry in entries:
        name=f'{entry["seed"]}_{entry["scenario"]}';facts=read(HERE/stage/'facts'/f'{name}.json');assert facts['stage']==stage
        x=np.asarray(facts['X']);d=np.asarray(facts['offered_incentive']);y=np.asarray(facts['outcome_seconds']);groups=np.asarray(facts['users']);assert len(y)==480 and x.shape==(480,2) and np.all((d>0)&(d<2.4)) and np.all((y>=0)&(y<=1800));assert np.array_equal(np.asarray(facts['raw_latent_fraction'])*1800,y)
        staged_users[stage].update(groups);canonical_users[stage].update((entry['seed'],u.rsplit('|',1)[-1]) for u in groups);stagefacts[stage]+=len(y)
        folder='baseline' if stage=='development' else 'results';record=read(HERE/stage/folder/f'{name}.json');truth=np.asarray(record['truth_seconds']);higher=population_curve(entry['scenario'],nodes=31);assert np.allclose(truth,higher,atol=1e-5,rtol=0)
        if entry['scenario']=='zero_effect':assert np.ptp(truth)<1e-9
        for method,result in record['results'].items():
            compare_result(result,truth,record['metrics'][method],entry['scenario'])
            if result['status']=='ok':
                folds=result['public_result']['audit']['fold_by_event'] if 'public_result' in result else result['fold_by_event'];folds=np.asarray(folds)
                for u in set(groups):assert np.unique(folds[groups==u]).size==1
                checks['grouped_fold_result_checks']+=1
        independent_metric_rows.append(dict(stage=stage,seed=entry['seed'],scenario=entry['scenario'],methods=record['metrics']))
assert not staged_users['development']&staged_users['final'];assert not canonical_users['development']&canonical_users['final']
# Development selection follows the declared criterion, not final data.
selection=read(HERE/'baseline_selection.json');means={m:np.mean([r['metrics'][m]['penalized_rmse_seconds'] for r in dev['baseline_entries']]) for m in ['existing_DR','continuous_DML']};assert selection['selected']==min(means,key=means.get)=='continuous_DML'
for method,summary in final['summary'].items():
    rr=[r['metrics'][method] for r in final['entries']];assert summary['planned']==len(rr) and summary['successful']==sum(r['status']=='ok' for r in rr);assert math.isclose(summary['primary_seconds'],sum(r['penalized_rmse_seconds'] for r in rr)/len(rr),abs_tol=1e-10)
for row in final['weak_support']:assert all(status=='unsupported' for status in row['statuses'].values());checks['weak_support_cohorts_rejected']+=1
# Physical generation and the frozen first-block input/output chain.
physical=read(HERE/'endtoend/physical_inputs.json');ledger=read(HERE/'endtoend/evaluator.json');outputs=read(HERE/'endtoend/first_block_outputs.json');native_curves=read(HERE/'endtoend/native_curves.json');assert len(physical)==len(ledger)==len(outputs)==640
offset=0;duration_error=[]
for k,scenario in enumerate(spec['endtoend']['mechanisms']):
    clean=read(HERE/'endtoend'/scenario/'clean_facts.json');clean_input=read(HERE/'endtoend'/scenario/'clean_inference_input.json');observed=read(HERE/'endtoend'/scenario/'extracted_inference_input.json');assert clean==clean_input
    for field in ['X','offered_incentive','users','known_density']:assert clean[field]==observed[field]
    truth=np.asarray(read(HERE/'endtoend'/scenario/'population_truth.json')['mean_seconds']);unrounded=population_curve(scenario);assert np.max(abs(truth-unrounded))<=5.00001
    for mode in ['clean','extracted']:
        r=read(HERE/'endtoend'/scenario/f'{mode}_results.json')
        for method,out in r['results'].items():compare_result(out,truth,r['metrics'][method],scenario)
    rng=np.random.default_rng(spec['endtoend']['seed']+k+500)
    for i,true_duration in enumerate(clean['outcome_seconds']):
        j=offset+i;c=physical[j];l=ledger[j];out=outputs[j];n=int(round(true_duration/10));s=np.asarray(c['starts_s']);e=np.asarray(c['ends_s']);assert s.tolist()==list(np.arange(-900,2700,10.)) and np.array_equal(e,s+10)
        assert c['task']['task_id']==l['task_id']==out['task_id'];assert true_duration==l['true_cumulative_seconds']==out['true_cumulative_seconds'];assert l['active_cells']==n
        wave=np.zeros(len(s));begin=int(rng.integers(0,181-n)) if n else 0;task_indices=np.flatnonzero((s>=0)&(s<1800));wave[task_indices[begin:begin+n]]=1.5;post=s>=1800;wave[post]=-.4*(n/180)*np.exp(-(s[post]-1800)/180);power=3.-wave+rng.normal(0,.05,len(s));assert np.array_equal(power,c['power_kw'])
        p=out['process'];assert p['status']=='ok' and p['method']=='B1_effective_response_refined';value=p['duration_estimates']['cumulative_response_seconds'];assert value==observed['outcome_seconds'][i];duration_error.append(abs(value-true_duration));assert np.array_equal(p['reduction_interval_kw'],native_curves[str(j)]['prediction'])
        checks['frozen_first_block_physical_records']+=1
    offset+=len(clean['outcome_seconds'])
# Read each native CSV once and compare the actual inputs, without refitting.
native_count=0
for path in (HERE/'endtoend/native/cpop').glob('chunk*/*/input.csv'):
    chunks=collections.defaultdict(list)
    with path.open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):chunks[int(r['case_id'])].append(r)
    for case,rows in chunks.items():
        c=physical[case];assert np.array_equal([float(r['y']) for r in rows],np.asarray(c['reference_kw'])-np.asarray(c['power_kw']));assert np.allclose([float(r['x']) for r in rows],(np.asarray(c['starts_s'])+np.asarray(c['ends_s']))/120,atol=1e-10,rtol=0);native_count+=1
assert native_count==640 and read(HERE/'endtoend/public_check.json')['status']=='passed';checks['original_native_physical_inputs']=native_count
assert not decision['adopt_two_part'] and not decision['adopt_DML_as_replacement'];assert final['summary']['existing_DR']['primary_seconds']<final['summary']['continuous_DML']['primary_seconds'];assert decision['checks']['actual_gain5'] is False and decision['checks']['heldout_mechanism_nonincrease'] is False
assert read(HERE/'freeze.json')['created_utc']>read(HERE/'baseline_selection.json')['created_utc'];assert read(HERE/'endtoend/source_freeze.json')['before_physical_generation'] is True
report=dict(status='passed',checks=dict(checks),development_fact_variants=stagefacts['development'],final_main_fact_variants=stagefacts['final'],development_independent_seed_blocks=3,final_independent_seed_blocks=4,final_main_curve_variants=24,final_base_user_contexts=len(canonical_users['final']),same_seed_mechanisms_are_paired_not_independent_repetitions=True,endtoend_physical_events=640,endtoend_base_users=320,first_block_duration_mae_seconds=float(np.mean(duration_error)),first_block_raw_models_and_api_unchanged=True,main_models_and_metrics_frozen_before_final=True,no_main_or_endtoend_case_excluded=True,new_whole_test_mechanisms=['nonmonotone','assignment_mixture'],continuous_query_and_nuisance_checks='technical_checks.json',conditional_bands_not_certified_full_causal_CI=True,performance_is_simulation_not_real=True,production_method_preserved='existing_continuous_DR',no_post_final_parameter_tuning=True)
path=HERE/'verification.json'
if path.exists():assert read(path)==native(report)
else:save('verification.json',report)
print(json.dumps(native(report)),flush=True)
