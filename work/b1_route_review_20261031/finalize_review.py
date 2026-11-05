"""Verify review artifacts and their links; no model imports or fitting."""
from pathlib import Path
import csv, hashlib, json, re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
def read(name):
    return json.loads((HERE/name).read_text(encoding='utf-8'))

diagnosis = read('saved_process_diagnosis.json')
independent = read('independent_diagnostic_check.json')
protection = read('protection_receipt.json')
assert protection['unchanged'] and protection['files_before'] == 3290
assert independent['status'] == 'passed'
for key in ['n','template_miss','cpop_miss','witness_n',
            'missed_with_exact_witness_beats_selected_and_passes']:
    assert diagnosis['overall'][key] == independent['overall'][key]
assert len(diagnosis['input_sha256']) == independent['source_files'] == 40
with (HERE/'saved_process_diagnosis.csv').open(encoding='utf-8',newline='') as stream:
    rows = list(csv.DictReader(stream))
assert len(rows) == len({row['task_id'] for row in rows}) == 1024
for relative, expected in diagnosis['input_sha256'].items():
    assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() == expected

receipt_path = HERE/'review_receipt.json'
receipt = dict(schema='b1.route-review.v1', date='2026-10-31',
    scope='Internal route review only; no implementation or new experiment approval',
    recommendation='One bounded observable short-response deterministic-search candidate; unchanged native CPOP remains the independent main process comparator; stop if no independent practical gain.',
    completed=['Original scope and comparator history checked',
               'Production module/call-chain and frozen positive/negative evidence reviewed',
               'Read-only weak-response diagnostic and independent overlap-integral verification',
               'Competing routes, ablations, development boundaries and proposed stop criteria documented'],
    diagnosis=dict(fact_tasks=1024, true_threshold_positive=690, template_misses=151,
                   cpop_misses=38, amplitude_gate_misses=148, post_detection_misses=3,
                   exact_legal_witnesses=358, missed_with_better_legal_witness=55,
                   input_files_sha_checked=40, independent_checker_passed=True),
    protected_original_files=3290, protected_original_files_unchanged=True,
    operations=dict(source_modified=False, original_data_modified=False,
                    frozen_records_modified=False, model_fitting=False,
                    new_experiments=False, deletion=False, installs=False,
                    formal_report=False, B2_B3_B4_expansion=False, uploads_or_commits=False),
    limitations=['The diagnostic reuses already-seen test data; no new performance validation.',
                 'Truth-based witnesses prove existence/objective gaps, not deployable initialization or future gains.',
                 'No proof that the global optimum detects a response, nor that the proposed search beats CPOP.',
                 'Reference/long-weak response confounding and all-chain uncertainty remain unresolved.',
                 'Numeric adoption margins are protocol suggestions, not user-approved or task-book requirements.',
                 'Protection snapshot covers listed source/evidence/original-document directories, not all project data.'])
receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
missing=[]
checked=0
for path in HERE.glob('*.md'):
    for target in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
        if re.match(r'^https?://',target):
            continue
        local=target.split('#')[0]
        if not local:
            continue
        checked+=1
        if not (path.parent/local).exists():
            missing.append({'file':path.name,'target':target})
assert not missing, missing
receipt['local_links_checked']=checked
receipt['local_links_missing']=missing
receipt['artifact_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted(HERE.iterdir()) if p.is_file() and p != receipt_path}
receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='passed', local_links_checked=checked,
                     artifact_count=len(receipt['artifact_sha256']),
                     originals_unchanged=protection['unchanged'], diagnosis=receipt['diagnosis']),ensure_ascii=False))
