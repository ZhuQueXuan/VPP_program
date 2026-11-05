"""Record relocation identities; no experiments and no deletion."""
from pathlib import Path
import hashlib, json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
manifest = json.loads((HERE / 'before_manifest.json').read_text(encoding='utf-8'))
allowed = {'b1_algorithm/api.py', 'b1_algorithm/process/_cpop.py'}
changed = []
for item in manifest:
    dst = ROOT / item['new']
    assert dst.is_file() and not (ROOT / item['old']).exists(), item
    item['sha256_after'] = hashlib.sha256(dst.read_bytes()).hexdigest()
    item['unchanged_content'] = item['sha256_after'] == item['sha256_before']
    if not item['unchanged_content']:
        assert item['old'] in allowed, item
        changed.append(item['old'])
assert set(changed) == allowed
before = json.loads((HERE / 'before/numerical_result.json').read_text(encoding='utf-8'))
after = json.loads((HERE / 'after/numerical_result.json').read_text(encoding='utf-8'))
assert before == after
pipeline = json.loads((HERE / 'after/pipeline_verification.json').read_text(encoding='utf-8'))
assert pipeline['passed'] and pipeline['n_checks'] == 31
source = ROOT / 'B1算法'
files = sorted(str(p.relative_to(source)) for p in source.rglob('*') if p.is_file())
assert len(files) == 22, files
assert not (source / 'work').exists()
assert not (ROOT / 'b1_algorithm').exists() and not (ROOT / 'b1_api.py').exists()
receipt = dict(passed=True, date='2026-10-30', source_directory=str(source),
    entry_point=str(source / 'b1_api.py'), source_files=files, moved_file_count=len(manifest),
    content_unchanged_files=sum(i['unchanged_content'] for i in manifest),
    path_only_changes=changed, native_and_reference_numerical_identity=True,
    integration_checks=31, integration_events=600,
    process_materials=str(HERE), old_active_paths_absent=True,
    deletion_performed=False, new_report_or_package_created=False,
    scope='source organization and runtime regression only; no new algorithm performance study',
    files=manifest)
(HERE / 'organization_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in receipt.items() if k not in ('files', 'source_files')}, ensure_ascii=False, indent=2))
