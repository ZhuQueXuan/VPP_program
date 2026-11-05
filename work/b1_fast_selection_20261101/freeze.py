from common import *

def main():
    rank=read('development_acceptable_rank.json');best=rank[0];settings=read('learned_settings.json')[best['method']]
    assert best['method']=='learn_l31_w1_below1'
    settings['offset_sigma']=0.
    settings['method_name']='segment_boost'
    settings['domain']=dict(task_minutes=30.,request_kw=1.5,noise_sigma_kw=.05,pre_minutes=15.,post_minutes=15.,meter_minutes=[1/6,1.])
    write('selected_config.json',settings)
    write('evaluation_protocol.json',dict(selection='All exploration/training selection finished before fresh validation/test generation. Seen development results retained without claiming new evidence.',
        primary='For each panel average the condition-specific primary MAEs, then average two panels. Primary within each task is mean of cumulative/longest absolute errors.',
        validation_seeds=[7661100,7661101],test_seeds=list(range(7662000,7662012)),stress_seeds=[7663000,7663001],per_kind_validation=2,per_kind_test=3,per_kind_stress=2,
        panels=['minute','10s'],validation_only_gate_no_retuning=True,
        adoption=dict(primary_relative_improvement=.10,paired12seed_student95_upper_below0=True,
            majority_seed_blocks_at_least8of12=True,each_panel_primary_noninferiority_seconds=5.,
            cumulative_mae_noninferiority_seconds=5.,no_extra_short_local_misses=True,no_extra_true_short_gap_fill=True,
            null_false_positive_no_more_than_original_plus1=True,whole_misses_no_more_than_original_plus2=True,stress_noninferiority_seconds=5.,all_outputs_available=True),
        stress='Additional independently scaled near-threshold/subthreshold panel declared before generation, seeds7663000/1, no selection or rescue from stress. Original main evidence not relabelled if stress fails.',
        runtime='Recorded for engineering only, not an adoption gate after user clarification.',
        limits='Known simulated reference, no field clean truth or unknown-reference gain claim. Future real use remains bounded to validated information/scale.'))
    paths=[p for p in HERE.glob('*.py')]+[HERE/'selected_config.json',HERE/'evaluation_protocol.json',HERE/settings['model']]
    paths += [V1/'simulation.py',PREVIOUS/'simulation.py',PREVIOUS/'labs_batch.R',PREVIOUS/'vendor/LABS/LABS_functions.R',ROOT/'work/b1_cpop_fine_v3_20261031/simulation.py']
    paths += [p for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    write('selection_freeze.json',dict(method=best['method'],settings=settings,source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in paths},
        training_receipt_sha256=sha(HERE/'training_receipt.json'),development_result_sha256=sha(HERE/'development_learned_summary.json')))
    protected=[p for scope in ['B1算法','resource_research_results/ev_charging','task','01_项目依据','work/b1_cpop_jump_v2_20261031','work/b1_cpop_fine_v3_20261031','work/b1_execution_evidence_20261031'] for p in (ROOT/scope).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    write('protected_before.json',{p.relative_to(ROOT).as_posix():sha(p) for p in protected})
    print(json.dumps(settings),flush=True)
if __name__=='__main__':main()
