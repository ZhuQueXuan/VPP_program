"""Verify survey-local artifacts, citations' local targets and old-file hashes."""
from pathlib import Path
import hashlib,json,re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
receipt_path=HERE/'survey_receipt.json'
protected=json.loads((HERE/'protected_before.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha for name,sha in protected.items())
protection=json.loads((HERE/'protection_receipt.json').read_text(encoding='utf-8'))
assert protection['unchanged']
required=['README.md','scenario_recovery.md','prior_scenario_screenshot.png',
          '未知参考场景的方法调研与重新选型建议.md','reference_methods.md',
          'process_methods.md','process_sources.md','independent_selection_review.md','final_review.md']
assert all((HERE/name).is_file() for name in required)
receipt=dict(schema='b1.unknown-reference-survey.v1',date='2026-10-31',
    status='completed_literature_and_selection_review_only',
    scenario=dict(task_known=True,unknown='Untreated reference power',
        source_thread='01a1867b-53df-78c0-8924-f141cd199c10',
        source_turn='01a18bc4-d2e7-7592-b074-d4a58d8e3477',
        screenshot_found_and_viewed=True),
    completed=['Previous screenshot/context recovered',
               'Primary literature and official software checked for reference and process methods',
               'Unknown-reference methods and same-information baseline layers proposed',
               'Independent review completed'],
    recommendation='Limited conditional boosted-tree versus GP reference study; flexible trend-filtering/generalized-lasso foundation; same-information GLS-TF as strong process baseline, CPOP retained as strong supplementary comparator; new contributions require explicit feature-reliability/censoring mechanisms and independent tests.',
    protected_old_files=len(protected),protected_old_files_unchanged=True,
    performed=dict(new_model_implementation=False,model_fitting=False,new_experiments=False,
        data_or_weight_download=False,library_install=False,runtime_default_change=False,
        original_data_or_frozen_result_change=False,deletion=False,formal_report=False,
        B2_B3_B4_expansion=False,uploads_or_commits=False),
    limitations=['Not an exhaustive systematic literature or novelty review.',
        'Several publisher full texts were restricted; reading depth is documented.',
        'No method has been newly reproduced or shown superior on this project.',
        'Standard weighted generalized lasso is a mature method, not a claimed novel process algorithm.',
        'Probability paths, task calibration, and 15-minute physical identification need separate validation.',
        'Protection hashes cover listed old directories, not all project data.'])
receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
missing=[];count=0
for path in HERE.glob('*.md'):
    for target in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
        if re.match(r'^https?://',target):continue
        local=target.split('#')[0]
        if not local:continue
        count+=1
        if not (path.parent/local).exists():missing.append(dict(file=path.name,target=target))
assert not missing,missing
receipt.update(local_links_checked=count,local_links_missing=missing,
    artifacts_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(HERE.iterdir()) if p.is_file() and p!=receipt_path})
receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='passed',old_files_unchanged=len(protected),
    local_links_checked=count,artifacts=len(receipt['artifacts_sha256']))))
