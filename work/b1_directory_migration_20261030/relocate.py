"""One-time, explicit file relocation; no deletion or overwriting."""
from pathlib import Path
import hashlib, json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1].resolve()
TARGET = ROOT / 'B1算法'
assert not TARGET.exists(), 'Destination already exists; inspect instead of overwriting'
runtime = [
    'b1_api.py',
    'b1_algorithm/__init__.py', 'b1_algorithm/api.py', 'b1_algorithm/contracts.py',
    'b1_algorithm/runtime.json',
    'b1_algorithm/reference/__init__.py', 'b1_algorithm/reference/core.py',
    'b1_algorithm/effects/__init__.py', 'b1_algorithm/effects/api.py',
    'b1_algorithm/effects/core.py', 'b1_algorithm/effects/validation.py',
    'b1_algorithm/process/__init__.py', 'b1_algorithm/process/api.py',
    'b1_algorithm/process/batch.py', 'b1_algorithm/process/_cpop.py',
    'b1_algorithm/process/_frozen_f0.py', 'b1_algorithm/process/_ride_template.py',
    'b1_algorithm/process/_template_fit.py', 'b1_algorithm/process/_policy.json',
    'b1_algorithm/process/cpop_batch.R',
]
documentation = [
    'b1_algorithm/README.md', 'b1_algorithm/reference/README.md',
    'b1_algorithm/process/README.md', 'b1_algorithm/process/SOURCE_ORIGIN.json',
    'b1_algorithm/effects/README.md', 'b1_algorithm/effects/SOURCES.json',
]
plan = [(p, TARGET / p, 'runtime') for p in runtime]
plan += [('b1_algorithm/requirements.txt', TARGET / 'requirements.txt', 'dependency')]
plan += [(p, HERE / 'documentation' / p, 'documentation') for p in documentation]
manifest = []
for old, new, role in plan:
    src = (ROOT / old).resolve(); dst = new.resolve()
    assert src.is_relative_to(ROOT) and dst.is_relative_to(ROOT)
    assert src.is_file() and not dst.exists(), (src, dst)
    manifest.append(dict(old=old, new=str(dst.relative_to(ROOT)), role=role,
                         sha256_before=hashlib.sha256(src.read_bytes()).hexdigest()))
(HERE / 'before_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
for entry in manifest:
    src = ROOT / entry['old']; dst = ROOT / entry['new']
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    assert hashlib.sha256(dst.read_bytes()).hexdigest() == entry['sha256_before']
# Preserve the now inactive, cache-only tree without deleting directories.
old_tree = (ROOT / 'b1_algorithm').resolve()
cache_archive = (HERE / 'legacy_cache_tree').resolve()
assert old_tree.is_relative_to(ROOT) and cache_archive.is_relative_to(ROOT)
assert not cache_archive.exists()
remaining = [p for p in old_tree.rglob('*') if p.is_file()]
assert all(p.suffix == '.pyc' and p.parent.name == '__pycache__' for p in remaining)
old_tree.rename(cache_archive)
print(json.dumps(dict(moved_files=len(manifest), runtime_files=len(runtime) + 1,
                      source=str(TARGET), preserved_cache_files=len(remaining)), ensure_ascii=False))
