"""Final read-only checks and receipt; no fit, tuning or process rerun."""
from pathlib import Path
import json,re
from pilot_common import HERE,ROOT,read,write_new,sha,assert_identity

frozen=read(HERE/'freeze.json');assert_identity(frozen['source_identity'])
for p,digest in frozen['artifact_sha256'].items():assert sha(ROOT/p)==digest
supp=read(HERE/'supplement_freeze.json')
assert supp['script_sha256']==sha(HERE/'cpop_sensitivity.py')
assert supp['protocol_sha256']==sha(HERE/'supplement_protocol.json')
assert supp['main_freeze_sha256']==sha(HERE/'freeze.json')
assert supp['calibration_sha256']==sha(HERE/'sensitivity_calibration.json')

previous=read(ROOT/'work/b1_unknown_reference_survey_20261031/protected_before.json')
changes=[p for p,digest in previous.items() if sha(ROOT/p)!=digest]
assert changes==['AGENTS.md'],changes
production=[p for p in previous if p.startswith('B1算法/')]
assert all(sha(ROOT/p)==previous[p] for p in production)
data_hashes={}
for path in (HERE/'data_receipts').glob('*.json'):
    for row in read(path)['rows']:
        for p,digest in row['sha256'].items():
            assert sha(ROOT/p)==digest
            data_hashes[p]=digest

summary=read(HERE/'pilot_summary.json');main=read(HERE/'test_assessment.json')
assert main['all_outputs_ok'] and main['raw_eta_equal_across_methods']
assert main['rows']==2304 and main['base_tasks']==256 and main['factual_variants']==768
assert read(HERE/'independent_audit.json')['status']=='passed'
refcheck=read(HERE/'reference_result_review_receipt.json')
tfcheck=read(HERE/'technical_review'/'technical_result_receipt.json')
assert refcheck.get('passed',refcheck.get('status')=='passed')
assert tfcheck.get('passed',tfcheck.get('status')=='passed')

receipt_path=HERE/'completion_receipt.json'
receipt=dict(schema='b1.unknown-reference-pilot-completion.v1',date='2026-10-31',
    status='small_reproduction_and_comparison_completed',formal_adoption=False,
    formal_comparison_scope='B1 feature extraction block only; CPOP one comparator with fixed sigma sensitivity; reference selection internal, response-analysis unchanged',
    selected_internal_reference=summary['selected_internal_reference'],
    train=dict(users=64,records=128,horizons_per_record=8,rows_per_model=1024,internal_configurations=4),
    test=dict(seed_blocks=4,users=128,base_tasks=256,paired_variants=768,main_outputs=2304,cpop_sensitivity_outputs=768,
        all_ok=True,raw_eta_invariant=True),
    conclusion=summary['conclusion'],
    comparison=summary['compact'],
    independent_checks=dict(all_chain='independent_audit.json',reference='reference_result_review_receipt.json',
        numerical_process='technical_review/technical_result_receipt.json',not_performance_sample_counts=True),
    old_protection=dict(previously_snapshotted_files=len(previous),unchanged_except_document_update=len(previous)-1,
        allowed_changes=changes,reason='Only prepended latest user authorization, block-level comparator scope and completed pilot decision to AGENTS; historical entries preserved.',
        production_files_verified_unchanged=len(production),old_scientific_directories_unchanged=True,
        limitation='Prior protected snapshot covers listed sources/evidence, not all project data; this pilot writes raw facts only under a new versioned data directory.'),
    frozen_source_count=len(frozen['source_identity']),data_and_truth_metadata_files_hash_checked=len(data_hashes),
    actual_changes=summary['actual_implementation'],not_implemented=summary['not_implemented'],
    limitations=summary['interpretability_limits']+[
        'Only complete1min W30/q1.5 EV smooth-continuous-natural-load simulation; not field or general task/resource evidence.',
        'GP kernel and training horizon budget limited; no superiority over all GP configurations claimed.',
        'CPOP meter sigma sensitivity designed after response validation and frozen before test generation; all results retained.',
        'No GP posterior-path propagation or validated confidence intervals for features.',
        'Null test user-block evidence false rates TFGLS12/128, CPOP_effective11/128, CPOP_meter13/128 all exceed nominal5percent; event rates alone do not establish the block target.',
        'Independent rank exchangeability assumptions not a certified field5percent error rate.'],
    operations=dict(new_dependencies=False,GPU=False,deletion=False,ZIP_or_launcher=False,
        production_default_change=False,second_block_change=False,B2_B3_B4_or_other_resource_change=False,
        formal_report=False,upload_or_commit=False))
write_new(receipt_path,receipt)
missing=[];links=0
for path in HERE.glob('*.md'):
    for target in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
        if re.match(r'^https?://',target):continue
        local=target.split('#')[0]
        if not local:continue
        links+=1
        if not (path.parent/local).exists():missing.append(dict(file=path.name,target=target))
assert not missing,missing
manifest={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(HERE.rglob('*'))
    if p.is_file() and p.name not in ['artifact_manifest.json'] and '__pycache__' not in p.parts}
write_new(HERE/'artifact_manifest.json',dict(source_identity=frozen['source_identity'],
    artifacts_sha256=manifest,new_data_sha256=data_hashes,local_links_checked=links,local_links_missing=missing))
print(json.dumps(dict(status='passed',frozen_sources=len(frozen['source_identity']),data_files=len(data_hashes),
    artifacts=len(manifest),links_checked=links,production_unchanged=True,allowed_document_update=changes)))
