from study import *
from importlib.metadata import version

old=json.loads((HERE/'production_before.json').read_text(encoding='utf-8'))
changed=[name for name,h in old.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=h]
allowed=['B1算法/b1_api.py','B1算法/README.md','B1算法/requirements.txt','B1算法/b1_algorithm/factors.py']
assert set(changed)==set(allowed),changed
frozen=json.loads((HERE/'source_freeze.json').read_text(encoding='utf-8'))['files']
assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h for name,h in frozen.items())
audit={}
for path in HERE.glob('audit_*result.json'):
    value=json.loads(path.read_text(encoding='utf-8'));audit[path.name]=value.get('status')
    expected='complete' if path.name=='audit_refit_result.json' else ('passed_injected_failure_branch_test' if path.name=='audit_refit_failure_result.json' else 'passed')
    assert value.get('status')==expected,(path.name,value.get('status'))
q=json.loads((HERE/'physical/query.json').read_text(encoding='utf-8'))
cli=json.loads((HERE/'cli_raw_check/result.json').read_text(encoding='utf-8'))
assert np.allclose(q['mean_curve']['curve']['contrasts'],cli['mean_curve']['curve']['contrasts'],rtol=0,atol=1e-9)
assert np.allclose(q['direct_marginal_effect']['estimates'],cli['direct_marginal_effect']['estimates'],rtol=0,atol=1e-9)
decision=json.loads((HERE/'decision.json').read_text(encoding='utf-8'))
refit=json.loads((HERE/'refit_summary.json').read_text(encoding='utf-8'))
artifacts=['protocol.json','source_freeze.json','development_selection.json','decision.json','verification.json',
    'structure_evaluation.json','physical/score.json','refit_summary.json','audit_physical_result.json','README.md']
formal_new=['B1算法/b1_algorithm/research.py','B1算法/b1_algorithm/structure.py',
    'B1算法/b1_algorithm/effects/nonlinear.py','B1算法/b1_algorithm/effects/refit.py',
    'B1算法/research_cli.py','B1算法/run_research_point_one.ps1','B1算法/运行研究点一.cmd',
    'B1算法/RESEARCH_POINT_ONE.md','B1算法/research_request_example.json']
receipt=dict(status='integrated_algorithm_v1_delivered_with_EV_simulation_evidence',
    executed=['new_development_fits','frozen_new_final_fits','actual_PC_FCI_KCI','direct_DR_derivative',
              'raw_physical_native_to_high_level_factor_chain','full_raw_input_CLI_replay','PowerShell_launcher_query',
              'JSON_save_load_and_arbitrary_amount_query','whole_original_user_nuisance_refits','independent_audits'],
    real_world_validation=False,all_resource_adapters_complete=False,formal_taskbook_acceptance=False,
    raw_unique_physical_tasks=240,raw_CLI_same_tasks_replay_not_additional_N=True,
    unique_main_final_fact_variants=5760,main_final_independent_seed_blocks=4,
    frozen_sources_unchanged=len(frozen),original_formal_files_unchanged=len(old)-len(changed),
    changed_old_formal_files=changed,
    original_process_files_unchanged=sum('/process/' in name for name in old),
    source_process_or_existing_DR_algorithm_changed=False,original_default_changed=False,
    dependency_versions={name:version(name) for name in ['causal-learn','networkx','pydot','momentchi2']},
    dependencies_isolated_under='work/b1_research_point1_20261103/runtime/site-packages',
    audit_results=audit,raw_public_CLI_matches_frozen_physical_result=True,
    mean_method_kept=decision['mean_method'],default_marginal_effect=decision['default_marginal_effect'],
    direct_derivative_replacement_adopted=False,
    refit_draws_attempted=refit['all_draws_attempted'],
    refit_draw_success=sum(r['success_draws'] for r in refit['rows']),
    refit_draw_failure=sum(r['failed_draws'] for r in refit['rows']),
    refit_incomplete_status_retained=True,no_post_final_parameter_tuning=True,
    former_real_test_or_external_opened=False,files_deleted=False,committed_or_uploaded=False,
    artifact_sha256={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in artifacts},
    formal_new_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in formal_new},
    user_entry='B1算法/运行研究点一.cmd',usage='B1算法/RESEARCH_POINT_ONE.md',
    scope='known-reference EV simulation integrated prototype; complete mechanism/real/multi-resource evidence remains future work')
save(HERE/'completion_receipt.json',receipt)
print(json.dumps({k:receipt[k] for k in ['status','raw_unique_physical_tasks','frozen_sources_unchanged',
    'original_formal_files_unchanged','original_process_files_unchanged','refit_draws_attempted','refit_draw_success',
    'refit_draw_failure','audit_results']},ensure_ascii=False))
