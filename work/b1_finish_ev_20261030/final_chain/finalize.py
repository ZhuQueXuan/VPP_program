"""Seal the retained initial audit and corrected audit without overwriting."""
from pathlib import Path
import hashlib
import json

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)


def main():
    original=read(HERE/'scientific_files_sha256.json')
    changed=[name for name,value in original.items() if sha(ROOT/name)!=value]
    corrected=read(HERE/'audit_corrected_receipt.json')
    audit=read(HERE/'audit_receipt.json')
    receipt=read(HERE/'receipt.json')
    out=dict(schema='b1.final-chain.final-receipt.v1',completed=receipt['completed'] and corrected['passed'] and not changed,
        main_receipt='receipt.json',main_receipt_sha256=sha(HERE/'receipt.json'),
        assessment='assessment.json',assessment_sha256=sha(HERE/'assessment.json'),
        corrected_audit='audit_corrected_receipt.json',corrected_audit_sha256=sha(HERE/'audit_corrected_receipt.json'),
        initial_audit_retained='audit_receipt.json',initial_audit_passed=audit['passed'],
        initial_audit_correction='The first audit incorrectly required resource_type in normalized task output and untyped user IDs in the frozen model. The correction honors canonical task fields and string: user ID prefixes. All science outputs/scores are unchanged.',
        original_scientific_artifacts_verified=len(original),changed_original_scientific_artifacts=changed,
        scientific_run_repeated=False,estimator_or_process_refitted_by_audit=False,
        scalar_or_contract_checks=corrected['scalar_or_contract_checks'],checks_are_not_independent_performance_trials=True,
        native_side_identity='runtime_identity.json',source_freeze_sha256=sha(HERE/'source_freeze.json'))
    dump(HERE/'final_receipt.json',out)
    science=[p for p in HERE.rglob('*') if p.is_file() and p.suffix.lower() in ('.json','.csv','.py','.r') and p.name!='scientific_files_final_sha256.json']
    science.extend(p for p in (ROOT/'data/B1_finish_chain_v1_20261030').glob('*') if p.is_file())
    dump(HERE/'scientific_files_final_sha256.json',{p.relative_to(ROOT).as_posix():sha(p) for p in sorted(science)})
    print(json.dumps(dict(completed=out['completed'],changed_original_scientific_artifacts=changed,
        corrected_audit_passed=corrected['passed'],scientific_files=len(science),
        manifest_sha256=sha(HERE/'scientific_files_final_sha256.json'),final_receipt_sha256=sha(HERE/'final_receipt.json')),indent=2))
    assert out['completed']


if __name__=='__main__':main()
