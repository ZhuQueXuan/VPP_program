from common import *

def main():
    chosen=dict(method='fixed_t0.6_cap0.2_directional_guard',score=None);cfg=read('selected_config.json');cfg.update(method_name='duration_fusion',beta=3.,
        preserve_original_positive_runs_seconds=60.,preserve_nearzero_gap_runs_seconds=60.,
        domain=dict(task_minutes=30.,request_kw=1.5,noise_sigma_kw=.05,pre_minutes=15.,post_minutes=15.,meter_minutes=[1/6,1.],onset_fraction=.1,dwell_seconds=30.))
    # Configuration copied unchanged except explicit directional safety guard.
    write('evaluation_protocol.json',dict(selection='Broad seen main/stress development used. Earlier rounds and failed stress retained. No new final test has been generated or used for selection.',
        validation_seeds=[7691100,7691101],test_seeds=list(range(7692000,7692012)),stress_seeds=[7693000,7693001],
        per_kind_validation=2,per_kind_test=3,per_kind_stress=2,panels=['minute','10s'],
        primary='Equal condition means within each panel, then equal panel means. Per task: mean of cumulative/longest duration absolute errors.',
        adoption=dict(primary_relative_improvement=.10,paired12seed95_upper_below0=True,at_least8of12_seed_blocks_better=True,
            cumulative_noninferiority_seconds=5.,each_panel_noninferiority_seconds=5.,short_local_miss_not_increased=True,true_gap_fill_not_increased=True,
            task_positive_status_identical_to_original=True,stress_noninferiority_seconds=5.,stress_short_and_gap_not_worse=True,curve_pooled_MSE_ratio_at_most1_21=True,all_available=True),
        stress='New seeds. Peaks scaled to.08/.13/.145/.155/.18/.25kW, pair-consistent scaling, unchanged observation noise and spikes.',
        timing='Not an adoption criterion. User means work efficiency; algorithm accuracy is primary.',
        limits='Controlled known-reference simulation only. Learned standard models trained on synthetic latent curves; no field-clean100ms or unknown-reference validation. Event detection stays exactly original CPOP; do not claim false-event improvement.',
        code='Standard segmented regression, gradient-boosted quantile/state inference and observable CPOP safeguards. No claim of new DP/boosting estimator.'))
    files=[p for p in HERE.glob('*.py')]+[HERE/'selected_config.json',HERE/'evaluation_protocol.json',HERE/cfg['quantile_model'],HERE/cfg['state_model']]
    files += [V1/'simulation.py',PREVIOUS/'simulation.py',PREVIOUS/'labs_batch.R',PREVIOUS/'vendor/LABS/LABS_functions.R',ROOT/'work/b1_cpop_fine_v3_20261031/simulation.py']
    files += [p for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    write('selection_freeze.json',dict(configuration=cfg,selected_development_method=chosen['method'],development_score=chosen['score'],
        source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in files},
        training_source_sha256=sha(ROOT/'work/b1_fast_selection_20261101/training_features.npz')))
    protected=[p for scope in ['B1算法','resource_research_results/ev_charging','task','01_项目依据','work/b1_cpop_jump_v2_20261031','work/b1_cpop_fine_v3_20261031','work/b1_execution_evidence_20261031','work/b1_fast_selection_20261101','work/b1_duration_selection_20261101','work/b1_duration_adoption_20261101'] for p in (ROOT/scope).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    write('protected_before.json',{p.relative_to(ROOT).as_posix():sha(p) for p in protected})
    print(json.dumps(cfg),flush=True)
if __name__=='__main__':main()
