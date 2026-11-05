from common import *

def main():
    rank=read('guarded_rank.json');chosen=rank[0];cfg=read('guarded_settings.json')[chosen['method']]
    cfg.update(method_name='duration_fusion',beta=3.,domain=dict(task_minutes=30.,request_kw=1.5,noise_sigma_kw=.05,pre_minutes=15.,post_minutes=15.,meter_minutes=[1/6,1.],onset_fraction=.1,dwell_seconds=30.))
    write('selected_config.json',cfg)
    write('evaluation_protocol.json',dict(selection='Development complete. Original CPOP event-positive status is retained exactly; improvement target is duration, not sensor-fault classification.',
        validation_seeds=[7671100,7671101],test_seeds=list(range(7672000,7672012)),stress_seeds=[7673000,7673001],
        per_kind_validation=2,per_kind_test=3,per_kind_stress=2,panels=['minute','10s'],
        primary='Mean within condition, then within panel, then equal average of panels. Each task primary=(cumulative duration absolute error+longest duration absolute error)/2.',
        adoption=dict(primary_relative_improvement=.10,paired12seed95_upper_below0=True,at_least8of12_seed_blocks_better=True,
            cumulative_noninferiority_seconds=5.,each_panel_noninferiority_seconds=5.,short_local_miss_not_increased=True,true_gap_fill_not_increased=True,
            task_positive_status_identical_to_original=True,stress_noninferiority_seconds=5.,all_available=True),
        stress='All positive mechanisms scaled to physical peaks.08/.13/.145/.155/.18/.25kW, paired scale per base task, same noise/spikes. New independent seeds, no tuning on stress.',
        timing='Runtime recorded only; not an adoption gate. User clarified work efficiency, not algorithm speed.',
        reality='Known-reference simulations, trained on controlled latent curves. Not field100ms fault recognition or unknown-reference proof.',
        code='Standard segmented regression and sklearn quantile/classifier, domain-specific observable safeguards; no claim of inventing DP or boosting.'))
    files=[p for p in HERE.glob('*.py')]+[HERE/'selected_config.json',HERE/'evaluation_protocol.json',HERE/cfg['quantile_model'],HERE/cfg['state_model']]
    files += [V1/'simulation.py',PREVIOUS/'simulation.py',PREVIOUS/'labs_batch.R',PREVIOUS/'vendor/LABS/LABS_functions.R',ROOT/'work/b1_cpop_fine_v3_20261031/simulation.py']
    files += [p for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    write('selection_freeze.json',dict(configuration=cfg,selected_development_method=chosen['method'],development_primary=chosen['primary_seconds'],
        source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in files},model_training_sha256=sha(HERE/'training_receipt.json')))
    protected=[p for scope in ['B1算法','resource_research_results/ev_charging','task','01_项目依据','work/b1_cpop_jump_v2_20261031','work/b1_cpop_fine_v3_20261031','work/b1_execution_evidence_20261031','work/b1_fast_selection_20261101'] for p in (ROOT/scope).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    write('protected_before.json',{p.relative_to(ROOT).as_posix():sha(p) for p in protected})
    print(json.dumps(cfg),flush=True)
if __name__=='__main__':main()
