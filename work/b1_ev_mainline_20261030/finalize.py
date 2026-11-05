"""Final file identity and protected-state audit; no scientific fitting."""
from pathlib import Path
import json,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)
def main():
    if (HERE/'adoption_receipt.json').exists():raise RuntimeError('completed final audit cannot be overwritten')
    before=read(HERE/'before_manifest.json');protected={k:v for k,v in before.items() if not k.startswith('B1算法/')}
    assert len(protected)==75
    assert all((ROOT/k).is_file() and sha(ROOT/k)==v for k,v in protected.items())
    existing={k:dict(before=v,after=sha(ROOT/k)) for k,v in before.items() if k.startswith('B1算法/') and sha(ROOT/k)!=v}
    assert set(existing)=={'B1算法/b1_api.py','B1算法/README.md'},existing
    current={p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'B1算法').rglob('*') if p.is_file()}
    new=set(current)-set(before)
    assert new=={'B1算法/b1_algorithm/factors.py','B1算法/b1_algorithm/reference/ev_selection.py'},new
    assert not list((ROOT/'B1算法').rglob('__pycache__'))
    scientific=read(HERE/'scientific_source_freeze.json');replay=read(HERE/'corrective_replay_receipt.json')
    assert replay['passed'] and replay['main_results_refit'] is False
    for k,v in replay['original_raw_sha256'].items():assert sha(ROOT/k)==v
    for k,v in replay['original_event_sha256'].items():assert sha(ROOT/k)==v
    for name in ('verification_post_contract_fix.json','wrapper_check_receipt.json','technical_review/audit_receipt_corrected.json'):
        assert read(HERE/name)['passed']
    assert read(HERE/'research_receipt.json')['completed']
    evidence={p.relative_to(ROOT).as_posix():sha(p) for p in HERE.rglob('*') if p.is_file() and 'before_source' not in p.parts}
    write(HERE/'final_manifest.json',dict(runtime_source=current,protected_files=protected,evidence=evidence))
    write(HERE/'adoption_receipt.json',dict(implemented_steps=[1,2,3],limited_EV_mainline_connected=True,
        public_entry='B1算法/b1_api.py:analyze_ev_factor_study / fit_ev_factor_curve',
        existing_B1_files_modified=existing,new_runtime_files=sorted(new),protected_files_matched=75,
        existing_process_and_continuous_effect_core_unchanged=True,raw_eta_definition_unchanged=True,
        optional_reference_selector=True,default_prediction_routing_changed=False,
        cumulative_duration_workflow_recommendation='explicit CPOP for this unknown-reference EV study; RIDE and raw threshold retained',
        reference_false_detection_resolved=False,scientific_increment_universal=False,
        main_independent_blocks=8,main_factual_variants=6400,stress_factual_variants=256,
        strict_replayed_outcome_rows=replay['strict_outcome_rows'],
        reference_numeric_replays=replay['reference_replays'],
        research_point1_complete=False,real_EV_validation=False,report_written=False,
        zip_or_launcher_created=False,source_bytecode_directories=0,new_dependencies_installed=False,
        deferred_steps=[4,5,6],inference_limit='conditional measured-outcome effects; no full-chain uncertainty coverage guarantee'))
    print(json.dumps(dict(passed=True,protected_files_matched=75,runtime_files=len(current),new_runtime_files=len(new),
        deferred_steps=[4,5,6])))
if __name__=='__main__':main()
